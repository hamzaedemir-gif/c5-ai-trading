"""US equity market-hours helpers (America/New_York).

Used to label after-hours paper tests. Note: this is a prototype helper — it
covers weekends and regular/extended session times but does NOT account for
market holidays.
"""
from __future__ import annotations

from datetime import datetime, time
from typing import Optional

try:
    from zoneinfo import ZoneInfo

    _ET: Optional[ZoneInfo] = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover - tzdata missing
    _ET = None

SESSION_REGULAR = "regular"
SESSION_PRE = "pre"
SESSION_AFTER = "after"
SESSION_CLOSED = "closed"

_REGULAR_OPEN = time(9, 30)
_REGULAR_CLOSE = time(16, 0)
_PRE_OPEN = time(4, 0)
_AFTER_CLOSE = time(20, 0)

AFTER_HOURS_WARNING = (
    "After-hours paper test: spreads may be wider and liquidity may be lower."
)


def now_et() -> datetime:
    if _ET is not None:
        return datetime.now(_ET)
    return datetime.now()  # best-effort fallback to local time


def market_session(dt: Optional[datetime] = None) -> str:
    dt = dt or now_et()
    # Saturday=5, Sunday=6
    if dt.weekday() >= 5:
        return SESSION_CLOSED
    t = dt.time()
    if _REGULAR_OPEN <= t < _REGULAR_CLOSE:
        return SESSION_REGULAR
    if _PRE_OPEN <= t < _REGULAR_OPEN:
        return SESSION_PRE
    if _REGULAR_CLOSE <= t < _AFTER_CLOSE:
        return SESSION_AFTER
    return SESSION_CLOSED


def is_regular_open(dt: Optional[datetime] = None) -> bool:
    return market_session(dt) == SESSION_REGULAR


def is_after_hours(dt: Optional[datetime] = None) -> bool:
    """True whenever the regular session is not open (pre, after, or closed)."""
    return market_session(dt) != SESSION_REGULAR
