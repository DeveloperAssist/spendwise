"""Imports, transactions, budgets and the dashboard, through the API."""

import csv
import io

from conftest import SAMPLE, fake_ai, register, upload


def test_import_then_again_then_overlapping(client):
    h = register(client)
    first = upload(client, h).json()
    assert (first["added"], first["duplicates"], first["skipped"]) == (227, 0, 0)
    assert upload(client, h).json()["added"] == 0  # the same statement again: nothing new
    lines = SAMPLE.read_text(encoding="utf-8").splitlines()
    newer = "\n".join(lines[:-1] + ["30-09-2026,30-09-2026,UPI/DR/1/NEW CAFE/YESB/x@ybl,1,180.00,,1"])
    r = upload(client, h, newer.encode(), "overlap.csv").json()
    assert (r["added"], r["duplicates"]) == (1, 227)  # only the new payment


def test_import_categories_use_ai_for_unknown_merchants(client, ai_holder):
    ai_holder["ai"] = fake_ai(categories={"Chaayos": "food", "Snitch": "shopping", "Torrent Power": "bills"})
    h = register(client)
    r = upload(client, h).json()
    assert r["categorized_by"]["ai"] > 0 and r["categorized_by"]["rule"] > 150
    items = client.get("/api/transactions?q=chaayos", headers=h).json()["items"]
    assert items and {(t["category"], t["category_source"]) for t in items} == {("food", "ai")}


def test_undo_import(client):
    h = register(client)
    imp = upload(client, h).json()
    assert client.delete(f"/api/imports/{imp['id']}", headers=h).status_code == 204
    assert client.get("/api/transactions", headers=h).json()["total"] == 0
    assert upload(client, h).json()["added"] == 227  # and it can be imported again


def test_upload_limits(client):
    h = register(client)
    assert upload(client, h, b"", "empty.csv").status_code == 400
    assert upload(client, h, b"x" * (3 * 1024 * 1024), "big.csv").status_code == 413
    assert upload(client, h, b"%PDF", "s.pdf").status_code == 400
    assert upload(client, h, b"hello,world\n1,2\n", "s.csv").status_code == 400


def test_filters_search_and_paging(client):
    h = register(client)
    upload(client, h)
    sept = client.get("/api/transactions?month=2026-09&page_size=100", headers=h).json()
    assert sept["total"] == len(sept["items"]) and all(t["date"].startswith("2026-09") for t in sept["items"])
    food = client.get("/api/transactions?category=food&kind=debit", headers=h).json()
    assert food["total"] > 0 and {t["category"] for t in food["items"]} == {"food"}
    page2 = client.get("/api/transactions?page=2&page_size=10", headers=h).json()
    page1 = client.get("/api/transactions?page=1&page_size=10", headers=h).json()
    assert {t["id"] for t in page1["items"]}.isdisjoint({t["id"] for t in page2["items"]})
    biggest = client.get("/api/transactions?sort=biggest&kind=debit&page_size=1", headers=h).json()["items"][0]
    assert biggest["amount"] == 8999.0 and biggest["merchant"] == "Croma"
    # % and _ are LIKE wildcards: a search for them must not match everything
    assert client.get("/api/transactions?q=%25", headers=h).json()["total"] == 0
    assert client.get("/api/transactions?q=_", headers=h).json()["total"] == 0
    assert client.get("/api/transactions?month=Sept", headers=h).status_code == 422


def test_add_fix_and_delete(client):
    h = register(client)
    r = client.post(
        "/api/transactions", headers=h, json={"date": "2026-10-01", "merchant": "  Zomato ", "amount": 249.5}
    )
    assert r.status_code == 201
    t = r.json()
    assert (t["merchant"], t["category"], t["category_source"], t["amount"]) == ("Zomato", "food", "rule", 249.5)
    income = client.post(
        "/api/transactions",
        headers=h,
        json={"date": "2026-10-01", "merchant": "Stipend", "amount": 15000, "kind": "credit"},
    ).json()
    assert income["category"] == "income"
    assert (
        client.post(
            "/api/transactions", headers=h, json={"date": "2026-10-01", "merchant": "x", "amount": 1.234}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/transactions", headers=h, json={"date": "2026-10-01", "merchant": "x", "amount": -5}
        ).status_code
        == 422
    )

    fixed = client.patch(f"/api/transactions/{t['id']}", headers=h, json={"category": "groceries", "note": "party"})
    assert (fixed.json()["category"], fixed.json()["category_source"], fixed.json()["note"]) == (
        "groceries",
        "you",
        "party",
    )
    later = client.post("/api/transactions", headers=h, json={"date": "2026-10-02", "merchant": "ZOMATO", "amount": 99})
    assert later.json()["category"] == "groceries"  # your fix is remembered
    assert client.delete(f"/api/transactions/{t['id']}", headers=h).status_code == 204
    assert client.delete(f"/api/transactions/{t['id']}", headers=h).status_code == 404


def test_fix_applies_to_every_payment_of_that_merchant(client):
    h = register(client)
    upload(client, h)
    rapido = client.get("/api/transactions?q=rapido&page_size=100", headers=h).json()
    client.patch(f"/api/transactions/{rapido['items'][0]['id']}", headers=h, json={"category": "other"})
    after = client.get("/api/transactions?q=rapido&page_size=100", headers=h).json()["items"]
    assert len(after) == rapido["total"] and {t["category"] for t in after} == {"other"}


def test_export_csv_is_safe_in_excel(client):
    h = register(client)
    client.post(
        "/api/transactions",
        headers=h,
        json={"date": "2026-10-01", "merchant": '=HYPERLINK("x")', "amount": 10, "note": "+cmd"},
    )
    r = client.get("/api/transactions/export.csv", headers=h)
    assert r.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[1][1].startswith("'=") and rows[1][5] == "'+cmd"  # formulas neutralised


def test_budgets_and_dashboard(client):
    h = register(client)
    upload(client, h)
    assert client.put("/api/budgets/food", headers=h, json={"limit": 2000}).json() == {
        "category": "food",
        "limit": 2000.0,
    }
    assert client.put("/api/budgets/income", headers=h, json={"limit": 5}).status_code == 422
    assert client.put("/api/budgets/food", headers=h, json={"limit": 0}).status_code == 422
    d = client.get("/api/analytics/dashboard?month=2026-09", headers=h).json()
    txs = client.get("/api/transactions?month=2026-09&kind=debit&page_size=100", headers=h).json()["items"]
    assert abs(d["summary"]["spent"] - sum(t["amount"] for t in txs)) < 0.01  # the numbers add up
    assert d["summary"]["income"] == 23000.0
    assert [b["category"] for b in d["budgets"]] == ["food"] and d["budgets"][0]["status"] == "over"
    assert len(d["trend"]) == 6 and len(d["daily"]) == 30
    assert client.delete("/api/budgets/food", headers=h).status_code == 204
    assert client.get("/api/budgets", headers=h).json() == []


def test_subscriptions_and_unusual(client):
    h = register(client)
    upload(client, h)
    subs = client.get("/api/analytics/subscriptions", headers=h).json()
    assert "Spotify" in {s["merchant"] for s in subs["items"]} and subs["per_month"] > 0
    odd = client.get("/api/analytics/unusual?month=2026-09", headers=h).json()["items"]
    assert odd[0]["merchant"] == "Croma"


def test_empty_account_dashboard(client):
    h = register(client)
    d = client.get("/api/analytics/dashboard", headers=h).json()
    assert d["summary"]["spent"] == 0 and d["budgets"] == []


def test_sample_statement_download(client):
    h = register(client)
    r = client.get("/api/imports/sample", headers=h)
    assert r.status_code == 200 and "SAMPLE DATA" in r.text
    assert client.get("/api/imports/sample").status_code == 401
