"""Writes data/sample_statement.csv: six months of MADE-UP payments for practice.

It looks like a real bank export on purpose (title lines, UPI narrations, Debit / Credit / Balance
columns), so the importer is tested on realistic mess. Nothing here is anyone's real account.

    uv run python scripts/make_sample_statement.py
"""

import csv
import datetime as dt
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "sample_statement.csv"
rng = random.Random(2027)  # noqa: S311  (made-up sample data, not security)
START, END = dt.date(2026, 4, 1), dt.date(2026, 9, 30)

# merchant name on the statement, UPI handle, bank code, amount range (rupees), visits per month
EVERYDAY = [
    ("SWIGGY", "swiggy", "YESB", (160, 420), 6),
    ("ZOMATO LTD", "zomato", "HDFC", (180, 390), 3),
    ("CHAI POINT", "chaipoint", "ICIC", (40, 90), 6),
    ("RAPIDO", "rapido", "AXIS", (55, 140), 7),
    ("UBER INDIA", "uber", "YESB", (150, 380), 2),
    ("BLINKIT", "blinkit", "HDFC", (120, 480), 2),
    ("AMAZON", "amazon", "YESB", (299, 1599), 1),
    ("MYNTRA", "myntra", "ICIC", (499, 1299), 0.4),
    ("BOOKMYSHOW", "bookmyshow", "ICIC", (180, 420), 0.5),
    ("APOLLO PHARMACY", "apollo", "HDFC", (90, 320), 0.4),
]
# no keyword rule knows these: the AI sorts them
AI_ONLY = [
    ("CHAAYOS", "chaayos", "ICIC", (90, 220)),
    ("WOW MOMO", "wowmomo", "HDFC", (150, 280)),
    ("SNITCH", "snitch", "YESB", (899, 1599)),
    ("BEWAKOOF", "bewakoof", "AXIS", (499, 899)),
    ("PHYSICSWALLAH", "pw", "ICIC", (499, 499)),
    ("SMAAASH", "smaaash", "HDFC", (400, 700)),
    ("BARBEQUE NATION", "bbqnation", "YESB", (650, 900)),
    ("TORRENT POWER", "torrentpower", "HDFC", (640, 910)),
]


def ref() -> str:
    return str(rng.randint(10**11, 10**12 - 1))


def upi_dr(name: str, handle: str, bank: str) -> str:
    return f"UPI/DR/{ref()}/{name}/{bank}/{handle}@{rng.choice(['ybl', 'axl', 'okhdfcbank', 'paytm'])}/Payment"


rows: list[tuple[dt.date, str, int, int]] = []  # date, narration, debit, credit
month = START
while month <= END:
    days = (dt.date(month.year + month.month // 12, month.month % 12 + 1, 1) - month).days

    def day(m=month, n=days) -> dt.date:
        return m.replace(day=rng.randint(1, n))

    # money in
    rows.append((month.replace(day=1), f"IMPS/P2A/{ref()}/MONTHLY ALLOWANCE/SBIN", 0, 8000))
    if month >= dt.date(2026, 6, 1):
        rows.append((month.replace(day=5), f"NEFT/N{ref()}/INTERNSHIP STIPEND ACME LABS", 0, 15000))
    # regular bills and subscriptions
    rows.append((month.replace(day=3), f"NEFT/N{ref()}/SUNRISE PG HOSTEL RENT", 6500, 0))
    rows.append((month.replace(day=2), upi_dr("AIRTEL PREPAID", "airtelpre", "AIRP"), 299, 0))
    rows.append((month.replace(day=7), upi_dr("SPOTIFY INDIA", "spotify", "YESB"), 119, 0))
    rows.append((month.replace(day=9), "ACH D- NETFLIX ENTERTAINMENT-" + ref()[:7], 199, 0))
    # everyday spending
    for name, handle, bank, (lo, hi), per_month in EVERYDAY:
        n = int(per_month) + (rng.random() < per_month % 1)
        for _ in range(n):
            rows.append((day(), upi_dr(name, handle, bank), rng.randint(lo, hi), 0))
    for name, handle, bank, (lo, hi) in rng.sample(AI_ONLY, 3):
        rows.append((day(), upi_dr(name, handle, bank), rng.randint(lo, hi), 0))
    month = dt.date(month.year + month.month // 12, month.month % 12 + 1, 1)

# one-offs: a refund, a transfer to a friend, and one unusually big purchase
rows.append((dt.date(2026, 8, 18), f"UPI/CR/{ref()}/REFUND AMAZON/YESB", 0, 499))
rows.append((dt.date(2026, 7, 22), f"UPI/DR/{ref()}/9876543210@ybl/SBIN", 500, 0))
rows.append((dt.date(2026, 9, 26), "POS 4567XXXX1234 CROMA RETAIL", 8999, 0))
rows.sort(key=lambda r: r[0])

OUT.parent.mkdir(exist_ok=True)
balance = 12000
with OUT.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["SpendWise Sample Bank: SAMPLE DATA FOR PRACTICE, NOT A REAL ACCOUNT"])
    w.writerow(["Account statement from 01-04-2026 to 30-09-2026"])
    w.writerow([])
    w.writerow(["Txn Date", "Value Date", "Description", "Ref No.", "Debit", "Credit", "Balance"])
    w.writerow(["01-04-2026", "", "OPENING BALANCE", "", "", "", f"{balance:.2f}"])
    for d, desc, dr, cr in rows:
        balance += cr - dr
        w.writerow(
            [
                d.strftime("%d-%m-%Y"),
                d.strftime("%d-%m-%Y"),
                desc,
                ref()[:10],
                f"{dr:.2f}" if dr else "",
                f"{cr:.2f}" if cr else "",
                f"{balance:.2f}",
            ]
        )
    w.writerow(["", "", "CLOSING BALANCE", "", "", "", f"{balance:.2f}"])
print(f"{OUT}: {len(rows)} transactions, closing balance {balance}")
