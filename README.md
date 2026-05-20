# c5-ai-trading

C5 AI Trading — automated trading bot driven by earnings, volume, and
social-sentiment signals. Defaults to **paper mode**; live trading is
intentionally not wired up until backtests look reasonable.

## Architecture

```
data/      ingests prices, earnings, news, social sentiment -> SQLite
signals/   converts raw rows into scored Signals (confidence in [0, 1])
risk/      gates each signal: position sizing, stop-loss, daily cap, kill switch
backtest/  replays history through signals + risk and reports metrics
```

Every signal is persisted in `signal_log` with its full inputs so any
decision is auditable. Every paper trade is persisted in `trades`.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # then fill in keys
```

### Required `.env` variables

| Variable | Purpose |
|---|---|
| `FINNHUB_API_KEY` | Earnings calendar + company news (free tier) |
| `ALPHA_VANTAGE_API_KEY` | Optional: alternate earnings/news provider |
| `ALPACA_API_KEY` / `ALPACA_API_SECRET` | Optional: paper-broker price feed |
| `ALPACA_BASE_URL` | Defaults to Alpaca paper endpoint |
| `STOCKTWITS_BASE_URL` | Defaults to public StockTwits API |
| `C5_DB_PATH` | SQLite path (default `c5_data.sqlite`) |
| `C5_TRADING_MODE` | `paper` (default) or `live` (not wired up) |
| `C5_STARTING_CAPITAL` | Paper portfolio size (default 10000) |
| `C5_POSITION_PCT` | Per-trade equity fraction (default 0.02 = 2%) |
| `C5_STOP_LOSS_PCT` | Per-position hard stop (default 0.03 = 3%) |
| `C5_DAILY_MAX_LOSS_PCT` | Daily loss that trips the kill switch (default 0.05 = 5%) |

`yfinance` needs no API key — it is the default price source.

`.env` is git-ignored. Never commit it.

## Running in paper mode

```bash
# 1) pull market data into the SQLite DB
python run_paper.py ingest AAPL MSFT TSLA

# 2) score signals (volume spikes, earnings surprises, sentiment shifts)
python run_paper.py signals AAPL MSFT TSLA

# 3) backtest the signal + risk engine on the ingested history
python run_paper.py backtest AAPL
```

The runner refuses to start when `C5_TRADING_MODE=live`. There is no
live order-routing code in this repo. To go live later you must (a) be
satisfied with backtest results, (b) add a broker adapter, and (c) flip
the mode explicitly.

## Tests

```bash
python -m pytest tests/ -q
```

36 tests covering DB writes, parsers, signal math, risk gating, and the
backtester. All run offline — no network calls.

## Safety defaults

- **Paper mode** unless explicitly set otherwise.
- **Hard stop** on every position (`C5_STOP_LOSS_PCT`).
- **Daily loss cap** auto-trips the kill switch (`C5_DAILY_MAX_LOSS_PCT`).
- **Kill switch** can be tripped manually via `RiskManager.trip_kill_switch()`.
- **No position stacking** — the manager rejects entries when a position
  is already open in the same symbol.
- **Min-confidence floor** (default 0.5) rejects weak or flat signals.
