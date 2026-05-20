import asyncio

import pytest

from data.alpaca_stream import AlpacaStream, _iso_from_alpaca_ts
from data.db import Database


def test_iso_from_alpaca_ts_passthrough():
    assert _iso_from_alpaca_ts("2026-05-20T14:00:00Z") == "2026-05-20T14:00:00Z"


def test_iso_from_alpaca_ts_epoch_nanos():
    # 1747680000 seconds -> 2025-05-19T20:00:00 UTC
    ns = 1747680000 * 1_000_000_000
    out = _iso_from_alpaca_ts(ns)
    assert out.startswith("2025-05-19T")
    assert out.endswith("+00:00")


def test_handle_trade_persists_and_emits(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    stream = AlpacaStream(api_key="x", api_secret="y",
                          stream_url="ws://test", symbols=["AAPL"], db=db)
    trade = {"T": "t", "S": "AAPL", "p": 100.5, "s": 50,
             "t": "2026-05-20T14:00:00Z"}
    rows, events = stream._handle_message(trade)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "AAPL"
    assert rows[0]["close"] == 100.5
    assert rows[0]["source"] == "alpaca_stream"
    assert events[0]["type"] == "trade"
    assert stream.latest["AAPL"]["price"] == 100.5
    assert stream.latest["AAPL"]["day_volume"] == 50
    db.close()


def test_handle_quote_updates_recent_quotes():
    stream = AlpacaStream(api_key="x", api_secret="y",
                          stream_url="ws://test", symbols=["AAPL"])
    quote = {"T": "q", "S": "AAPL", "bp": 100.0, "ap": 100.2,
             "t": "2026-05-20T14:00:00Z"}
    rows, events = stream._handle_message(quote)
    assert rows == []
    assert events[0]["type"] == "quote"
    assert stream.recent_quotes["AAPL"][-1]["bid"] == 100.0


def test_change_pct_computed_against_prior_trade():
    stream = AlpacaStream(api_key="x", api_secret="y",
                          stream_url="ws://test", symbols=["AAPL"])
    stream._handle_message({"T": "t", "S": "AAPL", "p": 100, "s": 10,
                            "t": "2026-05-20T14:00:00Z"})
    _, events = stream._handle_message({"T": "t", "S": "AAPL", "p": 102, "s": 5,
                                        "t": "2026-05-20T14:00:01Z"})
    assert events[0]["change_pct"] == 2.0
    assert stream.latest["AAPL"]["day_volume"] == 15


def test_process_payload_runs_listener(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    stream = AlpacaStream(api_key="x", api_secret="y",
                          stream_url="ws://test", symbols=["AAPL"], db=db)
    received = []

    async def listener(ev):
        received.append(ev)

    stream.add_listener(listener)
    asyncio.run(stream._process_payload([
        {"T": "t", "S": "AAPL", "p": 100, "s": 10, "t": "2026-05-20T14:00:00Z"},
        {"T": "q", "S": "AAPL", "bp": 99.9, "ap": 100.1, "t": "2026-05-20T14:00:00Z"},
    ]))
    assert len(received) == 2
    # trade should also be in the prices table
    fetched = db.fetch_prices("AAPL")
    assert len(fetched) == 1
    db.close()


def test_handle_unknown_message_type_is_safe():
    stream = AlpacaStream(api_key="x", api_secret="y",
                          stream_url="ws://test", symbols=["AAPL"])
    rows, events = stream._handle_message({"T": "weird", "foo": 1})
    assert rows == [] and events == []
