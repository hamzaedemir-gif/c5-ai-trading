# c5-ai-trading

C5 AI Trading is a local paper-trading decision-support prototype for US equities.
It uses setup detection, confluence scoring, warnings, and paper-trade logging.
It does not place real trades, does not execute orders, and does not guarantee profit.

---

## ⚠️ Disclaimer

**Simulation only.** C5 v1 is a paper-trading prototype. It does **not** connect to a
brokerage for trading, does **not** route or execute real orders, and makes **no profit
guarantees**. All trades, balances, and P/L are simulated. The Confluence Score is a
decision-support signal — **not history validated** — and must not be treated as
financial advice.

---

## What C5 v1 includes

- **Streamlit dashboard** — single-screen control panel
- **$1,000 paper account** — fully simulated cash, positions, and P/L
- **Live current-price display** and **candlestick chart panel**
- **Setup detection** — identifies candidate intraday setups
- **Confluence Score (0–100)** — the C5 model, with component breakdown, reasons, and warnings
- **10-minute paper-trade test** — a timed simulated trade with mark-to-market P/L
- **Trade log** — every paper trade persisted to **SQLite**
- **Feed health status** — live / stale / disconnected indicator per data source

## Data feed modes

| Mode | Status | Needs |
|------|--------|-------|
| `mock` | ✅ Works immediately (default) | nothing |
| `manual` | ✅ Available | you type prices in the UI |
| `finnhub` | ✅ Ready, dormant until you add a key | `FINNHUB_API_KEY` |
| `webull` | 🚧 Placeholder only | pending Webull OpenAPI approval |

## Quick start

```bash
# 1. (optional) create a virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. install dependencies
pip install -r requirements.txt

# 3. run the app (mock mode — no configuration needed)
streamlit run app.py
```

The app opens in your browser (default http://localhost:8501) and starts in **mock mode**
immediately. To use other modes, copy `.env.example` to `.env` and adjust `C5_DATA_MODE`.

## Project layout

```
app.py                 Streamlit dashboard (entry point)
c5/
  config.py            settings + mode selection
  data/                pluggable price feeds (mock, manual, finnhub, webull)
  engine/              indicators, setup detection, confluence scoring
  paper/               $1,000 paper account + 10-minute trade test
  db/                  SQLite store (trade log, snapshots, feed health)
tests/                 unit tests
```

## Roadmap

1. ✅ Phase 0 — scaffold
2. ✅ Phase 1 — mock mode (runs immediately)
3. ✅ Manual mode
4. ⏳ Finnhub mode — code present, dormant until a key is supplied
5. 🚧 Webull mode — placeholder only, pending OpenAPI approval
