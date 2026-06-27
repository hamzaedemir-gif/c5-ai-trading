# C5 Trading Center — First Draft (Scaffold)

A runnable Streamlit prototype of **C5 Trading Center**.

> **C5 is an automated trading system that watches the U.S. market across the full
> regular session — from early-market open through the normal close — and takes
> trades on its own when its engine rates a setup highly enough. It does not trade
> after-hours.** A user connects an account, picks how much to commit, sets a
> confidence threshold, chooses live or paper mode, and presses START. C5 then
> shows every trade it takes, the running balance, live charts, a reviewable
> history of past trades, and a day-by-day profit/loss summary. STOP halts it.

## ⚠️ This is a scaffold / first draft

Everything external is a **mock stub returning simulated data**. There are **no real
accounts, no real money, and no real orders**. Each real wiring point is marked with
`# TODO:` in the code.

## Run it

```bash
cd c5-trading-center
python3 -m venv venv && source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Opens at http://localhost:8501.

## Navigate end-to-end

**Home** → *Sign up / Sign in* → **Sign in / Connect** (any email; connect TradingView +
Webull) → **Investing** (pick the 4 settings) → **Trading** (press **START** to run the
simulated loop, **STOP** to halt). Past trades are clickable for detail; P&L shows a
day-by-day summary.

Settings persist across pages. Defaults: **confidence 70**, **Paper** mode.

## Layout

```
app.py                  entry point + session_state view routing
config.py               every tunable value (session window, money, confidence, modes)
styles.py               black & blue CSS (P/L green/red only)
state.py                session_state init + navigation helpers
.streamlit/config.toml  dark black & blue theme
tradingview.py          TradingView Advanced Chart embed (DISPLAY ONLY) + symbol map
views/
  home.py               hero + "what C5 is" + Sign up / Sign in
  signin.py             mock email auth + mock TradingView/Webull connect
  investing.py          screener + the 4 run settings + Open Charts link
  trading.py            START/STOP + simulated loop + live TradingView chart
  charts.py             pull up a TradingView chart for any US ticker
stubs/
  auth.py               sign_in()                       # mock
  brokers.py            connect_tradingview/webull()    # mock
  data_feed.py          candidate_tickers/live/yesterday prices  # mock
  broker.py             place_order/close_order()       # mock
  c5_engine.py          get_confluence()                # mock (10–99)
```

## Charts — TradingView is DISPLAY ONLY

The app embeds TradingView's free **Advanced Chart** widget (`tradingview.py`,
`tv_chart(symbol, height=520)`) purely as the **visual chart layer**:

- The **Trading** page shows the TradingView chart for the trade currently being
  taken (resyncs on refresh / the "Sync to current trade" button).
- The **Charts** page lets you pull up any US ticker (search/select), mapping
  plain tickers to TradingView's `EXCHANGE:SYMBOL` format where known.

**TradingView is never a data source.** Every price C5 analyzes and trades on
comes from the market-data provider (Webull OpenAPI primary, Finnhub backup) via
`stubs/data_feed.py`. No analysis or trade data is read from TradingView.

- [ ] **(Optional future)** Upgrade the embedded widget to the TradingView
      **Charting Library** + a custom **Datafeed API** adapter wired to the same
      Webull/Finnhub feed C5 analyzes, so the displayed candles match the
      analyzed candles exactly. (See the TODO in `tradingview.py`.)

## Confidence wording

The threshold is labelled a **confluence score (10–99)** — a transparent confluence
reading from the C5 engine, **not** a statistical probability or percentage.

## Timezone — CONFIRM before wiring real data

`config.py` binds the session window to **one** timezone (`SESSION_TIMEZONE`). The
draft uses `America/Chicago` because `SESSION_START = 03:00` matches CT pre-market
open (= 04:00 ET). U.S. regular hours are 09:30–16:00 ET (08:30–15:00 CT).
**Re-confirm `SESSION_END`** (16:00 ET close = 15:00 CT) before connecting live data.

## TODO — real integration points still to wire

Search the code for `# TODO:`. Each is a mock today:

- [ ] **Auth** — `stubs/auth.py: sign_in()` → real authentication.
- [ ] **TradingView** — `stubs/brokers.py: connect_tradingview()` → connect / execution
      path only (not a C5 data source).
- [ ] **Webull OpenAPI** — `stubs/brokers.py: connect_webull()` + `stubs/data_feed.py`
      → primary read-only market data and (later) execution. Its OHLCV bars endpoint is
      ~1 call/sec, so scanning every U.S. ticker live is not feasible — the real feed
      must **pre-filter candidates** (Top Active / Gainers / Losers funnel). The draft
      uses a fixed mock candidate list.
- [ ] **C5 database / confluence engine** — `stubs/c5_engine.py: get_confluence()` →
      real source of the live chart reading and the 10–99 confluence score.
- [ ] **Market data** — `stubs/data_feed.py: live_prices()` / `yesterday_prices()` →
      real live prices and previous-session replay for paper.
- [ ] **Execution** — `stubs/broker.py: place_order()` / `close_order()` → real orders.
      Keep **LIVE execution behind an explicit confirmation step**; default to Paper.
- [ ] **Session window / timezone** — confirm `SESSION_START/END` + `SESSION_TIMEZONE`
      in `config.py`. No after-hours trading (`TRADE_AFTER_HOURS = False`).
```
```
