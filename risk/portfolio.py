"""In-memory portfolio state for paper trading and backtests."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Dict


@dataclass
class Position:
    symbol: str
    qty: float        # positive=long, negative=short
    avg_price: float
    stop_price: float | None = None
    opened_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def market_value(self, price: float) -> float:
        return self.qty * price

    def unrealized_pnl(self, price: float) -> float:
        return (price - self.avg_price) * self.qty


@dataclass
class Portfolio:
    cash: float
    starting_equity: float
    realized_pnl: float = 0.0
    positions: Dict[str, Position] = field(default_factory=dict)
    day_start_equity: float = 0.0
    day_date: str = field(default_factory=lambda: date.today().isoformat())

    @classmethod
    def new(cls, starting_capital: float) -> "Portfolio":
        return cls(cash=starting_capital, starting_equity=starting_capital,
                   day_start_equity=starting_capital)

    def equity(self, marks: Dict[str, float] | None = None) -> float:
        marks = marks or {}
        market = 0.0
        for pos in self.positions.values():
            price = marks.get(pos.symbol, pos.avg_price)
            market += pos.market_value(price)
        return self.cash + market

    def roll_day_if_needed(self, today: str | None = None,
                           marks: Dict[str, float] | None = None) -> None:
        d = today or date.today().isoformat()
        if d != self.day_date:
            self.day_date = d
            self.day_start_equity = self.equity(marks)

    def daily_pnl(self, marks: Dict[str, float] | None = None) -> float:
        return self.equity(marks) - self.day_start_equity

    # ---- mutations ---------------------------------------------------
    def open_position(self, symbol: str, qty: float, price: float,
                      stop_price: float | None = None) -> Position:
        cost = qty * price
        self.cash -= cost
        pos = Position(symbol=symbol, qty=qty, avg_price=price, stop_price=stop_price)
        self.positions[symbol] = pos
        return pos

    def close_position(self, symbol: str, price: float) -> float:
        pos = self.positions.pop(symbol, None)
        if not pos:
            return 0.0
        proceeds = pos.qty * price
        pnl = (price - pos.avg_price) * pos.qty
        self.cash += proceeds
        self.realized_pnl += pnl
        return pnl
