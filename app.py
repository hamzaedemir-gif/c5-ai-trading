"""C5 Live Paper Trading Dashboard (simulation only).

Run with:  streamlit run app.py   (or double-click run_c5.bat on Windows)

PAPER TRADING ONLY. This app does NOT place real orders, does NOT connect to a
brokerage for execution, uses NO real money, and makes NO profit guarantees.
Losses are shown honestly. The Confluence Score is decision-support and is NOT
history validated.
"""
from __future__ import annotations

import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from c5.config import (
    ALL_MODES,
    MODE_FINNHUB,
    MODE_MANUAL,
    MODE_MOCK,
    MODE_WEBULL,
    get_settings,
)
from c5.data.provider import MarketDataProvider
from c5.db import Store
from c5.engine import indicators as ind
from c5.engine.confluence import SCORE_LABEL
from c5.market_hours import AFTER_HOURS_WARNING, is_after_hours, market_session
from c5.paper import AutoConfig, AutoTrader, PaperAccount
from c5.scanner import parse_watchlist, scan

st.set_page_config(page_title="C5 Live Paper Trading", layout="wide", page_icon="📈")

PAPER_BANNER = "🧾 Paper trade only — simulation, no real orders, no real money."
MIN_CANDLES_FOR_CHART = 8


# ----------------------------------------------------------------------
# Key resolution + provider
# ----------------------------------------------------------------------
def resolve_finnhub_key() -> str:
    """Priority: in-app sidebar input > Streamlit secrets > .env/env. Never printed."""
    k = st.session_state.get("finnhub_key", "").strip()
    if k:
        return k
    try:
        if "FINNHUB_API_KEY" in st.secrets:  # type: ignore[attr-defined]
            return str(st.secrets["FINNHUB_API_KEY"]).strip()
    except Exception:
        pass
    return st.session_state.settings.finnhub_api_key


def provider_signature(mode: str, key: str) -> str:
    return f"{mode}:{'set' if key else 'none'}:{hash(key) & 0xFFFF if key else 0}"


def get_provider() -> MarketDataProvider:
    mode = st.session_state.mode
    key = resolve_finnhub_key()
    sig = provider_signature(mode, key)
    if st.session_state.get("provider_sig") != sig:
        st.session_state.provider = MarketDataProvider(mode, key)
        st.session_state.provider_sig = sig
    return st.session_state.provider


# ----------------------------------------------------------------------
# State init
# ----------------------------------------------------------------------
def init_state() -> None:
    if "settings" not in st.session_state:
        st.session_state.settings = get_settings()
    s = st.session_state.settings

    st.session_state.setdefault("store", Store(s.db_path))
    st.session_state.setdefault("account", PaperAccount(st.session_state.store, s.starting_cash))
    st.session_state.setdefault("auto_trader", AutoTrader(st.session_state.account))
    st.session_state.setdefault("mode", s.data_mode)
    st.session_state.setdefault("watchlist_text", s.default_watchlist)
    st.session_state.setdefault("finnhub_key", "")
    st.session_state.setdefault("event_risk", False)
    st.session_state.setdefault("low_float", False)
    st.session_state.setdefault("auto_enabled", False)
    st.session_state.setdefault("max_alloc", 200.0)
    st.session_state.setdefault("max_simul", 5)
    st.session_state.setdefault("max_risk_pct", 1.0)


# ----------------------------------------------------------------------
# Badges / labels
# ----------------------------------------------------------------------
def mode_badge(provider: MarketDataProvider, any_live: bool, any_delayed: bool) -> str:
    mode = st.session_state.mode
    if mode == MODE_MOCK:
        return "🧪 MOCK"
    if mode == MODE_MANUAL:
        return "✍️ MANUAL"
    if mode == MODE_WEBULL:
        return "🚧 WEBULL PENDING"
    if mode == MODE_FINNHUB:
        if provider.fell_back:
            return "🟠 FINNHUB — NO KEY (mock fallback)"
        if any_delayed and not any_live:
            return "🟡 FINNHUB DELAYED"
        if any_live:
            return "🟢 FINNHUB LIVE"
        return "🔴 FINNHUB DISCONNECTED"
    return mode.upper()


def session_badge() -> str:
    sess = market_session().upper()
    icon = {"REGULAR": "🟢", "PRE": "🌅", "AFTER": "🌙", "CLOSED": "🔴"}.get(sess, "•")
    return f"{icon} {sess}"


# ----------------------------------------------------------------------
# Charts
# ----------------------------------------------------------------------
def render_tradingview(symbol: str) -> None:
    st.caption("📺 TradingView chart (visual reference only — paper P/L uses the data-feed quote).")
    html = f"""
    <div class="tradingview-widget-container">
      <div id="tv_chart"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "width": "100%", "height": 380, "symbol": "{symbol}", "interval": "1",
        "timezone": "America/New_York", "theme": "light", "style": "1",
        "locale": "en", "toolbar_bg": "#f1f3f6", "hide_top_toolbar": false,
        "allow_symbol_change": true, "container_id": "tv_chart"
      }});
      </script>
    </div>
    """
    components.html(html, height=400)


def render_candles(candles: pd.DataFrame, symbol: str) -> None:
    df = candles.copy()
    df["vwap"] = ind.vwap(df)
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df["time"], open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name=symbol))
    fig.add_trace(go.Scatter(x=df["time"], y=df["vwap"], name="VWAP",
                             line=dict(color="orange", width=1.5)))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                      xaxis_rangeslider_visible=False, showlegend=True)
    st.plotly_chart(fig, use_container_width=True)


# ----------------------------------------------------------------------
# Sections
# ----------------------------------------------------------------------
def render_top(provider, opps) -> None:
    any_live = any(o.health.is_live for o in opps)
    any_delayed = any(o.health.delayed for o in opps)
    st.title("📈 C5 Live Paper Trading Dashboard")
    b1, b2, b3, b4 = st.columns(4)
    b1.markdown(f"**Data mode**\n\n{mode_badge(provider, any_live, any_delayed)}")
    b2.markdown(f"**Market session**\n\n{session_badge()}")
    feed_txt = "🟢 LIVE" if any_live else ("🟡 DELAYED" if any_delayed else "⚪ no live feed")
    b3.markdown(f"**Feed health**\n\n{feed_txt}")
    b4.markdown(f"**Mode**\n\n{'AUTO ▶' if st.session_state.auto_enabled else 'manual ⏸'}")
    st.warning(
        f"{PAPER_BANNER} No brokerage execution. No profit guarantees. "
        f"Scores are _{SCORE_LABEL}_.",
        icon="⚠️",
    )
    if st.session_state.mode == MODE_FINNHUB and provider.fell_back:
        st.error("Finnhub selected but no API key found — falling back to MOCK data. "
                 "Paste your key in the sidebar to use real prices.")
    if st.session_state.mode == MODE_FINNHUB and is_after_hours():
        st.warning(AFTER_HOURS_WARNING, icon="🌙")
    if st.session_state.mode == MODE_WEBULL:
        st.info("Webull mode is a placeholder pending OpenAPI approval — no data, no execution.")


def render_account(account: PaperAccount, store: Store, price_map) -> None:
    st.subheader("1 · Paper Account Summary")
    equity = account.equity(price_map)
    unreal = account.open_unrealized(price_map)
    realized = account.realized_pnl()
    total_ret = 100.0 * (equity - account.starting_cash) / account.starting_cash
    wl = store.win_loss_counts()

    c = st.columns(6)
    c[0].metric("Starting", f"${account.starting_cash:,.0f}")
    c[1].metric("Equity", f"${equity:,.2f}", f"{total_ret:+.2f}%")
    c[2].metric("Cash", f"${account.cash:,.2f}")
    c[3].metric("Realized P/L", f"${realized:+,.2f}")
    c[4].metric("Unrealized P/L", f"${unreal:+,.2f}")
    c[5].metric("Open / W / L", f"{len(account.positions)} / {wl['wins']} / {wl['losses']}")


def render_watchlist(opps) -> None:
    st.subheader("2 · Live Watchlist Prices")
    rows = []
    for o in opps:
        q = o.quote
        rows.append({
            "Symbol": o.symbol,
            "Price": round(q.price, 4) if q.price else None,
            "Change": round(q.change, 4) if q.change is not None else None,
            "Change %": round(q.change_pct, 2) if q.change_pct is not None else None,
            "Source": (q.source or st.session_state.mode).upper(),
            "Quote time": time.strftime("%H:%M:%S", time.localtime(q.ts)) if q.ts else "—",
            "Live/Delayed": o.data_label,
            "Session": market_session().upper(),
            "Spread %": round(q.spread_pct, 3) if q.spread_pct is not None else None,
            "Feed": o.health.label,
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def render_opportunities(opps) -> None:
    st.subheader("3 · Ranked Opportunities  ·  _Confluence Score — not history validated_")
    candidates = [o for o in opps if o.is_candidate]
    if not candidates:
        st.error("🚫 NO TRADE — no valid setup across the watchlist right now. "
                 "C5 will not force trades.", icon="🚫")
    rows = []
    for o in opps:
        rows.append({
            "Symbol": o.symbol,
            "Score": o.score,
            "Band": o.band,
            "Setup": o.setup.kind if o.setup.detected else "—",
            "Dir": o.setup.direction if o.setup.detected else "—",
            "Entry": round(o.setup.entry, 4) if o.setup.entry else None,
            "Stop": round(o.setup.stop, 4) if o.setup.stop else None,
            "Target": round(o.setup.target, 4) if o.setup.target else None,
            "R:R": round(o.setup.rr, 2) if o.setup.rr else None,
            "Candidate": "✓" if o.is_candidate else "",
            "70+ Qualifies": "🔥" if o.qualifies else "",
        })
    df = pd.DataFrame(rows)

    def _hl(row):
        if row["70+ Qualifies"] == "🔥":
            return ["background-color: #1b5e20; color: white"] * len(row)
        return [""] * len(row)

    st.dataframe(df.style.apply(_hl, axis=1), hide_index=True, use_container_width=True)


def render_open_trades(account: PaperAccount, by_symbol) -> None:
    st.subheader("4 · Open Paper Trades  ·  live P/L")
    if not account.positions:
        st.caption("No open paper trades.")
    else:
        rows = []
        now = time.time()
        for p in account.positions.values():
            opp = by_symbol.get(p.symbol)
            cur = opp.quote.price if (opp and opp.quote.price > 0) else p.entry_price
            t_left = max(0, int(p.duration - (now - p.opened_ts))) if p.opened_ts else None
            rows.append({
                "ID": p.trade_id, "Symbol": p.symbol, "Setup": p.setup or "—",
                "Side": p.side, "Auto": "🤖" if p.is_auto else "",
                "Entry": round(p.entry_price, 4), "Current": round(cur, 4),
                "Stop": round(p.stop, 4) if p.stop else None,
                "Target": round(p.target, 4) if p.target else None,
                "Qty": round(p.qty, 4),
                "P/L $": round(p.unrealized_pnl(cur), 2),
                "P/L %": round(p.unrealized_pct(cur), 2),
                "Time left": f"{t_left // 60}m{t_left % 60:02d}s" if t_left is not None else "—",
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    log = st.session_state.auto_trader.log
    if log:
        with st.expander("Auto-trader activity (recent)", expanded=False):
            for line in reversed(log[-25:]):
                st.text(line)


def render_selected(opps) -> None:
    st.subheader("5 · Selected Symbol — Chart & Setup")
    symbols = [o.symbol for o in opps]
    if not symbols:
        return
    sel = st.selectbox("Symbol", symbols, key="selected_symbol")
    opp = next((o for o in opps if o.symbol == sel), None)
    if opp is None:
        return

    enough = opp.candles is not None and len(opp.candles) >= MIN_CANDLES_FOR_CHART
    if st.session_state.mode == MODE_FINNHUB and not enough:
        st.info("Finnhub still accumulating candles — showing TradingView reference chart.")
        render_tradingview(sel)
    elif enough:
        render_candles(opp.candles, sel)
    else:
        render_tradingview(sel)

    if opp.result is None:
        st.caption("No score yet (insufficient data).")
        return
    res = opp.result
    ca, cb = st.columns([1, 2])
    with ca:
        st.metric(f"Score ({res.band})", f"{res.total}/100")
        st.caption("🟢 LIVE" if res.is_live else "⚪ not live")
        st.caption(f"_{SCORE_LABEL}_")
    with cb:
        comp_df = pd.DataFrame(
            [{"Component": c.name, "Score": c.score, "Max": c.max_points} for c in res.components])
        st.dataframe(comp_df, hide_index=True, use_container_width=True)
    r1, r2 = st.columns(2)
    with r1:
        st.markdown("**Reasons**")
        for r in (res.reasons or ["_No supporting reasons._"]):
            st.markdown(f"- {r}")
    with r2:
        st.markdown("**Warnings**")
        if res.warnings:
            for w in res.warnings:
                tag = "🚨 critical" if w.critical else "⚠️"
                st.markdown(f"- {tag} **{w.label}** ({w.penalty}) — {w.detail}")
        else:
            st.markdown("- _None._")


def render_trade_log(store: Store) -> None:
    st.subheader("6 · Closed Trades / Trade Log")
    trades = store.get_trades(300)
    if not trades:
        st.caption("No paper trades yet.")
        return
    df = pd.DataFrame(trades)
    for col in ("opened_ts", "closed_ts"):
        if col in df:
            df[col] = pd.to_datetime(df[col], unit="s").dt.strftime("%Y-%m-%d %H:%M:%S")
    rename = {
        "id": "Trade ID", "symbol": "Symbol", "setup": "Setup", "opened_ts": "Entry time",
        "entry_price": "Entry", "closed_ts": "Exit time", "exit_price": "Exit", "qty": "Qty",
        "confluence": "Score", "reasons": "Reasons", "warnings": "Warnings",
        "mode": "Source", "feed_label": "Live/Delayed", "reason": "Exit reason",
        "pnl": "P/L $", "pnl_pct": "P/L %", "side": "Side", "status": "Status",
        "is_auto": "Auto", "is_test": "Test",
    }
    order = ["id", "symbol", "setup", "side", "opened_ts", "entry_price", "closed_ts",
             "exit_price", "qty", "confluence", "reasons", "warnings", "mode",
             "feed_label", "reason", "pnl", "pnl_pct", "status", "is_auto"]
    df = df[[c for c in order if c in df.columns]].rename(columns=rename)
    st.dataframe(df, hide_index=True, use_container_width=True)


# ----------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------
def render_sidebar() -> None:
    s = st.session_state.settings
    st.sidebar.title("C5 controls")
    st.sidebar.caption("Paper trading only · no real orders")

    mode_names = {MODE_MOCK: "Mock (synthetic)", MODE_MANUAL: "Manual entry",
                  MODE_FINNHUB: "Finnhub (live/delayed)", MODE_WEBULL: "Webull (placeholder)"}
    st.session_state.mode = st.sidebar.selectbox(
        "Data mode", ALL_MODES, index=ALL_MODES.index(st.session_state.mode),
        format_func=lambda m: mode_names.get(m, m))

    # Finnhub key — password field, never echoed/committed, session-only.
    st.sidebar.markdown("**Finnhub API key** (session only)")
    st.session_state.finnhub_key = st.sidebar.text_input(
        "Paste FINNHUB_API_KEY", value=st.session_state.finnhub_key,
        type="password", label_visibility="collapsed",
        placeholder="paste key for live prices")
    if st.session_state.mode == MODE_FINNHUB:
        if resolve_finnhub_key():
            st.sidebar.success("Finnhub key active (hidden).")
        else:
            st.sidebar.error("No key — using mock fallback. Add a key for real prices.")

    st.sidebar.markdown("**Watchlist**")
    st.session_state.watchlist_text = st.sidebar.text_area(
        "Tickers (comma separated)", value=st.session_state.watchlist_text, height=70)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Auto Paper Trading")
    st.session_state.auto_enabled = st.sidebar.toggle(
        "Enable Auto Paper Trading", value=st.session_state.auto_enabled)
    st.session_state.max_alloc = st.sidebar.number_input(
        "Max allocation / trade ($)", min_value=10.0, value=float(st.session_state.max_alloc), step=10.0)
    st.session_state.max_simul = st.sidebar.number_input(
        "Max simultaneous trades", min_value=1, max_value=20, value=int(st.session_state.max_simul))
    st.session_state.max_risk_pct = st.sidebar.number_input(
        "Max risk / trade (% of equity)", min_value=0.1, max_value=10.0,
        value=float(st.session_state.max_risk_pct), step=0.1)
    st.sidebar.caption("Auto-entry gate: score ≥ 70, no critical warning, valid entry/stop/target.")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Simulated warning toggles** (apply to scan)")
    st.session_state.event_risk = st.sidebar.checkbox(
        "Imminent event risk (-15, critical)", value=st.session_state.event_risk)
    st.session_state.low_float = st.sidebar.checkbox(
        "Low float / gap risk (-8)", value=st.session_state.low_float)

    st.sidebar.markdown("---")
    st.session_state.auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)
    st.session_state.interval = st.sidebar.slider("Refresh seconds", 2, 30, 10)
    st.sidebar.caption("Finnhub free tier ≈ 60 calls/min. With N tickers, keep interval ≥ N seconds.")
    if st.sidebar.button("🔄 Refresh now"):
        st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("⚠️ Reset paper account & log"):
        st.session_state.store.reset()
        st.session_state.account = PaperAccount(st.session_state.store, s.starting_cash)
        st.session_state.auto_trader = AutoTrader(st.session_state.account)
        st.rerun()


# ----------------------------------------------------------------------
# Live panel (auto-refreshing)
# ----------------------------------------------------------------------
def live_panel() -> None:
    s = st.session_state.settings
    provider = get_provider()
    account = st.session_state.account
    store = st.session_state.store
    auto = st.session_state.auto_trader

    symbols = parse_watchlist(st.session_state.watchlist_text)
    if not symbols:
        st.info("Add at least one ticker to the watchlist in the sidebar.")
        return

    opps = scan(provider, symbols, s, st.session_state.event_risk, st.session_state.low_float)
    by_symbol = {o.symbol: o for o in opps}
    price_map = {o.symbol: o.quote.price for o in opps if o.quote.price > 0}

    # Run the automated engine (exits always; entries only when enabled).
    config = AutoConfig(
        enabled=st.session_state.auto_enabled,
        max_alloc_per_trade=float(st.session_state.max_alloc),
        max_simultaneous=int(st.session_state.max_simul),
        max_risk_pct=float(st.session_state.max_risk_pct),
        duration_seconds=s.trade_test_seconds,
    )
    auto.step(opps, config)
    store.log_feed_health(st.session_state.mode,
                          opps[0].health.status if opps else "n/a",
                          opps[0].health.detail if opps else "")
    account.snapshot(price_map)

    render_top(provider, opps)
    st.markdown("---")
    render_account(account, store, price_map)
    st.markdown("---")
    render_watchlist(opps)
    st.markdown("---")
    render_opportunities(opps)
    st.markdown("---")
    render_open_trades(account, by_symbol)
    st.markdown("---")
    render_selected(opps)
    st.markdown("---")
    render_trade_log(store)


def main() -> None:
    init_state()
    render_sidebar()
    interval = st.session_state.get("interval", 10) if st.session_state.get("auto_refresh", True) else None
    if hasattr(st, "fragment"):
        st.fragment(run_every=interval)(live_panel)()
    else:  # pragma: no cover
        live_panel()


if __name__ == "__main__":
    main()
