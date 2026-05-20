import asyncio

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from api.app import create_app
from data.db import Database
from demo import DEMO_SYMBOLS, SimulatedTicker, seed_database


def test_seed_database_writes_rows(tmp_path):
    db = Database(tmp_path / "demo.sqlite")
    counts = seed_database(db, ["AAPL", "MSFT"])
    assert counts["prices"] > 0
    assert counts["news"] > 0
    assert counts["earnings"] > 0
    assert counts["sentiment"] > 0
    db.close()


def test_simulated_ticker_emits_events(tmp_path):
    db = Database(tmp_path / "demo.sqlite")
    seed_database(db, ["AAPL"])
    ticker = SimulatedTicker(["AAPL"], db, interval_s=0.05)
    received = []

    async def listener(ev):
        received.append(ev)

    ticker.add_listener(listener)

    async def runit():
        task = asyncio.create_task(ticker.run())
        await asyncio.sleep(0.25)
        ticker.stop()
        await task

    asyncio.run(runit())
    assert any(e["type"] == "trade" for e in received)
    # latest should now have AAPL
    assert "AAPL" in ticker.snapshot()
    db.close()


def test_create_app_demo_mode_seeds_and_runs():
    app = create_app(demo_mode=True, enable_stream=False)
    with TestClient(app) as c:
        h = c.get("/healthz").json()
        assert h["demo_mode"] is True
        assert h["paper_mode"] is True
        assert set(h["symbols"]) >= {"AAPL", "MSFT"}
        opps = c.get("/opportunities").json()
        assert opps["items"], "demo data should produce at least one opportunity"
        movers = c.get("/movers").json()
        assert "gainers" in movers
        ws_hello = None
        with c.websocket_connect("/ws") as ws:
            ws_hello = ws.receive_json()
        assert ws_hello["type"] == "hello"
        assert ws_hello["demo_mode"] is True


def test_demo_symbol_list_is_stable():
    assert "AAPL" in DEMO_SYMBOLS
    assert "NVDA" in DEMO_SYMBOLS
