"""Payments: list (filter, search, page), add, fix, delete, export."""

import csv
import io
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi import Path as PathParam
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlmodel import Session, select

from ..db import get_session
from ..models import Transaction, User
from ..services import analytics as an
from ..services.categorizer import categorize, credit_category, remember
from ..services.imports import manual_key
from ..services.merchants import GENERIC_KEYS, merchant_key
from ..services.money import rupees, to_paise
from .deps import MeteredAI, get_current_user, optional_ai
from .schemas import Page, TransactionIn, TransactionOut, TransactionPatch

router = APIRouter(prefix="/api/transactions", tags=["transactions"])
TxId = PathParam(ge=1, le=2**31 - 1)  # a bigger id overflowed the database integer (500)


def out(t: Transaction) -> TransactionOut:
    return TransactionOut(
        id=t.id,
        date=t.date,
        merchant=t.merchant,
        description=t.description,
        amount=rupees(t.amount_paise),
        kind=t.kind,
        category=t.category,
        category_source=t.category_source,
        note=t.note,
        import_id=t.import_id,
    )


def _filtered(user_id: int, month, category, kind, q):
    query = select(Transaction).where(Transaction.user_id == user_id)
    if month:
        try:
            start, end = an.month_range(month)
        except ValueError as e:
            raise HTTPException(422, str(e)) from None
        query = query.where(Transaction.date >= start, Transaction.date < end)
    if category:
        query = query.where(Transaction.category == category)
    if kind:
        query = query.where(Transaction.kind == kind)
    if q:
        needle = q.strip().lower()
        query = query.where(
            func.lower(Transaction.merchant).contains(needle, autoescape=True)
            | func.lower(Transaction.description).contains(needle, autoescape=True)
        )
    return query


def _owned(session: Session, user: User, tx_id: int) -> Transaction:
    t = session.get(Transaction, tx_id)
    if t is None or t.user_id != user.id:  # someone else's id looks exactly like a missing one
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such transaction.")
    return t


@router.get("", response_model=Page)
def list_transactions(
    month: str | None = None,
    category: str | None = None,
    kind: Literal["debit", "credit"] | None = None,
    q: str | None = Query(None, max_length=60),
    sort: Literal["newest", "oldest", "biggest"] = "newest",
    page: int = Query(1, ge=1, le=10_000),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    base = _filtered(user.id, month, category, kind, q)
    total = session.exec(select(func.count()).select_from(base.subquery())).one()
    order = {
        "newest": (Transaction.date.desc(), Transaction.id.desc()),
        "oldest": (Transaction.date, Transaction.id),
        "biggest": (Transaction.amount_paise.desc(), Transaction.id.desc()),
    }[sort]
    rows = session.exec(base.order_by(*order).offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=[out(t) for t in rows], total=total, page=page, page_size=page_size)


@router.get("/export.csv")
def export_csv(
    month: str | None = None, user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    rows = session.exec(_filtered(user.id, month, None, None, None).order_by(Transaction.date)).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "merchant", "amount", "type", "category", "note"])

    def safe(v: str | None) -> str:
        # a cell starting with = + - @ runs as a formula in Excel ("CSV injection"); quote it
        v = v or ""
        return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") else v

    for t in rows:
        w.writerow(
            [t.date.isoformat(), safe(t.merchant), f"{rupees(t.amount_paise):.2f}", t.kind, t.category, safe(t.note)]
        )
    name = f"spendwise-{month or 'all'}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'}
    )


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def add_transaction(
    body: TransactionIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    ai: MeteredAI | None = Depends(optional_ai),
):
    if body.category:
        category, source = body.category, "you"
    elif body.kind == "credit":
        category, source = credit_category(body.merchant), "rule"
    else:
        category, source = categorize(session, user.id, [(body.merchant, "")], ai)[merchant_key(body.merchant)]
    t = Transaction(
        user_id=user.id,
        date=body.date,
        merchant=body.merchant,
        description=body.merchant,
        amount_paise=to_paise(f"{body.amount:.2f}"),
        kind=body.kind,
        category=category,
        category_source=source,
        note=body.note,
        dedup_key=manual_key(),
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return out(t)


@router.patch("/{tx_id}", response_model=TransactionOut)
def update_transaction(
    body: TransactionPatch,
    tx_id: int = TxId,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    t = _owned(session, user, tx_id)
    if "note" in body.model_fields_set:
        t.note = body.note
    if body.category and body.category != t.category:
        key = merchant_key(t.merchant)
        # "UPI transfer" is many different people: fixing one must not re-label all of them
        if body.apply_to_merchant and t.kind == "debit" and key not in GENERIC_KEYS:
            for other in session.exec(
                select(Transaction).where(Transaction.user_id == user.id, Transaction.kind == "debit")
            ).all():
                if merchant_key(other.merchant) == key:
                    other.category, other.category_source = body.category, "you"
                    session.add(other)
            remember(session, user.id, key, body.category, "you")
        t.category, t.category_source = body.category, "you"
    session.add(t)
    session.commit()
    session.refresh(t)
    return out(t)


@router.delete("/{tx_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    tx_id: int = TxId, user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    session.delete(_owned(session, user, tx_id))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
