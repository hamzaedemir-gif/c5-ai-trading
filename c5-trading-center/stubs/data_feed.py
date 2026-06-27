"""Mock market-data feed stub.

Returns simulated prices and a small set of mock candidate tickers so the
trading loop is demonstrable. A simple random walk per ticker keeps prices
moving between ticks.
"""
from __future__ import annotations

import random
from typing import Dict, List

# Internal mock price state (random walk). Draft-only; not real data.
_PRICES: Dict[str, float] = {}

# Mock candidate universe. The real feed must PRE-FILTER candidates because
# Webull's OHLCV endpoint is ~1 call/sec — scanning every US ticker live is
# not feasible.
_CANDIDATES = [
    "AAPL", "NVDA", "TSLA", "AMD", "META", "MSFT", "AMZN", "GOOGL",
    "NFLX", "SPY", "QQQ", "COIN", "PLTR", "SHOP", "UBER", "BABA",
]


def _walk(ticker: str) -> float:
    if ticker not in _PRICES:
        _PRICES[ticker] = round(random.uniform(20, 400), 2)
    _PRICES[ticker] = max(1.0, round(_PRICES[ticker] * (1 + random.gauss(0, 0.004)), 2))
    return _PRICES[ticker]


def candidate_tickers() -> List[str]:
    """Mock candidate list.

    # TODO: Webull OpenAPI Top Active / Gainers / Losers funnel to pre-filter
    #        a tradable candidate set (the real feed cannot scan every ticker).
    """
    return list(_CANDIDATES)


def live_prices(tickers: List[str]) -> Dict[str, float]:
    """Mock live prices.

    # TODO: Webull OpenAPI live/last prices for the candidate set.
    """
    return {t: _walk(t) for t in tickers}


def yesterday_prices(tickers: List[str]) -> Dict[str, float]:
    """Mock 'yesterday' prices for Paper Trade Trial mode.

    # TODO: replay the previous session's recorded prices for paper trials.
    """
    return {t: _walk(t) for t in tickers}
