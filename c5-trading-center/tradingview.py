"""TradingView Advanced Chart embed — DISPLAY ONLY.

This is the visual chart layer. It is **never** a data source. C5's analysis and
trades use the market-data provider stubs (Webull OpenAPI primary, Finnhub
backup) — do NOT read analysis/trade data from TradingView.

# TODO (optional future upgrade): swap the embedded Advanced Chart widget for
#   the TradingView *Charting Library* + a custom *Datafeed API* adapter wired
#   to the same Webull/Finnhub feed C5 analyzes, so the displayed candles match
#   the analyzed candles exactly. The embed below cannot do that — it renders
#   TradingView's own data for display only.
"""
from __future__ import annotations

import streamlit.components.v1 as components

from config import SESSION_TIMEZONE

# Plain ticker -> TradingView EXCHANGE:SYMBOL (best-effort; bare symbols also
# resolve, but a prefix is more reliable). Extend as the universe grows.
_EXCHANGE_MAP = {
    "AAPL": "NASDAQ:AAPL", "NVDA": "NASDAQ:NVDA", "TSLA": "NASDAQ:TSLA",
    "AMD": "NASDAQ:AMD", "META": "NASDAQ:META", "MSFT": "NASDAQ:MSFT",
    "AMZN": "NASDAQ:AMZN", "GOOGL": "NASDAQ:GOOGL", "GOOG": "NASDAQ:GOOG",
    "NFLX": "NASDAQ:NFLX", "COIN": "NASDAQ:COIN", "PLTR": "NASDAQ:PLTR",
    "INTC": "NASDAQ:INTC", "QQQ": "NASDAQ:QQQ",
    "SHOP": "NYSE:SHOP", "UBER": "NYSE:UBER", "BABA": "NYSE:BABA",
    "SPY": "AMEX:SPY",
}


def to_tv_symbol(ticker: str) -> str:
    """Map a plain ticker to TradingView's EXCHANGE:SYMBOL format where known."""
    t = (ticker or "").upper().strip()
    if not t:
        return ""
    if ":" in t:           # already EXCHANGE:SYMBOL
        return t
    return _EXCHANGE_MAP.get(t, t)   # fall back to bare symbol (TV resolves many)


def tv_chart(symbol: str, height: int = 520, interval: str = "5") -> None:
    """Embed the TradingView Advanced Chart widget (dark, display-only)."""
    tv_symbol = to_tv_symbol(symbol) or "NASDAQ:AAPL"
    # Unique-ish container id per symbol so re-renders only reload on a real
    # symbol change.
    cid = "tvc_" + "".join(ch for ch in tv_symbol if ch.isalnum())
    html = f"""
    <div class="tradingview-widget-container">
      <div id="{cid}"></div>
      <script src="https://s3.tradingview.com/tv.js"></script>
      <script>
      new TradingView.widget({{
        "container_id": "{cid}",
        "symbol": "{tv_symbol}",
        "interval": "{interval}",
        "theme": "dark",
        "style": "1",
        "width": "100%",
        "height": {height},
        "timezone": "{SESSION_TIMEZONE}",
        "toolbar_bg": "#05070D",
        "allow_symbol_change": true,
        "hide_side_toolbar": false
      }});
      </script>
    </div>
    """
    components.html(html, height=height + 8)
