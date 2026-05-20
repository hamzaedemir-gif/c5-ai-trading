"""Top gainers / losers / high-volume movers, computed from stored bars.

This module reads the existing `prices` table -- no new ingestion path.
"""
from __future__ import annotations

from typing import Iterable, List

from .db import Database


def compute_movers(db: Database, symbols: Iterable[str],
                   lookback_bars: int = 60) -> dict:
    """Return {"gainers": [...], "losers": [...], "high_volume": [...]}.

    For each symbol we use the most recent bar as the latest price and
    the bar `lookback_bars` ago as the baseline. Volume "score" is the
    latest bar's volume divided by the average of the lookback window.
    """
    rows = []
    for sym in symbols:
        bars = db.fetch_prices(sym, limit=lookback_bars + 1)
        if not bars or len(bars) < 2:
            continue
        bars = list(reversed(bars))           # oldest -> newest
        latest = bars[-1]
        baseline = bars[0]
        latest_close = latest["close"] or 0.0
        base_close = baseline["close"] or 0.0
        if base_close == 0:
            continue
        change_pct = (latest_close - base_close) / base_close * 100.0

        volumes = [(b["volume"] or 0) for b in bars[:-1]]
        avg_vol = (sum(volumes) / len(volumes)) if volumes else 0.0
        latest_vol = latest["volume"] or 0
        vol_ratio = (latest_vol / avg_vol) if avg_vol > 0 else 0.0

        rows.append({
            "symbol": sym,
            "price": latest_close,
            "change_pct": round(change_pct, 4),
            "volume": latest_vol,
            "avg_volume": round(avg_vol, 2),
            "volume_ratio": round(vol_ratio, 3),
            "ts": latest["ts"],
        })

    gainers = sorted(rows, key=lambda r: r["change_pct"], reverse=True)
    losers = sorted(rows, key=lambda r: r["change_pct"])
    high_volume = sorted(rows, key=lambda r: r["volume_ratio"], reverse=True)

    return {
        "gainers": gainers[:10],
        "losers": [r for r in losers if r["change_pct"] < 0][:10],
        "high_volume": [r for r in high_volume if r["volume_ratio"] > 0][:10],
    }


def latest_quote(db: Database, symbol: str) -> dict | None:
    rows = db.fetch_prices(symbol, limit=1)
    if not rows:
        return None
    r = rows[0]
    return {
        "symbol": symbol,
        "price": r["close"],
        "volume": r["volume"],
        "ts": r["ts"],
        "source": r["source"],
    }


def list_recent_news(db: Database, limit: int = 50,
                     symbol: str | None = None) -> List[dict]:
    return [dict(r) for r in db.fetch_news(symbol=symbol, limit=limit)]


def search_symbols(db: Database, query: str, limit: int = 15) -> List[str]:
    """Search distinct symbols stored in prices table by prefix / substring."""
    q = (query or "").strip().upper()
    if not q:
        return []
    rows = db.distinct_symbols_like(f"%{q}%", limit)
    syms = [r["symbol"] for r in rows]
    syms.sort(key=lambda s: (0 if s.startswith(q) else 1, s))
    return syms
