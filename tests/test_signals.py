import pytest

from data.db import Database
from signals import (Signal, SignalEngine, earnings_surprise_signal,
                     sentiment_shift_signal, volume_spike_signal)


def test_signal_validates_confidence():
    with pytest.raises(ValueError):
        Signal("AAPL", "x", 1.5, "long")
    with pytest.raises(ValueError):
        Signal("AAPL", "x", 0.5, "sideways")


def test_volume_spike_detects_burst():
    bars = [{"volume": 1000, "close": 100} for _ in range(40)]
    bars.append({"volume": 8000, "close": 102})       # big spike, price up
    sig = volume_spike_signal("AAPL", bars, lookback=30, z_threshold=2.0)
    assert sig.confidence > 0.5
    assert sig.direction == "long"
    assert sig.inputs["z_score"] > 2.0


def test_volume_spike_silent_when_flat():
    bars = [{"volume": 1000, "close": 100} for _ in range(40)]
    bars.append({"volume": 1050, "close": 100})
    sig = volume_spike_signal("AAPL", bars, lookback=30, z_threshold=2.0)
    assert sig.confidence == 0.0
    assert sig.direction == "flat"


def test_volume_spike_insufficient_history():
    bars = [{"volume": 1000, "close": 100} for _ in range(5)]
    sig = volume_spike_signal("AAPL", bars, lookback=30)
    assert sig.confidence == 0.0
    assert sig.inputs["reason"] == "insufficient_history"


def test_earnings_surprise_beat():
    row = {"eps_estimate": 1.00, "eps_actual": 1.20, "event_date": "2026-04-23"}
    sig = earnings_surprise_signal("AAPL", row, saturation_pct=0.20)
    assert sig.direction == "long"
    assert sig.confidence == 1.0


def test_earnings_surprise_miss():
    row = {"eps_estimate": 1.00, "eps_actual": 0.90}
    sig = earnings_surprise_signal("AAPL", row, saturation_pct=0.20)
    assert sig.direction == "short"
    assert 0.4 < sig.confidence < 0.6


def test_earnings_surprise_no_data():
    sig = earnings_surprise_signal("AAPL", None)
    assert sig.confidence == 0.0
    assert sig.direction == "flat"


def test_sentiment_shift_bullish():
    samples = [{"ts": f"2026-05-{d:02d}T00:00:00+00:00", "score": -0.2}
               for d in range(1, 18)]
    samples += [{"ts": "2026-05-19T00:00:00+00:00", "score": 0.6},
                {"ts": "2026-05-20T00:00:00+00:00", "score": 0.8},
                {"ts": "2026-05-20T12:00:00+00:00", "score": 0.7}]
    sig = sentiment_shift_signal("AAPL", samples,
                                 short_window=3, long_window=20)
    assert sig.direction == "long"
    assert sig.confidence > 0.5


def test_engine_logs_signals(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    # seed prices
    bars = [{"symbol": "AAPL", "ts": f"2026-05-19T{h:02d}:00:00+00:00",
             "open": 100, "high": 101, "low": 99, "close": 100,
             "volume": 1000, "source": "yfinance"} for h in range(10)]
    bars.append({"symbol": "AAPL", "ts": "2026-05-19T10:00:00+00:00",
                 "open": 100, "high": 105, "low": 100, "close": 104,
                 "volume": 50000, "source": "yfinance"})
    db.insert_prices(bars)

    engine = SignalEngine(db, persist=True)
    sigs = engine.evaluate("AAPL")
    # We should have one of each signal type.
    types = {s.signal_type for s in sigs}
    assert {"volume_spike", "earnings_surprise", "sentiment_shift"} <= types

    # signals were logged
    logged = db.fetch_signals("AAPL")
    assert len(logged) == len(sigs)
    db.close()


def test_engine_aggregate_balanced_is_flat():
    db_long = Signal("AAPL", "a", 0.6, "long")
    db_short = Signal("AAPL", "b", 0.55, "short")
    from signals.engine import SignalEngine
    eng = SignalEngine.__new__(SignalEngine)
    agg = eng.aggregate([db_long, db_short])
    assert agg.direction == "flat"


def test_engine_aggregate_picks_winner():
    sigs = [
        Signal("AAPL", "a", 0.8, "long"),
        Signal("AAPL", "b", 0.7, "long"),
        Signal("AAPL", "c", 0.2, "short"),
    ]
    from signals.engine import SignalEngine
    eng = SignalEngine.__new__(SignalEngine)
    agg = eng.aggregate(sigs)
    assert agg.direction == "long"
    assert agg.confidence > 0
