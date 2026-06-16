"""C5 analysis engine: indicators, setup detection, confluence scoring."""
from __future__ import annotations

from .confluence import (
    BAND_HIGH,
    BAND_LOW,
    BAND_MEDIUM,
    ConfluenceResult,
    ScoreComponent,
    Warning_,
    score_confluence,
)
from .setup_detection import Setup, detect_setup

__all__ = [
    "ConfluenceResult",
    "ScoreComponent",
    "Warning_",
    "score_confluence",
    "BAND_HIGH",
    "BAND_MEDIUM",
    "BAND_LOW",
    "Setup",
    "detect_setup",
]
