"""Tests for the live-vs-demo data-source selection in create_app()."""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from api.app import create_app
from config import load_config
from data.alpaca_stream import AlpacaStream
from data.db import Database
from demo.ticker import SimulatedTicker


@pytest.fixture
def clean_env(monkeypatch):
    """Strip any inherited Alpaca / demo-mode env so tests start from blank."""
    for k in ("ALPACA_API_KEY", "ALPACA_API_SECRET", "C5_DEMO_MODE"):
        monkeypatch.delenv(k, raising=False)


def test_load_config_reflects_current_env(clean_env, monkeypatch):
    """Refactor regression: load_config must read env each call, not at import."""
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_API_SECRET", "s")
    cfg = load_config()
    assert cfg.has_alpaca_keys()
    assert not cfg.effective_demo()

    monkeypatch.delenv("ALPACA_API_KEY")
    cfg2 = load_config()
    assert not cfg2.has_alpaca_keys()
    assert cfg2.effective_demo()


def test_demo_when_no_alpaca_keys(clean_env, tmp_path):
    db = Database(tmp_path / "demo.sqlite")
    app = create_app(db=db, symbols=["AAPL", "MSFT"], enable_stream=True)
    state = app.state.c5
    assert state.demo_mode is True
    assert isinstance(state.stream, SimulatedTicker)


def test_live_when_alpaca_keys_present(clean_env, monkeypatch, tmp_path):
    monkeypatch.setenv("ALPACA_API_KEY", "test_key_AKID")
    monkeypatch.setenv("ALPACA_API_SECRET", "test_secret")
    db = Database(tmp_path / "live.sqlite")
    app = create_app(db=db, symbols=["AAPL"], enable_stream=True)
    state = app.state.c5
    assert state.demo_mode is False
    assert isinstance(state.stream, AlpacaStream)
    # Must not have seeded sample data in live mode.
    assert state.db.fetch_prices("AAPL", limit=1) == []


def test_force_demo_overrides_keys(clean_env, monkeypatch, tmp_path):
    """C5_DEMO_MODE=1 forces demo even when valid Alpaca keys exist."""
    monkeypatch.setenv("ALPACA_API_KEY", "test_key")
    monkeypatch.setenv("ALPACA_API_SECRET", "test_secret")
    monkeypatch.setenv("C5_DEMO_MODE", "1")
    db = Database(tmp_path / "forced.sqlite")
    app = create_app(db=db, symbols=["AAPL"], enable_stream=True)
    state = app.state.c5
    assert state.demo_mode is True
    assert isinstance(state.stream, SimulatedTicker)


def test_partial_keys_count_as_no_keys(clean_env, monkeypatch, tmp_path):
    """If only one of {key, secret} is set, we must NOT try live mode."""
    monkeypatch.setenv("ALPACA_API_KEY", "only_key_no_secret")
    db = Database(tmp_path / "partial.sqlite")
    app = create_app(db=db, symbols=["AAPL"], enable_stream=True)
    state = app.state.c5
    assert state.demo_mode is True
    assert isinstance(state.stream, SimulatedTicker)


def test_healthz_and_ws_hello_report_correct_mode(clean_env, tmp_path):
    """End-to-end: the /ws hello must say demo_mode=true with no keys."""
    db = Database(tmp_path / "e2e.sqlite")
    app = create_app(db=db, symbols=["AAPL"], enable_stream=True)
    with TestClient(app) as c:
        h = c.get("/healthz").json()
        assert h["demo_mode"] is True
        with c.websocket_connect("/ws") as ws:
            hello = ws.receive_json()
            assert hello["type"] == "hello"
            assert hello["demo_mode"] is True


def test_healthz_reports_live_when_keys_set(clean_env, monkeypatch, tmp_path):
    monkeypatch.setenv("ALPACA_API_KEY", "test_key")
    monkeypatch.setenv("ALPACA_API_SECRET", "test_secret")
    db = Database(tmp_path / "e2e_live.sqlite")
    # Seed one bar so /healthz and downstream endpoints don't 500 on empty data.
    db.insert_prices([{
        "symbol": "AAPL", "ts": "2026-05-20T14:00:00+00:00",
        "open": 100, "high": 100, "low": 100, "close": 100,
        "volume": 100, "source": "test",
    }])
    # enable_stream=False so we don't actually open a websocket to Alpaca.
    app = create_app(db=db, symbols=["AAPL"], enable_stream=False)
    with TestClient(app) as c:
        h = c.get("/healthz").json()
        assert h["demo_mode"] is False
        with c.websocket_connect("/ws") as ws:
            hello = ws.receive_json()
            assert hello["demo_mode"] is False


def test_live_mode_does_not_use_finnhub_for_prices(clean_env, monkeypatch, tmp_path):
    """Regression guard: ingest_prices uses yfinance, never Finnhub."""
    from data.ingest import Ingestor
    monkeypatch.setenv("FINNHUB_API_KEY", "fh_test")
    db = Database(tmp_path / "src.sqlite")
    ing = Ingestor(db, finnhub_key="fh_test")
    # Method should NOT touch self.finnhub_key.
    import inspect
    src = inspect.getsource(ing.ingest_prices)
    assert "finnhub" not in src.lower()
