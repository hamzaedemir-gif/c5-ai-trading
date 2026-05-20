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
    alpaca_data_feed: str = _env("ALPACA_DATA_FEED", "iex")
    alpaca_stream_url: str = _env("ALPACA_STREAM_URL", "wss://stream.data.alpaca.markets/v2/iex")
    alpaca_symbols: str = _env("ALPACA_SYMBOLS", "AAPL,MSFT,TSLA,NVDA,AMD,SPY,QQQ")

    finnhub_api_key: str = _env("FINNHUB_API_KEY")
    alpha_vantage_api_key: str = _env("ALPHA_VANTAGE_API_KEY")
    stocktwits_base_url: str = _env("STOCKTWITS_BASE_URL", "https://api.stocktwits.com/api/2")

    starting_capital: float = _env_float("C5_STARTING_CAPITAL", 10_000.0)
    position_pct: float = _env_float("C5_POSITION_PCT", 0.02)
    stop_loss_pct: float = _env_float("C5_STOP_LOSS_PCT", 0.03)
    daily_max_loss_pct: float = _env_float("C5_DAILY_MAX_LOSS_PCT", 0.05)

    api_host: str = _env("C5_API_HOST", "0.0.0.0")
    api_port: int = int(_env("C5_API_PORT", "8000"))
    api_cors_origins: str = _env("C5_API_CORS_ORIGINS",
                                 "http://localhost:5173,http://127.0.0.1:5173")

    demo_mode: bool = _env("C5_DEMO_MODE", "0").lower() in ("1", "true", "yes")

    def demo(self) -> bool:
        return self.demo_mode

    def symbol_list(self) -> list[str]:
        return [s.strip().upper() for s in self.alpaca_symbols.split(",") if s.strip()]

    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    def is_paper(self) -> bool:
        return self.trading_mode.lower() != "live"


def load_config() -> Config:
    return Config()


ROOT = Path(__file__).resolve().parent
