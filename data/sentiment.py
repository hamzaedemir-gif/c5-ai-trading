"""Social-sentiment ingestion.

Primary source: StockTwits public streams (no key required for low volume).
Sentiment is computed from explicit message sentiment tags when present;
otherwise falls back to a simple keyword-based classifier.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List, Mapping

import requests

SOURCE_STOCKTWITS = "stocktwits"

_BULLISH = {"bull", "bullish", "buy", "long", "moon", "rocket", "calls", "breakout", "pump"}
_BEARISH = {"bear", "bearish", "sell", "short", "puts", "dump", "crash", "drop"}


def keyword_score(text: str) -> float:
    """Cheap fallback classifier: returns score in [-1, 1]."""
    if not text:
        return 0.0
    tokens = {t.strip(".,!?:;()[]\"'").lower() for t in text.split()}
    bull = len(tokens & _BULLISH)
    bear = len(tokens & _BEARISH)
    if bull == 0 and bear == 0:
        return 0.0
    return (bull - bear) / (bull + bear)


def fetch_stocktwits(symbol: str, base_url: str = "https://api.stocktwits.com/api/2",
                     timeout: float = 10.0) -> List[dict]:
    """Return one aggregated sentiment row per fetch.

    Aggregates the most recent ~30 messages into a mean score and total
    message count. Returns an empty list on rate-limit / errors so the
    pipeline does not die on a flaky social feed.
    """
    url = f"{base_url}/streams/symbol/{symbol}.json"
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code != 200:
            return []
        payload = resp.json() or {}
    except (requests.RequestException, ValueError):
        return []
    return aggregate_stocktwits_messages(symbol, payload.get("messages", []))


def aggregate_stocktwits_messages(symbol: str, messages: Iterable[Mapping]) -> List[dict]:
    scores: List[float] = []
    count = 0
    for msg in messages or []:
        count += 1
        sentiment = (msg.get("entities") or {}).get("sentiment") or {}
        basic = (sentiment.get("basic") or "").lower()
        if basic == "bullish":
            scores.append(1.0)
        elif basic == "bearish":
            scores.append(-1.0)
        else:
            scores.append(keyword_score(msg.get("body", "")))
    if count == 0:
        return []
    mean = sum(scores) / len(scores)
    return [{
        "symbol": symbol,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "score": round(mean, 4),
        "volume": count,
        "source": SOURCE_STOCKTWITS,
    }]
