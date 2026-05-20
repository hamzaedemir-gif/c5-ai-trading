import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from api.app import create_app
from data.db import Database


@pytest.fixture
def client(tmp_path):
    db = Database(tmp_path / "api.sqlite")
    # seed some prices
    bars = []
    for sym, base in [("AAPL", 100.0), ("MSFT", 200.0), ("TSLA", 150.0)]:
        for i in range(70):
            price = base + i * 0.1
            bars.append({
                "symbol": sym,
                "ts": f"2026-05-19T{i:02d}:00:00+00:00".replace(":99", ":00"),
                "open": price, "high": price + 0.5, "low": price - 0.5,
                "close": price, "volume": 1000 + (5000 if i == 69 and sym == "AAPL" else 0),
                "source": "test",
            })
    db.insert_prices(bars)
    db.insert_news([
        {"symbol": "AAPL", "headline": "Apple ships product",
         "url": "u1", "summary": None,
         "published_at": "2026-05-19T10:00:00+00:00", "source": "finnhub"},
    ])

    app = create_app(db=db, symbols=["AAPL", "MSFT", "TSLA"], enable_stream=False)
    with TestClient(app) as c:
        yield c


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    data = r.json()
    assert data["paper_mode"] is True
    assert "AAPL" in data["symbols"]


def test_disclaimer(client):
    r = client.get("/disclaimer")
    assert r.status_code == 200
    body = r.json()
    assert "no trades" in body["text"].lower() or "not financial advice" in body["text"].lower()
    assert body["paper_mode"] is True


def test_candidates_returns_ranked_items(client):
    r = client.get("/candidates")
    assert r.status_code == 200
    items = r.json()["items"]
    assert isinstance(items, list)
    if items:
        first = items[0]
        assert {"symbol", "confidence", "direction", "reasons"} <= set(first)
        # confidence is sorted descending
        confs = [it["confidence"] for it in items]
        assert confs == sorted(confs, reverse=True)


def test_movers(client):
    r = client.get("/movers")
    assert r.status_code == 200
    data = r.json()
    assert set(data) == {"gainers", "losers", "high_volume"}


def test_news_endpoint(client):
    r = client.get("/news")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert items[0]["headline"].startswith("Apple")


def test_news_filtered_by_symbol(client):
    r = client.get("/news", params={"symbol": "MSFT"})
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_search(client):
    r = client.get("/search", params={"q": "aa"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert "AAPL" in items


def test_search_empty_query_returns_empty(client):
    r = client.get("/search", params={"q": ""})
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_stock_detail(client):
    r = client.get("/stocks/AAPL")
    assert r.status_code == 200
    data = r.json()
    assert data["symbol"] == "AAPL"
    assert data["quote"]["price"] is not None
    assert len(data["intraday"]) > 0
    assert len(data["daily"]) >= 1
    assert isinstance(data["news"], list)
    assert "signal" in data


def test_stock_detail_unknown_404(client):
    r = client.get("/stocks/ZZZZ")
    assert r.status_code == 404


def test_audit_log_endpoint(client):
    # Hitting /candidates does NOT persist (engine constructed with persist=False).
    # But /stocks/AAPL also constructs an engine with persist=False, so log starts empty.
    r = client.get("/audit-log")
    assert r.status_code == 200
    assert "items" in r.json()


def test_websocket_hello(client):
    with client.websocket_connect("/ws") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "hello"
        assert msg["paper_mode"] is True
