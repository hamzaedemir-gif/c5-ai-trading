"""Webull feed — PLACEHOLDER ONLY.

Webull OpenAPI access is pending approval. This class intentionally does NOT
connect to Webull, does NOT use any credentials, and does NOT execute or route
any orders. It exists so the mode is selectable in the UI and clearly surfaced
as "pending approval". It will be implemented after OpenAPI approval clears.
"""
from __future__ import annotations

import pandas as pd

from .base import (
    HEALTH_PLACEHOLDER,
    FeedHealth,
    PriceFeed,
    Quote,
)

PENDING_MESSAGE = (
    "Webull OpenAPI access is pending approval. This is a placeholder only — "
    "no live data, no credentials, and no order execution."
)


class WebullFeed(PriceFeed):
    name = "webull"
    supports_live = False
    is_placeholder = True

    def get_quote(self) -> Quote:
        # No data available — return an empty quote rather than raising so the
        # UI can render the placeholder banner gracefully.
        return Quote(symbol=self.symbol, price=0.0)

    def get_candles(self, limit: int = 120) -> pd.DataFrame:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume", "time"])

    def health(self) -> FeedHealth:
        return FeedHealth(
            status=HEALTH_PLACEHOLDER,
            detail=PENDING_MESSAGE,
            last_quote_age=None,
            is_live=False,
        )
