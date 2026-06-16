"""Lightweight technical indicators used by setup detection and scoring."""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def vwap(df: pd.DataFrame) -> pd.Series:
    """Session VWAP from typical price * volume."""
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    cum_vol = df["volume"].cumsum().replace(0, np.nan)
    return (tp * df["volume"]).cumsum() / cum_vol


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=1).mean()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.rolling(window=window, min_periods=window).mean()
    avg_loss = loss.rolling(window=window, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50.0)


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window=window, min_periods=1).mean()


def rvol(df: pd.DataFrame, lookback: int = 20) -> Optional[float]:
    """Relative volume: latest candle volume vs trailing average."""
    if len(df) < 2:
        return None
    recent = df["volume"].iloc[-1]
    base = df["volume"].iloc[-(lookback + 1):-1]
    if base.empty:
        base = df["volume"].iloc[:-1]
    avg = base.mean()
    if not avg or avg <= 0:
        return None
    return float(recent / avg)


def atr_pct(df: pd.DataFrame, window: int = 14) -> Optional[float]:
    if df.empty:
        return None
    a = atr(df, window).iloc[-1]
    price = df["close"].iloc[-1]
    if not price or price <= 0:
        return None
    return float(100.0 * a / price)
