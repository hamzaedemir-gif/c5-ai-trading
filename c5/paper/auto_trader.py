"""Automated paper-trading engine.

SIMULATION ONLY. This NEVER routes a real order or touches a brokerage. When
enabled, it opens simulated positions for qualifying scanner opportunities
(Confluence Score >= 70, no critical warning, valid entry/stop/target) and
closes them on predefined rules — target, stop, time exit, setup invalidation,
or a critical warning. Losses are recorded honestly.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..scanner import Opportunity
from .account import PaperAccount, Position

EXIT_TARGET = "target hit"
EXIT_STOP = "stop hit"
EXIT_TIME = "10-minute time exit"
EXIT_INVALIDATED = "setup invalidated"
EXIT_CRITICAL = "critical warning"


@dataclass
class AutoConfig:
    enabled: bool = False
    min_score: int = 70
    max_alloc_per_trade: float = 200.0
    max_simultaneous: int = 5
    max_risk_pct: float = 1.0      # percent of paper equity risked per trade
    duration_seconds: int = 600    # 10-minute time exit


@dataclass
class AutoTrader:
    account: PaperAccount
    log: List[str] = field(default_factory=list)

    # -- public step -----------------------------------------------------
    def step(self, opps: List[Opportunity], config: AutoConfig) -> List[str]:
        """Run one engine cycle: exits first, then (if enabled) entries."""
        actions: List[str] = []
        by_symbol: Dict[str, Opportunity] = {o.symbol: o for o in opps}

        actions += self._process_exits(by_symbol, config)
        if config.enabled:
            actions += self._process_entries(opps, by_symbol, config)

        for a in actions:
            self.log.append(f"{time.strftime('%H:%M:%S')}  {a}")
        self.log = self.log[-100:]
        return actions

    # -- exits -----------------------------------------------------------
    def _process_exits(self, by_symbol: Dict[str, Opportunity], config: AutoConfig) -> List[str]:
        actions: List[str] = []
        for trade_id, pos in list(self.account.positions.items()):
            opp = by_symbol.get(pos.symbol)
            price = opp.quote.price if (opp and opp.quote.price > 0) else None
            if price is None:
                continue
            reason = self._exit_reason(pos, price, opp, config)
            if reason:
                pnl = self.account.close_position(trade_id, price, reason=reason)
                actions.append(
                    f"EXIT {pos.symbol} @ {price:.4f} — {reason} "
                    f"(P/L ${0.0 if pnl is None else pnl:+.2f})"
                )
        return actions

    def _exit_reason(
        self, pos: Position, price: float, opp: Optional[Opportunity], config: AutoConfig
    ) -> Optional[str]:
        # Stop / target (direction-aware).
        if pos.side == "long":
            if pos.stop is not None and price <= pos.stop:
                return EXIT_STOP
            if pos.target is not None and price >= pos.target:
                return EXIT_TARGET
        else:  # short
            if pos.stop is not None and price >= pos.stop:
                return EXIT_STOP
            if pos.target is not None and price <= pos.target:
                return EXIT_TARGET

        # Time exit.
        if pos.opened_ts and (time.time() - pos.opened_ts) >= pos.duration:
            return EXIT_TIME

        # Critical warning / setup invalidation from the live scan.
        if opp is not None and opp.result is not None:
            if opp.result.has_critical_warning:
                return EXIT_CRITICAL
            still_valid = opp.setup.detected and opp.setup.direction == pos.side
            if not still_valid:
                return EXIT_INVALIDATED
        return None

    # -- entries ---------------------------------------------------------
    def _process_entries(
        self, opps: List[Opportunity], by_symbol: Dict[str, Opportunity], config: AutoConfig
    ) -> List[str]:
        actions: List[str] = []
        open_symbols = {p.symbol for p in self.account.positions.values()}
        price_map = {o.symbol: o.quote.price for o in opps if o.quote.price > 0}
        equity = self.account.equity(price_map)

        # Best scores first.
        for opp in sorted(opps, key=lambda o: o.score, reverse=True):
            if len(self.account.positions) >= config.max_simultaneous:
                break
            if not opp.qualifies or opp.result.total < config.min_score:
                continue
            if opp.symbol in open_symbols:
                continue  # no duplicate open trade for the same symbol

            qty = self._size(opp, equity, config)
            if qty <= 0:
                continue

            feed_label = opp.data_label
            using_real = opp.quote.source == "finnhub" and opp.health.is_live
            note_src = feed_label if using_real else f"{feed_label} (non-real data)"
            pos = self.account.open_position(
                symbol=opp.symbol,
                side=opp.setup.direction,
                price=opp.quote.price,
                qty=qty,
                stop=opp.setup.stop,
                target=opp.setup.target,
                confluence=opp.result.total,
                band=opp.result.band,
                mode=opp.quote.source or "mock",
                is_auto=True,
                setup=opp.setup.kind,
                feed_label=note_src,
                reasons=" | ".join(opp.result.reasons[:6]),
                warnings=" | ".join(opp.result.warnings_text()),
                duration=config.duration_seconds,
            )
            if pos:
                open_symbols.add(opp.symbol)
                actions.append(
                    f"ENTER {opp.symbol} {opp.setup.direction} {opp.setup.kind} "
                    f"@ {opp.quote.price:.4f} (score {opp.result.total}, {note_src})"
                )
        return actions

    def _size(self, opp: Opportunity, equity: float, config: AutoConfig) -> float:
        """Position size: risk-based, capped by max allocation and cash."""
        price = opp.quote.price
        if price <= 0:
            return 0.0
        risk_per_share = abs(opp.setup.entry - opp.setup.stop) if opp.setup.stop else 0.0
        risk_dollars = max(0.0, equity * config.max_risk_pct / 100.0)

        qty_alloc = config.max_alloc_per_trade / price
        qty_risk = (risk_dollars / risk_per_share) if risk_per_share > 0 else qty_alloc
        qty = min(qty_alloc, qty_risk)

        # Never exceed available cash on a long.
        if opp.setup.direction == "long":
            qty = min(qty, self.account.cash / price)
        return max(0.0, qty)
