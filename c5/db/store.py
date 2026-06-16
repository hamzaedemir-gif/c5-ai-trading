"""SQLite store: trade log, account snapshots, and feed-health log.

All persistence is local. Nothing here connects to a brokerage or executes any
real order — rows represent SIMULATED paper trades only.
"""
from __future__ import annotations

import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    opened_ts    REAL NOT NULL,
    closed_ts    REAL,
    symbol       TEXT NOT NULL,
    side         TEXT NOT NULL,           -- long | short
    qty          REAL NOT NULL,
    entry_price  REAL NOT NULL,
    exit_price   REAL,
    stop         REAL,
    target       REAL,
    status       TEXT NOT NULL,           -- open | closed
    pnl          REAL,
    pnl_pct      REAL,
    confluence   INTEGER,                 -- score at entry
    band         TEXT,
    mode         TEXT,                    -- data mode at entry
    reason       TEXT,                    -- close reason / note
    is_test      INTEGER DEFAULT 0,       -- 1 = 10-minute paper-trade test
    setup        TEXT,                    -- setup kind at entry
    feed_label   TEXT,                    -- e.g. FINNHUB LIVE / MOCK
    is_auto      INTEGER DEFAULT 0,       -- 1 = opened by the auto-trader
    reasons      TEXT,                    -- score reasons (joined)
    warnings     TEXT                     -- score warnings (joined)
);

CREATE TABLE IF NOT EXISTS account_snapshots (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           REAL NOT NULL,
    cash         REAL NOT NULL,
    equity       REAL NOT NULL,
    realized_pnl REAL NOT NULL,
    open_positions INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS feed_health (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        REAL NOT NULL,
    mode      TEXT NOT NULL,
    status    TEXT NOT NULL,
    detail    TEXT
);
"""


class Store:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        # check_same_thread=False so Streamlit reruns can share the connection.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """Add columns that may be missing on databases created by older versions."""
        existing = {r[1] for r in self._conn.execute("PRAGMA table_info(trades)")}
        additions = {
            "setup": "TEXT",
            "feed_label": "TEXT",
            "is_auto": "INTEGER DEFAULT 0",
            "reasons": "TEXT",
            "warnings": "TEXT",
        }
        for col, decl in additions.items():
            if col not in existing:
                self._conn.execute(f"ALTER TABLE trades ADD COLUMN {col} {decl}")

    # -- trades ----------------------------------------------------------
    def insert_trade(self, trade: Dict[str, Any]) -> int:
        cols = (
            "opened_ts", "closed_ts", "symbol", "side", "qty", "entry_price",
            "exit_price", "stop", "target", "status", "pnl", "pnl_pct",
            "confluence", "band", "mode", "reason", "is_test",
            "setup", "feed_label", "is_auto", "reasons", "warnings",
        )
        values = [trade.get(c) for c in cols]
        placeholders = ", ".join("?" for _ in cols)
        sql = f"INSERT INTO trades ({', '.join(cols)}) VALUES ({placeholders})"
        cur = self._conn.execute(sql, values)
        self._conn.commit()
        return int(cur.lastrowid)

    def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        reason: str = "",
        closed_ts: Optional[float] = None,
    ) -> None:
        self._conn.execute(
            """UPDATE trades
                   SET closed_ts = ?, exit_price = ?, status = 'closed',
                       pnl = ?, pnl_pct = ?, reason = ?
                 WHERE id = ?""",
            (closed_ts or time.time(), exit_price, pnl, pnl_pct, reason, trade_id),
        )
        self._conn.commit()

    def get_trades(self, limit: int = 200) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_open_trades(self) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM trades WHERE status = 'open' ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def realized_pnl(self) -> float:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(pnl), 0) AS total FROM trades WHERE status = 'closed'"
        ).fetchone()
        return float(row["total"] or 0.0)

    def win_loss_counts(self) -> Dict[str, int]:
        row = self._conn.execute(
            """SELECT
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) AS losses,
                   SUM(CASE WHEN pnl = 0 THEN 1 ELSE 0 END) AS flats
               FROM trades WHERE status = 'closed'"""
        ).fetchone()
        return {
            "wins": int(row["wins"] or 0),
            "losses": int(row["losses"] or 0),
            "flats": int(row["flats"] or 0),
        }

    # -- snapshots & health ---------------------------------------------
    def snapshot_account(self, cash: float, equity: float, realized: float, open_positions: int) -> None:
        self._conn.execute(
            "INSERT INTO account_snapshots (ts, cash, equity, realized_pnl, open_positions) VALUES (?,?,?,?,?)",
            (time.time(), cash, equity, realized, open_positions),
        )
        self._conn.commit()

    def log_feed_health(self, mode: str, status: str, detail: str = "") -> None:
        self._conn.execute(
            "INSERT INTO feed_health (ts, mode, status, detail) VALUES (?,?,?,?)",
            (time.time(), mode, status, detail),
        )
        self._conn.commit()

    def reset(self) -> None:
        """Wipe all paper-trading data (used by the UI reset button)."""
        self._conn.executescript(
            "DELETE FROM trades; DELETE FROM account_snapshots; DELETE FROM feed_health;"
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
