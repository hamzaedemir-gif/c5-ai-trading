"""Central configuration for C5 v1.

Reads from environment / .env but ships with safe defaults so the app runs
immediately in mock mode with no configuration at all.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

try:  # optional dependency; app still works without a .env file
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is best-effort
    pass


# Data-feed modes ---------------------------------------------------------
MODE_MOCK = "mock"
MODE_MANUAL = "manual"
MODE_FINNHUB = "finnhub"
MODE_WEBULL = "webull"

ALL_MODES: List[str] = [MODE_MOCK, MODE_MANUAL, MODE_FINNHUB, MODE_WEBULL]


@dataclass
class Settings:
    data_mode: str = field(default_factory=lambda: os.getenv("C5_DATA_MODE", MODE_MOCK).lower())
    finnhub_api_key: str = field(default_factory=lambda: os.getenv("FINNHUB_API_KEY", "").strip())
    starting_cash: float = field(default_factory=lambda: float(os.getenv("C5_STARTING_CASH", "1000")))
    default_symbol: str = field(default_factory=lambda: os.getenv("C5_DEFAULT_SYMBOL", "AAPL").upper())
    db_path: str = field(default_factory=lambda: os.getenv("C5_DB_PATH", "data/c5.db"))

    # Paper-trade test length, in seconds (10 minutes).
    trade_test_seconds: int = 600

    # A quote older than this many seconds is considered stale (triggers the
    # -20 "delayed/stale data" warning and removes the "live" label).
    stale_after_seconds: int = 60

    def __post_init__(self) -> None:
        if self.data_mode not in ALL_MODES:
            self.data_mode = MODE_MOCK

    @property
    def finnhub_available(self) -> bool:
        return bool(self.finnhub_api_key)


def get_settings() -> Settings:
    """Build a fresh Settings object from the current environment."""
    return Settings()
