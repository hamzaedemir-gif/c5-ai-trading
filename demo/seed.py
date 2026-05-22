"""Deterministic sample data so the dashboard has something to display
the instant it boots, without any network calls or API keys."""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Iterable

from data.db import Database

DEMO_SYMBOLS = ["AAPL", "MSFT", "TSLA", "NVDA", "AMD", "SPY", "QQQ", "GOOGL"]

_HEADLINES = [
    "{sym} ships record quarter, beats analyst estimates",
    "Analysts upgrade {sym} on strong forward guidance",
    "{sym} CEO outlines aggressive growth plans for next year",
    "Unusual options activity detected in {sym}",
    "{sym} climbs on cloud revenue strength",
    "Short interest in {sym} hits multi-month high",
    "{sym} faces regulatory probe over data practices",
    "{sym} announces $5B buyback program",
    "Earnings preview: what to expect from {sym} tomorrow",
    "{sym} unveils next-generation product line",
]


def _gen_intraday_bars(symbol: str, base_price: float, n_bars: int = 180,
                       seed: int = 0) -> list[dict]:
    rng = random.Random(seed)
    rows: list[dict] = []
    price = base_price
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    for i in range(n_bars, 0, -1):
        ts = now - timedelta(minutes=i)
        drift = math.sin(i / 25.0) * 0.0008
        shock = rng.uniform(-0.004, 0.004)
        open_p = price
        close_p = max(0.01, price * (1 + drift + shock))
        high_p = max(open_p, close_p) * (1 + abs(rng.uniform(0, 0.0015)))
        low_p = min(open_p, close_p) * (1 - abs(rng.uniform(0, 0.0015)))
        # occasional volume spike
        spike = 6.0 if (i in (1, 12, 40) and symbol in ("NVDA", "TSLA")) else 1.0
        volume = int(rng.uniform(5_000, 25_000) * spike)
        rows.append({
            "symbol": symbol,
            "ts": ts.isoformat(timespec="seconds"),
            "open": round(open_p, 4),
            "high": round(high_p, 4),
            "low": round(low_p, 4),
            "close": round(close_p, 4),
            "volume": volume,
            "source": "demo",
        })
        price = close_p
    return rows


def _gen_news(symbol: str, seed: int = 0) -> list[dict]:
    rng = random.Random(seed + 31)
    out: list[dict] = []
    now = datetime.now(timezone.utc)
    chosen = rng.sample(_HEADLINES, k=min(4, len(_HEADLINES)))
    for i, tmpl in enumerate(chosen):
        ts = now - timedelta(hours=rng.randint(1, 48))
        out.append({
            "symbol": symbol,
            "headline": tmpl.format(sym=symbol),
            "url": f"https://example.com/demo/{symbol.lower()}/{i}",
            "summary": "Demo news item generated locally for dashboard preview.",
            "published_at": ts.isoformat(timespec="seconds"),
            "source": "demo",
        })
    return out


def _gen_earnings(symbol: str, seed: int = 0) -> list[dict]:
    rng = random.Random(seed + 99)
    surprises = [(1.20, 1.35), (0.85, 0.78), (1.55, 1.62), (2.10, 1.95)]
    out: list[dict] = []
    today = datetime.now(timezone.utc).date()
    for i, (est, act) in enumerate(surprises):
        d = today - timedelta(days=90 * (i + 1))
        out.append({
            "symbol": symbol,
            "event_date": d.isoformat(),
            "period": f"Q{((i + 3) % 4) + 1}",
            "eps_estimate": est + rng.uniform(-0.05, 0.05),
            "eps_actual": act + rng.uniform(-0.05, 0.05),
            "revenue_estimate": 50 + rng.uniform(-5, 5),
            "revenue_actual": 52 + rng.uniform(-5, 5),
            "source": "demo",
        })
    return out


def _gen_sentiment(symbol: str, seed: int = 0) -> list[dict]:
    rng = random.Random(seed + 7)
    rows: list[dict] = []
    now = datetime.now(timezone.utc)
    base = rng.uniform(-0.2, 0.2)
    for i in range(30, 0, -1):
        ts = now - timedelta(hours=i * 3)
        # Inject a clear shift in the last few samples for a couple symbols.
        boost = 0.0
        if symbol in ("NVDA", "GOOGL") and i < 4:
            boost = 0.6
        rows.append({
            "symbol": symbol,
            "ts": ts.isoformat(timespec="seconds"),
            "score": round(max(-1.0, min(1.0, base + rng.uniform(-0.2, 0.2) + boost)), 4),
            "volume": rng.randint(20, 200),
            "source": "demo",
        })
    return rows


def seed_database(db: Database, symbols: Iterable[str] = DEMO_SYMBOLS,
                  *, seed: int = 1) -> dict:
    """Populate `db` with fully self-consistent demo data."""
    base_prices = {
        "AAPL": 187.0, "MSFT": 420.0, "TSLA": 235.0, "NVDA": 920.0,
        "AMD": 165.0, "SPY": 525.0, "QQQ": 460.0, "GOOGL": 170.0,
    }
    totals = {"prices": 0, "news": 0, "earnings": 0, "sentiment": 0}
    for i, sym in enumerate(symbols):
        bp = base_prices.get(sym, 100.0)
        bars = _gen_intraday_bars(sym, bp, seed=seed + i)
        totals["prices"] += db.insert_prices(bars)
        totals["news"] += db.insert_news(_gen_news(sym, seed=seed + i))
        totals["earnings"] += db.insert_earnings(_gen_earnings(sym, seed=seed + i))
        totals["sentiment"] += db.insert_sentiment(_gen_sentiment(sym, seed=seed + i))
    return totals
