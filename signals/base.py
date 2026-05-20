"""Common types for signals.

A Signal always carries a confidence score in [0, 1] and a direction. The
raw inputs that produced it travel alongside so every decision is auditable.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

DIRECTION_LONG = "long"
DIRECTION_SHORT = "short"
DIRECTION_FLAT = "flat"


@dataclass
class Signal:
    symbol: str
    signal_type: str
    confidence: float        # 0.0 .. 1.0
    direction: str           # long | short | flat
    inputs: Mapping[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    notes: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0,1], got {self.confidence}")
        if self.direction not in (DIRECTION_LONG, DIRECTION_SHORT, DIRECTION_FLAT):
            raise ValueError(f"invalid direction {self.direction}")

    def to_log_kwargs(self) -> dict:
        return {
            "symbol": self.symbol,
            "signal_type": self.signal_type,
            "confidence": self.confidence,
            "direction": self.direction,
            "inputs_json": json.dumps(dict(self.inputs), default=str, sort_keys=True),
            "ts": self.ts,
            "notes": self.notes,
        }

    def asdict(self) -> dict:
        d = asdict(self)
        d["inputs"] = dict(self.inputs)
        return d
