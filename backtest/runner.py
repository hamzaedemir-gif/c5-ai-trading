"""Replay historical bars through the signal + risk engine.

Designed to be deterministic and dependency-free at test time: the runner
takes plain dicts (the same shape the data layer produces) and operates on
in-memory portfolios.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Sequence

from risk import Portfolio, RiskManager
from signals import volume_spike_signal

from .metrics import BacktestMetrics, compute_metrics

# Strategy callable signature: (symbol, history_so_far) -> Signal
SignalFn = Callable[[str, Sequence[dict]], "object"]


@dataclass
class BacktestResult:
    metrics: BacktestMetrics
    equity_curve: List[float] = field(default_factory=list)
    trade_pnls: List[float] = field(default_factory=list)
    trade_log: List[dict] = field(default_factory=list)


class Backtester:
    """Bar-by-bar replay.

    For each bar:
      1. Mark the open position (if any) and check stops.
      2. Build the history-so-far window and call the signal function.
      3. If approved by the risk manager, open a position at the bar's close.
      4. Record equity.
    """

    def __init__(self, *, starting_capital: float = 10_000.0,
                 signal_fn: SignalFn | None = None,
                 position_pct: float = 0.02,
                 stop_loss_pct: float = 0.03,
                 daily_max_loss_pct: float = 0.05,
                 min_confidence: float = 0.5,
                 max_hold_bars: int = 30):
        self.starting_capital = starting_capital
        self.signal_fn = signal_fn or (lambda sym, hist: volume_spike_signal(sym, hist))
        self.position_pct = position_pct
        self.stop_loss_pct = stop_loss_pct
        self.daily_max_loss_pct = daily_max_loss_pct
        self.min_confidence = min_confidence
        self.max_hold_bars = max_hold_bars

    def run(self, symbol: str, bars: Sequence[dict]) -> BacktestResult:
        if not bars:
            metrics = compute_metrics([self.starting_capital], [], self.starting_capital)
            return BacktestResult(metrics=metrics, equity_curve=[self.starting_capital])

        portfolio = Portfolio.new(self.starting_capital)
        rm = RiskManager(portfolio,
                         position_pct=self.position_pct,
                         stop_loss_pct=self.stop_loss_pct,
                         daily_max_loss_pct=self.daily_max_loss_pct,
                         min_confidence=self.min_confidence)

        equity_curve: List[float] = []
        trade_pnls: List[float] = []
        trade_log: List[dict] = []
        bars_held = 0

        for i, bar in enumerate(bars):
            price = float(bar.get("close") or 0)
            marks = {symbol: price} if price > 0 else {}

            # roll-over day boundaries based on bar timestamp date prefix
            ts = str(bar.get("ts", ""))
            today = ts[:10] if len(ts) >= 10 else None
            portfolio.roll_day_if_needed(today=today, marks=marks)

            # 1) stop-loss check
            for forced in rm.check_stops(marks):
                if forced.symbol in portfolio.positions:
                    pnl = portfolio.close_position(forced.symbol, price)
                    trade_pnls.append(pnl)
                    trade_log.append({"bar": i, "ts": ts, "side": forced.side,
                                      "price": price, "pnl": pnl, "reason": "stop_loss"})
                    bars_held = 0

            # 2) timeout exit
            if symbol in portfolio.positions:
                bars_held += 1
                if bars_held >= self.max_hold_bars:
                    pnl = portfolio.close_position(symbol, price)
                    trade_pnls.append(pnl)
                    trade_log.append({"bar": i, "ts": ts, "side": "sell",
                                      "price": price, "pnl": pnl, "reason": "timeout"})
                    bars_held = 0

            # 3) generate signal from history so far (excluding lookahead)
            history = list(bars[: i + 1])
            sig = self.signal_fn(symbol, history)
            decision = rm.evaluate(sig, price=price, marks=marks)

            if decision.approved and decision.side in ("buy", "sell"):
                # backtest only handles long entries for simplicity
                if decision.side == "buy":
                    portfolio.open_position(symbol, qty=decision.qty,
                                            price=price, stop_price=decision.stop_price)
                    bars_held = 0
                    trade_log.append({"bar": i, "ts": ts, "side": "buy",
                                      "price": price, "qty": decision.qty,
                                      "stop": decision.stop_price,
                                      "reason": "signal"})

            equity_curve.append(portfolio.equity(marks))

        # Close any remaining position at the final price
        if symbol in portfolio.positions:
            last_price = float(bars[-1].get("close") or 0)
            pnl = portfolio.close_position(symbol, last_price)
            trade_pnls.append(pnl)
            trade_log.append({"bar": len(bars) - 1, "side": "sell",
                              "price": last_price, "pnl": pnl, "reason": "eod_close"})
            equity_curve[-1] = portfolio.equity({})

        metrics = compute_metrics(equity_curve, trade_pnls, self.starting_capital)
        return BacktestResult(metrics=metrics, equity_curve=equity_curve,
                              trade_pnls=trade_pnls, trade_log=trade_log)
