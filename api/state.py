"""Shared in-process state for the API server.

A single Database connection and the Alpaca stream client are constructed
at startup so handlers can read from them without re-opening files. The
state lives on `app.state` so tests can inject their own.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from data.alpaca_stream import AlpacaStream
from data.db import Database


@dataclass
class AppState:
    db: Database
    symbols: List[str]
    stream: AlpacaStream | None = None
    paper_mode: bool = True
    demo_mode: bool = False
    paper: "object | None" = None    # PaperPortfolioService; forward ref
    disclaimer: str = (
        "Analytics & education only. This dashboard displays market data and "
        "ranks candidates. It places NO trades and is NOT financial advice."
    )
    recent_events: List[dict] = field(default_factory=list)

    def add_event(self, event: dict, *, cap: int = 250) -> None:
        self.recent_events.append(event)
        if len(self.recent_events) > cap:
            del self.recent_events[: len(self.recent_events) - cap]

    def marks(self) -> dict:
        """Latest price per symbol, from the live stream if available."""
        out: dict = {}
        if self.stream is not None:
            for sym, snap in self.stream.snapshot().items():
                if snap.get("price"):
                    out[sym] = snap["price"]
        # fall back to DB latest for symbols without live data
        from data import latest_quote
        for sym in self.symbols:
            if sym not in out:
                q = latest_quote(self.db, sym)
                if q and q.get("price"):
                    out[sym] = q["price"]
        return out
