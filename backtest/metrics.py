"""Performance metrics for a backtest run."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass
class BacktestMetrics:
    n_trades: int
    n_wins: int
    n_losses: int
    win_rate: float
    avg_gain: float
    avg_loss: float
    total_pnl: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe: float
    final_equity: float
    starting_equity: float

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def compute_metrics(equity_curve: Sequence[float],
                    trade_pnls: Sequence[float],
                    starting_equity: float) -> BacktestMetrics:
    """Derive headline metrics from an equity curve and a list of trade PnLs."""
    n_trades = len(trade_pnls)
    wins = [p for p in trade_pnls if p > 0]
    losses = [p for p in trade_pnls if p < 0]

    win_rate = len(wins) / n_trades if n_trades else 0.0
    avg_gain = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    total_pnl = sum(trade_pnls)

    max_dd, max_dd_pct = _max_drawdown(equity_curve)

    sharpe = _sharpe(equity_curve)

    final = equity_curve[-1] if equity_curve else starting_equity
    return BacktestMetrics(
        n_trades=n_trades,
        n_wins=len(wins),
        n_losses=len(losses),
        win_rate=round(win_rate, 4),
        avg_gain=round(avg_gain, 4),
        avg_loss=round(avg_loss, 4),
        total_pnl=round(total_pnl, 4),
        max_drawdown=round(max_dd, 4),
        max_drawdown_pct=round(max_dd_pct, 4),
        sharpe=round(sharpe, 4),
        final_equity=round(final, 4),
        starting_equity=starting_equity,
    )


def _max_drawdown(equity: Sequence[float]) -> tuple[float, float]:
    if not equity:
        return 0.0, 0.0
    peak = equity[0]
    max_dd = 0.0
    max_dd_pct = 0.0
    for v in equity:
        if v > peak:
            peak = v
        dd = peak - v
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = dd / peak if peak > 0 else 0.0
    return max_dd, max_dd_pct


def _sharpe(equity: Sequence[float], periods_per_year: int = 252) -> float:
    if len(equity) < 2:
        return 0.0
    rets = []
    for i in range(1, len(equity)):
        prev = equity[i - 1]
        if prev == 0:
            continue
        rets.append((equity[i] - prev) / prev)
    if not rets:
        return 0.0
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    std = math.sqrt(var)
    if std == 0:
        return 0.0
    return (mean / std) * math.sqrt(periods_per_year)
