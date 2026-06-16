"""Tests for the paper account and 10-minute trade test."""
import os
import tempfile

from c5.db import Store
from c5.paper import PaperAccount, TradeTest


def _store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return Store(path), path


def test_long_profit_updates_cash_and_realized():
    store, path = _store()
    try:
        acct = PaperAccount(store, starting_cash=1000.0)
        pos = acct.open_position("AAA", "long", price=100.0, cash_to_risk=500.0, mode="mock")
        assert pos is not None
        assert acct.cash == 500.0  # 500 reserved into the position
        pnl = acct.close_position(pos.trade_id, price=110.0)
        assert pnl is not None and pnl > 0
        # 5 shares * $10 gain = $50 realized; cash back to 1050.
        assert round(acct.cash, 2) == 1050.0
        assert round(acct.realized_pnl(), 2) == 50.0
    finally:
        store.close()
        os.remove(path)


def test_short_pnl():
    store, path = _store()
    try:
        acct = PaperAccount(store, starting_cash=1000.0)
        pos = acct.open_position("BBB", "short", price=100.0, qty=2.0, mode="mock")
        pnl = acct.close_position(pos.trade_id, price=90.0)
        assert round(pnl, 2) == 20.0  # short gains when price falls
    finally:
        store.close()
        os.remove(path)


def test_trade_test_auto_closes_on_target():
    store, path = _store()
    try:
        acct = PaperAccount(store, starting_cash=1000.0)
        tt = TradeTest(acct, duration_seconds=600)
        tt.start("CCC", "long", price=100.0, stop=99.0, target=102.0,
                 confluence=80, band="High", mode="mock", cash_to_risk=300.0)
        assert tt.is_running
        tt.update(102.5)  # hits target
        assert tt.state.status == "done"
        assert tt.state.closed_reason == "target hit"
        assert tt.state.final_pnl is not None and tt.state.final_pnl > 0
    finally:
        store.close()
        os.remove(path)
