"""Turn a bank's narration into a merchant name.

A real statement doesn't say "Swiggy". It says something like
    UPI/DR/612345678901/SWIGGY/YESB/swiggy@ybl/Payment
    UPI-ZOMATO LTD-zomato@hdfcbank-HDFC0000001-612345678902-UPI
We split it into pieces and throw away everything that isn't a name: reference numbers, UPI IDs,
IFSC and bank codes, and words like UPI / DR / PAYMENT.
"""

import re

NOISE = {
    "upi",
    "dr",
    "cr",
    "p2m",
    "p2a",
    "pay",
    "payment",
    "payments",
    "paid",
    "to",
    "from",
    "via",
    "ref",
    "txn",
    "imps",
    "neft",
    "rtgs",
    "pos",
    "ecom",
    "debit",
    "credit",
    "transfer",
    "trf",
    "mob",
    "mb",
    "collect",
    "request",
    "sent",
    "received",
    "upi intent",
    "upi collect",
    "na",
    "null",
    "the",
    "ach",
    "nach",
    "ecs",
    "bil",
    "bpay",
    "billpay",
}
BANK_CODES = {
    "YESB",
    "HDFC",
    "ICIC",
    "SBIN",
    "UTIB",
    "KKBK",
    "PUNB",
    "BARB",
    "AIRP",
    "PYTM",
    "IDFB",
    "INDB",
    "FDRL",
    "CNRB",
    "UBIN",
    "IOBA",
    "BKID",
    "AXIS",
    "ICICI",
    "SBI",
    "PAYTM",
    "YBL",
}
SUFFIXES = re.compile(
    r"\b(pvt|private|ltd|limited|llp|inc|india|technologies|tech|services|online|"
    r"retail|commerce|payments?|co)\b\.?",
    re.I,
)
PREFIXES = re.compile(r"^(paid to|payment to|sent to|money sent to|received from|upi to|to)\s+", re.I)
IFSC = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$", re.I)
SPLIT = re.compile(r"[/|\\_*:#~]+|\s{2,}")
# a hyphen separates fields only in machine narrations ("UPI-ZOMATO-zomato@hdfc-61234567"),
# never in names like Coca-Cola or Wi-Fi
STRUCTURED = re.compile(r"@|\d{6,}")
JUNK_WORD = re.compile(r"^(\d[\d.,]*|[A-Za-z]{0,3}\d{6,}|\d{2,}[Xx*]+\d{2,})$")  # numbers, refs, masked cards


def _clean_piece(piece: str) -> str:
    words = [w for w in piece.split() if len(w) > 1 and w.lower() not in NOISE and not JUNK_WORD.match(w)]
    name = SUFFIXES.sub("", " ".join(words))
    return re.sub(r"\s+", " ", name).strip(" .,-&")


def clean_merchant(raw: str) -> str:
    text = PREFIXES.sub("", (raw or "").strip())
    pieces = SPLIT.split(text)
    if STRUCTURED.search(text):
        pieces = [p for piece in pieces for p in re.split(r"\s*-\s*", piece)]
    for piece in pieces:
        piece = piece.strip(" .,-")
        if (
            len(piece) < 2
            or "@" in piece
            or IFSC.match(piece)
            or piece.upper() in BANK_CODES
            or piece.lower() in NOISE
            or not re.search(r"[A-Za-z]{2}", piece)
        ):
            continue
        name = _clean_piece(piece)
        if len(name) < 2 or name.upper() in BANK_CODES:
            continue
        if name.isupper() or name.islower():
            name = name.title().replace("'S", "'s")
        return name[:80]
    if "@" in text:
        return "UPI transfer"  # e.g. to a phone-number UPI ID: never show the number
    return (text or "Unknown")[:80]


# names that stand for many different payees: never learned as one merchant, never "fix all"
GENERIC_KEYS = {"upitransfer", "unknown"}


def merchant_key(name: str) -> str:
    """'Chai Point' and 'CHAI-POINT' are the same merchant: 'chaipoint'."""
    return re.sub(r"[^a-z0-9]", "", name.lower())[:120] or "unknown"
