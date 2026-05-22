import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from api.app import create_app
from api.paper_portfolio import PaperPortfolioService
from data.db import Database


def _seed_prices(db: Database, sym: str = "AAPL", price: float = 100.0,
                 n: int = 80) -> None:
    rows = []
    for i in range(n):
        rows.append({
            "symbol": sym,
            "ts": f"2026-05-{(i % 28) + 1:02d}T{(i // 28) % 24:02d}:00:00+00:00",
            "open": price, "high": price, "low": price, "close": price,
            "volume": 1000, "source": "test",
        })
    db.insert_prices(rows)


def test_paper_buy_uses_risk_sizing(tmp_path):
    db = Database(tmp_path / "p.sqlite")
    _seed_prices(db, "AAPL", 100.0)
    svc = PaperPortfolioService(db, starting_capital=10_000,
                                position_pct=0.02, stop_loss_pct=0.03)
    r = svc.paper_buy("AAPL", current_price=100.0)
    assert r.approved
    assert r.qty == 2.0          # 2% of 10k = $200 / $100
    assert r.stop_price == 97.0   # 3% stop
    assert r.notional == 200.0


def test_paper_buy_rejects_when_no_price(tmp_path):
    db = Database(tmp_path / "p.sqlite")
    svc = PaperPortfolioService(db)
    r = svc.paper_buy("AAPL")     # no seeded price, no override
    assert not r.approved
    assert r.reason == "no_price_available"


def test_paper_buy_rejects_duplicate_position(tmp_path):
    db = Database(tmp_path / "p.sqlite")
    _seed_prices(db, "AAPL", 100.0)
    svc = PaperPortfolioService(db)
    assert svc.paper_buy("AAPL", current_price=100.0).approved
    r2 = svc.paper_buy("AAPL", current_price=101.0)
    assert not r2.approved
    assert r2.reason == "position_already_open"


def test_paper_sell_realises_pnl(tmp_path):
    db = Database(tmp_path / "p.sqlite")
    _seed_prices(db, "AAPL", 100.0)
    svc = PaperPortfolioService(db)
    svc.paper_buy("AAPL", current_price=100.0)
    out = svc.paper_sell("AAPL", current_price=110.0)
    assert out["closed"]
    assert out["realized_pnl"] == round((110 - 100) * 2, 2)


def test_status_reports_equity(tmp_path):
    db = Database(tmp_path / "p.sqlite")
    _seed_prices(db, "AAPL", 100.0)
    svc = PaperPortfolioService(db)
    svc.paper_buy("AAPL", current_price=100.0)
    st = svc.status({"AAPL": 105.0})
    assert st["mode"] == "paper"
    assert any(p["symbol"] == "AAPL" for p in st["positions"])
    assert st["equity"] == pytest.approx(10_000 + (105 - 100) * 2)


def test_persistence_across_restart(tmp_path):
    dbpath = tmp_path / "p.sqlite"
    db = Database(dbpath)
    _seed_prices(db, "AAPL", 100.0)
    svc = PaperPortfolioService(db)
    svc.paper_buy("AAPL", current_price=100.0)
    db.close()

    db2 = Database(dbpath)
    svc2 = PaperPortfolioService(db2)
    assert "AAPL" in svc2.portfolio.positions
    assert svc2.portfolio.cash < 10_000


def test_kill_switch_blocks_new_buys(tmp_path):
    db = Database(tmp_path / "p.sqlite")
    _seed_prices(db, "AAPL", 100.0)
    svc = PaperPortfolioService(db)
    svc.trip_kill_switch("test")
    r = svc.paper_buy("AAPL", current_price=100.0)
    assert not r.approved
    assert r.reason == "kill_switch_active"


# ---- API-level tests ------------------------------------------------

@pytest.fixture
def client(tmp_path):
    db = Database(tmp_path / "api.sqlite")
    _seed_prices(db, "AAPL", 100.0)
    _seed_prices(db, "MSFT", 200.0)
    app = create_app(db=db, symbols=["AAPL", "MSFT"], enable_stream=False)
    with TestClient(app) as c:
        yield c


def test_opportunities_endpoint_returns_disclaimer(client):
    r = client.get("/opportunities")
    assert r.status_code == 200
    body = r.json()
    assert "disclaimer" in body
    assert "label_explainer" in body
    if body["items"]:
        item = body["items"][0]
        assert "probability" in item
        assert "outcome_range" in item
        assert item["outcome_range"]["downside_pct"] < 0


def test_paper_endpoints_round_trip(client):
    r = client.get("/paper/portfolio")
    assert r.status_code == 200
    assert r.json()["cash"] == 10_000

    r = client.post("/paper/buy", json={"symbol": "AAPL", "price": 100.0})
    assert r.status_code == 200
    assert r.json()["approved"]
    assert r.json()["mode"] == "paper"

    r = client.get("/paper/portfolio")
    body = r.json()
    assert any(p["symbol"] == "AAPL" for p in body["positions"])

    r = client.post("/paper/sell", json={"symbol": "AAPL", "price": 105.0})
    assert r.status_code == 200
    assert r.json()["closed"]


def test_hit_rate_endpoint(client):
    r = client.get("/performance/hit-rate")
    assert r.status_code == 200
    body = r.json()
    assert body["overall"]["source"].startswith("backtest replay")
