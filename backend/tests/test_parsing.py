"""Money, merchant names and statement files: the messy-input layer."""

import datetime as dt
import io

import pytest
from conftest import SAMPLE
from openpyxl import Workbook

from spendwise.services.importer import parse_statement
from spendwise.services.merchants import clean_merchant, merchant_key
from spendwise.services.money import is_negative, to_paise


# ---------------------------------------------------------------- money
@pytest.mark.parametrize(
    "text,paise",
    [
        ("349", 34900),
        ("₹1,299.50", 129950),
        ("Rs. 250", 25000),
        ("250.00 Dr", 25000),
        ("-75.5", 7550),
        ("(100)", 10000),
        (0.1, 10),
        ("1,00,000", 10000000),
    ],
)
def test_to_paise(text, paise):
    assert to_paise(text) == paise


@pytest.mark.parametrize("bad", ["", "abc", "0", "0.00", "NaN", "inf", "9" * 20])
def test_bad_amounts(bad):
    with pytest.raises(ValueError):
        to_paise(bad)


def test_floats_cant_drift():
    assert to_paise("0.1") + to_paise("0.2") == to_paise("0.3")


def test_negative_forms():
    assert is_negative("-5") and is_negative("(5)") and not is_negative("5")


# ---------------------------------------------------------------- merchant names
@pytest.mark.parametrize(
    "raw,name",
    [
        ("UPI/DR/612345678901/SWIGGY/YESB/swiggy@ybl/Payment", "Swiggy"),
        ("UPI-ZOMATO LTD-zomato@hdfcbank-HDFC0000001-612345678902-UPI", "Zomato"),
        ("POS 4567XXXX1234 DECATHLON SPORTS INDIA", "Decathlon Sports"),
        ("ACH D- ZERODHA BROKING-1234567", "Zerodha Broking"),
        ("UPI/DR/612345678901/9876543210@ybl/YESB", "UPI transfer"),  # never show a phone number
        ("Coca-Cola", "Coca-Cola"),
        ("Wi-Fi Bill", "Wi-Fi Bill"),
        ("7-Eleven", "7-Eleven"),
        ("Paid to Rapido", "Rapido"),
        ("Chai point", "Chai point"),
        ("", "Unknown"),
    ],
)
def test_clean_merchant(raw, name):
    assert clean_merchant(raw) == name


def test_merchant_key_ignores_case_and_punctuation():
    assert merchant_key("Chai Point") == merchant_key("CHAI-POINT") == "chaipoint"


# ---------------------------------------------------------------- statement files
def test_sample_statement():
    r = parse_statement(SAMPLE.read_bytes(), "sample_statement.csv")
    assert r.skipped == []  # opening / closing balance lines are not rows
    assert len(r.rows) == 227
    assert {x.kind for x in r.rows} == {"debit", "credit"}
    assert len({x.dedup_key for x in r.rows}) == len(r.rows)


def test_header_below_title_lines_and_bad_rows():
    text = (
        "My Bank\nStatement for Sept\n\n"
        "Date,Narration,Withdrawal Amt,Deposit Amt\n"
        "29/09/2026,UPI/DR/1/SWIGGY/YESB/s@ybl,293.50,\n"
        "not a date,Uber,100,\n"
        "30/09/2026,,50,\n"
        "30/09/2026,Salary,,25000\n"
        "30/09/2026,Nothing here,,\n"
    )
    r = parse_statement(text.encode(), "s.csv")
    assert [(x.merchant, x.amount_paise, x.kind) for x in r.rows] == [
        ("Swiggy", 29350, "debit"),
        ("Salary", 2500000, "credit"),
    ]
    assert [s["line"] for s in r.skipped] == [6, 7, 9]  # real line numbers in the file


def test_type_column_and_the_deposit_trap():
    text = "Date,Description,Amount,Type\n01-09-2026,Rent,6500,DR\n02-09-2026,Pocket money,8000,Deposit\n"
    rows = parse_statement(text.encode(), "s.csv").rows
    assert [r.kind for r in rows] == ["debit", "credit"]  # "Deposit" starts with D but is money IN


def test_signed_amounts_and_payments_only_files():
    signed = "Date,Details,Amount\n01-09-2026,Swiggy,-250\n02-09-2026,Refund,99\n"
    assert [r.kind for r in parse_statement(signed.encode(), "s.csv").rows] == ["debit", "credit"]
    unsigned = "Date,Paid to,Amount\n01-09-2026,Swiggy,250\n02-09-2026,Uber,99\n"
    assert [r.kind for r in parse_statement(unsigned.encode(), "s.csv").rows] == ["debit", "debit"]


def test_excel_statement():
    wb = Workbook()
    ws = wb.active
    ws.append(["Bank of Practice"])
    ws.append(["Txn Date", "Particulars", "Debit", "Credit"])
    ws.append([dt.datetime(2026, 9, 1), "UPI/DR/1/ZOMATO/HDFC/z@hdfc", 349.5, None])
    ws.append([dt.datetime(2026, 9, 2), "NEFT/STIPEND", None, 15000])
    buf = io.BytesIO()
    wb.save(buf)
    rows = parse_statement(buf.getvalue(), "statement.xlsx").rows
    assert [(r.date, r.merchant, r.amount_paise, r.kind) for r in rows] == [
        (dt.date(2026, 9, 1), "Zomato", 34950, "debit"),
        (dt.date(2026, 9, 2), "Stipend", 1500000, "credit"),
    ]


def test_windows_1252_csv():
    text = "Date,Description,Amount\n01-09-2026,Café Coffee Day,120\n".encode("cp1252")
    assert parse_statement(text, "s.csv").rows[0].merchant == "Café Coffee Day"


@pytest.mark.parametrize(
    "data,name,msg",
    [
        (b"Date,Description\n01-09-2026,x\n", "s.csv", "header"),
        (b"Date,Amount\n01-09-2026,5\n", "s.csv", "description"),
        (b"%PDF-1.7", "s.pdf", "unsupported"),
        (b"not excel", "s.xlsx", "Excel"),
    ],
)
def test_unreadable_files(data, name, msg):
    with pytest.raises(ValueError, match=msg):
        parse_statement(data, name)


def test_too_many_rows():
    text = "Date,Description,Amount\n" + "01-09-2026,x,1\n" * 11
    with pytest.raises(ValueError, match="too many rows"):
        parse_statement(text.encode(), "s.csv", max_rows=10)


def test_dedup_keys_match_across_files_and_keep_identical_payments():
    one = "Date,Description,Amount\n01-09-2026,Chai,20\n01-09-2026,Chai,20\n"
    two = one + "02-09-2026,Chai,20\n"
    a = [r.dedup_key for r in parse_statement(one.encode(), "a.csv").rows]
    b = [r.dedup_key for r in parse_statement(two.encode(), "b.csv").rows]
    assert len(set(a)) == 2  # two genuine chais on one day: both kept
    assert b[:2] == a  # and the same keys in an overlapping file
