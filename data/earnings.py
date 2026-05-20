"""Earnings calendar + results via Finnhub (free tier)."""
from __future__ import annotations

from typing import List

import requests

SOURCE_FINNHUB = "finnhub"


def fetch_finnhub_earnings(symbol: str, api_key: str,
                           timeout: float = 10.0) -> List[dict]:
    """Earnings results for a symbol from Finnhub /stock/earnings."""
    if not api_key:
        raise ValueError("Finnhub API key required")
    url = "https://finnhub.io/api/v1/stock/earnings"
    resp = requests.get(url, params={"symbol": symbol, "token": api_key},
                        timeout=timeout)
    resp.raise_for_status()
    return parse_finnhub_earnings(symbol, resp.json())


def parse_finnhub_earnings(symbol: str, payload) -> List[dict]:
    rows: List[dict] = []
    if not payload:
        return rows
    for item in payload:
        rows.append({
            "symbol": symbol,
            "event_date": item.get("period") or item.get("date") or "",
            "period": item.get("period"),
            "eps_estimate": _f(item.get("estimate")),
            "eps_actual": _f(item.get("actual")),
            "revenue_estimate": _f(item.get("revenueEstimate")),
            "revenue_actual": _f(item.get("revenueActual")),
            "source": SOURCE_FINNHUB,
        })
    return rows


def fetch_finnhub_calendar(start: str, end: str, api_key: str,
                           timeout: float = 10.0) -> List[dict]:
    """Upcoming earnings calendar between two YYYY-MM-DD dates."""
    if not api_key:
        raise ValueError("Finnhub API key required")
    url = "https://finnhub.io/api/v1/calendar/earnings"
    resp = requests.get(url, params={"from": start, "to": end, "token": api_key},
                        timeout=timeout)
    resp.raise_for_status()
    payload = resp.json() or {}
    out: List[dict] = []
    for item in payload.get("earningsCalendar", []) or []:
        sym = item.get("symbol")
        if not sym:
            continue
        out.append({
            "symbol": sym,
            "event_date": item.get("date", ""),
            "period": item.get("quarter"),
            "eps_estimate": _f(item.get("epsEstimate")),
            "eps_actual": _f(item.get("epsActual")),
            "revenue_estimate": _f(item.get("revenueEstimate")),
            "revenue_actual": _f(item.get("revenueActual")),
            "source": SOURCE_FINNHUB,
        })
    return out


def _f(v):
    try:
        if v is None:
            return None
        v = float(v)
        return v if v == v else None
    except (TypeError, ValueError):
        return None
