"""Price-feed interface and shared data types."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

# Feed-health states.
HEALTH_LIVE = "live"
HEALTH_STALE = "stale"
HEALTH_DISCONNECTED = "disconnected"
HEALTH_PLACEHOLDER = "placeholder"


@dataclass
class Quote:
    """A single point-in-time price observation."""

    symbol: str
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    ts: float = field(default_factory=time.time)  # epoch seconds

    @property
    def spread(self) -> Optional[float]:
        if self.bid is None or self.ask is None or self.bid <= 0:
            return None
        return self.ask - self.bid

    @property
    def spread_pct(self) -> Optional[float]:
        s = self.spread
        if s is None or self.price <= 0:
            return None
        return 100.0 * s / self.price

    def age_seconds(self) -> float:
        return max(0.0, time.time() - self.ts)


@dataclass
class Candle:
    ts: float
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class FeedHealth:
    """Health snapshot for the UI badge."""

    status: str = HEALTH_DISCONNECTED
    detail: str = ""
    last_quote_age: Optional[float] = None
    is_live: bool = False

    @property
    def emoji(self) -> str:
        return {
            HEALTH_LIVE: "🟢",
            HEALTH_STALE: "🟡",
            HEALTH_DISCONNECTED: "🔴",
            HEALTH_PLACEHOLDER: "⚪",
        }.get(self.status, "⚪")

    @property
    def label(self) -> str:
        return f"{self.emoji} {self.status.upper()}"


class PriceFeed(ABC):
    """Common interface every data source implements."""

    name: str = "feed"
    supports_live: bool = True

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol.upper()

    @abstractmethod
    def get_quote(self) -> Quote:
        """Return the latest quote for the active symbol."""

    @abstractmethod
    def get_candles(self, limit: int = 120) -> pd.DataFrame:
        """Return recent OHLCV candles as a DataFrame.

        Columns: ts, open, high, low, close, volume (one row per candle).
        """

    @abstractmethod
    def health(self) -> FeedHealth:
        """Return the current feed-health snapshot."""

    def set_symbol(self, symbol: str) -> None:
        self.symbol = symbol.upper()

    @staticmethod
    def candles_to_df(candles: List[Candle]) -> pd.DataFrame:
        if not candles:
            return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
        rows = [
            {
                "ts": c.ts,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in candles
        ]
        df = pd.DataFrame(rows)
        df["time"] = pd.to_datetime(df["ts"], unit="s")
        return df
