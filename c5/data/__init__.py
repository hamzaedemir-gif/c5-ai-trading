"""Pluggable price-feed layer for C5 v1.

All feeds implement the same PriceFeed interface so the engine, paper account,
and UI never need to know where prices come from. This is what keeps mock,
manual, Finnhub, and (future) Webull swappable.
"""
from __future__ import annotations

from ..config import (
    MODE_FINNHUB,
    MODE_MANUAL,
    MODE_MOCK,
    MODE_WEBULL,
    Settings,
)
from .base import Candle, FeedHealth, PriceFeed, Quote
from .manual_feed import ManualFeed
from .mock_feed import MockFeed


def build_feed(settings: Settings) -> PriceFeed:
    """Construct the feed for the configured mode, with safe fallback to mock."""
    mode = settings.data_mode

    if mode == MODE_MANUAL:
        return ManualFeed(settings.default_symbol)

    if mode == MODE_FINNHUB:
        # Imported lazily so the app runs even without a key configured.
        from .finnhub_feed import FinnhubFeed

        if settings.finnhub_available:
            return FinnhubFeed(settings.finnhub_api_key, settings.default_symbol)
        # No key -> fall back to mock so the app still works.
        return MockFeed(settings.default_symbol)

    if mode == MODE_WEBULL:
        from .webull_feed import WebullFeed

        return WebullFeed(settings.default_symbol)

    # Default and explicit mock.
    return MockFeed(settings.default_symbol)


__all__ = [
    "Candle",
    "FeedHealth",
    "PriceFeed",
    "Quote",
    "MockFeed",
    "ManualFeed",
    "build_feed",
]
