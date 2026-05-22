"""Persistent paper portfolio backed by the existing risk manager.

Buys are SIMULATED. No order ever leaves this process. The risk manager
sizes the position, applies the stop, and rejects anything that would
breach the daily-loss cap or trip the kill switch.

State is persisted into the same SQLite database (in the existing
`trades` table plus a new tiny `paper_positions` table) so the
dashboard survives restarts.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List

from data import latest_quote
from data.db import Database
from risk import Portfolio, RiskManager
from signals.base import Signal

log = logging.getLogger(__name__)

EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS paper_positions (
    symbol TEXT PRIMARY KEY,
    qty REAL NOT NULL,
    avg_price REAL NOT NULL,
    stop_price REAL,
    opened_at TEXT NOT NULL,
    signal_json TEXT
);
CREATE TABLE IF NOT EXISTS paper_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass
class PaperBuyResult:
    approved: bool
    reason: str
    symbol: str
    qty: float = 0.0
    price: float = 0.0
    stop_price: float | None = None
    notional: float = 0.0
    trade_id: int | None = None


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PaperPortfolioService:
    """Thread-safe paper portfolio service backed by SQLite."""

    def __init__(self, db: Database, *, starting_capital: float = 10_000.0,
                 position_pct: float = 0.02, stop_loss_pct: float = 0.03,
                 daily_max_loss_pct: float = 0.05):
        self.db = db
        self.starting_capital = starting_capital
        self.position_pct = position_pct
        self.stop_loss_pct = stop_loss_pct
        self.daily_max_loss_pct = daily_max_loss_pct
        self._lock = threading.Lock()
        self._ensure_schema()
        self.portfolio = Portfolio.new(starting_capital)
        self._load_state()
        # Brand-new risk manager per request would forget the kill-switch,
        # so we keep one alive on the service. It's protected by self._lock.
        self.risk = RiskManager(
            self.portfolio,
            position_pct=position_pct,
            stop_loss_pct=stop_loss_pct,
            daily_max_loss_pct=daily_max_loss_pct,
            mode="paper",
        )

    # ---- persistence -------------------------------------------------
    def _ensure_schema(self) -> None:
        with self.db._lock:
            self.db._conn.executescript(EXTRA_SCHEMA)
            self.db._conn.commit()

    def _load_state(self) -> None:
        with self.db._lock:
            cash_row = self.db._conn.execute(
                "SELECT value FROM paper_state WHERE key='cash'",
            ).fetchone()
            realized_row = self.db._conn.execute(
                "SELECT value FROM paper_state WHERE key='realized_pnl'",
            ).fetchone()
            pos_rows = self.db._conn.execute(
                "SELECT * FROM paper_positions",
            ).fetchall()
        if cash_row:
            try:
                self.portfolio.cash = float(cash_row["value"])
            except (TypeError, ValueError):
                pass
        if realized_row:
            try:
                self.portfolio.realized_pnl = float(realized_row["value"])
            except (TypeError, ValueError):
                pass
        for r in pos_rows:
            self.portfolio.positions[r["symbol"]] = self._row_to_position(r)

    @staticmethod
    def _row_to_position(r: sqlite3.Row):
        from risk.portfolio import Position
        return Position(symbol=r["symbol"], qty=r["qty"],
                        avg_price=r["avg_price"],
                        stop_price=r["stop_price"], opened_at=r["opened_at"])

    def _persist_state(self) -> None:
        with self.db._lock:
            self.db._conn.execute(
                "INSERT OR REPLACE INTO paper_state(key, value) VALUES('cash', ?)",
                (str(self.portfolio.cash),))
            self.db._conn.execute(
                "INSERT OR REPLACE INTO paper_state(key, value) VALUES('realized_pnl', ?)",
                (str(self.portfolio.realized_pnl),))
            self.db._conn.commit()

    def _persist_position(self, pos) -> None:
        with self.db._lock:
            self.db._conn.execute(
                "INSERT OR REPLACE INTO paper_positions"
                "(symbol, qty, avg_price, stop_price, opened_at, signal_json)"
                " VALUES (?,?,?,?,?,?)",
                (pos.symbol, pos.qty, pos.avg_price, pos.stop_price,
                 pos.opened_at, None))
            self.db._conn.commit()

    def _delete_position(self, symbol: str) -> None:
        with self.db._lock:
            self.db._conn.execute(
                "DELETE FROM paper_positions WHERE symbol = ?", (symbol,),
            )
            self.db._conn.commit()

    # ---- public API --------------------------------------------------
    def status(self, marks: Dict[str, float] | None = None) -> dict:
        with self._lock:
            equity = self.portfolio.equity(marks)
            positions = []
            for sym, pos in self.portfolio.positions.items():
                price = (marks or {}).get(sym, pos.avg_price)
                positions.append({
                    "symbol": sym, "qty": pos.qty,
                    "avg_price": pos.avg_price, "stop_price": pos.stop_price,
                    "last_price": price,
                    "market_value": round(pos.market_value(price), 2),
                    "unrealized_pnl": round(pos.unrealized_pnl(price), 2),
                    "opened_at": pos.opened_at,
                })
            return {
                "mode": "paper",
                "starting_capital": self.portfolio.starting_equity,
                "cash": round(self.portfolio.cash, 2),
                "equity": round(equity, 2),
                "realized_pnl": round(self.portfolio.realized_pnl, 2),
                "kill_switch": self.risk.kill_switch,
                "positions": positions,
                "disclaimer": (
                    "Paper portfolio. No real orders, no real money. "
                    "Position sizing and stop-loss come from the risk module."
                ),
            }

    def paper_buy(self, symbol: str, *, signal: Signal | None = None,
                  current_price: float | None = None) -> PaperBuyResult:
        symbol = symbol.upper()
        if current_price is None:
            q = latest_quote(self.db, symbol)
            current_price = float(q["price"]) if q and q.get("price") else 0.0
        if not current_price or current_price <= 0:
            return PaperBuyResult(False, "no_price_available", symbol)
        sig = signal or Signal(symbol, "manual_paper_buy", 0.9, "long",
                               inputs={"source": "ui"})
        with self._lock:
            decision = self.risk.evaluate(sig, price=current_price)
            if not decision.approved:
                return PaperBuyResult(False, decision.reason, symbol)
            pos = self.portfolio.open_position(
                symbol, qty=decision.qty, price=current_price,
                stop_price=decision.stop_price)
            self._persist_position(pos)
            self._persist_state()
            trade_id = self.db.log_trade(
                symbol=symbol, side=decision.side, qty=decision.qty,
                price=current_price, mode="paper", reason="paper_buy_ui",
            )
        return PaperBuyResult(
            True, "ok", symbol, qty=decision.qty, price=current_price,
            stop_price=decision.stop_price, notional=decision.notional,
            trade_id=trade_id,
        )

    def paper_sell(self, symbol: str, *,
                   current_price: float | None = None) -> dict:
        symbol = symbol.upper()
        if current_price is None:
            q = latest_quote(self.db, symbol)
            current_price = float(q["price"]) if q and q.get("price") else 0.0
        with self._lock:
            if symbol not in self.portfolio.positions:
                return {"closed": False, "reason": "no_position"}
            if not current_price or current_price <= 0:
                return {"closed": False, "reason": "no_price_available"}
            pnl = self.portfolio.close_position(symbol, current_price)
            self._delete_position(symbol)
            self._persist_state()
            self.db.log_trade(
                symbol=symbol, side="sell", qty=0.0, price=current_price,
                mode="paper", reason="paper_sell_ui",
            )
        return {"closed": True, "symbol": symbol, "price": current_price,
                "realized_pnl": round(pnl, 2)}

    def trip_kill_switch(self, reason: str = "manual") -> None:
        with self._lock:
            self.risk.trip_kill_switch(reason=reason)

    def reset_kill_switch(self) -> None:
        with self._lock:
            self.risk.reset_kill_switch()

    def apply_stops(self, marks: Dict[str, float]) -> List[dict]:
        out: List[dict] = []
        with self._lock:
            forced = self.risk.check_stops(marks)
            for fd in forced:
                price = marks.get(fd.symbol)
                if price is None:
                    continue
                pnl = self.portfolio.close_position(fd.symbol, price)
                self._delete_position(fd.symbol)
                self.db.log_trade(symbol=fd.symbol, side=fd.side, qty=fd.qty,
                                  price=price, mode="paper",
                                  reason="stop_loss")
                out.append({"symbol": fd.symbol, "closed_at": price,
                            "realized_pnl": round(pnl, 2)})
            if out:
                self._persist_state()
        return out
