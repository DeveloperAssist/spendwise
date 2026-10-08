"""The tools the AI assistant may call.

Each tool is a plain Python function with typed arguments (a Pydantic model). The model only sees
each tool's name, description and argument schema. When it asks for a tool, we validate its
arguments, run the function for the LOGGED-IN user only, and give it back the result.

Every tool is read-only and filtered by user_id, so no matter what the model asks, or what a
merchant name in a statement says, it can't change data or see anyone else's.
"""

import datetime as dt
import json
from collections import defaultdict
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func
from sqlmodel import Session, select

from ..models import SPEND_CATEGORIES, Transaction
from ..services import analytics as an

Month = Field(default=None, description="A month as YYYY-MM, e.g. 2026-09. Leave empty for the latest month.")
Category = Literal[tuple(SPEND_CATEGORIES)]  # type: ignore[valid-type]


def r(paise: int) -> float:
    return round(paise / 100, 2)


class MonthArgs(BaseModel):
    month: str | None = Month


class RangeArgs(BaseModel):
    start_month: str | None = Field(default=None, description="First month, YYYY-MM. Empty = earliest.")
    end_month: str | None = Field(default=None, description="Last month, YYYY-MM. Empty = latest.")


class MerchantArgs(RangeArgs):
    merchant: str = Field(min_length=1, max_length=60, description="Merchant name or part of it, e.g. swiggy")


class CategoryArgs(RangeArgs):
    category: Category = Field(description="One spending category")


class SearchArgs(BaseModel):
    text: str | None = Field(default=None, max_length=60, description="Part of a merchant name")
    category: Category | None = None
    month: str | None = Month
    min_amount: float | None = Field(default=None, ge=0, le=10_000_000, description="Rupees")
    max_amount: float | None = Field(default=None, ge=0, le=10_000_000, description="Rupees")
    sort: Literal["newest", "biggest"] = Field(default="newest", description="biggest = largest amounts first")
    limit: int = Field(default=10, ge=1, le=25)


class CompareArgs(BaseModel):
    month_a: str = Field(description="YYYY-MM")
    month_b: str = Field(description="YYYY-MM")


class NoArgs(BaseModel):
    pass


def _range(session: Session, user_id: int, a: RangeArgs) -> tuple[dt.date, dt.date, str, str]:
    months = an.months_with_data(session, user_id)
    first = a.start_month or (months[-1] if months else an.latest_month(session, user_id))
    last = a.end_month or (months[0] if months else first)
    start, _ = an.month_range(first)
    _, end = an.month_range(last)
    return start, end, first, last


def month_overview(session: Session, user_id: int, a: MonthArgs) -> dict:
    month = a.month or an.latest_month(session, user_id)
    s = an.month_summary(session, user_id, month)
    b = an.budget_status(session, user_id, s["by_category"])
    return {
        "month": month,
        "spent": r(s["spent"]),
        "income": r(s["income"]),
        "saved": r(s["saved"]),
        "payments": s["payments"],
        "spent_by_category": {k: r(v) for k, v in s["by_category"].items()},
        "top_merchants": [{"merchant": m["merchant"], "spent": r(m["spent"])} for m in s["top_merchants"]],
        "budgets": [
            {"category": x["category"], "spent": r(x["spent"]), "limit": r(x["limit"]), "status": x["status"]}
            for x in b
        ],
    }


def spending_on_merchant(session: Session, user_id: int, a: MerchantArgs) -> dict:
    start, end, first, last = _range(session, user_id, a)
    rows = session.exec(
        select(Transaction.merchant, Transaction.date, Transaction.amount_paise).where(
            Transaction.user_id == user_id,
            Transaction.kind == "debit",
            Transaction.date >= start,
            Transaction.date < end,
            func.lower(Transaction.merchant).contains(a.merchant.strip().lower(), autoescape=True),
        )
    ).all()
    per_month: dict[str, int] = defaultdict(int)
    for _, d, amount in rows:
        per_month[d.strftime("%Y-%m")] += amount
    return {
        "merchant_search": a.merchant,
        "matched_merchants": sorted({m for m, _, _ in rows}),
        "from": first,
        "to": last,
        "total_spent": r(sum(per_month.values())),
        "payments": len(rows),
        "by_month": {m: r(v) for m, v in sorted(per_month.items())},
    }


def spending_by_category(session: Session, user_id: int, a: CategoryArgs) -> dict:
    start, end, first, last = _range(session, user_id, a)
    rows = session.exec(
        select(Transaction.date, Transaction.amount_paise).where(
            Transaction.user_id == user_id,
            Transaction.kind == "debit",
            Transaction.category == a.category,
            Transaction.date >= start,
            Transaction.date < end,
        )
    ).all()
    per_month: dict[str, int] = defaultdict(int)
    for d, amount in rows:
        per_month[d.strftime("%Y-%m")] += amount
    return {
        "category": a.category,
        "from": first,
        "to": last,
        "total_spent": r(sum(per_month.values())),
        "payments": len(rows),
        "by_month": {m: r(v) for m, v in sorted(per_month.items())},
    }


def find_transactions(session: Session, user_id: int, a: SearchArgs) -> dict:
    q = select(Transaction).where(Transaction.user_id == user_id, Transaction.kind == "debit")
    if a.month:
        start, end = an.month_range(a.month)
        q = q.where(Transaction.date >= start, Transaction.date < end)
    if a.text:
        q = q.where(func.lower(Transaction.merchant).contains(a.text.strip().lower(), autoescape=True))
    if a.category:
        q = q.where(Transaction.category == a.category)
    if a.min_amount is not None:
        q = q.where(Transaction.amount_paise >= round(a.min_amount * 100))
    if a.max_amount is not None:
        q = q.where(Transaction.amount_paise <= round(a.max_amount * 100))
    order = Transaction.amount_paise.desc() if a.sort == "biggest" else Transaction.date.desc()
    rows = session.exec(q.order_by(order, Transaction.id.desc()).limit(a.limit)).all()
    return {
        "transactions": [
            {"date": t.date.isoformat(), "merchant": t.merchant, "amount": r(t.amount_paise), "category": t.category}
            for t in rows
        ],
        "shown": len(rows),
    }


def subscriptions(session: Session, user_id: int, a: NoArgs) -> dict:
    subs = an.recurring(session, user_id)

    def item(s: dict) -> dict:
        return {"merchant": s["merchant"], "monthly_amount": r(s["amount"]), "next_expected": s["next_expected"]}

    # two separate lists: a model reading one mixed list happily "saved money" by cancelling the rent
    can_cancel = [s for s in subs if s["type"] == "subscription"]
    bills = [s for s in subs if s["type"] == "bill"]
    return {
        "subscriptions_you_can_cancel": [item(s) for s in can_cancel],
        "subscriptions_total_per_month": r(sum(s["amount"] for s in can_cancel)),
        "essential_bills_not_to_cancel": [item(s) for s in bills],
        "bills_total_per_month": r(sum(s["amount"] for s in bills)),
    }


def unusual_payments(session: Session, user_id: int, a: MonthArgs) -> dict:
    month = a.month or an.latest_month(session, user_id)
    odd = an.unusual(session, user_id, month)
    return {
        "month": month,
        "rule": "at least 3x the usual payment in that category (last 6 months) and at least Rs 500",
        "unusual_payments": [
            {
                "date": u["date"],
                "merchant": u["merchant"],
                "category": u["category"],
                "amount": r(u["amount"]),
                "usual_amount": r(u["typical"]),
                "times_usual": u["times_usual"],
            }
            for u in odd
        ],
    }


def compare_months(session: Session, user_id: int, a: CompareArgs) -> dict:
    ca = an.by_category(session, user_id, a.month_a)
    cb = an.by_category(session, user_id, a.month_b)
    cats = sorted(set(ca) | set(cb))
    return {
        "month_a": a.month_a,
        "month_b": a.month_b,
        "total_a": r(sum(ca.values())),
        "total_b": r(sum(cb.values())),
        "by_category": {c: {"a": r(ca.get(c, 0)), "b": r(cb.get(c, 0))} for c in cats},
    }


TOOLS: dict[str, tuple[Callable, type[BaseModel], str]] = {
    "month_overview": (
        month_overview,
        MonthArgs,
        "Totals for one month: spent, income, saved, spending by category, top merchants, budgets. "
        "Not for recurring payments: use the subscriptions tool for those.",
    ),
    "spending_on_merchant": (
        spending_on_merchant,
        MerchantArgs,
        "How much was spent at one merchant (e.g. Swiggy) over a range of months.",
    ),
    "spending_by_category": (
        spending_by_category,
        CategoryArgs,
        "How much was spent in one category over a range of months, month by month.",
    ),
    "find_transactions": (
        find_transactions,
        SearchArgs,
        "List individual payments, filtered by merchant text, category, month or amount; "
        "sort=biggest for the largest ones.",
    ),
    "subscriptions": (
        subscriptions,
        NoArgs,
        "Every recurring monthly payment: subscriptions (streaming, apps: can be cancelled) and essential "
        "bills (rent, phone, electricity). Use it for any question about subscriptions, bills or fixed costs.",
    ),
    "unusual_payments": (
        unusual_payments,
        MonthArgs,
        "Payments in a month that are far bigger than usual for their category (possible one-offs or mistakes).",
    ),
    "compare_months": (compare_months, CompareArgs, "Spending by category in two months, side by side."),
}


def schemas() -> list[dict]:
    """The tool list in the OpenAI / Groq function-calling format."""
    out = []
    for name, (_, model, desc) in TOOLS.items():
        params = model.model_json_schema()
        params.pop("title", None)
        out.append({"type": "function", "function": {"name": name, "description": desc, "parameters": params}})
    return out


def run(session: Session, user_id: int, name: str, arguments: str) -> tuple[dict, dict | None]:
    """-> (result, parsed arguments). Bad tool names or arguments become an error the model can read."""
    if name not in TOOLS:
        return {"error": f"unknown tool {name!r}"}, None
    fn, model, _ = TOOLS[name]
    try:
        args = model.model_validate(json.loads(arguments or "{}"))
    except (json.JSONDecodeError, ValidationError, TypeError) as e:
        return {"error": f"invalid arguments: {str(e)[:300]}"}, None
    try:
        return fn(session, user_id, args), args.model_dump(exclude_none=True)
    except (ValueError, ArithmeticError) as e:  # a month like "Sept"; a number too big for the database
        return {"error": str(e)[:300]}, args.model_dump(exclude_none=True)
