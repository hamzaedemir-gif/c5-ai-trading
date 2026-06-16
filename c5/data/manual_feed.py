"""Manual price feed — the user types prices into the UI.

Each manually entered price appends a 1-minute candle. With no entries yet,
it seeds a flat history around the first price so the engine has data to work
with. Because manual prices are user-driven (not streamed), this feed reports
its health based on how long ago the last price was entered.
"""
from __future__ import annotations

import time
from typing import List, Optional

import pandas as pd

from .base import (
    HEALTH_DISCONNECTED,
    HEALTH_LIVE,
    HEALTH_STALE,
    Candle,
    FeedHealth,
    PriceFeed,
    Quote,
)

_CANDLE_SECONDS = 60
_HISTORY = 120
_STALE_AFTER = 90  # seconds since last manual entry before flagged stale


class ManualFeed(PriceFeed):
    name = "manual"
    supports_live = False

    def __init__(self, symbol: str, default_volume: float = 100_000.0) -> None:
        super().__init__(symbol)
        self._candles: List[Candle] = []
        self._last_quote: Optional[Quote] = None
        self._default_volume = default_volume
        self._last_entry_ts: Optional[float] = None

    def submit_price(self, price: float, volume: Optional[float] = None) -> None:
        """Record a user-entered price as a new candle / quote."""
        price = float(price)
        vol = float(volume) if volume is not None else self._default_volume
        now = time.time()

        if not self._candles:
            # Seed a short flat history so indicators are computable.
            start = now - _HISTORY * _CANDLE_SECONDS
            for i in range(_HISTORY):
                ts = start + i * _CANDLE_SECONDS
                self._candles.append(Candle(ts, price, price, price, price, vol))
        else:
            last = self._candles[-1]
            o = last.close
            self._candles.append(
                Candle(now, o, max(o, price), min(o, price), price, vol)
            )
            self._candles = self._candles[-_HISTORY:]

        self._last_entry_ts = now
        self._last_quote = Quote(symbol=self.symbol, price=round(price, 4), ts=now)

    def get_quote(self) -> Quote:
        if self._last_quote is None:
            # No price entered yet.
            return Quote(symbol=self.symbol, price=0.0, ts=time.time())
        return self._last_quote

    def get_candles(self, limit: int = 120) -> pd.DataFrame:
        df = self.candles_to_df(self._candles)
        if df.empty:
            return df
        return df.tail(limit).reset_index(drop=True)

    def health(self) -> FeedHealth:
        if self._last_entry_ts is None:
            return FeedHealth(
                status=HEALTH_DISCONNECTED,
                detail="Awaiting first manual price entry.",
                last_quote_age=None,
                is_live=False,
            )
        age = time.time() - self._last_entry_ts
        if age <= _STALE_AFTER:
            return FeedHealth(
                status=HEALTH_LIVE,
                detail="Manual entry recent.",
                last_quote_age=age,
                is_live=True,
            )
        return FeedHealth(
            status=HEALTH_STALE,
            detail=f"No manual price for {int(age)}s.",
            last_quote_age=age,
            is_live=False,
        )

    @property
    def has_data(self) -> bool:
        return self._last_quote is not None
