"""Tests for the watchlist scanner and the automated paper-trading engine."""
import os
import tempfile
import time

import pandas as pd

from c5.config import get_settings
from c5.data.base import HEALTH_LIVE, FeedHealth, Quote
from c5.data.provider import MarketDataProvider
from c5.db import Store
from c5.engine.confluence import ScoreInputs, score_confluence
from c5.engine.setup_detection import Setup
from c5.paper import AutoConfig, AutoTrader, PaperAccount
from c5.scanner import Opportunity, parse_watchlist, scan


def _store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return Store(path), path


def _flat_df(price=100.0, n=30):
    rows = [{"ts": i, "open": price, "high": price * 1.001,
             "low": price * 0.999, "close": price, "volume": 100000} for i in range(n)]
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["ts"], unit="s")
    return df


def _qualifying_opp(symbol="AAA", price=100.0, delayed=False):
    setup = Setup(detected=True, kind="breakout", direction="long",
                  trigger_quality=1.0, entry=price, stop=price - 1, target=price + 2)
    df = _flat_df(price)
    res = score_confluence(ScoreInputs(
        setup=setup, candles=df, rvol=2.5, spread_pct=0.05,
        catalyst_quality=1.0, regime="with", atr_pct=1.0, quote_age=2, feed_is_live=True))
    quote = Quote(symbol=symbol, price=price, source="finnhub", ts=time.time())
    health = FeedHealth(status=HEALTH_LIVE, is_live=True, delayed=delayed)
    return Opportunity(symbol, quote, df, health, setup, res)


# -- watchlist / scanning -------------------------------------------------
def test_parse_watchlist_dedup_and_clean():
    assert parse_watchlist("aapl, nvda  tsla\nAAPL") == ["AAPL", "NVDA", "TSLA"]


def test_scan_ranks_by_score_desc():
    provider = MarketDataProvider("mock")
    opps = scan(provider, ["AAA", "BBB", "CCC"], get_settings())
    scores = [o.score for o in opps]
    assert scores == sorted(scores, reverse=True)
    assert len(opps) == 3


# -- 70+ filtering --------------------------------------------------------
def test_qualifies_requires_70_and_no_critical():
    opp = _qualifying_opp()
    assert opp.score >= 70
    assert opp.qualifies is True

    # Rebuild the same strong setup but with imminent event risk (a critical
    # warning) -> it must no longer qualify for auto entry.
    crit = score_confluence(ScoreInputs(
        setup=opp.setup, candles=opp.candles, rvol=2.5, spread_pct=0.05,
        catalyst_quality=1.0, regime="with", atr_pct=1.0, quote_age=2,
        feed_is_live=True, event_risk=True))
    opp.result = crit
    assert crit.has_critical_warning is True
    assert opp.qualifies is False


# -- auto entry -----------------------------------------------------------
def test_auto_trader_opens_qualifying_trade():
    store, path = _store()
    try:
        acct = PaperAccount(store, 1000.0)
        auto = AutoTrader(acct)
        cfg = AutoConfig(enabled=True, max_alloc_per_trade=200.0, max_simultaneous=5, max_risk_pct=1.0)
        auto.step([_qualifying_opp("AAA", 100.0)], cfg)
        assert len(acct.positions) == 1
        pos = list(acct.positions.values())[0]
        assert pos.is_auto is True and pos.symbol == "AAA" and pos.side == "long"
    finally:
        store.close(); os.remove(path)


def test_auto_trader_no_entry_when_disabled():
    store, path = _store()
    try:
        acct = PaperAccount(store, 1000.0)
        auto = AutoTrader(acct)
        auto.step([_qualifying_opp()], AutoConfig(enabled=False))
        assert len(acct.positions) == 0
    finally:
        store.close(); os.remove(path)


def test_auto_trader_no_duplicate_symbol():
    store, path = _store()
    try:
        acct = PaperAccount(store, 1000.0)
        auto = AutoTrader(acct)
        cfg = AutoConfig(enabled=True)
        auto.step([_qualifying_opp("AAA", 100.0)], cfg)
        auto.step([_qualifying_opp("AAA", 100.0)], cfg)
        assert len(acct.positions) == 1  # no second trade for same symbol
    finally:
        store.close(); os.remove(path)


def test_auto_trader_respects_max_simultaneous():
    store, path = _store()
    try:
        acct = PaperAccount(store, 1000.0)
        auto = AutoTrader(acct)
        cfg = AutoConfig(enabled=True, max_simultaneous=2, max_alloc_per_trade=100.0)
        opps = [_qualifying_opp(s, 50.0) for s in ("A", "B", "C", "D")]
        auto.step(opps, cfg)
        assert len(acct.positions) == 2
    finally:
        store.close(); os.remove(path)


# -- auto exits -----------------------------------------------------------
def test_exit_on_target_and_stop():
    store, path = _store()
    try:
        acct = PaperAccount(store, 1000.0)
        auto = AutoTrader(acct)
        cfg = AutoConfig(enabled=True)
        auto.step([_qualifying_opp("AAA", 100.0)], cfg)  # entry @100, stop 99, target 102
        # Price jumps to target -> exit target hit, realized > 0.
        win = _qualifying_opp("AAA", 102.5)
        auto.step([win], AutoConfig(enabled=False))  # disabled so only exits run
        assert len(acct.positions) == 0
        assert store.realized_pnl() > 0
    finally:
        store.close(); os.remove(path)


def test_exit_on_stop_records_loss():
    store, path = _store()
    try:
        acct = PaperAccount(store, 1000.0)
        auto = AutoTrader(acct)
        auto.step([_qualifying_opp("BBB", 100.0)], AutoConfig(enabled=True))
        loss = _qualifying_opp("BBB", 98.0)  # below stop 99
        auto.step([loss], AutoConfig(enabled=False))
        assert len(acct.positions) == 0
        assert store.realized_pnl() < 0  # loss shown honestly
    finally:
        store.close(); os.remove(path)


def test_exit_on_invalidation():
    store, path = _store()
    try:
        acct = PaperAccount(store, 1000.0)
        auto = AutoTrader(acct)
        auto.step([_qualifying_opp("CCC", 100.0)], AutoConfig(enabled=True))
        # Setup no longer detected at ~same price -> invalidation exit.
        inval = _qualifying_opp("CCC", 100.5)
        inval.setup = Setup(False, "none", "none", 0.0)
        auto.step([inval], AutoConfig(enabled=False))
        assert len(acct.positions) == 0
    finally:
        store.close(); os.remove(path)


# -- labels ---------------------------------------------------------------
def test_data_label_live_and_delayed():
    assert "LIVE" in _qualifying_opp(delayed=False).data_label
    assert "DELAYED" in _qualifying_opp(delayed=True).data_label
