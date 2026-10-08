"""'Today' for an Indian user. The server's clock is usually UTC (always in Docker), and before
5:30 AM IST that is still yesterday, so dates come from here, never from dt.date.today()."""

import datetime as dt
from zoneinfo import ZoneInfo

from ..config import get_settings


def today() -> dt.date:
    return dt.datetime.now(ZoneInfo(get_settings().timezone)).date()


EARLIEST = dt.date(2000, 1, 1)


def check_date(d: dt.date) -> dt.date:
    """Payments from 2000 up to a month ahead. A typo like 9999-12-31 would otherwise become
    "the latest month" and break every default view."""
    if not EARLIEST <= d <= today() + dt.timedelta(days=31):
        raise ValueError(f"date {d.isoformat()} is out of range")
    return d
