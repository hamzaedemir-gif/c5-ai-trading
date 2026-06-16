"""Tests for the mock feed."""
from c5.data.base import HEALTH_LIVE
from c5.data.mock_feed import MockFeed


def test_mock_feed_produces_quote_and_candles():
    feed = MockFeed("TEST", seed=1)
    q = feed.get_quote()
    assert q.price > 0
    assert q.bid is not None and q.ask is not None and q.ask >= q.bid
    df = feed.get_candles(120)
    assert not df.empty
    assert set(["open", "high", "low", "close", "volume", "time"]).issubset(df.columns)
    assert feed.health().status == HEALTH_LIVE
    assert feed.health().is_live is True


def test_mock_feed_high_low_bounds():
    feed = MockFeed("XYZ", seed=2)
    df = feed.get_candles(120)
    assert (df["high"] >= df["low"]).all()
    assert (df["high"] >= df["close"]).all()
    assert (df["low"] <= df["close"]).all()
