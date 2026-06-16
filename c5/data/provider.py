"""Multi-symbol market-data provider.

Wraps the per-symbol feed classes so the scanner and dashboard can request
quotes/candles/health for any number of watchlist tickers from one object.

A provider has a single mode (mock | manual | finnhub | webull) and lazily
creates one feed per symbol. Finnhub without a key transparently falls back to
mock and flags `fell_back=True` so the UI can warn the user.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pandas as pd

from ..config import MODE_FINNHUB, MODE_MANUAL, MODE_MOCK, MODE_WEBULL
from .base import FeedHealth, PriceFeed, Quote
from .finnhub_feed import FinnhubFeed
from .manual_feed import ManualFeed
from .mock_feed import MockFeed
from .webull_feed import WebullFeed


class MarketDataProvider:
    def __init__(self, mode: str, api_key: Optional[str] = None) -> None:
        self.mode = mode
        self.api_key = (api_key or "").strip()
        self._feeds: Dict[str, PriceFeed] = {}
        # True when Finnhub was requested but no key was available.
        self.fell_back = mode == MODE_FINNHUB and not self.api_key

    @property
    def effective_mode(self) -> str:
        """The mode actually used for data (mock if Finnhub fell back)."""
        if self.mode == MODE_FINNHUB and self.fell_back:
            return MODE_MOCK
        return self.mode

    def _make(self, symbol: str) -> PriceFeed:
        sym = symbol.upper()
        if self.mode == MODE_FINNHUB and self.api_key:
            return FinnhubFeed(self.api_key, sym)
        if self.mode == MODE_MANUAL:
            return ManualFeed(sym)
        if self.mode == MODE_WEBULL:
            return WebullFeed(sym)
        return MockFeed(sym)

    def feed_for(self, symbol: str) -> PriceFeed:
        sym = symbol.upper()
        if sym not in self._feeds:
            self._feeds[sym] = self._make(sym)
        return self._feeds[sym]

    def get_quote(self, symbol: str) -> Quote:
        return self.feed_for(symbol).get_quote()

    def get_candles(self, symbol: str, limit: int = 120) -> pd.DataFrame:
        return self.feed_for(symbol).get_candles(limit)

    def health(self, symbol: str) -> FeedHealth:
        return self.feed_for(symbol).health()

    def manual_feed(self, symbol: str) -> Optional[ManualFeed]:
        feed = self.feed_for(symbol)
        return feed if isinstance(feed, ManualFeed) else None

    def all_quotes(self, symbols: List[str]) -> Dict[str, Quote]:
        return {s.upper(): self.get_quote(s) for s in symbols}
