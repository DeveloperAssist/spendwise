"""Categories and analytics, straight against the database."""

import datetime as dt

import pytest
from conftest import SAMPLE, FakeLLM
from sqlmodel import select

from spendwise.ai.service import AIService
from spendwise.models import Budget, MerchantCategory, User
from spendwise.services import analytics as an
from spendwise.services.categorizer import by_rules, categorize, remember
from spendwise.services.imports import import_statement


@pytest.fixture
def user(session):
    u = User(email="t@example.com", name="T", password_hash="x")
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


@pytest.fixture
def loaded(session, user):
    import_statement(session, user, SAMPLE.read_bytes(), "sample.csv", None)
    return user


# ---------------------------------------------------------------- categories
@pytest.mark.parametrize(
    "text,cat",
    [
        ("Swiggy", "food"),
        ("Coca-Cola", None),
        ("Facebook ads", None),
        ("Ola cabs", "travel"),
        ("Grocery store", "groceries"),
        ("Chaitanya", None),
        ("BookMyShow", "entertainment"),
        ("Jio recharge", "bills"),
        ("Sunrise Pg Hostel Rent", "rent"),
        ("UPI transfer", "transfers"),
    ],
)
def test_keyword_rules_match_whole_words(text, cat):
    assert by_rules(text) == cat


def test_rules_then_one_ai_request_then_remembered(session, user):
    llm = FakeLLM(categories={"Chaayos": "food", "Snitch": "shopping"})
    got = categorize(
        session, user.id, [("Swiggy", ""), ("Chaayos", ""), ("Snitch", ""), ("Chaayos", "")], AIService(llm)
    )
    assert got == {"swiggy": ("food", "rule"), "chaayos": ("food", "ai"), "snitch": ("shopping", "ai")}
    assert len(llm.requests) == 1  # one request for all unknowns
    again = FakeLLM()
    assert categorize(session, user.id, [("Chaayos", "")], AIService(again))["chaayos"] == ("food", "learned")
    assert again.requests == []  # never asked twice


def test_ai_answers_are_checked_and_failures_are_harmless(session, user):
    made_up = FakeLLM(categories={"Snitch": "fashion vibes"})
    assert categorize(session, user.id, [("Snitch", "")], AIService(made_up))["snitch"] == ("other", "other")

    class Broken:
        def categorize(self, *a):
            raise TimeoutError("AI is down")

    assert categorize(session, user.id, [("Wow Momo", "")], Broken())["wowmomo"] == ("other", "other")


def test_your_fix_beats_rules_and_ai(session, user):
    remember(session, user.id, "swiggy", "groceries", "you")
    remember(session, user.id, "swiggy", "food", "rule")  # a rule can't overwrite you
    session.commit()
    assert session.exec(select(MerchantCategory)).one().category == "groceries"
    assert categorize(session, user.id, [("Swiggy", "")])["swiggy"] == ("groceries", "you")


# ---------------------------------------------------------------- months
def test_month_helpers():
    assert an.month_range("2026-12") == (dt.date(2026, 12, 1), dt.date(2027, 1, 1))
    assert an.shift_month("2027-01", -1) == "2026-12" and an.shift_month("2026-11", 3) == "2027-02"
    for bad in ("Sept", "2026-13", "", None):
        with pytest.raises(ValueError):
            an.month_range(bad)


# ---------------------------------------------------------------- analytics on the sample data
def test_month_summary(session, loaded):
    s = an.month_summary(session, loaded.id, "2026-09", today=dt.date(2026, 10, 8))
    assert s["income"] == 2300000  # allowance 8,000 + stipend 15,000
    assert s["spent"] == sum(s["by_category"].values())
    assert s["saved"] == s["income"] - s["spent"]
    assert s["forecast"] is None  # September is over
    assert list(s["by_category"].values()) == sorted(s["by_category"].values(), reverse=True)


def test_forecast_only_while_the_month_runs(session, loaded):
    s = an.month_summary(session, loaded.id, "2026-09", today=dt.date(2026, 9, 15))
    spent_so_far = s["spent"]  # the whole month is in the data
    assert s["forecast"] == spent_so_far * 30 // 15 and s["days_left"] == 15


def test_trend_has_every_month(session, loaded):
    t = an.trend(session, loaded.id, "2026-10", 8)
    assert [x["month"] for x in t][0] == "2026-03" and t[-1]["month"] == "2026-10"
    assert t[0]["spent"] == 0 and t[-1]["spent"] == 0  # empty months are kept, as zero


def test_budgets(session, loaded):
    session.add(Budget(user_id=loaded.id, category="food", limit_paise=100_00))
    session.add(Budget(user_id=loaded.id, category="health", limit_paise=1_000_000_00))
    session.commit()
    s = an.month_summary(session, loaded.id, "2026-09")
    status = {b["category"]: b["status"] for b in an.budget_status(session, loaded.id, s["by_category"])}
    assert status == {"food": "over", "health": "ok"}


def test_recurring_finds_subscriptions_not_daily_habits(session, loaded):
    found = an.recurring(session, loaded.id, today=dt.date(2026, 10, 8))
    names = {s["merchant"] for s in found}
    kinds = {s["merchant"]: s["type"] for s in found}
    assert kinds["Spotify"] == "subscription" and kinds["Sunrise Pg Hostel Rent"] == "bill"
    assert {"Spotify", "Airtel Prepaid", "Netflix Entertainment", "Sunrise Pg Hostel Rent"} <= names
    assert not {"Swiggy", "Rapido", "Uber", "Chai Point", "Blinkit"} & names  # frequent, not monthly bills


def test_unusual_flags_the_big_croma_purchase(session, loaded):
    odd = an.unusual(session, loaded.id, "2026-09")
    assert [o["merchant"] for o in odd] == ["Croma"] and odd[0]["times_usual"] >= 3


def test_import_is_idempotent(session, user):
    first, _, _ = import_statement(session, user, SAMPLE.read_bytes(), "a.csv", None)
    again, _, _ = import_statement(session, user, SAMPLE.read_bytes(), "b.csv", None)
    assert (first.added, first.duplicates) == (227, 0)
    assert (again.added, again.duplicates) == (0, 227)
