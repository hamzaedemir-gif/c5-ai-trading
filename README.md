# c5-ai-trading

> ⚠ **Analytics & education only.** This dashboard displays market data and
> ranks candidates. It places **no trades** and is **not financial advice**.
> Trading mode is hard-coded to paper; there is no live order-routing code.

Real-time market data + signal dashboard, driven by earnings, volume, and
social-sentiment signals.

## Architecture

```
data/           ingest prices / earnings / news / sentiment -> SQLite
  alpaca_stream.py     real-time websocket feed (Alpaca, free IEX tier)
  prices.py            historical backfill via yfinance
  earnings.py / news.py Finnhub (free tier)
  sentiment.py         StockTwits public stream
signals/        Signal dataclass + volume/earnings/sentiment scorers
risk/           paper portfolio + risk manager (sizing, stops, kill switch)
backtest/       historical replay through signals + risk -> metrics
api/            FastAPI backend exposing the dashboard + /ws live updates
frontend/       React + TypeScript + Tailwind + Lightweight Charts UI
```

Every signal is persisted in `signal_log` with full inputs so any decision
is auditable. Every paper trade is persisted in `trades`. Defaults to
**paper mode**; the backend refuses to start when `C5_TRADING_MODE=live`.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # fill in keys (see below)
```

Frontend:

```bash
cd frontend
npm install
```

### Getting free API keys

- **Alpaca** (real-time prices, free IEX feed): sign up at
  <https://alpaca.markets> → Paper Trading → Generate API Keys → copy
  `ALPACA_API_KEY` + `ALPACA_API_SECRET` into `.env`.
- **Finnhub** (earnings + news, free tier): sign up at
  <https://finnhub.io> → dashboard shows your `FINNHUB_API_KEY`.
- **StockTwits**: public endpoint, no key required.
- **yfinance**: no key required; used only for historical backfill.

### `.env` variables

| Variable | Purpose |
|---|---|
| `ALPACA_API_KEY` / `ALPACA_API_SECRET` | **Required for real-time prices.** |
| `ALPACA_STREAM_URL` | Defaults to `wss://stream.data.alpaca.markets/v2/iex` (free) |
| `ALPACA_SYMBOLS` | Comma-separated tickers to subscribe to (e.g. `AAPL,MSFT,TSLA`) |
| `FINNHUB_API_KEY` | Earnings + company news |
| `STOCKTWITS_BASE_URL` | Defaults to public StockTwits API |
| `C5_DB_PATH` | SQLite path (default `c5_data.sqlite`) |
| `C5_TRADING_MODE` | `paper` (default). `live` is intentionally not wired up. |
| `C5_API_HOST` / `C5_API_PORT` | Backend bind address (default `0.0.0.0:8000`) |
| `C5_API_CORS_ORIGINS` | Comma-separated origins allowed for the React dev server |
| `C5_STARTING_CAPITAL`, `C5_POSITION_PCT`, `C5_STOP_LOSS_PCT`, `C5_DAILY_MAX_LOSS_PCT` | Risk params for backtests / paper sim |

`.env` is git-ignored. Never commit it.

## Running the dashboard

```bash
# 1) backfill some historical bars + news/earnings for your watchlist
python run_paper.py ingest AAPL MSFT TSLA NVDA AMD SPY QQQ

# 2) start the API backend (also opens the Alpaca websocket if keys are set)
uvicorn api.app:create_app --factory --reload --port 8000

# 3) start the React frontend (separate terminal)
cd frontend && npm run dev   # http://localhost:5173
```

The frontend proxies `/api/*` to `http://localhost:8000`, including the
`/api/ws` websocket. Once Alpaca trades start flowing, the dashboard
updates in real time — no fixed polling timer for prices.

### Without Alpaca keys

The backend still runs; `/candidates`, `/movers`, `/news`, `/stocks/...`
work against whatever is in SQLite. The "LIVE" pill in the header turns
off and the websocket sends a hello but no trade events. Real-time
requires Alpaca keys.

## Endpoints

| Path | Description |
|---|---|
| `GET  /healthz` | server + stream status |
| `GET  /disclaimer` | banner text (rendered in UI) |
| `GET  /candidates?top_n=&min_confidence=` | ranked swing candidates + reasons |
| `GET  /movers?lookback=` | top gainers / losers / high-volume movers |
| `GET  /news?symbol=&limit=` | latest news headlines |
| `GET  /search?q=` | ticker search |
| `GET  /stocks/{symbol}` | intraday + daily bars + news + signal + audit log |
| `GET  /audit-log?symbol=&limit=` | per-signal history with inputs |
| `WS   /ws` | live trade events fan-out |

## CLI (paper-only)

```bash
python run_paper.py ingest AAPL MSFT      # pull + store
python run_paper.py signals AAPL MSFT     # score + audit log
python run_paper.py backtest AAPL         # win rate, max DD, Sharpe…
```

## Tests

```bash
python -m pytest tests/ -q
```

61 backend tests covering DB, parsers, signals, risk gating, backtester,
the Alpaca stream message handler, movers, and every FastAPI endpoint.
All run offline — no network calls.

## Safety defaults

- **Paper mode** unless explicitly overridden in `.env`; backend refuses
  to start in `live` mode.
- **No order routing** exists in this codebase.
- **Hard stop** per position, **daily loss cap** auto-trips the kill
  switch, **no position stacking**, **min-confidence floor**.
- **Audit log**: every signal persisted with full inputs.
