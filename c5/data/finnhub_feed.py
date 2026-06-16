"""Finnhub live feed — ready but dormant until a key is supplied.

Activated only when C5_DATA_MODE=finnhub and FINNHUB_API_KEY is set. Uses
Finnhub's free quote endpoint for the current price; intraday candles are
maintained from successive quotes (the free tier's candle endpoint is limited),
so the chart fills in as the app runs. Falls back gracefully and reports
disconnected/stale health on any error.
"""
from __future__ import annotations

import time
from typing import List, Optional

import pandas as pd
import requests

from ..market_hours import is_regular_open
from .base import (
    HEALTH_DISCONNECTED,
    HEALTH_LIVE,
    HEALTH_STALE,
    Candle,
    FeedHealth,
    PriceFeed,
    Quote,
)

_QUOTE_URL = "https://finnhub.io/api/v1/quote"
_CANDLE_SECONDS = 60
_HISTORY = 120
_STALE_AFTER = 30
# If the last-trade timestamp lags real time by more than this during the
# regular session, the data is treated as delayed (labelled FINNHUB DELAYED).
_DELAY_AFTER = 90


class FinnhubFeed(PriceFeed):
    name = "finnhub"
    supports_live = True

    def __init__(self, api_key: str, symbol: str, timeout: float = 6.0) -> None:
        super().__init__(symbol)
        self._api_key = api_key
        self._timeout = timeout
        self._candles: List[Candle] = []
        self._last_quote: Optional[Quote] = None
        self._last_error: Optional[str] = None
        self._last_trade_ts: Optional[float] = None  # Finnhub "t" field (epoch)

    def _fetch(self) -> Optional[dict]:
        try:
            resp = requests.get(
                _QUOTE_URL,
                params={"symbol": self.symbol, "token": self._api_key},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            # Finnhub returns c=current, but 0 means "no data / invalid symbol".
            if not data or float(data.get("c", 0)) == 0:
                self._last_error = "No data for symbol (or rate-limited)."
                return None
            self._last_error = None
            return data
        except Exception as exc:  # network, JSON, etc.
            self._last_error = str(exc)
            return None

    def _push_candle(self, price: float, prev_close: float) -> None:
        now = time.time()
        if self._candles and now - self._candles[-1].ts < _CANDLE_SECONDS:
            last = self._candles[-1]
            last.close = price
            last.high = max(last.high, price)
            last.low = min(last.low, price)
        else:
            o = self._candles[-1].close if self._candles else (prev_close or price)
            self._candles.append(Candle(now, o, max(o, price), min(o, price), price, 0.0))
            self._candles = self._candles[-_HISTORY:]

    def get_quote(self) -> Quote:
        data = self._fetch()
        if data is None:
            if self._last_quote is not None:
                return self._last_quote
            return Quote(symbol=self.symbol, price=0.0, ts=time.time())
        price = float(data["c"])
        prev_close = float(data.get("pc", price) or price)
        try:
            self._last_trade_ts = float(data.get("t", 0)) or None
        except (TypeError, ValueError):
            self._last_trade_ts = None
        self._push_candle(price, prev_close)
        change = float(data.get("d") or (price - prev_close))
        change_pct = float(data.get("dp") or (100.0 * change / prev_close if prev_close else 0.0))
        q = Quote(
            symbol=self.symbol,
            price=round(price, 4),
            ts=time.time(),
            prev_close=round(prev_close, 4),
            change=round(change, 4),
            change_pct=round(change_pct, 3),
            source="finnhub",
            last_trade_ts=self._last_trade_ts,
        )
        self._last_quote = q
        return q

    def _trade_lag(self) -> Optional[float]:
        """Seconds between now and Finnhub's last-trade timestamp."""
        if self._last_trade_ts is None:
            return None
        return max(0.0, time.time() - self._last_trade_ts)

    @property
    def is_delayed(self) -> bool:
        lag = self._trade_lag()
        if lag is None:
            return False
        # Only meaningful during the regular session — outside it, trades are
        # naturally old and the after-hours banner explains the staleness.
        return is_regular_open() and lag > _DELAY_AFTER

    def get_candles(self, limit: int = 120) -> pd.DataFrame:
        df = self.candles_to_df(self._candles)
        if df.empty:
            return df
        return df.tail(limit).reset_index(drop=True)

    def health(self) -> FeedHealth:
        if self._last_error:
            return FeedHealth(
                status=HEALTH_DISCONNECTED,
                detail=f"Finnhub error: {self._last_error}",
                last_quote_age=None,
                is_live=False,
            )
        if self._last_quote is None:
            return FeedHealth(
                status=HEALTH_DISCONNECTED,
                detail="No quote received yet.",
                is_live=False,
            )
        age = self._last_quote.age_seconds()
        delayed = self.is_delayed
        lag = self._trade_lag()
        if age <= _STALE_AFTER:
            if delayed:
                return FeedHealth(
                    status=HEALTH_LIVE,
                    detail=f"Finnhub data delayed (last trade ~{int(lag or 0)}s ago).",
                    last_quote_age=age,
                    is_live=True,
                    delayed=True,
                )
            return FeedHealth(
                status=HEALTH_LIVE,
                detail="Finnhub live quote.",
                last_quote_age=age,
                is_live=True,
                delayed=False,
            )
        return FeedHealth(
            status=HEALTH_STALE,
            detail=f"Last poll {int(age)}s ago.",
            last_quote_age=age,
            is_live=False,
            delayed=delayed,
        )
