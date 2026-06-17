"""Synthetic price feed — runs immediately with no API key.

Generates a deterministic-ish intraday random walk with realistic OHLCV
candles and a moving "current" price, so the engine, scoring, charts, and
paper account all have something to work on out of the box.
"""
from __future__ import annotations

import random
import time
from typing import List

import pandas as pd

from .base import (
    HEALTH_LIVE,
    Candle,
    FeedHealth,
    PriceFeed,
    Quote,
)

_CANDLE_SECONDS = 60  # 1-minute candles
_HISTORY = 120        # candles of history to keep


class MockFeed(PriceFeed):
    name = "mock"
    supports_live = True

    def __init__(self, symbol: str, seed: int | None = None) -> None:
        super().__init__(symbol)
        self._rng = random.Random(seed if seed is not None else hash(self.symbol) & 0xFFFF)
        self._base_price = self._rng.uniform(20, 300)
        self._avg_volume = self._rng.uniform(80_000, 400_000)
        # Momentum "run" state — creates realistic intraday trends/moves so
        # genuine breakouts and VWAP reclaims form (not pure noise).
        self._run_remaining = 0
        self._run_bias = 0.0
        self._candles: List[Candle] = []
        self._last_quote: Quote | None = None
        self._build_history()

    def _momentum(self) -> float:
        """Return a directional bias for this bar, occasionally starting a run."""
        if self._run_remaining > 0:
            self._run_remaining -= 1
            return self._run_bias
        if self._rng.random() < 0.10:  # ~10% chance to start a trend leg
            self._run_remaining = self._rng.randint(4, 10)
            self._run_bias = self._rng.choice([-1, 1]) * self._rng.uniform(0.0010, 0.0028)
            return self._run_bias
        return 0.0

    # -- generation -------------------------------------------------------
    def _build_history(self) -> None:
        now = time.time()
        start = now - _HISTORY * _CANDLE_SECONDS
        price = self._base_price
        # Give the walk a gentle intraday drift so VWAP/trend logic is meaningful.
        drift = self._rng.uniform(-0.0004, 0.0004)
        for i in range(_HISTORY):
            ts = start + i * _CANDLE_SECONDS
            o = price
            shock = self._rng.gauss(0, 0.0030) + drift + self._momentum()
            c = max(0.5, o * (1 + shock))
            hi = max(o, c) * (1 + abs(self._rng.gauss(0, 0.0015)))
            lo = min(o, c) * (1 - abs(self._rng.gauss(0, 0.0015)))
            # Volume spikes occasionally to create RVOL signal.
            vmult = 1.0
            if self._rng.random() < 0.12:
                vmult = self._rng.uniform(1.8, 4.0)
            vol = max(1.0, self._avg_volume * vmult * self._rng.uniform(0.6, 1.4))
            self._candles.append(Candle(ts, o, hi, lo, c, vol))
            price = c
        self._base_price = price

    def _advance(self) -> None:
        """Append/extend the most recent candle as wall-clock time passes."""
        now = time.time()
        last = self._candles[-1]
        if now - last.ts >= _CANDLE_SECONDS:
            o = last.close
            shock = self._rng.gauss(0, 0.0030) + self._momentum()
            c = max(0.5, o * (1 + shock))
            hi = max(o, c) * (1 + abs(self._rng.gauss(0, 0.0015)))
            lo = min(o, c) * (1 - abs(self._rng.gauss(0, 0.0015)))
            vmult = self._rng.uniform(1.8, 4.0) if self._rng.random() < 0.12 else 1.0
            vol = max(1.0, self._avg_volume * vmult * self._rng.uniform(0.6, 1.4))
            self._candles.append(Candle(now, o, hi, lo, c, vol))
            self._candles = self._candles[-_HISTORY:]
        else:
            # Wiggle the live candle's close/high/low intra-bar.
            shock = self._rng.gauss(0, 0.0012)
            c = max(0.5, last.close * (1 + shock))
            last.close = c
            last.high = max(last.high, c)
            last.low = min(last.low, c)
            last.volume += max(1.0, self._avg_volume / 60.0 * self._rng.uniform(0.5, 1.5))

    # -- PriceFeed API ----------------------------------------------------
    def get_quote(self) -> Quote:
        self._advance()
        price = self._candles[-1].close
        prev_close = self._candles[-2].close if len(self._candles) > 1 else price
        change = price - prev_close
        change_pct = (100.0 * change / prev_close) if prev_close else 0.0
        # Tight, realistic synthetic spread.
        half = max(0.005, price * 0.0004) / 2.0
        q = Quote(
            symbol=self.symbol,
            price=round(price, 4),
            bid=round(price - half, 4),
            ask=round(price + half, 4),
            ts=time.time(),
            prev_close=round(prev_close, 4),
            change=round(change, 4),
            change_pct=round(change_pct, 3),
            source="mock",
        )
        self._last_quote = q
        return q

    def get_candles(self, limit: int = 120) -> pd.DataFrame:
        self._advance()
        df = self.candles_to_df(self._candles)
        return df.tail(limit).reset_index(drop=True)

    def health(self) -> FeedHealth:
        age = self._last_quote.age_seconds() if self._last_quote else 0.0
        return FeedHealth(
            status=HEALTH_LIVE,
            detail="Synthetic mock feed (no external data).",
            last_quote_age=age,
            is_live=True,
        )

    @property
    def avg_volume(self) -> float:
        return self._avg_volume
