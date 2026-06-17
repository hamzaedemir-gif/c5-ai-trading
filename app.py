"""C5 Paper Trading — simple dashboard with full-market rotating scanner.

Run with:  streamlit run app.py   (or double-click run_c5.bat on Windows)

PAPER TRADING ONLY. No real orders, no brokerage execution, no real money, no
profit guarantees. Losses are shown honestly. Prices can be simulated or real
(Finnhub); every trade here is paper.
"""
from __future__ import annotations

import math
import time

import pandas as pd
import streamlit as st

from c5.config import MODE_FINNHUB, MODE_MOCK, get_settings
from c5.data.provider import MarketDataProvider
from c5.db import Store
from c5.demo import (
    DEFAULT_COMPRESSION,
    SESSION_OPEN,
    demo_clock,
    demo_session,
    session_progress,
)
from c5.market_hours import market_session
from c5.paper import AutoConfig, AutoTrader, PaperAccount
from c5.scanner import parse_watchlist, scan
from c5.universe import BUILTIN_UNIVERSE, fetch_us_universe, rotate_chunk

st.set_page_config(page_title="C5 Paper Trading", layout="wide", page_icon="📈")

UNIVERSE_FULL = "Entire US market"
UNIVERSE_POPULAR = "Popular list (~150)"
CHUNK_CAP = 40  # max symbols scanned per refresh (latency bound)


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


def get_universe() -> list:
    """The list of tickers the scanner rotates through, cached per session."""
    mode = st.session_state.mode
    key = resolve_finnhub_key()
    want_full = mode == MODE_FINNHUB and key and st.session_state.scan_universe == UNIVERSE_FULL
    cache_sig = f"{mode}:{st.session_state.scan_universe}:{bool(key)}"
    if st.session_state.get("universe_sig") != cache_sig:
        if want_full:
            st.session_state.universe = fetch_us_universe(key)
        else:
            st.session_state.universe = list(BUILTIN_UNIVERSE)
        st.session_state.universe_sig = cache_sig
        st.session_state.scan_cursor = 0
    return st.session_state.universe


def init_state() -> None:
    if "settings" not in st.session_state:
        st.session_state.settings = get_settings()
    s = st.session_state.settings
    st.session_state.setdefault("store", Store(s.db_path))
    st.session_state.setdefault("account", PaperAccount(st.session_state.store, s.starting_cash))
    st.session_state.setdefault("auto_trader", AutoTrader(st.session_state.account))
    st.session_state.setdefault("mode", MODE_MOCK)
    st.session_state.setdefault("priority_text", "AAPL, NVDA, TSLA, SPY")
    st.session_state.setdefault("finnhub_key", "")
    st.session_state.setdefault("scan_universe", UNIVERSE_FULL)
    st.session_state.setdefault("calls_per_min", 55)
    st.session_state.setdefault("scan_cursor", 0)
    st.session_state.setdefault("max_alloc", 200.0)
    st.session_state.setdefault("min_gain_pct", 1.0)
    st.session_state.setdefault("max_simul", 8)
    st.session_state.setdefault("auto_enabled", True)
    st.session_state.setdefault("demo_start", time.time())
    st.session_state.setdefault("compression", DEFAULT_COMPRESSION)


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
        st.session_state.scan_universe = st.sidebar.radio(
            "Scan universe", [UNIVERSE_FULL, UNIVERSE_POPULAR],
            index=0 if st.session_state.scan_universe == UNIVERSE_FULL else 1)

    st.sidebar.markdown("**Priority tickers** (always scanned)")
    st.session_state.priority_text = st.sidebar.text_input(
        "Priority", value=st.session_state.priority_text, label_visibility="collapsed")

    st.sidebar.markdown("---")
    st.session_state.max_alloc = st.sidebar.number_input(
        "💵 Max allocation per trade ($)", min_value=10.0,
        value=float(st.session_state.max_alloc), step=10.0)
    st.session_state.min_gain_pct = st.sidebar.number_input(
        "🎯 Minimum gain per trade (%)", min_value=0.1, max_value=50.0,
        value=float(st.session_state.min_gain_pct), step=0.1,
        help="Each trade aims to sell once it's up at least this much.")
    st.session_state.max_simul = st.sidebar.number_input(
        "🔢 Max simultaneous trades", min_value=1, max_value=50,
        value=int(st.session_state.max_simul))
    st.session_state.auto_enabled = st.sidebar.toggle(
        "Auto-take trades (rapid)", value=st.session_state.auto_enabled)

    with st.sidebar.expander("Advanced (scanner speed)"):
        st.session_state.calls_per_min = st.number_input(
            "Finnhub calls/min budget", min_value=10, max_value=2000,
            value=int(st.session_state.calls_per_min),
            help="Free tier ≈ 60. Raise this only if you have a paid Finnhub plan.")
        st.session_state.interval = st.slider("Refresh seconds", 2, 30, 6)
        st.session_state.compression = st.slider(
            "Demo-day speed (× real time)", 1.0, 30.0, float(st.session_state.compression),
            help="How fast the simulated trading day advances (Simulated mode).")

    if st.session_state.mode == MODE_MOCK:
        st.sidebar.markdown("---")
        if st.sidebar.button("🌅 Start new demo trading day"):
            st.session_state.demo_start = time.time()
            st.session_state.store.reset()
            st.session_state.account = PaperAccount(st.session_state.store, s.starting_cash)
            st.session_state.auto_trader = AutoTrader(st.session_state.account)
            st.rerun()

    st.sidebar.markdown("---")
    st.session_state.auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)
    if st.sidebar.button("🔄 Refresh now"):
        st.rerun()
    if st.sidebar.button("⚠️ Reset account & trades"):
        st.session_state.store.reset()
        st.session_state.account = PaperAccount(st.session_state.store, s.starting_cash)
        st.session_state.auto_trader = AutoTrader(st.session_state.account)
        st.rerun()


# ----------------------------------------------------------------------
# Scan-budget helper
# ----------------------------------------------------------------------
def compute_chunk_size(mode_is_real: bool, interval: int, reserved: int, universe_n: int) -> int:
    """Symbols to scan this refresh, respecting the Finnhub rate budget."""
    if not mode_is_real:
        return min(universe_n, max(20, CHUNK_CAP))  # mock has no rate limit
    budget = int(st.session_state.calls_per_min)
    per_refresh = max(1, int(budget * interval / 60))
    return max(1, min(CHUNK_CAP, per_refresh - reserved))


# ----------------------------------------------------------------------
# Panels
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


def render_scanner_status(universe_n, chunk_n, interval, scanned_syms, candidates) -> None:
    sweep_cycles = math.ceil(universe_n / max(1, chunk_n)) if universe_n else 0
    sweep_sec = sweep_cycles * interval
    sweep_txt = f"{sweep_sec // 60}m{sweep_sec % 60:02d}s" if sweep_sec < 3600 else f"~{sweep_sec // 3600}h{(sweep_sec % 3600) // 60}m"
    st.subheader("Scanner")
    c = st.columns(4)
    c[0].metric("Universe", f"{universe_n:,} tickers")
    c[1].metric("Per refresh", f"{chunk_n} scanned")
    c[2].metric("Full sweep ≈", sweep_txt)
    c[3].metric("Candidates now", f"{candidates}")
    st.caption("Auto-takes **only setups scoring 70+** on the Confluence model (not random); "
               "rotates through the whole universe in rate-safe chunks and re-checks open "
               "trades every refresh for fast exits.")


def render_activity() -> None:
    log = st.session_state.auto_trader.log
    if log:
        with st.expander("Live activity (entries & exits)", expanded=True):
            for line in reversed(log[-20:]):
                st.text(line)


def render_ongoing(account: PaperAccount, by_symbol) -> None:
    st.subheader("Ongoing Trades")
    if not account.positions:
        st.caption("No ongoing trades — they open automatically on qualifying setups.")
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
    total_gain = sum((t["pnl"] or 0) for t in closed)
    st.caption(f"{len(closed)} completed · total realized {total_gain:+.2f}")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


# ----------------------------------------------------------------------
# Live loop
# ----------------------------------------------------------------------
def live_panel() -> None:
    s = st.session_state.settings
    provider = get_provider()
    account = st.session_state.account
    store = st.session_state.store
    auto = st.session_state.auto_trader
    interval = st.session_state.get("interval", 6)

    universe = get_universe()
    priority = parse_watchlist(st.session_state.priority_text)
    open_syms = [p.symbol for p in account.positions.values()]
    mode_is_real = provider.effective_mode == MODE_FINNHUB

    reserved = len(set(priority + open_syms))
    chunk_n = compute_chunk_size(mode_is_real, interval, reserved, len(universe))
    chunk, new_cursor = rotate_chunk(universe, st.session_state.scan_cursor, chunk_n)
    st.session_state.scan_cursor = new_cursor

    # Always scan priority + open positions (for fast exits) + the rotating chunk.
    scan_syms = list(dict.fromkeys(priority + open_syms + chunk))
    opps = scan(provider, scan_syms, s)
    by_symbol = {o.symbol: o for o in opps}
    price_map = {o.symbol: o.quote.price for o in opps if o.quote.price > 0}
    candidates = sum(1 for o in opps if o.qualifies)

    config = AutoConfig(
        enabled=st.session_state.auto_enabled,
        max_alloc_per_trade=float(st.session_state.max_alloc),
        min_gain_pct=float(st.session_state.min_gain_pct),
        max_simultaneous=int(st.session_state.max_simul),
        max_risk_pct=1.0,
        duration_seconds=s.trade_test_seconds,
    )
    auto.step(opps, config)
    account.snapshot(price_map)

    real = mode_is_real and any(o.health.is_live for o in opps)
    auto_txt = "ON ⚡" if st.session_state.auto_enabled else "OFF"
    if st.session_state.mode == MODE_MOCK:
        dt = demo_clock(st.session_state.demo_start, float(st.session_state.compression))
        sess = demo_session(dt)
        st.info(
            f"**🌅 Simulated Trading Day (demo)** — {dt:%a %b %d}, **{dt:%H:%M} ET · {sess}**  ·  "
            f"$1,000 paper account · auto-takes only setups scoring **70+** · auto-take {auto_txt}. "
            f"_Synthetic prices for demonstration — not real market data._",
            icon="🧪",
        )
        st.progress(session_progress(dt),
                    text=f"Trading day 08:30 → 16:00 ET ({int(session_progress(dt)*100)}%)")
    else:
        src = "🟢 Finnhub real prices" if real else "🟠 Finnhub (no key → simulated)"
        st.caption(f"{src}  ·  US market: {market_session().upper()}  ·  "
                   f"takes only 70+ setups · auto-take: {auto_txt}")

    render_summary(account, store, price_map)
    st.markdown("---")
    render_scanner_status(len(universe), chunk_n, interval, scan_syms, candidates)
    render_activity()
    st.markdown("---")
    render_ongoing(account, by_symbol)
    st.markdown("---")
    render_past(store)


def main() -> None:
    init_state()
    st.title("📈 C5 Paper Trading")
    st.caption("🧾 Paper trade only — simulation, no real orders, no real money, no profit guarantees.")
    render_sidebar()
    interval = st.session_state.get("interval", 6) if st.session_state.get("auto_refresh", True) else None
    if hasattr(st, "fragment"):
        st.fragment(run_every=interval)(live_panel)()
    else:  # pragma: no cover
        live_panel()


if __name__ == "__main__":
    main()
