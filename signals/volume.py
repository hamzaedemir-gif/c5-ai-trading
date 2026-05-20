"""Volume-spike detection."""
from __future__ import annotations

import math
from typing import Sequence

from .base import DIRECTION_FLAT, DIRECTION_LONG, DIRECTION_SHORT, Signal


def volume_spike_signal(symbol: str, bars: Sequence[dict],
                        lookback: int = 30,
                        z_threshold: float = 2.0) -> Signal:
    """Score a volume spike on the most recent bar.

    `bars` is a sequence ordered oldest -> newest of dicts with at least
    `volume` and `close` keys (close used for direction inference).
    Confidence saturates at z = z_threshold + 4 to give a smooth 0..1 score.
    """
    if len(bars) < lookback + 1:
        return Signal(symbol, "volume_spike", 0.0, DIRECTION_FLAT,
                      inputs={"reason": "insufficient_history",
                              "n_bars": len(bars)})

    window = bars[-(lookback + 1):-1]   # exclude latest
    latest = bars[-1]

    volumes = [float(b.get("volume") or 0) for b in window]
    mean = sum(volumes) / len(volumes)
    var = sum((v - mean) ** 2 for v in volumes) / len(volumes)
    std = math.sqrt(var)
    latest_v = float(latest.get("volume") or 0)

    if std == 0:
        # Constant-volume baseline: fall back to ratio-based detection.
        ratio = latest_v / mean if mean > 0 else 0.0
        z = max(0.0, ratio - 1.0) * z_threshold   # ratio of 2 -> z=z_threshold
    else:
        z = (latest_v - mean) / std

    confidence = max(0.0, min(1.0, (z - z_threshold) / 4.0))

    direction = DIRECTION_FLAT
    if confidence > 0:
        prev_close = float(window[-1].get("close") or 0)
        latest_close = float(latest.get("close") or 0)
        if prev_close > 0:
            direction = DIRECTION_LONG if latest_close >= prev_close else DIRECTION_SHORT

    return Signal(
        symbol=symbol,
        signal_type="volume_spike",
        confidence=round(confidence, 4),
        direction=direction,
        inputs={
            "lookback": lookback,
            "z_threshold": z_threshold,
            "mean_volume": round(mean, 2),
            "std_volume": round(std, 2),
            "latest_volume": latest_v,
            "z_score": round(z, 3),
        },
    )
