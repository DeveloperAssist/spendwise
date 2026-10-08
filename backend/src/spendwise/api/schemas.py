"""What goes in and out of the API. Pydantic validates every request before our code sees it.

Inside, money is paise (int); in the API it's rupees (a number with up to 2 decimals).
"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from ..models import CATEGORIES, SPEND_CATEGORIES
from ..services.clock import check_date

CategoryName = Literal[tuple(CATEGORIES)]  # type: ignore[valid-type]
SpendCategory = Literal[tuple(SPEND_CATEGORIES)]  # type: ignore[valid-type]
MAX_RUPEES = 10_000_000


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("name can't be empty")
        return v


class UserOut(BaseModel):
    id: int
    email: str
    name: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105  (the OAuth2 token type, not a secret)
    user: UserOut


class DeleteAccountIn(BaseModel):
    password: str


class TransactionOut(BaseModel):
    id: int
    date: dt.date
    merchant: str
    description: str
    amount: float
    kind: str
    category: str
    category_source: str
    note: str | None
    import_id: int | None


class TransactionIn(BaseModel):
    date: dt.date
    merchant: str = Field(min_length=1, max_length=120)
    amount: float = Field(gt=0, le=MAX_RUPEES)
    kind: Literal["debit", "credit"] = "debit"
    category: CategoryName | None = None
    note: str | None = Field(default=None, max_length=200)

    @field_validator("amount")
    @classmethod
    def two_decimals(cls, v: float) -> float:
        if round(v, 2) != v:
            raise ValueError("amount can have at most 2 decimal places")
        return v

    @field_validator("date")
    @classmethod
    def sane_date(cls, v: dt.date) -> dt.date:
        return check_date(v)

    @field_validator("merchant")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("merchant can't be empty")
        return v


class TransactionPatch(BaseModel):
    category: CategoryName | None = None
    note: str | None = Field(default=None, max_length=200)
    apply_to_merchant: bool = True  # a category fix moves every payment to that merchant


class Page(BaseModel):
    items: list[TransactionOut]
    total: int
    page: int
    page_size: int


class BudgetIn(BaseModel):
    limit: float = Field(gt=0, le=MAX_RUPEES)

    @field_validator("limit")
    @classmethod
    def whole_paise(cls, v: float) -> float:
        if round(v, 2) != v or round(v, 2) == 0:  # 0.001 rounded to ₹0.00 and crashed the save
            raise ValueError("limit must be at least 0.01, with up to 2 decimal places")
        return v


class BudgetOut(BaseModel):
    category: str
    limit: float


class ImportOut(BaseModel):
    id: int
    filename: str
    added: int
    duplicates: int
    skipped: int
    created_at: dt.datetime
    skipped_rows: list[dict] = []
    categorized_by: dict[str, int] = {}


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)


class ChatOut(BaseModel):
    answer: str
    steps: list[dict]
