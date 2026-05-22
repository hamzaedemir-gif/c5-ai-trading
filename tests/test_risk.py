import pytest

from risk import Portfolio, RiskManager
from signals.base import Signal


def make_signal(direction="long", confidence=0.8):
    return Signal("AAPL", "test", confidence, direction, inputs={})


def test_portfolio_open_close_pnl():
    p = Portfolio.new(10_000)
    p.open_position("AAPL", qty=10, price=100, stop_price=97)
    assert p.cash == 9_000
    pnl = p.close_position("AAPL", price=105)
    assert pnl == 50
    assert p.cash == 10_050
    assert p.realized_pnl == 50


def test_risk_approves_long_with_correct_sizing():
    p = Portfolio.new(10_000)
    rm = RiskManager(p, position_pct=0.02, stop_loss_pct=0.03)
    dec = rm.evaluate(make_signal("long", 0.8), price=100)
    assert dec.approved
    assert dec.side == "buy"
    # 2% of 10k = $200 / $100 = 2 shares
    assert dec.qty == 2.0
    assert dec.stop_price == round(100 * 0.97, 4)
    assert dec.mode == "paper"


def test_risk_rejects_low_confidence():
    rm = RiskManager(Portfolio.new(10_000))
    dec = rm.evaluate(make_signal("long", 0.3), price=100)
    assert not dec.approved
    assert "low_confidence" in dec.reason


def test_risk_rejects_flat_direction():
    rm = RiskManager(Portfolio.new(10_000))
    dec = rm.evaluate(make_signal("flat", 0.9), price=100)
    assert not dec.approved


def test_kill_switch_blocks_everything():
    rm = RiskManager(Portfolio.new(10_000))
    rm.trip_kill_switch("test")
    dec = rm.evaluate(make_signal("long", 0.9), price=100)
    assert not dec.approved
    assert dec.reason == "kill_switch_active"


def test_daily_loss_limit_trips_kill_switch():
    p = Portfolio.new(10_000)
    # Simulate big realized loss already today.
    p.realized_pnl = -600
    p.cash = 9_400
    rm = RiskManager(p, daily_max_loss_pct=0.05)  # 5% of 10k = $500
    dec = rm.evaluate(make_signal("long", 0.9), price=100)
    assert not dec.approved
    assert dec.reason == "daily_max_loss_breached"
    assert rm.kill_switch


def test_no_stacking_into_existing_position():
    p = Portfolio.new(10_000)
    p.open_position("AAPL", qty=2, price=100, stop_price=97)
    rm = RiskManager(p)
    dec = rm.evaluate(make_signal("long", 0.9), price=101)
    assert not dec.approved
    assert dec.reason == "position_already_open"


def test_check_stops_triggers_long_stop():
    p = Portfolio.new(10_000)
    p.open_position("AAPL", qty=2, price=100, stop_price=97)
    rm = RiskManager(p)
    decisions = rm.check_stops({"AAPL": 96.5})
    assert len(decisions) == 1
    assert decisions[0].reason == "stop_loss"
    assert decisions[0].side == "sell"


def test_check_stops_triggers_short_stop():
    p = Portfolio.new(10_000)
    p.open_position("AAPL", qty=-2, price=100, stop_price=103)
    rm = RiskManager(p)
    decisions = rm.check_stops({"AAPL": 103.5})
    assert len(decisions) == 1
    assert decisions[0].side == "buy"


def test_short_signal_sets_stop_above_price():
    p = Portfolio.new(10_000)
    rm = RiskManager(p, position_pct=0.02, stop_loss_pct=0.03)
    dec = rm.evaluate(make_signal("short", 0.8), price=100)
    assert dec.approved
    assert dec.side == "sell"
    assert dec.stop_price == round(100 * 1.03, 4)


def test_live_mode_requires_explicit_opt_in():
    rm = RiskManager(Portfolio.new(10_000), mode="live")
    dec = rm.evaluate(make_signal("long", 0.9), price=100)
    assert dec.mode == "live"
    with pytest.raises(ValueError):
        RiskManager(Portfolio.new(10_000), mode="real_money_please")
