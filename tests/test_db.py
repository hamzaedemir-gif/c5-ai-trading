from data.db import Database


def test_insert_and_fetch_prices(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    rows = [
        {"symbol": "AAPL", "ts": "2026-05-19T15:30:00+00:00",
         "open": 100, "high": 101, "low": 99, "close": 100.5,
         "volume": 1000, "source": "yfinance"},
        {"symbol": "AAPL", "ts": "2026-05-19T15:31:00+00:00",
         "open": 100.5, "high": 102, "low": 100, "close": 101.7,
         "volume": 1500, "source": "yfinance"},
    ]
    assert db.insert_prices(rows) == 2
    # duplicates are ignored
    assert db.insert_prices(rows) == 0
    fetched = db.fetch_prices("AAPL")
    assert len(fetched) == 2
    assert fetched[0]["close"] in (100.5, 101.7)
    db.close()


def test_insert_sentiment_and_earnings(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    db.insert_sentiment([
        {"symbol": "TSLA", "ts": "2026-05-19T15:30:00+00:00",
         "score": 0.4, "volume": 12, "source": "stocktwits"},
    ])
    db.insert_earnings([
        {"symbol": "TSLA", "event_date": "2026-04-23", "period": "Q1",
         "eps_estimate": 0.55, "eps_actual": 0.62,
         "revenue_estimate": 1.0, "revenue_actual": 1.05, "source": "finnhub"},
    ])
    assert len(db.fetch_sentiment("TSLA")) == 1
    assert len(db.fetch_earnings("TSLA")) == 1
    db.close()


def test_log_signal_and_trade(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    sid = db.log_signal(symbol="AAPL", signal_type="volume_spike",
                        confidence=0.82, direction="long",
                        inputs_json='{"z":3.2}')
    tid = db.log_trade(symbol="AAPL", side="buy", qty=10, price=100.5,
                       mode="paper", signal_id=sid, reason="paper open")
    assert sid > 0 and tid > 0
    db.close()
