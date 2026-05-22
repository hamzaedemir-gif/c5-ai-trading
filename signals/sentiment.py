"""Sentiment-shift signal."""
from __future__ import annotations

from typing import Sequence

from .base import DIRECTION_FLAT, DIRECTION_LONG, DIRECTION_SHORT, Signal


def sentiment_shift_signal(symbol: str, samples: Sequence[dict],
                           short_window: int = 3,
                           long_window: int = 20,
                           saturation: float = 0.5) -> Signal:
    """Compare recent sentiment to a longer baseline.

    `samples` is ordered newest-first or oldest-first; we re-sort to
    oldest -> newest for clarity. Each sample needs `score` in [-1, 1].
    """
    if not samples or len(samples) < short_window + 1:
        return Signal(symbol, "sentiment_shift", 0.0, DIRECTION_FLAT,
                      inputs={"reason": "insufficient_history",
                              "n_samples": len(samples) if samples else 0})

    # Normalize to oldest -> newest using the `ts` field if present.
    if all("ts" in s for s in samples):
        ordered = sorted(samples, key=lambda s: s["ts"])
    else:
        ordered = list(samples)

    short = [float(s["score"]) for s in ordered[-short_window:]]
    long_n = min(long_window, len(ordered))
    long = [float(s["score"]) for s in ordered[-long_n:]]

    short_mean = sum(short) / len(short)
    long_mean = sum(long) / len(long)
    shift = short_mean - long_mean

    confidence = max(0.0, min(1.0, abs(shift) / saturation))
    direction = DIRECTION_LONG if shift > 0 else DIRECTION_SHORT if shift < 0 else DIRECTION_FLAT

    return Signal(
        symbol=symbol,
        signal_type="sentiment_shift",
        confidence=round(confidence, 4),
        direction=direction,
        inputs={
            "short_window": short_window,
            "long_window": long_window,
            "short_mean": round(short_mean, 4),
            "long_mean": round(long_mean, 4),
            "shift": round(shift, 4),
            "saturation": saturation,
            "n_samples": len(ordered),
        },
    )
