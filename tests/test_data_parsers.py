from data.earnings import parse_finnhub_earnings
from data.news import parse_finnhub_news
from data.prices import normalize_bars
from data.sentiment import aggregate_stocktwits_messages, keyword_score


def test_parse_finnhub_earnings():
    payload = [
        {"period": "2026-03-31", "estimate": 1.20, "actual": 1.35,
         "revenueEstimate": 90.0, "revenueActual": 95.5},
        {"period": "2025-12-31", "estimate": 1.10, "actual": 1.05},
    ]
    rows = parse_finnhub_earnings("AAPL", payload)
    assert len(rows) == 2
    assert rows[0]["symbol"] == "AAPL"
    assert rows[0]["eps_actual"] == 1.35
    assert rows[1]["revenue_actual"] is None


def test_parse_finnhub_news():
    payload = [
        {"datetime": 1747680000, "headline": "Apple beats Q1",
         "url": "http://example.com", "summary": "..."},
        {"datetime": 1747683600, "headline": ""},   # filtered (empty headline)
    ]
    rows = parse_finnhub_news("AAPL", payload)
    assert len(rows) == 1
    assert rows[0]["headline"] == "Apple beats Q1"
    assert rows[0]["published_at"].endswith("+00:00")


def test_normalize_bars_handles_epoch_and_aliases():
    rows = normalize_bars("AAPL", [
        {"t": 1747680000, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100},
    ], source="alpaca")
    assert rows[0]["open"] == 1 and rows[0]["close"] == 1.5
    assert rows[0]["volume"] == 100


def test_keyword_score():
    assert keyword_score("Going to the moon, calls printing") > 0
    assert keyword_score("Crash incoming, puts only") < 0
    assert keyword_score("just sitting on the fence") == 0.0


def test_aggregate_stocktwits_messages():
    msgs = [
        {"entities": {"sentiment": {"basic": "Bullish"}}, "body": "calls"},
        {"entities": {"sentiment": {"basic": "Bearish"}}, "body": "puts"},
        {"body": "bullish breakout"},
    ]
    rows = aggregate_stocktwits_messages("AAPL", msgs)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "AAPL"
    assert rows[0]["volume"] == 3
    assert -1.0 <= rows[0]["score"] <= 1.0
