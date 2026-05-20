"""Signal engine: runs per-symbol signals and logs them to the DB."""
from __future__ import annotations

import logging
from typing import Iterable, List

from data.db import Database

from .base import (DIRECTION_FLAT, DIRECTION_LONG, DIRECTION_SHORT, Signal)
from .earnings import earnings_surprise_signal
from .sentiment import sentiment_shift_signal
from .volume import volume_spike_signal

log = logging.getLogger(__name__)


class SignalEngine:
    def __init__(self, db: Database, *, persist: bool = True):
        self.db = db
        self.persist = persist

    def evaluate(self, symbol: str) -> List[Signal]:
        out: List[Signal] = []

        # ---- volume spike ------------------------------------------------
        rows = list(self.db.fetch_prices(symbol, limit=200))
        # fetch_prices returns DESC; reverse to oldest -> newest
        bars = [dict(r) for r in reversed(rows)]
        if bars:
            out.append(volume_spike_signal(symbol, bars))

        # ---- earnings surprise ------------------------------------------
        earnings_rows = list(self.db.fetch_earnings(symbol))
        latest = next((dict(r) for r in earnings_rows
                       if r["eps_estimate"] is not None and r["eps_actual"] is not None),
                      None)
        out.append(earnings_surprise_signal(symbol, latest))

        # ---- sentiment shift --------------------------------------------
        sent_rows = list(self.db.fetch_sentiment(symbol, limit=50))
        samples = [dict(r) for r in reversed(sent_rows)]
        out.append(sentiment_shift_signal(symbol, samples))

        if self.persist:
            for s in out:
                self.db.log_signal(**s.to_log_kwargs())

        return out

    def evaluate_all(self, symbols: Iterable[str]) -> dict[str, List[Signal]]:
        return {sym: self.evaluate(sym) for sym in symbols}

    def aggregate(self, signals: List[Signal]) -> Signal:
        """Combine multiple signals into a single directional score.

        Conservative aggregation: take confidence-weighted vote across signals
        that agree on direction. If long and short are roughly balanced we
        emit a flat signal regardless of magnitudes.
        """
        if not signals:
            return Signal("", "aggregate", 0.0, DIRECTION_FLAT, inputs={})

        symbol = signals[0].symbol
        long_w = sum(s.confidence for s in signals if s.direction == DIRECTION_LONG)
        short_w = sum(s.confidence for s in signals if s.direction == DIRECTION_SHORT)
        total = long_w + short_w

        if total == 0:
            direction = DIRECTION_FLAT
            confidence = 0.0
        elif abs(long_w - short_w) / total < 0.2:
            direction = DIRECTION_FLAT
            confidence = 0.0
        else:
            direction = DIRECTION_LONG if long_w > short_w else DIRECTION_SHORT
            confidence = round(max(long_w, short_w) / max(1, len(signals)), 4)

        return Signal(
            symbol=symbol,
            signal_type="aggregate",
            confidence=confidence,
            direction=direction,
            inputs={
                "components": [
                    {"type": s.signal_type, "conf": s.confidence,
                     "dir": s.direction}
                    for s in signals
                ],
                "long_weight": round(long_w, 4),
                "short_weight": round(short_w, 4),
            },
        )
