"""Budgets, the dashboard numbers, and the AI endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from ..ai.service import AIService
from ..config import get_settings
from ..db import get_session
from ..models import SPEND_CATEGORIES, Budget, User
from ..services import analytics as an
from ..services.money import rupees, to_paise
from .deps import get_ai, get_current_user, require_ai
from .schemas import BudgetIn, BudgetOut, ChatIn, ChatOut

router = APIRouter(prefix="/api", tags=["insights"])
log = logging.getLogger("spendwise.api")


def _month(session: Session, user: User, month: str | None) -> str:
    month = month or an.latest_month(session, user.id)
    try:
        an.month_range(month)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    return month


def _r(d: dict, *keys: str) -> dict:
    return {**d, **{k: rupees(d[k]) for k in keys if d.get(k) is not None}}


# ---------------------------------------------------------------- budgets
@router.get("/budgets", response_model=list[BudgetOut])
def list_budgets(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    rows = session.exec(select(Budget).where(Budget.user_id == user.id).order_by(Budget.category)).all()
    return [BudgetOut(category=b.category, limit=rupees(b.limit_paise)) for b in rows]


@router.put("/budgets/{category}", response_model=BudgetOut)
def set_budget(
    category: str, body: BudgetIn, user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    if category not in SPEND_CATEGORIES:
        raise HTTPException(422, f"category must be one of: {', '.join(SPEND_CATEGORIES)}")
    b = session.exec(select(Budget).where(Budget.user_id == user.id, Budget.category == category)).first()
    b = b or Budget(user_id=user.id, category=category, limit_paise=1)
    b.limit_paise = to_paise(f"{body.limit:.2f}")
    session.add(b)
    session.commit()
    return BudgetOut(category=category, limit=rupees(b.limit_paise))


@router.delete("/budgets/{category}", status_code=status.HTTP_204_NO_CONTENT)
def remove_budget(category: str, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    b = session.exec(select(Budget).where(Budget.user_id == user.id, Budget.category == category)).first()
    if b:
        session.delete(b)
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- analytics
@router.get("/analytics/months")
def months(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> list[str]:
    return an.months_with_data(session, user.id)


@router.get("/analytics/dashboard")
def dashboard(
    month: str | None = None, user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    """Everything the dashboard page shows, in one request."""
    month = _month(session, user, month)
    this = an.month_summary(session, user.id, month)
    last = an.month_summary(session, user.id, an.shift_month(month, -1))
    budgets = an.budget_status(session, user.id, this["by_category"])
    return {
        "month": month,
        "summary": {
            **_r(this, "spent", "income", "saved", "daily_average", "forecast"),
            "by_category": {k: rupees(v) for k, v in this["by_category"].items()},
            "top_merchants": [_r(m, "spent") for m in this["top_merchants"]],
        },
        "change": an.compare(this, last),
        "budgets": [_r(b, "spent", "limit") for b in budgets],
        "trend": [_r(t, "spent", "income") for t in an.trend(session, user.id, month, 6)],
        "daily": [_r(d, "spent") for d in an.daily_spending(session, user.id, month)],
    }


@router.get("/analytics/subscriptions")
def subscriptions(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    subs = an.recurring(session, user.id)
    return {"items": [_r(s, "amount") for s in subs], "per_month": rupees(sum(s["amount"] for s in subs))}


@router.get("/analytics/unusual")
def unusual(month: str | None = None, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    month = _month(session, user, month)
    return {"month": month, "items": [_r(u, "amount", "typical") for u in an.unusual(session, user.id, month)]}


# ---------------------------------------------------------------- AI
@router.get("/ai/status")
def ai_status(ai: AIService | None = Depends(get_ai), user: User = Depends(get_current_user)):
    return {"enabled": ai is not None, "model": get_settings().ai_model if ai else None}


@router.post("/ai/insights")
def ai_insights(
    month: str | None = None,
    ai: AIService = Depends(require_ai),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    month = _month(session, user, month)
    this = an.month_summary(session, user.id, month)
    last = an.month_summary(session, user.id, an.shift_month(month, -1))
    facts = an.facts_for_ai(
        this,
        an.compare(this, last),
        an.budget_status(session, user.id, this["by_category"]),
        an.recurring(session, user.id),
        an.unusual(session, user.id, month),
    )
    try:
        text = ai.insights(facts)
    except Exception as e:
        log.warning("AI insights failed: %s", e)
        raise HTTPException(502, "The AI didn't answer. Try again in a minute.") from None
    return {"month": month, "text": text}


@router.post("/ai/chat", response_model=ChatOut)
def ai_chat(
    body: ChatIn,
    ai: AIService = Depends(require_ai),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    try:
        result = ai.ask(session, user, body.message, [t.model_dump() for t in body.history])
    except Exception as e:
        log.warning("AI chat failed: %s", e)
        raise HTTPException(502, "The AI didn't answer. Try again in a minute.") from None
    return ChatOut(**result)
