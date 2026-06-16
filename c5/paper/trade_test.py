"""10-minute paper-trade test.

Opens a single simulated position and tracks it for 10 minutes (configurable),
marking to market on every refresh. It auto-closes when:
  * the 10-minute timer elapses, or
  * price hits the stop, or
  * price hits the target.

SIMULATION ONLY — nothing is sent to a brokerage.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from .account import PaperAccount, Position

STATE_IDLE = "idle"
STATE_RUNNING = "running"
STATE_DONE = "done"


@dataclass
class TradeTestState:
    status: str = STATE_IDLE
    trade_id: Optional[int] = None
    symbol: str = ""
    side: str = "long"
    started_ts: Optional[float] = None
    duration: int = 600
    entry_price: float = 0.0
    last_price: float = 0.0
    stop: Optional[float] = None
    target: Optional[float] = None
    closed_reason: str = ""
    final_pnl: Optional[float] = None
    final_pnl_pct: Optional[float] = None

    def seconds_left(self) -> int:
        if self.status != STATE_RUNNING or self.started_ts is None:
            return 0
        return max(0, int(self.duration - (time.time() - self.started_ts)))

    def elapsed(self) -> int:
        if self.started_ts is None:
            return 0
        return int(time.time() - self.started_ts)


class TradeTest:
    """Coordinates a single timed paper-trade test against a PaperAccount."""

    def __init__(self, account: PaperAccount, duration_seconds: int = 600) -> None:
        self.account = account
        self.duration = duration_seconds
        self.state = TradeTestState(duration=duration_seconds)

    @property
    def is_running(self) -> bool:
        return self.state.status == STATE_RUNNING

    def start(
        self,
        symbol: str,
        side: str,
        price: float,
        stop: Optional[float],
        target: Optional[float],
        confluence: Optional[int],
        band: Optional[str],
        mode: str,
        cash_to_risk: Optional[float] = None,
    ) -> Optional[Position]:
        if self.is_running or price <= 0:
            return None
        pos = self.account.open_position(
            symbol=symbol,
            side=side,
            price=price,
            cash_to_risk=cash_to_risk,
            stop=stop,
            target=target,
            confluence=confluence,
            band=band,
            mode=mode,
            is_test=True,
        )
        if pos is None:
            return None
        self.state = TradeTestState(
            status=STATE_RUNNING,
            trade_id=pos.trade_id,
            symbol=symbol,
            side=side,
            started_ts=time.time(),
            duration=self.duration,
            entry_price=price,
            last_price=price,
            stop=stop,
            target=target,
        )
        return pos

    def update(self, price: float) -> None:
        """Mark to market; auto-close on stop/target/timer."""
        if not self.is_running or price <= 0:
            return
        self.state.last_price = price
        s = self.state

        reason = None
        if s.side == "long":
            if s.stop is not None and price <= s.stop:
                reason = "stop hit"
            elif s.target is not None and price >= s.target:
                reason = "target hit"
        else:  # short
            if s.stop is not None and price >= s.stop:
                reason = "stop hit"
            elif s.target is not None and price <= s.target:
                reason = "target hit"

        if reason is None and s.seconds_left() <= 0:
            reason = "10-minute timer elapsed"

        if reason is not None:
            self._finish(price, reason)

    def _finish(self, price: float, reason: str) -> None:
        trade_id = self.state.trade_id
        if trade_id is None:
            return
        pos = self.account.positions.get(trade_id)
        pnl_pct = pos.unrealized_pct(price) if pos else None
        pnl = self.account.close_position(trade_id, price, reason=reason)
        self.state.status = STATE_DONE
        self.state.closed_reason = reason
        self.state.final_pnl = pnl
        self.state.final_pnl_pct = pnl_pct

    def reset(self) -> None:
        self.state = TradeTestState(duration=self.duration)
