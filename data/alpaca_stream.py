"""Alpaca real-time market-data websocket client.

Reuses the existing SQLite store: each incoming trade is normalised into
the same bar shape the rest of the data layer uses (1-second snapshots),
then written via `Database.insert_prices`. Subscribers (e.g. the FastAPI
websocket broadcaster) can also tap the in-memory feed.

This module is intentionally framework-light: a small asyncio coroutine
plus an `AlpacaStream` class. Tests do not hit the network -- they call
`_handle_message` directly with canned payloads.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Awaitable, Callable, Deque, Dict, Iterable, List

from .db import Database

log = logging.getLogger(__name__)

SOURCE_ALPACA_STREAM = "alpaca_stream"

Listener = Callable[[dict], Awaitable[None]]


def _iso_from_alpaca_ts(ts: str | int | float | None) -> str:
    """Alpaca sends RFC3339 strings for trade/quote `t`. Be tolerant of ints."""
    if ts is None:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    if isinstance(ts, (int, float)):
        # nanoseconds since epoch
        secs = ts / 1_000_000_000 if ts > 10**12 else ts
        return datetime.fromtimestamp(secs, tz=timezone.utc).isoformat(timespec="seconds")
    return str(ts)


class AlpacaStream:
    """Async websocket client that turns Alpaca trades/quotes into bars + events.

    The class is split so it is easy to test:
      - `_handle_message` is pure: takes a parsed payload, mutates state,
        returns the list of bars to persist + the events to broadcast.
      - `run` is the live loop that owns the network connection.
    """

    def __init__(self, *, api_key: str, api_secret: str, stream_url: str,
                 symbols: Iterable[str], db: Database | None = None,
                 max_recent_quotes: int = 200):
        self.api_key = api_key
        self.api_secret = api_secret
        self.stream_url = stream_url
        self.symbols = [s.upper() for s in symbols]
        self.db = db
        self.listeners: List[Listener] = []
        # Last known price per symbol, used for quick movers/quote endpoints.
        self.latest: Dict[str, dict] = {}
        self.recent_quotes: Dict[str, Deque[dict]] = defaultdict(
            lambda: deque(maxlen=max_recent_quotes)
        )
        self._stop = asyncio.Event()

    # ---- public API --------------------------------------------------
    def add_listener(self, fn: Listener) -> None:
        self.listeners.append(fn)

    def remove_listener(self, fn: Listener) -> None:
        try:
            self.listeners.remove(fn)
        except ValueError:
            pass

    def stop(self) -> None:
        self._stop.set()

    def snapshot(self) -> Dict[str, dict]:
        """Latest known price/volume per subscribed symbol."""
        return dict(self.latest)

    # ---- message handling (pure / testable) --------------------------
    def _handle_message(self, msg: dict) -> tuple[List[dict], List[dict]]:
        """Process a single parsed message.

        Returns (rows_to_persist, events_to_broadcast).
        """
        rows: List[dict] = []
        events: List[dict] = []
        mtype = msg.get("T")

        if mtype == "t":          # trade
            sym = msg.get("S", "")
            price = float(msg.get("p", 0) or 0)
            size = int(msg.get("s", 0) or 0)
            ts = _iso_from_alpaca_ts(msg.get("t"))
            row = {
                "symbol": sym, "ts": ts,
                "open": price, "high": price, "low": price, "close": price,
                "volume": size, "source": SOURCE_ALPACA_STREAM,
            }
            rows.append(row)
            prev = self.latest.get(sym, {})
            prev_close = prev.get("price")
            change_pct = ((price - prev_close) / prev_close * 100.0) if prev_close else 0.0
            day_volume = prev.get("day_volume", 0) + size
            self.latest[sym] = {
                "symbol": sym, "price": price, "ts": ts,
                "last_size": size, "day_volume": day_volume,
                "change_pct": round(change_pct, 4),
                "prev_price": prev_close,
            }
            events.append({"type": "trade", **self.latest[sym]})
        elif mtype == "q":        # quote
            sym = msg.get("S", "")
            bid = float(msg.get("bp", 0) or 0)
            ask = float(msg.get("ap", 0) or 0)
            ts = _iso_from_alpaca_ts(msg.get("t"))
            quote = {"symbol": sym, "ts": ts, "bid": bid, "ask": ask}
            self.recent_quotes[sym].append(quote)
            events.append({"type": "quote", **quote})
        elif mtype == "subscription":
            log.info("Alpaca subscription confirmed: %s", msg)
        elif mtype == "success":
            log.info("Alpaca: %s", msg.get("msg", msg))
        elif mtype == "error":
            log.error("Alpaca error: %s", msg)
        return rows, events

    async def _process_payload(self, payload) -> None:
        """Persist + broadcast a batch of messages."""
        if isinstance(payload, dict):
            payload = [payload]
        all_rows: List[dict] = []
        all_events: List[dict] = []
        for msg in payload:
            rows, events = self._handle_message(msg)
            all_rows.extend(rows)
            all_events.extend(events)
        if all_rows and self.db is not None:
            try:
                self.db.insert_prices(all_rows)
            except Exception as exc:    # never let DB errors kill the stream
                log.error("Failed to persist %d bars: %s", len(all_rows), exc)
        for ev in all_events:
            for listener in list(self.listeners):
                try:
                    await listener(ev)
                except Exception as exc:
                    log.error("Listener %r failed: %s", listener, exc)

    # ---- live loop ---------------------------------------------------
    async def run(self) -> None:
        """Connect and stream until `stop()` or unrecoverable error.

        Reconnects with exponential backoff on transient errors.
        """
        try:
            import websockets   # noqa: F401  -- imported lazily for tests
        except ImportError as exc:
            raise RuntimeError(
                "websockets package required for live streaming -- "
                "pip install websockets"
            ) from exc
        from websockets import connect
        from websockets.exceptions import ConnectionClosed

        backoff = 1.0
        while not self._stop.is_set():
            try:
                async with connect(self.stream_url, ping_interval=20) as ws:
                    await ws.send(json.dumps({
                        "action": "auth",
                        "key": self.api_key,
                        "secret": self.api_secret,
                    }))
                    await ws.send(json.dumps({
                        "action": "subscribe",
                        "trades": self.symbols,
                        "quotes": self.symbols,
                    }))
                    log.info("Alpaca stream connected: %s symbols", len(self.symbols))
                    backoff = 1.0
                    while not self._stop.is_set():
                        raw = await ws.recv()
                        try:
                            payload = json.loads(raw)
                        except json.JSONDecodeError:
                            log.warning("non-JSON frame ignored")
                            continue
                        await self._process_payload(payload)
            except ConnectionClosed:
                log.warning("Alpaca stream closed; reconnecting in %.1fs", backoff)
            except Exception as exc:
                log.error("Alpaca stream error %r; reconnect in %.1fs", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)


def staleness_seconds(snapshot_ts: str) -> float:
    """How old (in seconds) a snapshot ts is. Used by /healthz."""
    try:
        dt = datetime.fromisoformat(snapshot_ts.replace("Z", "+00:00"))
    except ValueError:
        return float("inf")
    return time.time() - dt.timestamp()
