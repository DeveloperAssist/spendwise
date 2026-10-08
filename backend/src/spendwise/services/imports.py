"""Save a parsed statement for one user: categorise, skip duplicates, record the batch."""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..models import ImportBatch, ImportDuplicate, Transaction, User
from .categorizer import categorize, credit_category
from .importer import parse_statement
from .merchants import merchant_key


class DuplicateRace(Exception):
    """Two imports of the same payments ran at the same moment."""


def import_statement(
    session: Session, user: User, data: bytes, filename: str, ai=None, max_rows: int = 20_000
) -> tuple[ImportBatch, list[dict], dict[str, int]]:
    parsed = parse_statement(data, filename, max_rows=max_rows)  # ValueError -> 400 in the API
    debits = [(r.merchant, r.description) for r in parsed.rows if r.kind == "debit"]
    cats = categorize(session, user.id, debits, ai)

    keys = [r.dedup_key for r in parsed.rows]
    existing: set[str] = set()
    for i in range(0, len(keys), 500):  # IN (...) in chunks
        existing |= set(
            session.exec(
                select(Transaction.dedup_key).where(
                    Transaction.user_id == user.id, Transaction.dedup_key.in_(keys[i : i + 500])
                )
            ).all()
        )

    batch = ImportBatch(user_id=user.id, filename=filename[:200] or "statement")
    session.add(batch)
    session.flush()  # gives batch.id
    by_source: dict[str, int] = {}
    for r in parsed.rows:
        if r.dedup_key in existing:
            batch.duplicates += 1
            # remembered, so undoing the earlier import hands this payment over instead of deleting it
            session.add(ImportDuplicate(user_id=user.id, import_id=batch.id, dedup_key=r.dedup_key))
            continue
        existing.add(r.dedup_key)
        if r.kind == "debit":
            category, source = cats[merchant_key(r.merchant)]
        else:
            category, source = credit_category(r.description), "rule"
        by_source[source] = by_source.get(source, 0) + 1
        session.add(
            Transaction(
                user_id=user.id,
                date=r.date,
                merchant=r.merchant,
                description=r.description,
                amount_paise=r.amount_paise,
                kind=r.kind,
                category=category,
                category_source=source,
                import_id=batch.id,
                dedup_key=r.dedup_key,
            )
        )
        batch.added += 1
    batch.skipped = len(parsed.skipped)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise DuplicateRace() from None
    session.refresh(batch)
    return batch, parsed.skipped, by_source


def manual_key() -> str:
    """Payments added by hand are never duplicates of each other."""
    return "manual:" + uuid.uuid4().hex
