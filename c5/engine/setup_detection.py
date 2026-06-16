"""Setup detection — identify a candidate intraday setup from candles.

C5 v1 detects a small set of common long-side intraday setups and produces a
single best Setup with an entry, stop, target, direction, and a normalized
trigger-quality score (0..1) that feeds the Confluence Score's
"setup trigger quality" component.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from . import indicators as ind


@dataclass
class Setup:
    detected: bool
    kind: str                       # e.g. "vwap_reclaim", "breakout", "pullback", "none"
    direction: str                  # "long" | "short" | "none"
    trigger_quality: float          # 0..1
    entry: Optional[float] = None
    stop: Optional[float] = None
    target: Optional[float] = None
    notes: List[str] = field(default_factory=list)

    @property
    def risk(self) -> Optional[float]:
        if self.entry is None or self.stop is None:
            return None
        return abs(self.entry - self.stop)

    @property
    def reward(self) -> Optional[float]:
        if self.entry is None or self.target is None:
            return None
        return abs(self.target - self.entry)

    @property
    def rr(self) -> Optional[float]:
        r = self.risk
        if r is None or r <= 0 or self.reward is None:
            return None
        return self.reward / r


def _no_setup(reason: str) -> Setup:
    return Setup(
        detected=False,
        kind="none",
        direction="none",
        trigger_quality=0.0,
        notes=[reason],
    )


def detect_setup(df: pd.DataFrame) -> Setup:
    """Return the best candidate setup from the candle DataFrame."""
    if df is None or len(df) < 20:
        return _no_setup("Not enough candles to evaluate a setup.")

    close = df["close"]
    price = float(close.iloc[-1])
    vwap_series = ind.vwap(df)
    vwap_now = float(vwap_series.iloc[-1])
    sma9 = ind.sma(close, 9)
    rsi_now = float(ind.rsi(close).iloc[-1])
    atrp = ind.atr_pct(df) or 0.0
    recent_high = float(df["high"].iloc[-20:-1].max())
    recent_low = float(df["low"].iloc[-20:-1].min())

    notes: List[str] = []
    above_vwap = price > vwap_now
    rising = bool(sma9.iloc[-1] > sma9.iloc[-5]) if len(sma9) >= 5 else False

    # --- Setup 1: breakout over recent high while above VWAP ---
    if price >= recent_high and above_vwap:
        entry = price
        stop = min(vwap_now, recent_high * 0.997)
        risk = max(entry - stop, price * 0.002)
        target = entry + 2.0 * risk
        quality = _clamp(0.55 + (0.25 if rising else 0) + (0.10 if rsi_now < 72 else -0.10))
        notes.append("Breakout above recent intraday high, price holding above VWAP.")
        return Setup(True, "breakout", "long", quality, entry, entry - risk, target, notes)

    # --- Setup 2: VWAP reclaim (price crossing back above VWAP) ---
    crossed_up = (
        len(close) >= 3
        and close.iloc[-2] <= vwap_series.iloc[-2]
        and price > vwap_now
    )
    if crossed_up:
        entry = price
        stop = min(recent_low, vwap_now * 0.997)
        risk = max(entry - stop, price * 0.002)
        target = entry + 1.8 * risk
        quality = _clamp(0.5 + (0.2 if rising else 0) + (0.1 if 45 <= rsi_now <= 68 else -0.05))
        notes.append("Price reclaimed VWAP from below — momentum shift attempt.")
        return Setup(True, "vwap_reclaim", "long", quality, entry, stop, target, notes)

    # --- Setup 3: pullback to VWAP in an uptrend ---
    near_vwap = abs(price - vwap_now) / max(price, 1e-9) < 0.0035
    if above_vwap and rising and near_vwap:
        entry = price
        stop = vwap_now * 0.996
        risk = max(entry - stop, price * 0.002)
        target = entry + 2.0 * risk
        quality = _clamp(0.5 + (0.15 if rsi_now > 50 else 0) + (0.1 if atrp < 4 else -0.1))
        notes.append("Pullback to rising VWAP in an uptrend.")
        return Setup(True, "pullback", "long", quality, entry, stop, target, notes)

    notes.append("No qualifying long setup at the current bar.")
    return _no_setup(" ".join(notes))


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))
