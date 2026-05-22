"""Orchestrates data ingestion across price, earnings, news, sentiment."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from core.retry import retry_with_backoff

from . import earnings as earnings_mod
from . import news as news_mod
from . import prices as prices_mod
from . import sentiment as sentiment_mod
from .db import Database

log = logging.getLogger(__name__)


@dataclass
class IngestResult:
    prices: int = 0
    earnings: int = 0
    news: int = 0
    sentiment: int = 0


class Ingestor:
    """High-level facade: pull → write → return counts.

    Each method is independently callable so tests / cron jobs can pick what
    they need without dragging in the full pipeline.
    """

    def __init__(self, db: Database, *, finnhub_key: str = "",
                 stocktwits_url: str = "https://api.stocktwits.com/api/2"):
        self.db = db
        self.finnhub_key = finnhub_key
        self.stocktwits_url = stocktwits_url

    @retry_with_backoff(attempts=3, base_delay=1.0,
                        fallback=lambda self, symbol, **kw: 0,
                        name="ingest_prices")
    def ingest_prices(self, symbol: str, period: str = "5d",
                      interval: str = "1m") -> int:
        rows = prices_mod.fetch_yfinance_history(symbol, period=period, interval=interval)
        n = self.db.insert_prices(rows)
        log.info("prices: %s rows=%d (new=%d)", symbol, len(rows), n)
        return n

    @retry_with_backoff(attempts=3, base_delay=1.0,
                        fallback=lambda self, symbol: 0,
                        name="ingest_earnings")
    def ingest_earnings(self, symbol: str) -> int:
        if not self.finnhub_key:
            log.warning("Skipping earnings for %s: no Finnhub key", symbol)
            return 0
        rows = earnings_mod.fetch_finnhub_earnings(symbol, self.finnhub_key)
        n = self.db.insert_earnings(rows)
        log.info("earnings: %s rows=%d (new=%d)", symbol, len(rows), n)
        return n

    @retry_with_backoff(attempts=3, base_delay=1.0,
                        fallback=lambda self, symbol, lookback_days=3: 0,
                        name="ingest_news")
    def ingest_news(self, symbol: str, lookback_days: int = 3) -> int:
        if not self.finnhub_key:
            log.warning("Skipping news for %s: no Finnhub key", symbol)
            return 0
        end = date.today()
        start = end - timedelta(days=lookback_days)
        rows = news_mod.fetch_finnhub_news(
            symbol, start.isoformat(), end.isoformat(), self.finnhub_key,
        )
        n = self.db.insert_news(rows)
        log.info("news: %s rows=%d (new=%d)", symbol, len(rows), n)
        return n

    @retry_with_backoff(attempts=3, base_delay=1.0,
                        fallback=lambda self, symbol: 0,
                        name="ingest_sentiment")
    def ingest_sentiment(self, symbol: str) -> int:
        rows = sentiment_mod.fetch_stocktwits(symbol, base_url=self.stocktwits_url)
        n = self.db.insert_sentiment(rows)
        log.info("sentiment: %s rows=%d (new=%d)", symbol, len(rows), n)
        return n

    def ingest_all(self, symbols: Iterable[str]) -> dict[str, IngestResult]:
        out: dict[str, IngestResult] = {}
        for sym in symbols:
            r = IngestResult()
            try: r.prices = self.ingest_prices(sym)
            except Exception as e: log.error("prices %s: %s", sym, e)
            try: r.earnings = self.ingest_earnings(sym)
            except Exception as e: log.error("earnings %s: %s", sym, e)
            try: r.news = self.ingest_news(sym)
            except Exception as e: log.error("news %s: %s", sym, e)
            try: r.sentiment = self.ingest_sentiment(sym)
            except Exception as e: log.error("sentiment %s: %s", sym, e)
            out[sym] = r
        return out
