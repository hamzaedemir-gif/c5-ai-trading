"""News headlines via Finnhub (company-news endpoint)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import requests

SOURCE_FINNHUB = "finnhub"


def fetch_finnhub_news(symbol: str, start: str, end: str, api_key: str,
                       timeout: float = 10.0) -> List[dict]:
    if not api_key:
        raise ValueError("Finnhub API key required")
    url = "https://finnhub.io/api/v1/company-news"
    resp = requests.get(
        url,
        params={"symbol": symbol, "from": start, "to": end, "token": api_key},
        timeout=timeout,
    )
    resp.raise_for_status()
    return parse_finnhub_news(symbol, resp.json() or [])


def parse_finnhub_news(symbol: str, payload) -> List[dict]:
    rows: List[dict] = []
    for item in payload or []:
        ts = item.get("datetime")
        if isinstance(ts, (int, float)):
            published = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")
        else:
            published = str(ts) if ts else ""
        headline = item.get("headline") or item.get("title")
        if not headline:
            continue
        rows.append({
            "symbol": symbol,
            "headline": headline,
            "url": item.get("url"),
            "summary": item.get("summary"),
            "published_at": published,
            "source": SOURCE_FINNHUB,
        })
    return rows
