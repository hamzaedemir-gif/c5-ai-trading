"""Background task that simulates live trades for demo mode.

Pretends to be the Alpaca stream: every ~1.5s it generates a random
trade for a watch-list symbol, writes a bar to SQLite, and broadcasts
the same `trade` event shape so the dashboard WebSocket sees it move.
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Awaitable, Callable, Iterable, List

from data.alpaca_stream import SOURCE_ALPACA_STREAM
from data.db import Database

log = logging.getLogger(__name__)

Listener = Callable[[dict], Awaitable[None]]


class SimulatedTicker:
    """Drop-in stand-in for `AlpacaStream` in demo mode.

    Implements the same public surface used by the API: snapshot(),
    add_listener(), and a run() coroutine that can be cancelled.
    """

    def __init__(self, symbols: Iterable[str], db: Database,
                 *, interval_s: float = 1.5, seed: int = 0):
        self.symbols = list(symbols)
        self.db = db
        self.interval_s = interval_s
        self._rng = random.Random(seed)
        self.listeners: List[Listener] = []
        self.latest: dict[str, dict] = {}
        self._stop = asyncio.Event()
        # Seed with current closing prices so the first tick is anchored.
        for sym in self.symbols:
            row = next(iter(self.db.fetch_prices(sym, limit=1)), None)
            if row is not None:
                self.latest[sym] = {
                    "symbol": sym,
                    "price": float(row["close"] or 0),
                    "ts": row["ts"],
                    "last_size": int(row["volume"] or 0),
                    "day_volume": int(row["volume"] or 0),
                    "change_pct": 0.0,
                    "prev_price": float(row["close"] or 0),
                }

    # ---- compatibility with AlpacaStream's listener / snapshot API ---
    def snapshot(self) -> dict:
        return dict(self.latest)

    def add_listener(self, fn: Listener) -> None:
        self.listeners.append(fn)

    def remove_listener(self, fn: Listener) -> None:
        try:
            self.listeners.remove(fn)
        except ValueError:
            pass

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        log.info("Demo simulated ticker starting for %d symbols", len(self.symbols))
        while not self._stop.is_set():
            try:
                await self._tick()
            except Exception as exc:    # never let demo ticker die silently
                log.error("Demo ticker tick failed: %s", exc)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_s)
                return
            except asyncio.TimeoutError:
                continue

    async def _tick(self) -> None:
        sym = self._rng.choice(self.symbols)
        prev = self.latest.get(sym, {})
        prev_price = float(prev.get("price") or 100.0)
        # Tiny random walk + occasional spike for excitement.
        drift = self._rng.uniform(-0.0025, 0.0025)
        if self._rng.random() < 0.05:
            drift += self._rng.choice([-0.01, 0.01])
        price = max(0.01, prev_price * (1 + drift))
        size = self._rng.randint(10, 500)
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

        row = {
            "symbol": sym, "ts": ts,
            "open": price, "high": price, "low": price, "close": price,
            "volume": size, "source": SOURCE_ALPACA_STREAM,
        }
        try:
            self.db.insert_prices([row])
        except Exception as exc:
            log.warning("demo bar write failed for %s: %s", sym, exc)

        day_volume = int(prev.get("day_volume", 0)) + size
        change_pct = ((price - prev_price) / prev_price * 100.0) if prev_price else 0.0
        snap = {
            "symbol": sym, "price": round(price, 4), "ts": ts,
            "last_size": size, "day_volume": day_volume,
            "change_pct": round(change_pct, 4),
            "prev_price": prev_price,
        }
        self.latest[sym] = snap
        event = {"type": "trade", **snap}
        for listener in list(self.listeners):
            try:
                await listener(event)
            except Exception as exc:
                log.error("demo listener %r failed: %s", listener, exc)
