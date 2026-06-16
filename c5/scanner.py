"""Live scanner — evaluate every watchlist symbol and rank opportunities.

For each ticker it pulls the latest quote + candles, runs C5 setup detection,
and computes the Confluence Score. Results are sorted highest-score first so the
dashboard and auto-trader can act on the best candidates.

Nothing here trades or guarantees anything — it only scores. The Confluence
Score is decision-support and is NOT history validated.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from .config import Settings
from .data.base import FeedHealth, Quote
from .data.provider import MarketDataProvider
from .engine import detect_setup, score_confluence
from .engine import indicators as ind
from .engine.confluence import ConfluenceResult, ScoreInputs
from .engine.setup_detection import Setup


@dataclass
class Opportunity:
    symbol: str
    quote: Quote
    candles: pd.DataFrame
    health: FeedHealth
    setup: Setup
    result: Optional[ConfluenceResult]

    @property
    def score(self) -> int:
        return self.result.total if self.result else 0

    @property
    def band(self) -> str:
        return self.result.band if self.result else "—"

    @property
    def is_candidate(self) -> bool:
        """A valid, tradeable opportunity (detected setup + valid levels)."""
        if not (self.setup and self.setup.detected):
            return False
        if self.quote.price <= 0:
            return False
        return all(v is not None for v in (self.setup.entry, self.setup.stop, self.setup.target))

    @property
    def qualifies(self) -> bool:
        """Meets the auto-trade gate: score >= 70 and no critical warning."""
        if not self.is_candidate or self.result is None:
            return False
        return self.result.total >= 70 and not self.result.has_critical_warning

    @property
    def data_label(self) -> str:
        src = (self.quote.source or self.health.status).upper()
        if self.health.delayed:
            return f"{src} DELAYED"
        if self.health.is_live:
            return f"{src} LIVE"
        return f"{src} {self.health.status.upper()}"


def _derive_regime(df: pd.DataFrame, direction: str) -> str:
    if df is None or len(df) < 20 or direction == "none":
        return "neutral"
    close = df["close"]
    trend_up = bool(close.iloc[-1] > ind.sma(close, 20).iloc[-1])
    if direction == "long":
        return "with" if trend_up else "against"
    return "against" if trend_up else "with"


def evaluate_symbol(
    provider: MarketDataProvider,
    symbol: str,
    settings: Settings,
    event_risk: bool = False,
    low_float: bool = False,
) -> Opportunity:
    quote = provider.get_quote(symbol)
    candles = provider.get_candles(symbol, 120)
    health = provider.health(symbol)

    if candles is None or candles.empty:
        empty_setup = Setup(False, "none", "none", 0.0, notes=["No candle data yet."])
        return Opportunity(symbol.upper(), quote, candles, health, empty_setup, None)

    setup = detect_setup(candles)
    rvol = ind.rvol(candles)
    atrp = ind.atr_pct(candles)
    catalyst = max(0.0, min(1.0, ((rvol or 1.0) - 1.0) / 2.0))
    regime = _derive_regime(candles, setup.direction)

    inputs = ScoreInputs(
        setup=setup,
        candles=candles,
        rvol=rvol,
        spread_pct=quote.spread_pct,
        catalyst_quality=catalyst,
        regime=regime,
        atr_pct=atrp,
        quote_age=quote.age_seconds(),
        stale_after=settings.stale_after_seconds,
        feed_is_live=health.is_live,
        event_risk=event_risk,
        low_float=low_float,
    )
    result = score_confluence(inputs)
    return Opportunity(symbol.upper(), quote, candles, health, setup, result)


def scan(
    provider: MarketDataProvider,
    symbols: List[str],
    settings: Settings,
    event_risk: bool = False,
    low_float: bool = False,
) -> List[Opportunity]:
    opps = [
        evaluate_symbol(provider, s, settings, event_risk, low_float)
        for s in symbols
        if s.strip()
    ]
    opps.sort(key=lambda o: o.score, reverse=True)
    return opps


def parse_watchlist(text: str) -> List[str]:
    """Parse a comma/space/newline separated watchlist into unique symbols."""
    raw = text.replace("\n", ",").replace(" ", ",").split(",")
    seen: List[str] = []
    for tok in raw:
        sym = tok.strip().upper()
        if sym and sym not in seen:
            seen.append(sym)
    return seen
