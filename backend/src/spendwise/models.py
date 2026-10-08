"""Database tables (SQLModel = SQLAlchemy tables that are also Pydantic models).

Money is always stored as whole paise (int). Every row that belongs to a person carries user_id,
and every query filters on it: that's what keeps one user's data invisible to another.
"""

import datetime as dt
import secrets

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, SQLModel

CATEGORIES = [
    "food",
    "groceries",
    "travel",
    "shopping",
    "bills",
    "rent",
    "entertainment",
    "health",
    "education",
    "transfers",
    "income",
    "other",
]
SPEND_CATEGORIES = [c for c in CATEGORIES if c != "income"]


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def new_token_salt() -> str:
    return secrets.token_hex(8)


class User(SQLModel, table=True):
    __tablename__ = "users"
    # SQLite reuses a deleted row's id unless told not to: a deleted user's id must never come back
    __table_args__ = {"sqlite_autoincrement": True}
    id: int | None = Field(default=None, primary_key=True)
    # inside every login token: a token only fits the account it was issued for, even if an id is reused
    token_salt: str = Field(default_factory=new_token_salt, max_length=32)
    email: str = Field(max_length=254, unique=True, index=True)
    name: str = Field(max_length=80)
    password_hash: str = Field(max_length=255)
    created_at: dt.datetime = Field(default_factory=utcnow)


class ImportBatch(SQLModel, table=True):
    """One uploaded statement: so an import can be listed, and undone."""

    __tablename__ = "imports"
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    filename: str = Field(max_length=200)
    added: int = 0
    duplicates: int = 0
    skipped: int = 0
    created_at: dt.datetime = Field(default_factory=utcnow)


class ImportDuplicate(SQLModel, table=True):
    """A payment an import contained but didn't add, because an earlier import already had it.
    Undoing that earlier import hands such payments over instead of deleting them."""

    __tablename__ = "import_duplicates"
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    import_id: int = Field(foreign_key="imports.id", index=True, ondelete="CASCADE")
    dedup_key: str = Field(max_length=64, index=True)


class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"
    # nearly every query asks for one user's rows in a date range: one index serves them all
    __table_args__ = (
        UniqueConstraint("user_id", "dedup_key", name="uq_transaction_dedup"),
        Index("ix_transactions_user_date", "user_id", "date"),
    )
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    date: dt.date = Field(index=True)
    merchant: str = Field(max_length=120)  # cleaned name: "Swiggy"
    description: str = Field(default="", max_length=300)  # the statement's raw text
    amount_paise: int = Field(gt=0)
    kind: str = Field(default="debit", max_length=6)  # debit (money out) | credit (money in)
    category: str = Field(max_length=20)
    category_source: str = Field(max_length=10)  # rule | ai | you | learned | other
    note: str | None = Field(default=None, max_length=200)
    import_id: int | None = Field(default=None, foreign_key="imports.id", index=True, ondelete="CASCADE")
    dedup_key: str = Field(max_length=64)  # same payment in two statements -> same key
    created_at: dt.datetime = Field(default_factory=utcnow)


class Budget(SQLModel, table=True):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("user_id", "category", name="uq_budget_category"),)
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    category: str = Field(max_length=20)
    limit_paise: int = Field(gt=0)


class MerchantCategory(SQLModel, table=True):
    """What a merchant is, for one user: learned from rules, the AI, or their own fixes."""

    __tablename__ = "merchant_categories"
    __table_args__ = (UniqueConstraint("user_id", "merchant_key", name="uq_merchant_category"),)
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    merchant_key: str = Field(max_length=120)  # "swiggy": lower-case letters and digits
    category: str = Field(max_length=20)
    source: str = Field(max_length=10)
