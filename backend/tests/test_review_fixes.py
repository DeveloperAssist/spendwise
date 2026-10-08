"""Regression tests for the issues an independent review found (2026-10-08). Each would have been a
crash, a security hole or lost data in the version before."""

import inspect
import io
import re
import time
import zipfile

import pytest
from conftest import SAMPLE, fake_ai, register, upload
from fastapi.testclient import TestClient
from openpyxl import Workbook

from spendwise.api import deps
from spendwise.api import imports as imports_api
from spendwise.security import RateLimiter
from spendwise.services.importer import parse_statement
from spendwise.services.money import to_paise


def xlsx(rows) -> bytes:
    wb = Workbook()
    for r in rows:
        wb.active.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def rewrite_zip(data: bytes, name: str, change) -> bytes:
    src, out = zipfile.ZipFile(io.BytesIO(data)), io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for item in src.infolist():
            content = src.read(item.filename)
            z.writestr(item, change(content) if item.filename == name else content)
    return out.getvalue()


# ---------------------------------------------------------------- 1. Excel files that would eat all memory
def test_xlsx_claiming_a_huge_sheet_is_read_quickly():
    data = xlsx([["Date", "Narration", "Debit"], ["01-09-2026", "Swiggy", 250]])
    bomb = rewrite_zip(
        data,
        "xl/worksheets/sheet1.xml",
        lambda c: re.sub(rb'<dimension ref="[^"]+"', b'<dimension ref="A1:XFD1048576"', c),
    )
    assert b"XFD1048576" in zipfile.ZipFile(io.BytesIO(bomb)).read("xl/worksheets/sheet1.xml")
    start = time.perf_counter()
    rows = parse_statement(bomb, "bomb.xlsx").rows
    assert time.perf_counter() - start < 3 and [r.merchant for r in rows] == ["Swiggy"]


def test_zip_bomb_is_refused_before_unzipping():
    data = rewrite_zip(xlsx([["Date"]]), "xl/worksheets/sheet1.xml", lambda c: c + b" " * (25 * 1024 * 1024))
    assert len(data) < 200_000  # tiny on disk, 25 MB inside
    with pytest.raises(ValueError, match="too large once unzipped"):
        parse_statement(data, "bomb.xlsx")


def test_corrupt_sheet_is_a_clean_error():
    broken = rewrite_zip(xlsx([["Date", "Narration", "Debit"]]), "xl/worksheets/sheet1.xml", lambda c: c[: len(c) // 2])
    with pytest.raises(ValueError, match="Excel"):
        parse_statement(broken, "broken.xlsx")


# ---------------------------------------------------------------- 2. a deleted account's token
def test_old_token_never_opens_a_new_account(client):
    alice = register(client, "alice@example.com", "Alice")
    assert (
        client.request("DELETE", "/api/auth/me", headers=alice, json={"password": "correct-horse-1"}).status_code == 204
    )
    bob = register(client, "bob@example.com", "Bob")
    assert client.get("/api/auth/me", headers=bob).json()["name"] == "Bob"
    assert client.get("/api/auth/me", headers=alice).status_code == 401  # was Bob's account before the fix


# ---------------------------------------------------------------- 3. uploads don't block the server
def test_upload_runs_in_a_worker_thread():
    assert not inspect.iscoroutinefunction(imports_api.upload)


# ---------------------------------------------------------------- 4. the AI quota covers every path
def test_adding_payments_cannot_drain_the_ai_quota(client, ai_holder):
    ai_holder["ai"] = fake_ai(categories={})
    llm = ai_holder["ai"].llm
    h = register(client)
    deps.ai_limiter.limit, old = 3, deps.ai_limiter.limit
    try:
        for i in range(8):
            r = client.post(
                "/api/transactions", headers=h, json={"date": "2026-09-01", "merchant": f"Shop {i}", "amount": 10}
            )
            assert r.status_code == 201  # over the limit it still saves, just without AI
    finally:
        deps.ai_limiter.limit = old
    assert len(llm.requests) == 3


# ---------------------------------------------------------------- 5. login limits
def test_a_stranger_cannot_lock_you_out(client):
    register(client, "victim@example.com")
    attacker = TestClient(client.app, client=("203.0.113.9", 4000))
    for _ in range(12):
        attacker.post("/api/auth/login", data={"username": "victim@example.com", "password": "guess"})
    assert (
        attacker.post("/api/auth/login", data={"username": "victim@example.com", "password": "guess"}).status_code
        == 429
    )
    ok = client.post("/api/auth/login", data={"username": "victim@example.com", "password": "correct-horse-1"})
    assert ok.status_code == 200  # the victim, from their own address, still gets in


def test_huge_usernames_are_refused_not_stored(client):
    r = client.post("/api/auth/login", data={"username": "x" * 100_000, "password": "p"})
    assert r.status_code == 401 and not any(len(k) > 300 for k in deps.login_limiter._events)


def test_rate_limiter_forgets_old_keys():
    rl = RateLimiter(limit=5, window=0.01)
    rl.MAX_KEYS = 100
    for i in range(500):
        rl.hit(f"key{i}")
        time.sleep(0.0001) if i % 100 == 0 else None
    time.sleep(0.02)
    rl.hit("last")
    assert len(rl._events) <= 101


# ---------------------------------------------------------------- 6. bad numbers and files are clean errors
@pytest.mark.parametrize("bad", ["1e30", "9" * 29, "0.004", "NaN"])
def test_absurd_amounts_are_refused(bad):
    with pytest.raises(ValueError):
        to_paise(bad)


def test_bad_rows_are_skipped_not_500(client):
    h = register(client)
    text = "Date,Narration,Debit\n01-09-2026,Swiggy,1e30\n01-09-2026,Zomato,0.004\n02-09-2026,Uber,120\n"
    r = upload(client, h, text.encode(), "s.csv").json()
    assert (r["added"], r["skipped"]) == (1, 2)
    huge_field = 'Date,Narration,Debit\n01-09-2026,"' + "x" * 200_000 + '",5\n'
    assert upload(client, h, huge_field.encode(), "s.csv").status_code == 400


# ---------------------------------------------------------------- 7. odd parameters are 422, not 500
def test_odd_parameters(client):
    h = register(client)
    upload(client, h)
    for path in (
        "/api/analytics/dashboard?month=0001-01",
        "/api/analytics/unusual?month=0001-0x",
        "/api/transactions/export.csv?month=２０２６-０９",
        f"/api/transactions?page={10**18}",
    ):
        assert client.get(path, headers=h).status_code == 422, path
    assert client.patch(f"/api/transactions/{2**63}", headers=h, json={"category": "food"}).status_code == 422
    assert client.delete(f"/api/imports/{2**63}", headers=h).status_code == 422
    assert client.put("/api/budgets/food", headers=h, json={"limit": 0.001}).status_code == 422
    far = client.post("/api/transactions", headers=h, json={"date": "9999-12-31", "merchant": "Typo", "amount": 5})
    assert far.status_code == 422
    text = "Date,Narration,Debit\n31-12-9999,Typo,5\n"
    assert upload(client, h, text.encode(), "far.csv").json()["added"] == 0
    assert client.get("/api/analytics/dashboard", headers=h).json()["month"] == "2026-09"


def test_ai_tool_with_absurd_numbers_is_an_error_not_a_crash(session):
    from spendwise.ai import tools

    result, _ = tools.run(session, 1, "find_transactions", '{"min_amount": 1e20}')
    assert "error" in result


# ---------------------------------------------------------------- 8. undo keeps what a later import still has
def test_undo_hands_over_payments_a_later_import_contained(client):
    h = register(client)
    lines = SAMPLE.read_text(encoding="utf-8").splitlines()
    head, body = lines[:4], lines[4:-1]
    first = upload(client, h, "\n".join(head + body[:150]).encode(), "april-july.csv").json()
    second = upload(client, h, "\n".join(head + body[100:]).encode(), "july-sept.csv").json()
    assert second["duplicates"] > 0
    total = client.get("/api/transactions", headers=h).json()["total"]
    assert client.delete(f"/api/imports/{first['id']}", headers=h).status_code == 204
    left = client.get("/api/transactions", headers=h).json()["total"]
    assert left == second["added"] + second["duplicates"]  # everything the second statement covers stays
    assert left < total


# ---------------------------------------------------------------- 9. "UPI transfer" is many people
def test_fixing_one_transfer_does_not_relabel_all_transfers(client):
    h = register(client)
    text = (
        "Date,Narration,Debit\n01-09-2026,UPI/DR/612345678901/9876543210@ybl/SBIN,7000\n"
        "05-09-2026,UPI/DR/612345678902/9123456780@ybl/SBIN,40\n"
    )
    upload(client, h, text.encode(), "p2p.csv")
    rent, chai = sorted(client.get("/api/transactions", headers=h).json()["items"], key=lambda t: -t["amount"])
    client.patch(f"/api/transactions/{rent['id']}", headers=h, json={"category": "rent"})
    after = {t["id"]: t["category"] for t in client.get("/api/transactions", headers=h).json()["items"]}
    assert after == {rent["id"]: "rent", chai["id"]: "transfers"}
    later = upload(client, h, b"Date,Narration,Debit\n06-10-2026,UPI/DR/6129/9000000000@ybl/SBIN,55\n", "x.csv")
    assert later.json()["added"] == 1
    assert client.get("/api/transactions?month=2026-10", headers=h).json()["items"][0]["category"] == "transfers"


# ---------------------------------------------------------------- low-severity items
def test_merchants_named_total_are_payments():
    text = "Date,Narration,Debit\n01-09-2026,TOTAL MALL BENGALURU,500\n02-09-2026,Total,999\n"
    assert [r.merchant for r in parse_statement(text.encode(), "s.csv").rows] == ["Total Mall Bengaluru"]


def test_us_style_dates_are_detected():
    text = "Date,Narration,Debit\n01/02/2026,A,10\n01/15/2026,B,10\n"
    assert [r.date.isoformat() for r in parse_statement(text.encode(), "s.csv").rows] == ["2026-01-02", "2026-01-15"]
    indian = "Date,Narration,Debit\n01/02/2026,A,10\n15/01/2026,B,10\n"
    assert [r.date.isoformat() for r in parse_statement(indian.encode(), "s.csv").rows] == ["2026-02-01", "2026-01-15"]
