"""Give every payment a category, cheapest answer first:

  1. learned - this user's own fixes and earlier answers for the merchant (free, instant)
  2. rule    - a keyword we know ("swiggy" -> food) (free, instant, exact)
  3. ai      - ONE request to the AI for all the merchants still unknown
  4. other   - no AI key, no answer, or an answer that isn't one of our categories

Money coming IN is "income" (or "transfers" for refunds), never sent to the AI.
Whatever we learn is saved per user, so the AI is asked about a merchant once.
"""

import logging
import re

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..models import SPEND_CATEGORIES, MerchantCategory
from .merchants import GENERIC_KEYS, merchant_key

log = logging.getLogger("spendwise.categorizer")

RULES: dict[str, list[str]] = {
    "food": [
        "swiggy",
        "zomato",
        "chai",
        "cafe",
        "coffee",
        "restaurant",
        "domino",
        "pizza",
        "mcdonald",
        "kfc",
        "burger",
        "canteen",
        "mess",
        "bakery",
        "dhaba",
        "biryani",
        "haldiram",
        "starbucks",
        "eatsure",
    ],
    "groceries": [
        "blinkit",
        "zepto",
        "bigbasket",
        "instamart",
        "dmart",
        "jiomart",
        "grocer",
        "kirana",
        "more retail",
        "reliance fresh",
    ],
    "travel": [
        "uber",
        "ola",
        "rapido",
        "metro",
        "irctc",
        "redbus",
        "petrol",
        "fuel",
        "fastag",
        "railway",
        "indigo",
        "air india",
        "makemytrip",
        "yulu",
        "bmtc",
        "best bus",
    ],
    "shopping": [
        "amazon",
        "flipkart",
        "myntra",
        "meesho",
        "ajio",
        "nykaa",
        "croma",
        "decathlon",
        "lenskart",
        "reliance digital",
        "zara",
        "h&m",
        "tata cliq",
    ],
    "bills": [
        "airtel",
        "jio",
        "vodafone",
        "vi prepaid",
        "electricity",
        "broadband",
        "recharge",
        "water bill",
        "gas",
        "bescom",
        "tata power",
        "act fibernet",
        "wi-fi",
        "wifi",
    ],
    "rent": ["rent", "nobroker", "pg", "hostel", "nestaway"],
    "entertainment": [
        "spotify",
        "netflix",
        "bookmyshow",
        "hotstar",
        "prime video",
        "pvr",
        "inox",
        "steam",
        "youtube premium",
        "jiocinema",
        "playstation",
    ],
    "health": [
        "pharmacy",
        "apollo",
        "medplus",
        "1mg",
        "pharmeasy",
        "hospital",
        "clinic",
        "gym",
        "cult.fit",
        "cultfit",
        "practo",
    ],
    "education": [
        "udemy",
        "coursera",
        "college",
        "fees",
        "university",
        "stationery",
        "unacademy",
        "byju",
        "leetcode",
        "book",
    ],
    "transfers": ["upi transfer", "zerodha", "groww", "upstox", "mutual fund", "sip"],
}


def _pattern(word: str) -> re.Pattern:
    """Whole words only, or "ola" would match Coca-Cola and "book" would match Facebook. Short keywords
    must match a whole word; longer ones may continue ("grocer" matches "grocery")."""
    w = re.escape(word.strip())
    return re.compile(rf"(?<![a-z0-9]){w}(?![a-z0-9])" if len(word.strip()) <= 4 else rf"(?<![a-z0-9]){w}")


PATTERNS = {cat: [_pattern(w) for w in words] for cat, words in RULES.items()}


def by_rules(text: str) -> str | None:
    t = text.lower()
    for category, patterns in PATTERNS.items():
        if any(p.search(t) for p in patterns):
            return category
    return None


def credit_category(text: str) -> str:
    return "transfers" if "refund" in text.lower() or "reversal" in text.lower() else "income"


def learned(session: Session, user_id: int, keys: list[str]) -> dict[str, MerchantCategory]:
    if not keys:
        return {}
    rows = session.exec(
        select(MerchantCategory).where(MerchantCategory.user_id == user_id, MerchantCategory.merchant_key.in_(keys))
    ).all()
    return {r.merchant_key: r for r in rows}


def remember(session: Session, user_id: int, key: str, category: str, source: str) -> None:
    """Upsert what a merchant is. Your own fix ("you") is never overwritten by a rule or the AI."""
    if key in GENERIC_KEYS:
        return
    query = select(MerchantCategory).where(MerchantCategory.user_id == user_id, MerchantCategory.merchant_key == key)
    row = session.exec(query).first()
    if row is None:
        try:
            with session.begin_nested():  # a savepoint: if a parallel request inserted it first...
                session.add(MerchantCategory(user_id=user_id, merchant_key=key, category=category, source=source))
            return
        except IntegrityError:
            row = session.exec(query).first()  # ...update the row it inserted instead of failing
    if row is not None and (row.source != "you" or source == "you"):
        row.category, row.source = category, source
        session.add(row)


def categorize(session: Session, user_id: int, merchants: list[tuple[str, str]], ai=None) -> dict[str, tuple[str, str]]:
    """merchants: (merchant, description) of money going OUT. -> {merchant_key: (category, source)}."""
    by_key: dict[str, tuple[str, str]] = {}
    for name, desc in merchants:
        by_key.setdefault(merchant_key(name), (name, desc))
    result: dict[str, tuple[str, str]] = {}

    for key, row in learned(session, user_id, list(by_key)).items():
        result[key] = (row.category, "learned" if row.source != "you" else "you")

    for key, (name, desc) in by_key.items():
        if key not in result and (cat := by_rules(f"{name} {desc}")):
            result[key] = (cat, "rule")
            remember(session, user_id, key, cat, "rule")

    unknown = {key: by_key[key][0] for key in by_key if key not in result}
    if unknown and ai is not None:
        try:
            answers = ai.categorize(list(unknown.values()), SPEND_CATEGORIES)
        except Exception as e:  # the AI being down must never break an import
            log.warning("AI categorization failed: %s", e)
            answers = {}
        for key, name in unknown.items():
            cat = str(answers.get(name, "")).strip().lower()
            if cat in SPEND_CATEGORIES and cat != "other":
                result[key] = (cat, "ai")
                remember(session, user_id, key, cat, "ai")

    for key in by_key:
        result.setdefault(key, ("other", "other"))
    return result
