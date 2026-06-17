"""US-equity ticker universe.

Provides the set of symbols the scanner rotates through:
- In Finnhub mode we fetch the full US common-stock list from Finnhub once and
  cache it for the session.
- In simulated mode (or with no key) we fall back to a curated list of liquid
  US names so the rotating scanner still demonstrates end to end.
"""
from __future__ import annotations

import re
from typing import List

import requests

_SYMBOL_URL = "https://finnhub.io/api/v1/stock/symbol"
_VALID = re.compile(r"^[A-Z]{1,5}$")  # plain common-stock tickers, no dots/units

# Curated, liquid US tickers (large-caps + major ETFs) for simulated/fallback.
BUILTIN_UNIVERSE: List[str] = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "GOOG", "META", "TSLA", "AVGO", "AMD",
    "NFLX", "ADBE", "CRM", "ORCL", "INTC", "QCOM", "CSCO", "TXN", "AMAT", "MU",
    "INTU", "NOW", "PYPL", "SHOP", "UBER", "ABNB", "SNOW", "PLTR", "COIN", "SQ",
    "JPM", "BAC", "WFC", "GS", "MS", "C", "SCHW", "AXP", "BLK", "V", "MA",
    "BRK.B", "UNH", "JNJ", "LLY", "PFE", "MRK", "ABBV", "TMO", "ABT", "DHR", "BMY",
    "AMGN", "GILD", "CVS", "MDT", "ISRG", "VRTX", "REGN",
    "XOM", "CVX", "COP", "SLB", "EOG", "OXY", "PSX", "MPC", "VLO",
    "WMT", "COST", "HD", "LOW", "TGT", "NKE", "MCD", "SBUX", "CMG", "PG", "KO",
    "PEP", "PM", "MO", "MDLZ", "CL", "KMB",
    "DIS", "CMCSA", "T", "VZ", "TMUS", "CHTR",
    "BA", "CAT", "DE", "GE", "HON", "LMT", "RTX", "UPS", "FDX", "UNP", "MMM",
    "F", "GM", "RIVN", "LCID",
    "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "XLF", "XLE", "XLK", "ARKK", "SOXL",
    "GLD", "SLV", "TLT", "HYG",
]


def _filter_symbols(raw: List[dict]) -> List[str]:
    """Keep only plain US common-stock tickers from a Finnhub symbol payload."""
    out: List[str] = []
    seen = set()
    for item in raw:
        sym = (item.get("symbol") or "").upper()
        typ = item.get("type") or ""
        if typ and typ != "Common Stock":
            continue
        if not _VALID.match(sym):
            continue
        if sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    out.sort()
    return out


def fetch_us_universe(api_key: str, timeout: float = 15.0) -> List[str]:
    """Fetch the full US common-stock universe from Finnhub.

    Returns the curated builtin list on any error so the app never breaks.
    """
    if not api_key:
        return list(BUILTIN_UNIVERSE)
    try:
        resp = requests.get(
            _SYMBOL_URL,
            params={"exchange": "US", "token": api_key},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        symbols = _filter_symbols(data if isinstance(data, list) else [])
        return symbols or list(BUILTIN_UNIVERSE)
    except Exception:
        return list(BUILTIN_UNIVERSE)


def rotate_chunk(universe: List[str], cursor: int, size: int):
    """Return (chunk, next_cursor) sweeping through the universe with wraparound."""
    n = len(universe)
    if n == 0 or size <= 0:
        return [], 0
    size = min(size, n)
    cursor = cursor % n
    end = cursor + size
    if end <= n:
        return universe[cursor:end], end % n
    return universe[cursor:] + universe[: end - n], end - n
