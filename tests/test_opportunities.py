from api.opportunities import (compute_hit_rate, estimate_outcome_range,
                                list_opportunities)
from data.db import Database


def test_outcome_range_always_shows_downside():
    import random
    random.seed(42)
    bars = []
    p = 100.0
    for _ in range(60):
        p *= 1 + random.uniform(-0.01, 0.015)   # noisy uptrend
        bars.append({"close": p})
    rng = estimate_outcome_range(bars, direction="long",
                                 confidence=0.95, horizon_days=5)
    # Downside must remain strictly negative even on a high-confidence long.
    assert rng.downside_pct < 0
    assert rng.upside_pct > 0
    assert rng.volatility_pct > 0


def test_outcome_range_handles_zero_volatility():
    bars = [{"close": 100.0} for _ in range(40)]
    rng = estimate_outcome_range(bars, direction="long",
                                 confidence=0.8, horizon_days=5)
    # Floor kicks in so we never advertise zero risk.
    assert rng.volatility_pct > 0
    assert rng.downside_pct < 0


def test_outcome_range_symmetric_for_flat_signal():
    bars = []
    p = 100
    for i in range(60):
        p += (1 if i % 2 == 0 else -1)
        bars.append({"close": p})
    rng = estimate_outcome_range(bars, direction="flat",
                                 confidence=0.0, horizon_days=5)
    # Expected midpoint ~0; upside and downside roughly mirror.
    assert abs(rng.expected_pct) < 0.5
    assert abs(rng.upside_pct + rng.downside_pct) < 0.5


def test_list_opportunities_returns_disclaimer_and_reasons(tmp_path):
    db = Database(tmp_path / "opp.sqlite")
    # seed price history with a clear volume spike on the latest bar
    bars = []
    for i in range(60):
        bars.append({
            "symbol": "AAPL",
            "ts": f"2026-05-19T{i:02d}:00:00+00:00",
            "open": 100 + i * 0.1, "high": 100 + i * 0.1,
            "low": 100 + i * 0.1, "close": 100 + i * 0.1,
            "volume": 1000,
            "source": "test",
        })
    bars.append({
        "symbol": "AAPL", "ts": "2026-05-19T60:00:00+00:00".replace(":60", ":00"),
        "open": 110, "high": 112, "low": 109, "close": 111,
        "volume": 50_000, "source": "test",
    })
    bars[-1]["ts"] = "2026-05-20T00:00:00+00:00"
    db.insert_prices(bars)

    items = list_opportunities(db, ["AAPL"])
    assert items, "expected at least one opportunity"
    item = items[0]
    assert item["symbol"] == "AAPL"
    assert 0.0 <= item["probability"] <= 1.0
    assert "disclaimer" in item
    assert "outcome_range" in item
    rng = item["outcome_range"]
    assert rng["downside_pct"] < 0
    assert rng["upside_pct"] > 0
    assert isinstance(item["reasons"], list)


def test_compute_hit_rate_uses_real_backtester(tmp_path):
    db = Database(tmp_path / "hit.sqlite")
    bars = []
    p = 100.0
    for i in range(120):
        p *= 1.001 if i % 3 != 0 else 0.998
        bars.append({"symbol": "AAA",
                     "ts": f"2026-05-{(i % 28) + 1:02d}T{(i // 28) % 24:02d}:00:00+00:00",
                     "open": p, "high": p, "low": p, "close": p,
                     "volume": 1000, "source": "test"})
    db.insert_prices(bars)
    out = compute_hit_rate(db, ["AAA", "MISSING"])
    assert out["overall"]["source"].startswith("backtest replay")
    # AAA processed, MISSING skipped.
    syms = {row["symbol"]: row for row in out["per_symbol"]}
    assert syms["MISSING"]["skipped"]
    assert syms["AAA"]["skipped"] is False
    assert "disclaimer" in out
