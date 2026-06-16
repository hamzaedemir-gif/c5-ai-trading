"""Tests for market-session helpers and Finnhub delay detection."""
import time
from datetime import datetime

from c5.market_hours import (
    SESSION_AFTER,
    SESSION_CLOSED,
    SESSION_PRE,
    SESSION_REGULAR,
    is_after_hours,
    market_session,
)


def _et(y, mo, d, h, mi):
    try:
        from zoneinfo import ZoneInfo
        return datetime(y, mo, d, h, mi, tzinfo=ZoneInfo("America/New_York"))
    except Exception:
        return datetime(y, mo, d, h, mi)


def test_regular_session_weekday():
    # 2026-06-16 is a Tuesday.
    assert market_session(_et(2026, 6, 16, 11, 0)) == SESSION_REGULAR
    assert is_after_hours(_et(2026, 6, 16, 11, 0)) is False


def test_pre_and_after_market():
    assert market_session(_et(2026, 6, 16, 8, 0)) == SESSION_PRE
    assert market_session(_et(2026, 6, 16, 18, 0)) == SESSION_AFTER
    assert is_after_hours(_et(2026, 6, 16, 18, 0)) is True


def test_weekend_closed():
    # 2026-06-20 is a Saturday.
    assert market_session(_et(2026, 6, 20, 12, 0)) == SESSION_CLOSED
    assert is_after_hours(_et(2026, 6, 20, 12, 0)) is True


def test_finnhub_delay_flag():
    from c5.data.finnhub_feed import FinnhubFeed

    feed = FinnhubFeed("KEY", "AAPL")
    # No trade timestamp -> not delayed.
    assert feed.is_delayed is False
    # A very old last-trade timestamp -> delayed only matters during regular
    # session; the property itself reflects the lag computation safely.
    feed._last_trade_ts = time.time() - 600
    assert feed._trade_lag() >= 600
