"""$1,000 paper-trading account.

SIMULATION ONLY. No orders are routed to any venue or brokerage. "Buying" and
"selling" simply adjust simulated cash and an in-memory position, persisted to
SQLite for the trade log. Supports long and short paper positions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from ..db.store import Store


@dataclass
class Position:
    symbol: str
    side: str          # "long" | "short"
    qty: float
    entry_price: float
    stop: Optional[float] = None
    target: Optional[float] = None
    trade_id: Optional[int] = None
    is_test: bool = False
    is_auto: bool = False
    setup: str = ""
    opened_ts: float = 0.0
    duration: int = 600  # seconds until time-exit

    def unrealized_pnl(self, price: float) -> float:
        if self.side == "long":
            return (price - self.entry_price) * self.qty
        return (self.entry_price - price) * self.qty

    def unrealized_pct(self, price: float) -> float:
        cost = self.entry_price * self.qty
        if cost <= 0:
            return 0.0
        return 100.0 * self.unrealized_pnl(price) / cost


class PaperAccount:
    def __init__(self, store: Store, starting_cash: float = 1000.0) -> None:
        self.store = store
        self.starting_cash = float(starting_cash)
        self.cash = float(starting_cash)
        self.positions: Dict[int, Position] = {}
        self._rehydrate()

    def _rehydrate(self) -> None:
        """Rebuild state from any open trades + realized P/L already in the DB."""
        realized = self.store.realized_pnl()
        self.cash = self.starting_cash + realized
        for row in self.store.get_open_trades():
            pos = Position(
                symbol=row["symbol"],
                side=row["side"],
                qty=row["qty"],
                entry_price=row["entry_price"],
                stop=row["stop"],
                target=row["target"],
                trade_id=row["id"],
                is_test=bool(row["is_test"]),
                is_auto=bool(row["is_auto"]) if "is_auto" in row.keys() else False,
                setup=row["setup"] if "setup" in row.keys() and row["setup"] else "",
                opened_ts=row["opened_ts"] or 0.0,
            )
            self.positions[row["id"]] = pos
            # Reserve the cost of open long positions against cash.
            if pos.side == "long":
                self.cash -= pos.entry_price * pos.qty

    # -- trading ---------------------------------------------------------
    def open_position(
        self,
        symbol: str,
        side: str,
        price: float,
        cash_to_risk: Optional[float] = None,
        qty: Optional[float] = None,
        stop: Optional[float] = None,
        target: Optional[float] = None,
        confluence: Optional[int] = None,
        band: Optional[str] = None,
        mode: str = "mock",
        is_test: bool = False,
        is_auto: bool = False,
        setup: str = "",
        feed_label: str = "",
        reasons: str = "",
        warnings: str = "",
        duration: int = 600,
    ) -> Optional[Position]:
        """Open a simulated position. Sizes by cash if qty not given."""
        if price <= 0:
            return None
        if qty is None:
            budget = cash_to_risk if cash_to_risk is not None else self.cash
            budget = min(budget, self.cash) if side == "long" else budget
            qty = max(0.0, budget / price)
        if qty <= 0:
            return None
        # Don't let a long position exceed available cash.
        if side == "long" and price * qty > self.cash + 1e-9:
            qty = max(0.0, self.cash / price)
        if qty <= 0:
            return None

        import time as _t

        opened = _t.time()
        trade_id = self.store.insert_trade(
            {
                "opened_ts": opened,
                "closed_ts": None,
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "entry_price": price,
                "exit_price": None,
                "stop": stop,
                "target": target,
                "status": "open",
                "pnl": None,
                "pnl_pct": None,
                "confluence": confluence,
                "band": band,
                "mode": mode,
                "reason": "",
                "is_test": 1 if is_test else 0,
                "setup": setup,
                "feed_label": feed_label,
                "is_auto": 1 if is_auto else 0,
                "reasons": reasons,
                "warnings": warnings,
            }
        )
        pos = Position(symbol, side, qty, price, stop, target, trade_id,
                       is_test=is_test, is_auto=is_auto, setup=setup,
                       opened_ts=opened, duration=duration)
        self.positions[trade_id] = pos
        if side == "long":
            self.cash -= price * qty
        return pos

    def close_position(self, trade_id: int, price: float, reason: str = "manual") -> Optional[float]:
        pos = self.positions.get(trade_id)
        if pos is None or price <= 0:
            return None
        pnl = pos.unrealized_pnl(price)
        pnl_pct = pos.unrealized_pct(price)
        # Return reserved capital (long) plus P/L; for shorts just credit P/L.
        if pos.side == "long":
            self.cash += pos.entry_price * pos.qty + pnl
        else:
            self.cash += pnl
        self.store.close_trade(trade_id, price, pnl, pnl_pct, reason)
        del self.positions[trade_id]
        return pnl

    # -- valuation -------------------------------------------------------
    def open_unrealized(self, price_by_symbol: Dict[str, float]) -> float:
        total = 0.0
        for pos in self.positions.values():
            price = price_by_symbol.get(pos.symbol, pos.entry_price)
            total += pos.unrealized_pnl(price)
        return total

    def reserved_cash(self) -> float:
        return sum(p.entry_price * p.qty for p in self.positions.values() if p.side == "long")

    def equity(self, price_by_symbol: Dict[str, float]) -> float:
        return self.cash + self.reserved_cash() + self.open_unrealized(price_by_symbol)

    def realized_pnl(self) -> float:
        return self.store.realized_pnl()

    @property
    def open_positions(self) -> List[Position]:
        return list(self.positions.values())

    def snapshot(self, price_by_symbol: Dict[str, float]) -> None:
        self.store.snapshot_account(
            cash=self.cash,
            equity=self.equity(price_by_symbol),
            realized=self.realized_pnl(),
            open_positions=len(self.positions),
        )
