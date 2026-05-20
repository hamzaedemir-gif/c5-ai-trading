# c5-ai-trading

> ⚠ **Analytics & education only.** This dashboard displays market data and
> ranks candidates. It places **no trades** and is **not financial advice**.
> The whole stack runs in paper / simulation mode; there is no live
> order-routing code in this repo.

---

## 🛠 Development (fast hot-reload) — start here

This is what you want during day-to-day work. Backend auto-restarts on
Python file saves; frontend reloads instantly on `.ts` / `.tsx` saves.
No Docker rebuilds. No API keys. Defaults to demo mode with sample data.

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** (which gives you `npm`)

#### Installing on Windows

1. **Python 3.10+** — go to <https://www.python.org/downloads/windows/>,
   download the latest 3.x installer, run it, and **tick "Add Python to
   PATH"** on the first screen. Or install from the Microsoft Store
   ("Python 3.12").
2. **Node.js 18+ LTS** — go to <https://nodejs.org>, click the green
   **LTS** button, run the installer with all defaults.
3. (Recommended) **Git for Windows** — <https://gitforwindows.org>.
4. Open **PowerShell** (Start menu → "PowerShell") and verify:
   ```powershell
   python --version    # 3.10 or higher
   node --version      # v18 or higher
   ```

#### Installing on macOS

```bash
brew install python@3.12 node
```

#### Installing on Linux

```bash
sudo apt install python3 python3-venv python3-pip nodejs npm        # Debian/Ubuntu
# or
sudo dnf install python3 python3-pip nodejs npm                      # Fedora/RHEL
```

### One command to launch dev mode

Pick the one for your OS — they all do the same thing and open at
**<http://localhost:5173>**:

| Your OS | Command |
|---|---|
| **Windows (PowerShell)** | `.\dev.ps1` |
| **macOS / Linux**        | `./dev.sh` |
| **anywhere (npm)**       | `npm install && npm run dev:all` |
| **anywhere (make)**      | `make dev` |

The first run installs the Python venv + npm packages (~1 minute). After
that it boots in ~3 seconds. Press **Ctrl+C** to stop both servers.

Edit any `*.py` file under `api/`, `data/`, `signals/`, etc → backend
restarts in ~1s. Edit any `*.tsx` / `*.ts` file under `frontend/src/` →
the browser updates instantly (Vite HMR).

> Windows note: if PowerShell refuses to run `.\dev.ps1` with an
> "execution policy" error, run this once in the same window first:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

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

## 📦 Production-ish run via Docker (no host installs needed)

Use this when you don't want to install Python and Node on the host, or
to demo on a friend's machine. Builds two images and starts them with one
command:

```bash
docker compose up --build
```

Wait ~60 seconds for the first build, then open
**<http://localhost:5173>**. `Ctrl+C` to stop.

This path does **not** hot-reload (each code change needs `docker compose
up --build` again). Use the dev mode above for editing.

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
