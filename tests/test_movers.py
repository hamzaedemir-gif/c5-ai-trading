from data import compute_movers, latest_quote, list_recent_news, search_symbols
from data.db import Database


def _seed(db: Database, sym: str, prices, volumes, *, day="2026-05-20"):
    rows = []
    for i, (p, v) in enumerate(zip(prices, volumes)):
        rows.append({
            "symbol": sym, "ts": f"{day}T{i:02d}:00:00+00:00",
            "open": p, "high": p, "low": p, "close": p, "volume": v,
            "source": "test",
        })
    db.insert_prices(rows)


def test_compute_movers_ranks_gainers_and_losers(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    _seed(db, "AAA", [100] * 10 + [110], [1000] * 11)   # +10%
    _seed(db, "BBB", [100] * 10 + [105], [1000] * 11)   # +5%
    _seed(db, "CCC", [100] * 10 + [95],  [1000] * 11)   # -5%
    _seed(db, "DDD", [100] * 10 + [101], [10_000] * 10 + [80_000])  # huge volume

    out = compute_movers(db, ["AAA", "BBB", "CCC", "DDD"], lookback_bars=10)
    assert out["gainers"][0]["symbol"] == "AAA"
    assert out["losers"][0]["symbol"] == "CCC"
    assert out["high_volume"][0]["symbol"] == "DDD"
    assert out["high_volume"][0]["volume_ratio"] > 5
    db.close()


def test_compute_movers_skips_symbols_without_history(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    _seed(db, "AAA", [100, 105], [1000, 1000])
    out = compute_movers(db, ["AAA", "ZZZ"], lookback_bars=1)
    syms = [r["symbol"] for r in out["gainers"]]
    assert "ZZZ" not in syms
    db.close()


def test_latest_quote_returns_most_recent(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    _seed(db, "AAA", [100, 102, 103], [10, 20, 30])
    q = latest_quote(db, "AAA")
    assert q is not None
    assert q["price"] == 103
    assert q["volume"] == 30
    assert latest_quote(db, "MISSING") is None
    db.close()


def test_search_symbols_prefix_first(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    _seed(db, "AAPL", [100], [10])
    _seed(db, "TAPL", [100], [10])
    out = search_symbols(db, "AAP")
    assert out[0] == "AAPL"


def test_search_symbols_empty(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    assert search_symbols(db, "") == []


def test_list_recent_news(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    db.insert_news([
        {"symbol": "AAPL", "headline": "Apple ships product",
         "url": "u1", "summary": None,
         "published_at": "2026-05-19T10:00:00+00:00", "source": "finnhub"},
        {"symbol": "MSFT", "headline": "MSFT update", "url": "u2",
         "summary": None, "published_at": "2026-05-19T11:00:00+00:00",
         "source": "finnhub"},
    ])
    all_news = list_recent_news(db)
    assert len(all_news) == 2
    aapl_only = list_recent_news(db, symbol="AAPL")
    assert len(aapl_only) == 1
    assert aapl_only[0]["headline"].startswith("Apple")
    db.close()
