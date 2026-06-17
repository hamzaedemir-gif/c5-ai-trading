"""C5 Paper Trading — simple dashboard (simulation only).

Run with:  streamlit run app.py   (or double-click run_c5.bat on Windows)

PAPER TRADING ONLY. No real orders, no brokerage execution, no real money, no
profit guarantees. Losses are shown honestly. Prices can be simulated or real
(Finnhub); either way every trade here is paper.
"""
from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from c5.config import MODE_FINNHUB, MODE_MOCK, get_settings
from c5.data.provider import MarketDataProvider
from c5.db import Store
from c5.market_hours import market_session
from c5.paper import AutoConfig, AutoTrader, PaperAccount
from c5.scanner import parse_watchlist, scan

st.set_page_config(page_title="C5 Paper Trading", layout="wide", page_icon="📈")


# ----------------------------------------------------------------------
# Setup
# ----------------------------------------------------------------------
def resolve_finnhub_key() -> str:
    k = st.session_state.get("finnhub_key", "").strip()
    if k:
        return k
    try:
        if "FINNHUB_API_KEY" in st.secrets:  # type: ignore[attr-defined]
            return str(st.secrets["FINNHUB_API_KEY"]).strip()
    except Exception:
        pass
    return st.session_state.settings.finnhub_api_key


def get_provider() -> MarketDataProvider:
    mode = st.session_state.mode
    key = resolve_finnhub_key()
    sig = f"{mode}:{bool(key)}:{hash(key) & 0xFFFF if key else 0}"
    if st.session_state.get("provider_sig") != sig:
        st.session_state.provider = MarketDataProvider(mode, key)
        st.session_state.provider_sig = sig
    return st.session_state.provider


def init_state() -> None:
    if "settings" not in st.session_state:
        st.session_state.settings = get_settings()
    s = st.session_state.settings
    st.session_state.setdefault("store", Store(s.db_path))
    st.session_state.setdefault("account", PaperAccount(st.session_state.store, s.starting_cash))
    st.session_state.setdefault("auto_trader", AutoTrader(st.session_state.account))
    st.session_state.setdefault("mode", MODE_MOCK)            # simulated by default
    st.session_state.setdefault("watchlist_text", s.default_watchlist)
    st.session_state.setdefault("finnhub_key", "")
    st.session_state.setdefault("max_alloc", 200.0)
    st.session_state.setdefault("min_gain_pct", 1.0)
    st.session_state.setdefault("auto_enabled", True)         # let trades happen


# ----------------------------------------------------------------------
# Sidebar = Settings
# ----------------------------------------------------------------------
def render_sidebar() -> None:
    s = st.session_state.settings
    st.sidebar.title("⚙️ Settings")
    st.sidebar.caption("Paper trading only · no real orders")

    mode_label = st.sidebar.radio(
        "Prices", ["Simulated", "Finnhub (real)"],
        index=0 if st.session_state.mode == MODE_MOCK else 1)
    st.session_state.mode = MODE_MOCK if mode_label == "Simulated" else MODE_FINNHUB

    if st.session_state.mode == MODE_FINNHUB:
        st.session_state.finnhub_key = st.sidebar.text_input(
            "Finnhub API key", value=st.session_state.finnhub_key,
            type="password", placeholder="paste key for real prices")
        st.sidebar.caption("Real prices need a key. Without one it stays simulated.")

    st.sidebar.markdown("**Tickers** (all are watched & tradable)")
    st.session_state.watchlist_text = st.sidebar.text_area(
        "Tickers", value=st.session_state.watchlist_text, height=80,
        label_visibility="collapsed")

    st.sidebar.markdown("---")
    st.session_state.max_alloc = st.sidebar.number_input(
        "💵 Max allocation per trade ($)", min_value=10.0,
        value=float(st.session_state.max_alloc), step=10.0)
    st.session_state.min_gain_pct = st.sidebar.number_input(
        "🎯 Minimum gain per trade (%)", min_value=0.1, max_value=50.0,
        value=float(st.session_state.min_gain_pct), step=0.1,
        help="Each trade aims to sell once it's up at least this much.")
    st.session_state.auto_enabled = st.sidebar.toggle(
        "Auto-take trades", value=st.session_state.auto_enabled)

    st.sidebar.markdown("---")
    st.session_state.auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)
    st.session_state.interval = st.sidebar.slider("Refresh seconds", 2, 30, 5)
    if st.sidebar.button("🔄 Refresh now"):
        st.rerun()
    if st.sidebar.button("⚠️ Reset account & trades"):
        st.session_state.store.reset()
        st.session_state.account = PaperAccount(st.session_state.store, s.starting_cash)
        st.session_state.auto_trader = AutoTrader(st.session_state.account)
        st.rerun()


# ----------------------------------------------------------------------
# Main panels
# ----------------------------------------------------------------------
def render_summary(account: PaperAccount, store: Store, price_map) -> None:
    equity = account.equity(price_map)
    gain = equity - account.starting_cash
    gain_pct = 100.0 * gain / account.starting_cash
    summ = store.trade_summary()

    st.subheader("Account Summary")
    c = st.columns(5)
    c[0].metric("Balance (paper)", f"${equity:,.2f}", f"{gain_pct:+.2f}%")
    c[1].metric("Total gain", f"${gain:+,.2f}")
    c[2].metric("Started with", f"${account.starting_cash:,.0f}")
    c[3].metric("Trades taken", f"{summ['total']}")
    c[4].metric("Ongoing", f"{summ['open']}")


def render_tickers(opps) -> None:
    in_trade = {p.symbol for p in st.session_state.account.positions.values()}
    rows = []
    for o in opps:
        rows.append({
            "Ticker": o.symbol,
            "Price": f"${o.quote.price:,.2f}" if o.quote.price else "—",
            "Change %": round(o.quote.change_pct, 2) if o.quote.change_pct is not None else None,
            "Status": "📈 In trade" if o.symbol in in_trade else "👀 Watching",
        })
    with st.expander(f"Watching {len(opps)} tickers", expanded=False):
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def render_ongoing(account: PaperAccount, by_symbol) -> None:
    st.subheader("Ongoing Trades")
    if not account.positions:
        st.caption("No ongoing trades. They open automatically when a qualifying setup appears.")
        return
    rows = []
    for p in account.positions.values():
        opp = by_symbol.get(p.symbol)
        cur = opp.quote.price if (opp and opp.quote.price > 0) else p.entry_price
        rows.append({
            "Ticker": p.symbol,
            "Got in at": f"${p.entry_price:,.2f}",
            "Current": f"${cur:,.2f}",
            "Gain so far": f"${p.unrealized_pnl(cur):+,.2f}",
            "Gain %": f"{p.unrealized_pct(cur):+.2f}%",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def render_past(store: Store) -> None:
    st.subheader("Past Trades")
    closed = store.closed_trades(300)
    if not closed:
        st.caption("No completed trades yet.")
        return
    rows = []
    for t in closed:
        rows.append({
            "Ticker": t["symbol"],
            "Got in at": f"${(t['entry_price'] or 0):,.2f}",
            "Sold for": f"${(t['exit_price'] or 0):,.2f}",
            "Gain": f"${(t['pnl'] or 0):+,.2f}",
            "Gain %": f"{(t['pnl_pct'] or 0):+.2f}%",
            "Closed": time.strftime("%H:%M:%S", time.localtime(t["closed_ts"])) if t["closed_ts"] else "—",
        })
    df = pd.DataFrame(rows)
    total_gain = sum((t["pnl"] or 0) for t in closed)
    st.caption(f"{len(closed)} completed · total realized {total_gain:+.2f}")
    st.dataframe(df, hide_index=True, use_container_width=True)


# ----------------------------------------------------------------------
# Live loop
# ----------------------------------------------------------------------
def live_panel() -> None:
    s = st.session_state.settings
    provider = get_provider()
    account = st.session_state.account
    store = st.session_state.store
    auto = st.session_state.auto_trader

    symbols = parse_watchlist(st.session_state.watchlist_text)
    if not symbols:
        st.info("Add at least one ticker in Settings.")
        return

    opps = scan(provider, symbols, s)
    by_symbol = {o.symbol: o for o in opps}
    price_map = {o.symbol: o.quote.price for o in opps if o.quote.price > 0}

    config = AutoConfig(
        enabled=st.session_state.auto_enabled,
        max_alloc_per_trade=float(st.session_state.max_alloc),
        min_gain_pct=float(st.session_state.min_gain_pct),
        max_simultaneous=20,
        max_risk_pct=1.0,
        duration_seconds=s.trade_test_seconds,
    )
    auto.step(opps, config)
    account.snapshot(price_map)

    # Header
    real = provider.effective_mode == MODE_FINNHUB and any(o.health.is_live for o in opps)
    src = "🟢 Finnhub real prices" if real else "🧪 Simulated prices"
    st.caption(f"{src}  ·  US market: {market_session().upper()}  ·  "
               f"auto-take: {'ON' if st.session_state.auto_enabled else 'OFF'}")

    render_summary(account, store, price_map)
    render_tickers(opps)
    st.markdown("---")
    render_ongoing(account, by_symbol)
    st.markdown("---")
    render_past(store)


def main() -> None:
    init_state()
    st.title("📈 C5 Paper Trading")
    st.caption("🧾 Paper trade only — simulation, no real orders, no real money, no profit guarantees.")
    render_sidebar()
    interval = st.session_state.get("interval", 5) if st.session_state.get("auto_refresh", True) else None
    if hasattr(st, "fragment"):
        st.fragment(run_every=interval)(live_panel)()
    else:  # pragma: no cover
        live_panel()


if __name__ == "__main__":
    main()
