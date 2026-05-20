"""Price/volume data via yfinance (free) with optional Alpaca path.

All fetchers return a list of dicts with keys:
  symbol, ts (ISO-8601 UTC), open, high, low, close, volume, source
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List, Mapping

SOURCE_YF = "yfinance"
SOURCE_ALPACA = "alpaca"


def _iso(ts) -> str:
    if hasattr(ts, "to_pydatetime"):
        ts = ts.to_pydatetime()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)
    return ts.isoformat(timespec="seconds")


def fetch_yfinance_history(symbol: str, period: str = "5d",
                           interval: str = "1m") -> List[dict]:
    """Pull historical price bars from yfinance.

    `period` examples: 1d, 5d, 1mo, 3mo, 1y. `interval`: 1m, 5m, 1h, 1d.
    Raises ImportError if yfinance is not installed.
    """
    import yfinance as yf  # local import: keeps tests light

    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval, auto_adjust=False)
    return _df_to_rows(symbol, df, SOURCE_YF)


def _df_to_rows(symbol: str, df, source: str) -> List[dict]:
    rows: List[dict] = []
    if df is None or len(df) == 0:
        return rows
    for idx, row in df.iterrows():
        rows.append({
            "symbol": symbol,
            "ts": _iso(idx),
            "open": _f(row.get("Open")),
            "high": _f(row.get("High")),
            "low": _f(row.get("Low")),
            "close": _f(row.get("Close")),
            "volume": _i(row.get("Volume")),
            "source": source,
        })
    return rows


def _f(v):
    try:
        if v is None:
            return None
        v = float(v)
        return v if v == v else None  # NaN check
    except (TypeError, ValueError):
        return None


def _i(v):
    try:
        if v is None:
            return None
        v = int(v)
        return v
    except (TypeError, ValueError):
        return None


def normalize_bars(symbol: str, bars: Iterable[Mapping], source: str) -> List[dict]:
    """Normalize a generic iterable of bar dicts into the canonical row shape."""
    out = []
    for b in bars:
        ts = b.get("ts") or b.get("t") or b.get("timestamp")
        if isinstance(ts, (int, float)):
            ts = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")
        out.append({
            "symbol": symbol,
            "ts": str(ts),
            "open": _f(b.get("open") or b.get("o")),
            "high": _f(b.get("high") or b.get("h")),
            "low": _f(b.get("low") or b.get("l")),
            "close": _f(b.get("close") or b.get("c")),
            "volume": _i(b.get("volume") or b.get("v")),
            "source": source,
        })
    return out
