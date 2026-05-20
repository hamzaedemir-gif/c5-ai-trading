from backtest import Backtester, compute_metrics
from signals.base import Signal


def test_metrics_basic():
    equity = [10_000, 10_100, 10_050, 10_200, 10_150]
    pnls = [100, -50, 150, -50]
    m = compute_metrics(equity, pnls, 10_000)
    assert m.n_trades == 4
    assert m.n_wins == 2
    assert m.n_losses == 2
    assert m.win_rate == 0.5
    assert m.avg_gain == 125.0
    assert m.avg_loss == -50.0
    assert m.max_drawdown >= 50
    assert m.final_equity == 10_150


def test_metrics_handles_empty():
    m = compute_metrics([], [], 10_000)
    assert m.n_trades == 0
    assert m.win_rate == 0
    assert m.sharpe == 0
    assert m.final_equity == 10_000


def _always_long(conf=0.9):
    def fn(sym, hist):
        return Signal(sym, "test_always_long", conf, "long", inputs={})
    return fn


def _never_signal():
    def fn(sym, hist):
        return Signal(sym, "test_flat", 0.0, "flat", inputs={})
    return fn


def _bars(prices, ts_prefix="2026-05-19T", start_hour=9):
    out = []
    for i, p in enumerate(prices):
        h = start_hour + i
        out.append({"symbol": "AAPL",
                    "ts": f"{ts_prefix}{h:02d}:00:00+00:00",
                    "open": p, "high": p, "low": p, "close": p,
                    "volume": 1000})
    return out


def test_backtest_profitable_uptrend():
    # gentle uptrend so we don't trip the 3% stop
    bars = _bars([100 + 0.2 * i for i in range(60)])
    bt = Backtester(starting_capital=10_000, signal_fn=_always_long(),
                    position_pct=0.10, max_hold_bars=5)
    res = bt.run("AAPL", bars)
    assert res.metrics.n_trades > 0
    assert res.metrics.total_pnl > 0
    assert res.metrics.final_equity > 10_000


def test_backtest_stop_loss_caps_loss():
    # gradual decline -> stop should fire near the 3% threshold
    prices = [100] * 3 + [100, 99.5, 99, 98.5, 98, 97.5, 96.8, 96, 95, 94, 93]
    bars = _bars(prices)
    bt = Backtester(starting_capital=10_000, signal_fn=_always_long(),
                    position_pct=0.10, stop_loss_pct=0.03, max_hold_bars=50)
    res = bt.run("AAPL", bars)
    # Loss capped at ~stop_loss_pct of notional plus a small overshoot.
    if res.trade_pnls:
        notional = 10_000 * 0.10
        worst = min(res.trade_pnls)
        assert worst > -(notional * 0.06)


def test_backtest_no_signals_no_trades():
    bars = _bars([100 + i for i in range(20)])
    bt = Backtester(starting_capital=10_000, signal_fn=_never_signal())
    res = bt.run("AAPL", bars)
    assert res.metrics.n_trades == 0
    assert res.metrics.final_equity == 10_000


def test_backtest_empty_input():
    bt = Backtester(starting_capital=5_000)
    res = bt.run("AAPL", [])
    assert res.metrics.final_equity == 5_000
    assert res.metrics.n_trades == 0
