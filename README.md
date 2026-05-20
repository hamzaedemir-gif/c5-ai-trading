# c5-ai-trading

> ⚠ **Analytics & education only.** This dashboard displays market data and
> ranks candidates. It places **no trades** and is **not financial advice**.
> The whole stack runs in paper / simulation mode; there is no live
> order-routing code in this repo.

---

## 🚀 Run it in 30 seconds (no API keys, no signup)

Pick ONE of these. Both serve the dashboard at **<http://localhost:5173>**.

### Option A — Docker (easiest, one command)

You need Docker Desktop installed.

```bash
docker compose up --build
```

Wait ~60 seconds the first time (it builds the Python + Node images), then
open **<http://localhost:5173>** in your browser. You'll see the
dashboard with sample data and a simulated price ticker driving the
"flash green / red" updates live. No keys required.

To stop: press `Ctrl+C` in that terminal.

### Option B — No Docker, native (Python 3.10+ and Node 18+ on your machine)

```bash
./run_demo.sh
```

This script creates a Python venv, installs deps, installs frontend
deps, and starts both servers. It prints `http://localhost:5173` when
ready — open that in your browser. `Ctrl+C` to stop everything.

### What you'll see

A dark dashboard with:
- **Top Opportunities** — tappable cards (ticker, live price, estimated
  probability, top reasons flagged, two-sided upside/downside range).
  Tap any card to drill in. Tap **Paper Buy** to add a simulated position.
- **Top Gainers / Losers / High Volume Movers** rows.
- **Live News Feed**.
- A **Paper Portfolio** page (top nav) with positions, stops, P&L.
- Header pills: `LIVE`, `PAPER MODE`, `DEMO DATA`.

---

## Switching from demo mode to real data

When you're ready to use real market data:

1. Get a free **Alpaca** key (real-time prices, IEX feed is free):
   <https://alpaca.markets> → Paper Trading → Generate API Keys.
2. Get a free **Finnhub** key (earnings + news):
   <https://finnhub.io> → dashboard.
3. `cp .env.example .env`, paste the keys, and set `C5_DEMO_MODE=0`.
4. Re-run with docker (`docker compose up`) or the dev workflow below.

There is still **no live order routing**: paper-buy stays simulated.

### `.env` variables

| Variable | What it does |
|---|---|
| `C5_DEMO_MODE` | `1` = sample data + simulated ticker, no keys needed. `0` = real data (needs Alpaca + Finnhub). |
| `ALPACA_API_KEY` / `ALPACA_API_SECRET` | Real-time price feed (free IEX feed). |
| `ALPACA_STREAM_URL` | Default: `wss://stream.data.alpaca.markets/v2/iex`. |
| `ALPACA_SYMBOLS` | Comma-separated tickers to subscribe to. |
| `FINNHUB_API_KEY` | Earnings + company news. |
| `STOCKTWITS_BASE_URL` | Public StockTwits API (no key). |
| `C5_DB_PATH` | SQLite path. |
| `C5_TRADING_MODE` | `paper` (default). Backend refuses to start if `live`. |
| `C5_API_HOST` / `C5_API_PORT` | Backend bind (default `0.0.0.0:8000`). |
| `C5_API_CORS_ORIGINS` | Allowed CORS origins. |
| `C5_STARTING_CAPITAL`, `C5_POSITION_PCT`, `C5_STOP_LOSS_PCT`, `C5_DAILY_MAX_LOSS_PCT` | Risk-manager parameters. |

`.env` is gitignored. Never commit it.

---

## Architecture

```
data/               ingestion (Alpaca real-time, yfinance backfill,
                    Finnhub earnings/news, StockTwits sentiment) -> SQLite
signals/            Signal dataclass + volume / earnings / sentiment scorers
risk/               paper Portfolio + RiskManager (sizing, stops, kill switch)
backtest/           bar-by-bar replay -> win rate, max DD, Sharpe
core/               TTLCache, retry-with-backoff, async BackgroundScheduler
api/                FastAPI app: opportunities, movers, news, search,
                    /stocks/{sym}, paper buy/sell/portfolio, WS /ws,
                    hit-rate (from real backtest results)
demo/               sample seed data + simulated ticker (no API keys)
frontend/           React + TypeScript + Tailwind + Lightweight Charts
```

### Reliability features (Part B)

- **Caching** — `core.cache.TTLCache` wraps hot endpoints (6–60s TTL).
  Every WebSocket tick invalidates the cache so the next request sees
  fresh data without polling.
- **Retry-with-backoff** — all four data fetchers (prices / earnings /
  news / sentiment) are wrapped in `@retry_with_backoff` with graceful
  fallback to "0 rows" so one source rate-limiting can't crash the board.
- **Background scheduler** — periodic refresh jobs run off the request
  path (news + earnings + sentiment every 5 min, price backfill every
  2 min, paper-portfolio stop-check every 10 s).
- **Alpaca WS auto-reconnect** — exponential backoff in
  `AlpacaStream.run`.

### Safety features

- `C5_TRADING_MODE=paper` default; backend refuses to start in `live`.
- Manual + automatic **kill switch** (auto-trips on daily-loss breach).
- **No position stacking** in same symbol; **min-confidence floor**.
- **Hard stop-loss** applied on every open via the risk manager.
- Every signal persisted in `signal_log` with full inputs (auditable).
- Visible disclaimer on every page.

---

## Endpoints

| Path | Description |
|---|---|
| `GET  /healthz` | server, stream, demo flag |
| `GET  /disclaimer` | banner text |
| `GET  /opportunities?top_n=&horizon_days=` | ranked feed with probability + two-sided outcome range |
| `GET  /performance/hit-rate` | backtest-derived win rate (no hardcoded numbers) |
| `GET  /candidates`, `GET /movers`, `GET /news`, `GET /search` | dashboard data |
| `GET  /stocks/{symbol}` | intraday + daily + news + signal + audit log |
| `GET  /paper/portfolio` | paper cash + positions + unrealised PnL |
| `POST /paper/buy` `{symbol, price?}` | simulated buy via risk manager |
| `POST /paper/sell` `{symbol, price?}` | simulated close, realises PnL |
| `POST /paper/kill-switch` `{action: trip\|reset}` | manual kill switch |
| `GET  /audit-log?symbol=&limit=` | per-signal history |
| `WS   /ws` | live trade events fan-out |

## CLI

```bash
python run_paper.py ingest AAPL MSFT      # pull + store
python run_paper.py signals AAPL MSFT     # score + audit log
python run_paper.py backtest AAPL         # win rate, max DD, Sharpe...
```

## Tests

```bash
python -m pytest tests/ -q
```

89 tests covering DB, parsers, signals, risk, backtester, Alpaca stream
handler, movers, every FastAPI endpoint (incl. `/ws`), opportunities
math (downside always shown), paper portfolio (sizing + stops +
persistence + kill-switch), cache, retry/backoff, scheduler, demo
seed + simulated ticker. All run offline.

---

## Disclaimer (also rendered in the UI)

This software is provided **for analytics and educational purposes only**.
It displays market data and ranks candidates. It places **no trades**.
Probabilities and outcome ranges are model estimates derived from
historical data; they are **not guarantees**. Past backtest performance
does not guarantee future results. This is **not financial advice**.
