"""Money as whole paise.

Floats can't hold most decimal fractions exactly (0.1 + 0.2 != 0.3), so adding thousands of float
rupees slowly drifts. Integers never do: ₹349.50 is stored as 34950.
"""

from decimal import Decimal, InvalidOperation

MAX_PAISE = 10**12  # ₹1,000 crore: anything bigger in a student's statement is a parsing error


def to_paise(value: str | int | float | Decimal) -> int:
    """'₹1,299.50' -> 129950, '-250' -> 25000 (the sign is the caller's business). ValueError if not money."""
    text = str(value).strip().replace("₹", "").replace("INR", "").replace(",", "")
    text = text.removeprefix("Rs.").removeprefix("Rs").strip()
    if text.endswith(("Dr", "DR", "Cr", "CR")):
        text = text[:-2].strip()
    if text.startswith("(") and text.endswith(")"):  # accounting style: (100) means -100
        text = text[1:-1].strip()
    shown = str(value)[:30]
    try:
        amount = abs(Decimal(text))
        if not amount.is_finite() or amount > MAX_PAISE:  # check size BEFORE quantize: 1e30 overflows it
            raise ValueError(f"not a payment amount: {shown!r}")
        paise = int((amount * 100).quantize(Decimal(1)))
    except (InvalidOperation, OverflowError):
        raise ValueError(f"not an amount: {shown!r}") from None
    if paise == 0:  # after rounding: 0.004 must not become a ₹0.00 payment
        raise ValueError(f"not a payment amount: {shown!r}")
    if paise > MAX_PAISE:
        raise ValueError(f"amount too large: {shown!r}")
    return paise


def is_negative(value: str | int | float | Decimal) -> bool:
    text = str(value).strip()
    return text.startswith("-") or (text.startswith("(") and text.endswith(")"))


def rupees(paise: int) -> float:
    """34950 -> 349.5, for JSON."""
    return paise / 100
