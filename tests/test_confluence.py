"""Tests for the C5 Confluence Score model."""
import pandas as pd

from c5.engine.confluence import (
    ALERT_THRESHOLD,
    BAND_HIGH,
    BAND_LOW,
    SCORE_LABEL,
    ScoreInputs,
    score_confluence,
)
from c5.engine.setup_detection import Setup


def _df(price=100.0, n=30):
    rows = []
    for i in range(n):
        rows.append({"ts": i, "open": price, "high": price * 1.001,
                     "low": price * 0.999, "close": price, "volume": 100000})
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["ts"], unit="s")
    return df


def _strong_setup():
    return Setup(detected=True, kind="breakout", direction="long",
                 trigger_quality=1.0, entry=100, stop=99, target=102)


def test_max_components_sum_to_100():
    from c5.engine.confluence import (MAX_CATALYST, MAX_LOCATION, MAX_REGIME,
                                      MAX_RR, MAX_RVOL, MAX_SETUP)
    assert MAX_SETUP + MAX_RVOL + MAX_LOCATION + MAX_RR + MAX_CATALYST + MAX_REGIME == 100


def test_high_band_and_alert():
    inp = ScoreInputs(
        setup=_strong_setup(), candles=_df(), rvol=2.5, spread_pct=0.05,
        catalyst_quality=1.0, regime="with", atr_pct=1.0, quote_age=2,
        feed_is_live=True,
    )
    res = score_confluence(inp)
    assert res.total >= 75
    assert res.band == BAND_HIGH
    assert res.alert is True
    assert res.label == SCORE_LABEL
    assert res.is_live is True


def test_stale_data_removes_live_and_blocks_alert():
    inp = ScoreInputs(
        setup=_strong_setup(), candles=_df(), rvol=2.5, spread_pct=0.05,
        catalyst_quality=1.0, regime="with", atr_pct=1.0,
        quote_age=120, stale_after=60, feed_is_live=True,
    )
    res = score_confluence(inp)
    # -20 stale penalty applied, live label removed, critical warning blocks alert.
    assert any(w.code == "stale_data" for w in res.warnings)
    assert res.is_live is False
    assert res.alert is False


def test_event_risk_is_critical_blocks_alert():
    inp = ScoreInputs(
        setup=_strong_setup(), candles=_df(), rvol=2.5, spread_pct=0.05,
        catalyst_quality=1.0, regime="with", atr_pct=1.0, quote_age=2,
        feed_is_live=True, event_risk=True,
    )
    res = score_confluence(inp)
    assert any(w.code == "event_risk" and w.critical for w in res.warnings)
    assert res.alert is False


def test_no_setup_low_band():
    inp = ScoreInputs(
        setup=Setup(False, "none", "none", 0.0), candles=_df(),
        rvol=0.5, spread_pct=1.0, catalyst_quality=0.0, regime="against",
        atr_pct=10.0, quote_age=2, feed_is_live=True,
    )
    res = score_confluence(inp)
    assert res.band == BAND_LOW
    assert res.total < 55
    assert res.alert is False
