"""Central configuration loaded from environment / .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return float(raw)


@dataclass(frozen=True)
class Config:
    db_path: str = _env("C5_DB_PATH", "c5_data.sqlite")
    trading_mode: str = _env("C5_TRADING_MODE", "paper")

    alpaca_api_key: str = _env("ALPACA_API_KEY")
    alpaca_api_secret: str = _env("ALPACA_API_SECRET")
    alpaca_base_url: str = _env("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    finnhub_api_key: str = _env("FINNHUB_API_KEY")
    alpha_vantage_api_key: str = _env("ALPHA_VANTAGE_API_KEY")
    stocktwits_base_url: str = _env("STOCKTWITS_BASE_URL", "https://api.stocktwits.com/api/2")

    starting_capital: float = _env_float("C5_STARTING_CAPITAL", 10_000.0)
    position_pct: float = _env_float("C5_POSITION_PCT", 0.02)
    stop_loss_pct: float = _env_float("C5_STOP_LOSS_PCT", 0.03)
    daily_max_loss_pct: float = _env_float("C5_DAILY_MAX_LOSS_PCT", 0.05)

    def is_paper(self) -> bool:
        return self.trading_mode.lower() != "live"


def load_config() -> Config:
    return Config()


ROOT = Path(__file__).resolve().parent
