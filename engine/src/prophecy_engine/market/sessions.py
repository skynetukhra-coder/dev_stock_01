"""Indian market trading sessions, market hours, and IST calendar helpers."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Optional

try:
    from zoneinfo import ZoneInfo

    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = timezone(timedelta(hours=5, minutes=30), name="IST")


class MarketSession(str, Enum):
    CLOSED = "CLOSED"
    PRE_OPEN = "PRE_OPEN"
    REGULAR = "REGULAR"
    POST_CLOSE = "POST_CLOSE"


# NSE / NFO Standard Market Hours in IST
PRE_OPEN_START = time(9, 0, 0)
PRE_OPEN_END = time(9, 15, 0)
REGULAR_START = time(9, 15, 0)
REGULAR_END = time(15, 30, 0)
POST_CLOSE_END = time(16, 0, 0)


def to_ist(dt: datetime) -> datetime:
    """Normalize any datetime (naive or aware) to Asia/Kolkata timezone."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    return dt.astimezone(IST)


def is_trading_day(d: date) -> bool:
    """Check if the given date is a weekday (Monday-Friday)."""
    # 0 = Monday, ..., 4 = Friday, 5 = Saturday, 6 = Sunday
    return d.weekday() < 5


def get_market_session(dt: Optional[datetime] = None) -> MarketSession:
    """Return the market session phase for the specified datetime (or now in IST)."""
    target = to_ist(dt or datetime.now(IST))
    if not is_trading_day(target.date()):
        return MarketSession.CLOSED

    current_time = target.time()
    if PRE_OPEN_START <= current_time < PRE_OPEN_END:
        return MarketSession.PRE_OPEN
    elif REGULAR_START <= current_time <= REGULAR_END:
        return MarketSession.REGULAR
    elif REGULAR_END < current_time <= POST_CLOSE_END:
        return MarketSession.POST_CLOSE
    else:
        return MarketSession.CLOSED


def is_market_open(dt: Optional[datetime] = None) -> bool:
    """Check if market is currently in the regular trading session."""
    return get_market_session(dt) == MarketSession.REGULAR


def get_current_session_date(dt: Optional[datetime] = None) -> date:
    """Return the current trading date in IST."""
    return to_ist(dt or datetime.now(IST)).date()
