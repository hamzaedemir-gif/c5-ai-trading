"""Risk manager: gates every signal before it becomes an order."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

from signals.base import DIRECTION_FLAT, DIRECTION_LONG, DIRECTION_SHORT, Signal

from .portfolio import Portfolio

log = logging.getLogger(__name__)


@dataclass
class RiskDecision:
    approved: bool
    reason: str
    symbol: str
    side: str           # buy | sell | hold
    qty: float = 0.0
    stop_price: float | None = None
    notional: float = 0.0
    mode: str = "paper"


class RiskRejected(Exception):
    pass


class RiskManager:
    """Enforces position sizing, stop-loss, daily-loss limit, and kill switch.

    Defaults to paper mode. Live mode must be explicitly opted into; even
    then, this layer never places an order itself — it only approves or
    rejects. Order routing is a separate concern.
    """

    MIN_CONFIDENCE = 0.5

    def __init__(self, portfolio: Portfolio, *,
                 position_pct: float = 0.02,
                 stop_loss_pct: float = 0.03,
                 daily_max_loss_pct: float = 0.05,
                 mode: str = "paper",
                 min_confidence: float | None = None):
        if mode not in ("paper", "live"):
            raise ValueError(f"unknown mode: {mode}")
        self.portfolio = portfolio
        self.position_pct = position_pct
        self.stop_loss_pct = stop_loss_pct
        self.daily_max_loss_pct = daily_max_loss_pct
        self.mode = mode
        self.kill_switch = False
        self.min_confidence = min_confidence if min_confidence is not None else self.MIN_CONFIDENCE

    # ---- safety controls ---------------------------------------------
    def trip_kill_switch(self, reason: str = "manual") -> None:
        log.warning("KILL SWITCH tripped: %s", reason)
        self.kill_switch = True

    def reset_kill_switch(self) -> None:
        self.kill_switch = False

    def daily_loss_breached(self, marks: Dict[str, float] | None = None) -> bool:
        self.portfolio.roll_day_if_needed(marks=marks)
        pnl = self.portfolio.daily_pnl(marks)
        max_loss = self.portfolio.day_start_equity * self.daily_max_loss_pct
        return pnl <= -max_loss

    # ---- evaluation --------------------------------------------------
    def evaluate(self, signal: Signal, price: float,
                 marks: Dict[str, float] | None = None) -> RiskDecision:
        sym = signal.symbol

        if self.kill_switch:
            return self._reject(sym, "kill_switch_active")

        if self.daily_loss_breached(marks):
            self.trip_kill_switch("daily_max_loss")
            return self._reject(sym, "daily_max_loss_breached")

        if signal.direction == DIRECTION_FLAT or signal.confidence < self.min_confidence:
            return self._reject(sym, f"low_confidence({signal.confidence:.2f})", side="hold")

        if price <= 0:
            return self._reject(sym, "non_positive_price")

        # Don't stack into an existing position; let the manager close first.
        if sym in self.portfolio.positions:
            return self._reject(sym, "position_already_open", side="hold")

        equity = self.portfolio.equity(marks)
        notional = equity * self.position_pct
        qty = notional / price
        if qty <= 0:
            return self._reject(sym, "qty_rounded_to_zero")

        if notional > self.portfolio.cash:
            return self._reject(sym, "insufficient_cash")

        if signal.direction == DIRECTION_LONG:
            side = "buy"
            stop = price * (1.0 - self.stop_loss_pct)
        else:  # DIRECTION_SHORT
            side = "sell"
            stop = price * (1.0 + self.stop_loss_pct)

        return RiskDecision(
            approved=True,
            reason="ok",
            symbol=sym,
            side=side,
            qty=round(qty, 6),
            stop_price=round(stop, 4),
            notional=round(notional, 2),
            mode=self.mode,
        )

    def check_stops(self, marks: Dict[str, float]) -> list[RiskDecision]:
        """Return forced-close decisions for any positions that hit their stop."""
        out: list[RiskDecision] = []
        for sym, pos in list(self.portfolio.positions.items()):
            price = marks.get(sym)
            if price is None or pos.stop_price is None:
                continue
            triggered = (
                (pos.qty > 0 and price <= pos.stop_price) or
                (pos.qty < 0 and price >= pos.stop_price)
            )
            if triggered:
                out.append(RiskDecision(
                    approved=True, reason="stop_loss",
                    symbol=sym, side="sell" if pos.qty > 0 else "buy",
                    qty=abs(pos.qty), stop_price=pos.stop_price,
                    notional=abs(pos.qty * price), mode=self.mode,
                ))
        return out

    # ---- helpers -----------------------------------------------------
    def _reject(self, symbol: str, reason: str, side: str = "hold") -> RiskDecision:
        return RiskDecision(
            approved=False, reason=reason, symbol=symbol, side=side,
            qty=0.0, mode=self.mode,
        )
