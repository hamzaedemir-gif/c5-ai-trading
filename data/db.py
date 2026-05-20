"""SQLite storage for ingested market data. Append-only with timestamps."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    ts TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER,
    source TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    UNIQUE(symbol, ts, source)
);
CREATE INDEX IF NOT EXISTS idx_prices_symbol_ts ON prices(symbol, ts);

CREATE TABLE IF NOT EXISTS earnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    event_date TEXT NOT NULL,
    period TEXT,
    eps_estimate REAL,
    eps_actual REAL,
    revenue_estimate REAL,
    revenue_actual REAL,
    source TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    UNIQUE(symbol, event_date, period, source)
);
CREATE INDEX IF NOT EXISTS idx_earnings_symbol ON earnings(symbol);

CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT,
    headline TEXT NOT NULL,
    url TEXT,
    summary TEXT,
    published_at TEXT NOT NULL,
    source TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    UNIQUE(symbol, headline, published_at)
);
CREATE INDEX IF NOT EXISTS idx_news_symbol_published ON news(symbol, published_at);

CREATE TABLE IF NOT EXISTS sentiment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    ts TEXT NOT NULL,
    score REAL NOT NULL,        -- -1.0 .. 1.0
    volume INTEGER,             -- message count
    source TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    UNIQUE(symbol, ts, source)
);
CREATE INDEX IF NOT EXISTS idx_sentiment_symbol_ts ON sentiment(symbol, ts);

CREATE TABLE IF NOT EXISTS signal_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    direction TEXT NOT NULL,   -- long | short | flat
    inputs_json TEXT NOT NULL,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_signal_log_symbol_ts ON signal_log(symbol, ts);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,        -- buy | sell
    qty REAL NOT NULL,
    price REAL NOT NULL,
    mode TEXT NOT NULL,        -- paper | live
    signal_id INTEGER,
    reason TEXT,
    FOREIGN KEY(signal_id) REFERENCES signal_log(id)
);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def open_db(path: str | Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


class Database:
    """Thin convenience wrapper around a sqlite3 connection."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *_exc) -> None:
        self._conn.commit()
        self.close()

    # ---- writers ----------------------------------------------------------
    def insert_prices(self, rows: Iterable[Mapping]) -> int:
        sql = (
            "INSERT OR IGNORE INTO prices "
            "(symbol, ts, open, high, low, close, volume, source, ingested_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)"
        )
        now = _utcnow()
        payload = [
            (
                r["symbol"], r["ts"], r.get("open"), r.get("high"), r.get("low"),
                r.get("close"), r.get("volume"), r["source"], now,
            )
            for r in rows
        ]
        cur = self._conn.executemany(sql, payload)
        self._conn.commit()
        return cur.rowcount

    def insert_earnings(self, rows: Iterable[Mapping]) -> int:
        sql = (
            "INSERT OR IGNORE INTO earnings "
            "(symbol, event_date, period, eps_estimate, eps_actual, "
            "revenue_estimate, revenue_actual, source, ingested_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)"
        )
        now = _utcnow()
        payload = [
            (
                r["symbol"], r["event_date"], r.get("period"),
                r.get("eps_estimate"), r.get("eps_actual"),
                r.get("revenue_estimate"), r.get("revenue_actual"),
                r["source"], now,
            )
            for r in rows
        ]
        cur = self._conn.executemany(sql, payload)
        self._conn.commit()
        return cur.rowcount

    def insert_news(self, rows: Iterable[Mapping]) -> int:
        sql = (
            "INSERT OR IGNORE INTO news "
            "(symbol, headline, url, summary, published_at, source, ingested_at) "
            "VALUES (?,?,?,?,?,?,?)"
        )
        now = _utcnow()
        payload = [
            (
                r.get("symbol"), r["headline"], r.get("url"),
                r.get("summary"), r["published_at"], r["source"], now,
            )
            for r in rows
        ]
        cur = self._conn.executemany(sql, payload)
        self._conn.commit()
        return cur.rowcount

    def insert_sentiment(self, rows: Iterable[Mapping]) -> int:
        sql = (
            "INSERT OR IGNORE INTO sentiment "
            "(symbol, ts, score, volume, source, ingested_at) "
            "VALUES (?,?,?,?,?,?)"
        )
        now = _utcnow()
        payload = [
            (
                r["symbol"], r["ts"], float(r["score"]),
                r.get("volume"), r["source"], now,
            )
            for r in rows
        ]
        cur = self._conn.executemany(sql, payload)
        self._conn.commit()
        return cur.rowcount

    def log_signal(self, *, symbol: str, signal_type: str, confidence: float,
                   direction: str, inputs_json: str, ts: str | None = None,
                   notes: str | None = None) -> int:
        sql = (
            "INSERT INTO signal_log "
            "(ts, symbol, signal_type, confidence, direction, inputs_json, notes) "
            "VALUES (?,?,?,?,?,?,?)"
        )
        cur = self._conn.execute(
            sql, (ts or _utcnow(), symbol, signal_type,
                  float(confidence), direction, inputs_json, notes),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def log_trade(self, *, symbol: str, side: str, qty: float, price: float,
                  mode: str, signal_id: int | None = None,
                  reason: str | None = None, ts: str | None = None) -> int:
        sql = (
            "INSERT INTO trades "
            "(ts, symbol, side, qty, price, mode, signal_id, reason) "
            "VALUES (?,?,?,?,?,?,?,?)"
        )
        cur = self._conn.execute(
            sql, (ts or _utcnow(), symbol, side, float(qty),
                  float(price), mode, signal_id, reason),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    # ---- readers ----------------------------------------------------------
    def fetch_prices(self, symbol: str, limit: int = 500) -> Sequence[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM prices WHERE symbol = ? ORDER BY ts DESC LIMIT ?",
            (symbol, limit),
        ).fetchall()

    def fetch_sentiment(self, symbol: str, limit: int = 100) -> Sequence[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM sentiment WHERE symbol = ? ORDER BY ts DESC LIMIT ?",
            (symbol, limit),
        ).fetchall()

    def fetch_earnings(self, symbol: str) -> Sequence[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM earnings WHERE symbol = ? ORDER BY event_date DESC",
            (symbol,),
        ).fetchall()

    def fetch_signals(self, symbol: str | None = None, limit: int = 100) -> Sequence[sqlite3.Row]:
        if symbol:
            return self._conn.execute(
                "SELECT * FROM signal_log WHERE symbol = ? ORDER BY ts DESC LIMIT ?",
                (symbol, limit),
            ).fetchall()
        return self._conn.execute(
            "SELECT * FROM signal_log ORDER BY ts DESC LIMIT ?", (limit,),
        ).fetchall()
