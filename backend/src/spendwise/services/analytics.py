"""Every number SpendWise shows. Plain Python and SQL: the AI never calculates anything.

All functions take a user id and only ever read that user's rows.
"""

import calendar
import datetime as dt
import re
import statistics
from collections import defaultdict

from sqlalchemy import func
from sqlmodel import Session, select

from ..models import Budget, Transaction
from . import clock

WARN_AT = 0.8  # a budget is "close" at 80% used
ESSENTIAL = {"rent", "bills", "education", "health", "groceries"}


# ---------------------------------------------------------------- months
MONTH = re.compile(r"(20[0-9]{2})-(0[1-9]|1[0-2])")  # ASCII digits only, years 2000-2099


def month_range(month: str) -> tuple[dt.date, dt.date]:
    """'2026-09' -> (2026-09-01, 2026-10-01): a half-open range that works in every database."""
    m_ = MONTH.fullmatch(month) if isinstance(month, str) else None
    if not m_:
        raise ValueError(f"month must look like 2026-09, got {str(month)[:20]!r}")
    y, m = int(m_[1]), int(m_[2])
    start = dt.date(y, m, 1)
    end = dt.date(y + (m == 12), 1 if m == 12 else m + 1, 1)
    return start, end


def shift_month(month: str, n: int) -> str:
    y, m = map(int, month.split("-"))
    i = y * 12 + (m - 1) + n
    return f"{i // 12}-{i % 12 + 1:02d}"


def months_with_data(session: Session, user_id: int) -> list[str]:
    """Newest first: ['2026-09', '2026-08', ...]."""
    dates = session.exec(select(Transaction.date).where(Transaction.user_id == user_id).distinct()).all()
    return sorted({d.strftime("%Y-%m") for d in dates}, reverse=True)


def latest_month(session: Session, user_id: int) -> str:
    return (months_with_data(session, user_id) or [clock.today().strftime("%Y-%m")])[0]


def _in_month(user_id: int, month: str):
    start, end = month_range(month)
    return (Transaction.user_id == user_id, Transaction.date >= start, Transaction.date < end)


# ---------------------------------------------------------------- the month
def by_category(session: Session, user_id: int, month: str) -> dict[str, int]:
    """Money out per category, biggest first (SQL GROUP BY)."""
    rows = session.exec(
        select(Transaction.category, func.sum(Transaction.amount_paise))
        .where(*_in_month(user_id, month), Transaction.kind == "debit")
        .group_by(Transaction.category)
    ).all()
    return dict(sorted(((c, int(s)) for c, s in rows), key=lambda kv: -kv[1]))


def month_summary(session: Session, user_id: int, month: str, today: dt.date | None = None) -> dict:
    start, end = month_range(month)
    totals = dict(
        session.exec(
            select(Transaction.kind, func.sum(Transaction.amount_paise))
            .where(*_in_month(user_id, month))
            .group_by(Transaction.kind)
        ).all()
    )
    spent, income = int(totals.get("debit") or 0), int(totals.get("credit") or 0)
    count = session.exec(
        select(func.count()).select_from(Transaction).where(*_in_month(user_id, month), Transaction.kind == "debit")
    ).one()
    top = session.exec(
        select(Transaction.merchant, func.sum(Transaction.amount_paise).label("total"), func.count())
        .where(*_in_month(user_id, month), Transaction.kind == "debit")
        .group_by(Transaction.merchant)
        .order_by(func.sum(Transaction.amount_paise).desc())
        .limit(5)
    ).all()

    days_in_month = calendar.monthrange(start.year, start.month)[1]
    today = today or clock.today()
    running = start <= today < end
    days = today.day if running else days_in_month
    return {
        "month": month,
        "spent": spent,
        "income": income,
        "saved": income - spent,
        "savings_rate": round((income - spent) / income, 3) if income else None,
        "payments": int(count),
        "by_category": by_category(session, user_id, month),
        "top_merchants": [{"merchant": m, "spent": int(t), "payments": int(n)} for m, t, n in top],
        "daily_average": spent // days if days else 0,
        # only a month still running gets a forecast: spending so far, at today's pace
        "forecast": spent * days_in_month // days if running and days else None,
        "days_left": (end - today).days - 1 if running else 0,
    }


def compare(this: dict, last: dict) -> dict[str, float | None]:
    """Percent change in spending vs the month before, per category and in total."""
    out: dict[str, float | None] = {}
    for cat in set(this["by_category"]) | set(last["by_category"]):
        now, before = this["by_category"].get(cat, 0), last["by_category"].get(cat, 0)
        out[cat] = round((now - before) * 100 / before, 1) if before else None
    out["total"] = round((this["spent"] - last["spent"]) * 100 / last["spent"], 1) if last["spent"] else None
    return out


def budget_status(session: Session, user_id: int, spent_by_category: dict[str, int]) -> list[dict]:
    budgets = session.exec(select(Budget).where(Budget.user_id == user_id).order_by(Budget.category)).all()
    out = []
    for b in budgets:
        spent = spent_by_category.get(b.category, 0)
        used = spent / b.limit_paise
        out.append(
            {
                "category": b.category,
                "spent": spent,
                "limit": b.limit_paise,
                "used": round(used, 3),
                "status": "over" if used > 1 else "close" if used >= WARN_AT else "ok",
            }
        )
    return out


def trend(session: Session, user_id: int, end_month: str, months: int = 12) -> list[dict]:
    """Money in and out for each of the last `months` months, oldest first (empty months included)."""
    first = shift_month(end_month, -(months - 1))
    start, _ = month_range(first)
    _, end = month_range(end_month)
    rows = session.exec(
        select(Transaction.date, Transaction.kind, Transaction.amount_paise).where(
            Transaction.user_id == user_id, Transaction.date >= start, Transaction.date < end
        )
    ).all()
    sums: dict[str, dict[str, int]] = defaultdict(lambda: {"debit": 0, "credit": 0})
    for d, kind, amount in rows:
        sums[d.strftime("%Y-%m")][kind] += amount
    return [
        {"month": m, "spent": sums[m]["debit"], "income": sums[m]["credit"]}
        for m in (shift_month(first, i) for i in range(months))
    ]


def daily_spending(session: Session, user_id: int, month: str) -> list[dict]:
    start, end = month_range(month)
    rows = session.exec(
        select(Transaction.date, func.sum(Transaction.amount_paise))
        .where(*_in_month(user_id, month), Transaction.kind == "debit")
        .group_by(Transaction.date)
    ).all()
    sums = {d: int(s) for d, s in rows}
    return [
        {"date": (start + dt.timedelta(days=i)).isoformat(), "spent": sums.get(start + dt.timedelta(days=i), 0)}
        for i in range((end - start).days)
    ]


# ---------------------------------------------------------------- patterns
def recurring(session: Session, user_id: int, today: dt.date | None = None, lookback_days: int = 200) -> list[dict]:
    """Subscriptions and regular bills: the same merchant, a similar amount (within 15%), about once
    a month (every 25 to 35 days), at least 3 times.

    Most of that merchant's payments must fit the pattern, at most one per month: otherwise two random
    Uber rides a month, picked out of many, look like a "₹250 subscription" (a bug found live)."""
    today = today or clock.today()
    last_date = session.exec(select(func.max(Transaction.date)).where(Transaction.user_id == user_id)).one()
    anchor = min(today, last_date) if last_date else today
    rows = session.exec(
        select(Transaction.merchant, Transaction.date, Transaction.amount_paise, Transaction.category)
        .where(
            Transaction.user_id == user_id,
            Transaction.kind == "debit",
            Transaction.date >= anchor - dt.timedelta(days=lookback_days),
        )
        .order_by(Transaction.date)
    ).all()
    groups: dict[str, list] = defaultdict(list)
    for merchant, d, amount, cat in rows:
        groups[merchant].append((d, amount, cat))
    out = []
    for merchant, items in groups.items():
        if len(items) < 3:
            continue
        typical = int(statistics.median(a for _, a, _ in items))
        similar = [(d, a, c) for d, a, c in items if abs(a - typical) <= 0.15 * typical]
        if len(similar) < 3 or len(similar) < 0.75 * len(items):
            continue
        if len({d.strftime("%Y-%m") for d, _, _ in similar}) < len(similar):  # two in one month: not a bill
            continue
        gaps = [(b[0] - a[0]).days for a, b in zip(similar, similar[1:], strict=False)]
        if not 25 <= statistics.median(gaps) <= 35:
            continue
        last = similar[-1][0]
        out.append(
            {
                "merchant": merchant,
                "category": similar[-1][2],
                # rent and utility bills are needs; streaming, apps and memberships can be cancelled
                "type": "bill" if similar[-1][2] in ESSENTIAL else "subscription",
                "amount": typical,
                "times": len(similar),
                "last_paid": last.isoformat(),
                "next_expected": (last + dt.timedelta(days=30)).isoformat(),
            }
        )
    return sorted(out, key=lambda r: -r["amount"])


def unusual(session: Session, user_id: int, month: str, factor: float = 3.0, min_paise: int = 50_000) -> list[dict]:
    """Payments in `month` that are much bigger than usual for their category: at least `factor` times
    the median of the previous 6 months (with 5+ payments to compare), and at least ₹500."""
    start, end = month_range(month)
    history = session.exec(
        select(Transaction.category, Transaction.amount_paise).where(
            Transaction.user_id == user_id,
            Transaction.kind == "debit",
            Transaction.date >= month_range(shift_month(month, -6))[0],
            Transaction.date < start,
        )
    ).all()
    per_cat: dict[str, list[int]] = defaultdict(list)
    for cat, amount in history:
        per_cat[cat].append(amount)
    medians = {c: statistics.median(v) for c, v in per_cat.items() if len(v) >= 5}
    rows = session.exec(
        select(Transaction)
        .where(*_in_month(user_id, month), Transaction.kind == "debit")
        .order_by(Transaction.amount_paise.desc())
    ).all()
    out = []
    for t in rows:
        typical = medians.get(t.category)
        if typical and t.amount_paise >= min_paise and t.amount_paise >= factor * typical:
            out.append(
                {
                    "id": t.id,
                    "date": t.date.isoformat(),
                    "merchant": t.merchant,
                    "category": t.category,
                    "amount": t.amount_paise,
                    "typical": int(typical),
                    "times_usual": round(t.amount_paise / typical, 1),
                }
            )
    return out


def facts_for_ai(summary: dict, change: dict, budgets: list[dict], subscriptions: list[dict], odd: list[dict]) -> dict:
    """The month in rupees, small enough to hand to the AI as the ONLY numbers it may use."""
    r = lambda p: round(p / 100)  # noqa: E731
    return {
        "month": summary["month"],
        "spent": r(summary["spent"]),
        "income": r(summary["income"]),
        "saved": r(summary["saved"]),
        "savings_rate_percent": round(summary["savings_rate"] * 100) if summary["savings_rate"] is not None else None,
        "payments": summary["payments"],
        "spent_by_category": {k: r(v) for k, v in summary["by_category"].items()},
        "change_vs_last_month_percent": change,
        "top_merchants": [[m["merchant"], r(m["spent"])] for m in summary["top_merchants"]],
        "budgets": [
            {"category": b["category"], "spent": r(b["spent"]), "limit": r(b["limit"]), "status": b["status"]}
            for b in budgets
        ],
        "subscriptions": [[s["merchant"], r(s["amount"])] for s in subscriptions],
        "unusual_payments": [[u["merchant"], r(u["amount"]), u["times_usual"]] for u in odd],
    }
