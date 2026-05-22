"""Central configuration loaded from environment / .env file.

`load_config()` always reads the *current* environment, so tests can
override values with `monkeypatch.setenv` without re-importing the module.
"""
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


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Config:
    db_path: str
    trading_mode: str

    alpaca_api_key: str
    alpaca_api_secret: str
    alpaca_base_url: str
    alpaca_data_feed: str
    alpaca_stream_url: str
    alpaca_symbols: str

    finnhub_api_key: str
    alpha_vantage_api_key: str
    stocktwits_base_url: str

    starting_capital: float
    position_pct: float
    stop_loss_pct: float
    daily_max_loss_pct: float

    api_host: str
    api_port: int
    api_cors_origins: str

    force_demo: bool

    def has_alpaca_keys(self) -> bool:
        return bool(self.alpaca_api_key and self.alpaca_api_secret)

    def effective_demo(self) -> bool:
        """True when the app should run on synthetic demo data.

        Demo mode kicks in when explicitly forced OR when we have no
        Alpaca keys to fetch real prices.
        """
        return self.force_demo or not self.has_alpaca_keys()

    # legacy alias kept so older callers keep working
    def demo(self) -> bool:
        return self.effective_demo()

    @property
    def demo_mode(self) -> bool:
        return self.effective_demo()

    def symbol_list(self) -> list[str]:
        return [s.strip().upper() for s in self.alpaca_symbols.split(",") if s.strip()]

    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    def is_paper(self) -> bool:
        return self.trading_mode.lower() != "live"


def load_config() -> Config:
    """Read the current environment and build a Config. Called fresh per request."""
    return Config(
        db_path=_env("C5_DB_PATH", "c5_data.sqlite"),
        trading_mode=_env("C5_TRADING_MODE", "paper"),

        alpaca_api_key=_env("ALPACA_API_KEY"),
        alpaca_api_secret=_env("ALPACA_API_SECRET"),
        alpaca_base_url=_env("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
        alpaca_data_feed=_env("ALPACA_DATA_FEED", "iex"),
        alpaca_stream_url=_env("ALPACA_STREAM_URL",
                               "wss://stream.data.alpaca.markets/v2/iex"),
        alpaca_symbols=_env("ALPACA_SYMBOLS", "AAPL,MSFT,TSLA,NVDA,AMD,SPY,QQQ"),

        finnhub_api_key=_env("FINNHUB_API_KEY"),
        alpha_vantage_api_key=_env("ALPHA_VANTAGE_API_KEY"),
        stocktwits_base_url=_env("STOCKTWITS_BASE_URL",
                                 "https://api.stocktwits.com/api/2"),

        starting_capital=_env_float("C5_STARTING_CAPITAL", 10_000.0),
        position_pct=_env_float("C5_POSITION_PCT", 0.02),
        stop_loss_pct=_env_float("C5_STOP_LOSS_PCT", 0.03),
        daily_max_loss_pct=_env_float("C5_DAILY_MAX_LOSS_PCT", 0.05),

        api_host=_env("C5_API_HOST", "0.0.0.0"),
        api_port=_env_int("C5_API_PORT", 8000),
        api_cors_origins=_env("C5_API_CORS_ORIGINS",
                              "http://localhost:5173,http://127.0.0.1:5173"),

        force_demo=_env_bool("C5_DEMO_MODE", False),
    )


ROOT = Path(__file__).resolve().parent
