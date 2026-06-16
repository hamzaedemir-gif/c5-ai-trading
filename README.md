# c5-ai-trading

C5 AI Trading is a local paper-trading decision-support prototype for US equities.
It uses setup detection, confluence scoring, warnings, and paper-trade logging.
It does not place real trades, does not execute orders, and does not guarantee profit.

---

## ⚠️ Disclaimer

**Paper trade only — simulation.** C5 does **not** connect to a brokerage for
trading, does **not** route or execute real orders, uses **no real money**, and
makes **no profit guarantees**. All trades, balances, and P/L are simulated, and
losses are shown honestly. The Confluence Score is decision-support — **not
history validated** — and is not financial advice.

---

## What C5 does now (Live Paper Trading Dashboard)

- **Live multi-symbol watchlist** — prices, change, source, quote time, live/delayed status, market session, spread, and feed health for every ticker.
- **Finnhub real-price mode** — live/delayed US-equity quotes when an API key is provided (paste it in the sidebar or set it in secrets/.env).
- **Live scanner** — continuously scans the watchlist, runs C5 setup detection, computes the Confluence Score, and shows a **ranked opportunities** table (highest score first). Shows **NO TRADE** when nothing valid appears.
- **Automated paper-trading engine** — an **Auto Paper Trading** toggle that opens paper trades for every qualifying setup (score ≥ 70, no critical warning, valid entry/stop/target) and **exits on rules**: target hit, stop hit, 10-minute time exit, setup invalidation, or a critical warning.
- **Live paper P/L** — $1,000 paper account, equity, cash, realized/unrealized P/L, total return %, win/loss counts, and per-trade detail.
- **Detailed trade log** — every paper trade with score, reasons, warnings, data source, live/delayed label, exit reason, and P/L.

### Data feed modes

| Mode | Label in app | Status |
|------|--------------|--------|
| `mock` | 🧪 MOCK | Works immediately (default), synthetic prices |
| `manual` | ✍️ MANUAL | Type prices in the UI |
| `finnhub` | 🟢 FINNHUB LIVE / 🟡 FINNHUB DELAYED / 🔴 FINNHUB DISCONNECTED | Real prices when a key is provided |
| `webull` | 🚧 WEBULL PENDING | Placeholder only — pending Webull OpenAPI (B1) approval |

---

## Open the app without using a terminal (Windows)

**Double-click `run_c5.bat` to launch C5.**

It will create a virtual environment if needed, install requirements, start the
app, and open **http://localhost:8501** in your browser automatically.

## Run manually (any OS)

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens at http://localhost:8501 and starts in **MOCK** mode with the
**$1,000** paper account.

## Use real Finnhub prices

Three ways to supply your key (priority order):

1. **In the app (easiest for testing):** sidebar → **Finnhub API key** → paste your key (hidden, session-only, never committed). Then set **Data mode → Finnhub**.
2. **Streamlit secrets:** copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and set `FINNHUB_API_KEY`.
3. **`.env` file:**
   ```
   FINNHUB_API_KEY=MY_REAL_KEY
   C5_DATA_MODE=finnhub
   ```

Get a free key at https://finnhub.io/dashboard. If Finnhub is delayed it is
labelled **FINNHUB DELAYED**; if disconnected it shows **FINNHUB DISCONNECTED**
and falls back to mock with a warning. When Finnhub has too few candles, the
quote still drives paper P/L and a **TradingView** chart is embedded for reference.

> **Rate limits:** the Finnhub free tier allows ~60 calls/min. The scanner makes
> one call per ticker per refresh, so keep the refresh interval ≥ (number of
> tickers) seconds.

---

## Deploy to Streamlit Community Cloud (hosted website)

1. Push this repo to GitHub (already done).
2. Go to **https://share.streamlit.io** → **New app**.
3. Pick this repository/branch and set the main file to **`app.py`**.
4. `requirements.txt` is already present — Streamlit Cloud installs it automatically.
5. **Set your key:** app → **Settings → Secrets**, paste:
   ```
   FINNHUB_API_KEY = "your_key_here"
   ```
6. Deploy. The app runs in hosted mode exactly like local; users select **Finnhub**
   mode and the key is read from secrets. No key is ever committed to the repo.

The app works in hosted mode with the same features (watchlist, scanner, auto
paper trading, trade log). It remains **paper trading only** — there is no
brokerage execution in any mode.

---

## Webull

**Webull stays a placeholder (🚧 WEBULL PENDING) — no connection, no data, no
order execution — until your Webull OpenAPI (B1) approval clears.** Once approved,
a real Webull data feed can be added behind the same interface the other feeds use.

---

## Project layout

```
app.py                 Streamlit dashboard (entry point)
run_c5.bat             Windows one-click launcher
c5/
  config.py            settings + mode selection
  market_hours.py      US market-session helper
  scanner.py           multi-symbol scan + ranking
  data/                feeds + multi-symbol provider
  engine/              indicators, setup detection, confluence scoring
  paper/               $1,000 account + auto-trading engine
  db/                  SQLite store (trades, snapshots, feed health)
tests/                 unit tests
```

## Tests

```bash
pip install pytest
pytest -q
```
