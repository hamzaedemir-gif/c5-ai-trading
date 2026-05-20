"""Earnings-surprise signal."""
from __future__ import annotations

from typing import Mapping

from .base import DIRECTION_FLAT, DIRECTION_LONG, DIRECTION_SHORT, Signal


def earnings_surprise_signal(symbol: str, earnings_row: Mapping | None,
                             saturation_pct: float = 0.20) -> Signal:
    """Score an earnings beat / miss.

    `earnings_row` is a dict (typically a SQLite row) with eps_estimate and
    eps_actual. Confidence saturates at `saturation_pct` (default 20% surprise).
    """
    if not earnings_row:
        return Signal(symbol, "earnings_surprise", 0.0, DIRECTION_FLAT,
                      inputs={"reason": "no_data"})

    est = earnings_row.get("eps_estimate") if hasattr(earnings_row, "get") else earnings_row["eps_estimate"]
    act = earnings_row.get("eps_actual") if hasattr(earnings_row, "get") else earnings_row["eps_actual"]

    if est is None or act is None:
        return Signal(symbol, "earnings_surprise", 0.0, DIRECTION_FLAT,
                      inputs={"reason": "missing_eps", "eps_estimate": est, "eps_actual": act})

    est_f = float(est)
    act_f = float(act)
    if est_f == 0:
        # Avoid div-by-zero; treat as no signal.
        return Signal(symbol, "earnings_surprise", 0.0, DIRECTION_FLAT,
                      inputs={"reason": "zero_estimate", "eps_actual": act_f})

    surprise = (act_f - est_f) / abs(est_f)
    confidence = max(0.0, min(1.0, abs(surprise) / saturation_pct))
    direction = DIRECTION_LONG if surprise > 0 else DIRECTION_SHORT if surprise < 0 else DIRECTION_FLAT

    return Signal(
        symbol=symbol,
        signal_type="earnings_surprise",
        confidence=round(confidence, 4),
        direction=direction,
        inputs={
            "eps_estimate": est_f,
            "eps_actual": act_f,
            "surprise_pct": round(surprise, 4),
            "saturation_pct": saturation_pct,
            "event_date": earnings_row.get("event_date") if hasattr(earnings_row, "get") else None,
        },
    )
