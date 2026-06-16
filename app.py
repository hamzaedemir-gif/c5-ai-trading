"""C5 v1 — Streamlit paper-trading dashboard (simulation only).

Run with:  streamlit run app.py

This app does NOT place real trades, does NOT execute orders, and makes NO
profit guarantees. All prices, trades, and P/L are simulated.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from c5.config import (
    MODE_FINNHUB,
    MODE_MANUAL,
    MODE_MOCK,
    MODE_WEBULL,
    get_settings,
)
from c5.data import build_feed
from c5.data.manual_feed import ManualFeed
from c5.db import Store
from c5.engine import detect_setup, score_confluence
from c5.engine import indicators as ind
from c5.engine.confluence import (
    BAND_HIGH,
    BAND_LOW,
    BAND_MEDIUM,
    SCORE_LABEL,
    ScoreInputs,
)
from c5.paper import PaperAccount, TradeTest

st.set_page_config(page_title="C5 v1 — Paper Trading", layout="wide", page_icon="📈")


# ----------------------------------------------------------------------
# State init
# ----------------------------------------------------------------------
def init_state() -> None:
    if "settings" not in st.session_state:
        st.session_state.settings = get_settings()
    s = st.session_state.settings

    if "store" not in st.session_state:
        st.session_state.store = Store(s.db_path)
    if "account" not in st.session_state:
        st.session_state.account = PaperAccount(st.session_state.store, s.starting_cash)
    if "feed" not in st.session_state:
        st.session_state.feed = build_feed(s)
    if "trade_test" not in st.session_state:
        st.session_state.trade_test = TradeTest(st.session_state.account, s.trade_test_seconds)
    if "event_risk" not in st.session_state:
        st.session_state.event_risk = False
    if "low_float" not in st.session_state:
        st.session_state.low_float = False


# ----------------------------------------------------------------------
# Signal computation
# ----------------------------------------------------------------------
def derive_regime(df: pd.DataFrame, direction: str) -> str:
    """Estimate market-regime alignment from the overall trend of the series."""
    if df is None or len(df) < 20 or direction == "none":
        return "neutral"
    close = df["close"]
    trend_up = bool(close.iloc[-1] > ind.sma(close, 20).iloc[-1])
    if direction == "long":
        return "with" if trend_up else "against"
    return "against" if trend_up else "with"


def compute_signals():
    s = st.session_state.settings
    feed = st.session_state.feed

    quote = feed.get_quote()
    candles = feed.get_candles(120)
    health = feed.health()

    if candles is None or candles.empty:
        return quote, candles, health, None, None

    setup = detect_setup(candles)
    rvol = ind.rvol(candles)
    atrp = ind.atr_pct(candles)
    catalyst = max(0.0, min(1.0, ((rvol or 1.0) - 1.0) / 2.0))
    regime = derive_regime(candles, setup.direction)

    inputs = ScoreInputs(
        setup=setup,
        candles=candles,
        rvol=rvol,
        spread_pct=quote.spread_pct,
        catalyst_quality=catalyst,
        regime=regime,
        atr_pct=atrp,
        quote_age=quote.age_seconds(),
        stale_after=s.stale_after_seconds,
        feed_is_live=health.is_live,
        event_risk=st.session_state.event_risk,
        low_float=st.session_state.low_float,
    )
    result = score_confluence(inputs)
    return quote, candles, health, setup, result


# ----------------------------------------------------------------------
# UI pieces
# ----------------------------------------------------------------------
def render_disclaimer() -> None:
    st.warning(
        "**Simulation only.** C5 v1 is a paper-trading prototype — no real orders, "
        "no brokerage execution, no profit guarantees. The Confluence Score is "
        "decision-support only and is **not history validated**.",
        icon="⚠️",
    )


def band_color(band: str) -> str:
    return {BAND_HIGH: "🟢", BAND_MEDIUM: "🟡", BAND_LOW: "🔴"}.get(band, "⚪")


def render_chart(candles: pd.DataFrame, symbol: str) -> None:
    df = candles.copy()
    df["vwap"] = ind.vwap(df)
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=df["time"], open=df["open"], high=df["high"],
            low=df["low"], close=df["close"], name=symbol,
        )
    )
    fig.add_trace(
        go.Scatter(x=df["time"], y=df["vwap"], name="VWAP",
                   line=dict(color="orange", width=1.5))
    )
    fig.update_layout(
        height=380, margin=dict(l=10, r=10, t=10, b=10),
        xaxis_rangeslider_visible=False, showlegend=True,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_score(result) -> None:
    st.subheader("Confluence Score")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric(f"{band_color(result.band)} Score", f"{result.total}/100", result.band)
        live_txt = "🟢 LIVE" if result.is_live else "⚪ not live"
        st.caption(live_txt)
        if result.alert:
            st.success("ALERT: score ≥ 70 and no critical warning.", icon="🔔")
        else:
            st.info("No alert (needs score ≥ 70 and no critical warning).")
    with c2:
        st.caption(f"_{SCORE_LABEL}_")
        comp_df = pd.DataFrame(
            [{"Component": c.name, "Score": c.score, "Max": c.max_points, "Detail": c.detail}
             for c in result.components]
        )
        st.dataframe(comp_df, hide_index=True, use_container_width=True)
        st.caption(f"Positive subtotal: {result.positive_subtotal}  •  Final after warnings: {result.total}")

    cols = st.columns(2)
    with cols[0]:
        st.markdown("**Reasons**")
        if result.reasons:
            for r in result.reasons:
                st.markdown(f"- {r}")
        else:
            st.markdown("- _No supporting reasons at this bar._")
    with cols[1]:
        st.markdown("**Warnings**")
        if result.warnings:
            for w in result.warnings:
                tag = "🚨 critical" if w.critical else "⚠️"
                st.markdown(f"- {tag} **{w.label}** ({w.penalty}) — {w.detail}")
        else:
            st.markdown("- _None._")


def render_account(account: PaperAccount, last_price: float, symbol: str) -> None:
    st.subheader("Paper Account")
    price_map = {symbol: last_price}
    equity = account.equity(price_map)
    unreal = account.open_unrealized(price_map)
    realized = account.realized_pnl()
    total_pl = equity - account.starting_cash

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Equity", f"${equity:,.2f}", f"{total_pl:+,.2f} total")
    c2.metric("Cash", f"${account.cash:,.2f}")
    c3.metric("Realized P/L", f"${realized:+,.2f}")
    c4.metric("Unrealized P/L", f"${unreal:+,.2f}")

    if account.open_positions:
        rows = []
        for p in account.open_positions:
            rows.append({
                "Symbol": p.symbol, "Side": p.side, "Qty": round(p.qty, 4),
                "Entry": round(p.entry_price, 4),
                "UPnL": round(p.unrealized_pnl(last_price), 2),
                "Test": "✓" if p.is_test else "",
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def render_trade_test(setup, result, quote, account) -> None:
    s = st.session_state.settings
    tt: TradeTest = st.session_state.trade_test
    symbol = st.session_state.feed.symbol
    price = quote.price

    st.subheader("10-Minute Paper-Trade Test")

    # Keep the running test marked-to-market.
    if tt.is_running and price > 0:
        tt.update(price)

    if tt.is_running:
        s_left = tt.state.seconds_left()
        pos = account.positions.get(tt.state.trade_id)
        upnl = pos.unrealized_pnl(price) if pos else 0.0
        st.progress(min(1.0, tt.state.elapsed() / max(1, tt.state.duration)),
                    text=f"{s_left // 60}m {s_left % 60}s left")
        c1, c2, c3 = st.columns(3)
        c1.metric("Entry", f"${tt.state.entry_price:,.4f}")
        c2.metric("Last", f"${price:,.4f}")
        c3.metric("Unrealized P/L", f"${upnl:+,.2f}")
        if st.button("Close test now", type="secondary"):
            tt._finish(price, "closed early by user")
            st.rerun()

    elif tt.state.status == "done":
        pnl = tt.state.final_pnl or 0.0
        st.success(
            f"Test complete — **{tt.state.closed_reason}**. "
            f"P/L: ${pnl:+,.2f} ({tt.state.final_pnl_pct or 0:+.2f}%)."
        )
        if st.button("Run another test"):
            tt.reset()
            st.rerun()

    else:
        can_trade = price > 0 and setup is not None
        side = setup.direction if (setup and setup.detected) else "long"
        default_stop = setup.stop if (setup and setup.stop) else round(price * 0.99, 4)
        default_target = setup.target if (setup and setup.target) else round(price * 1.02, 4)

        st.caption(
            f"Proposed: **{side}** {symbol} @ ${price:,.4f}  •  "
            f"stop ${default_stop:,.4f}  •  target ${default_target:,.4f}"
        )
        cash_to_risk = st.number_input(
            "Cash to allocate (USD)", min_value=10.0,
            max_value=max(10.0, float(account.cash)),
            value=min(200.0, max(10.0, float(account.cash))), step=10.0,
        )
        disabled = not can_trade
        if st.button("▶ Start 10-minute paper-trade test", type="primary", disabled=disabled):
            pos = tt.start(
                symbol=symbol, side=side, price=price,
                stop=default_stop, target=default_target,
                confluence=result.total if result else None,
                band=result.band if result else None,
                mode=s.data_mode, cash_to_risk=cash_to_risk,
            )
            if pos:
                st.rerun()
        if disabled:
            st.caption("_Waiting for a valid price / setup before a test can start._")


def render_trade_log(store: Store) -> None:
    st.subheader("Trade Log")
    trades = store.get_trades(200)
    if not trades:
        st.caption("No paper trades yet.")
        return
    df = pd.DataFrame(trades)
    for col in ("opened_ts", "closed_ts"):
        if col in df:
            df[col] = pd.to_datetime(df[col], unit="s").dt.strftime("%Y-%m-%d %H:%M:%S")
    cols = ["id", "opened_ts", "closed_ts", "symbol", "side", "qty", "entry_price",
            "exit_price", "status", "pnl", "pnl_pct", "confluence", "band", "mode",
            "is_test", "reason"]
    df = df[[c for c in cols if c in df.columns]]
    st.dataframe(df, hide_index=True, use_container_width=True)


# ----------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------
def render_sidebar() -> None:
    s = st.session_state.settings
    feed = st.session_state.feed

    st.sidebar.title("C5 v1")
    st.sidebar.caption("Local paper-trading prototype")

    mode_names = {
        MODE_MOCK: "Mock (synthetic)",
        MODE_MANUAL: "Manual entry",
        MODE_FINNHUB: "Finnhub (live)",
        MODE_WEBULL: "Webull (placeholder)",
    }
    st.sidebar.markdown(f"**Data mode:** {mode_names.get(s.data_mode, s.data_mode)}")
    if s.data_mode == MODE_FINNHUB and not s.finnhub_available:
        st.sidebar.info("No FINNHUB_API_KEY set — running on mock fallback.")
    if s.data_mode == MODE_WEBULL:
        st.sidebar.warning("Webull is a placeholder — pending OpenAPI approval. No data, no execution.")
    st.sidebar.caption("Change mode via C5_DATA_MODE in .env, then restart.")

    new_symbol = st.sidebar.text_input("Symbol", value=feed.symbol).upper().strip()
    if new_symbol and new_symbol != feed.symbol:
        feed.set_symbol(new_symbol)

    # Manual price entry.
    if isinstance(feed, ManualFeed):
        st.sidebar.markdown("**Manual price entry**")
        mp = st.sidebar.number_input("Price", min_value=0.0, value=0.0, step=0.01)
        mv = st.sidebar.number_input("Volume (optional)", min_value=0.0, value=100000.0, step=1000.0)
        if st.sidebar.button("Submit price"):
            if mp > 0:
                feed.submit_price(mp, mv)
                st.rerun()

    st.sidebar.markdown("**Simulated warning toggles**")
    st.session_state.event_risk = st.sidebar.checkbox(
        "Imminent event risk (-15, critical)", value=st.session_state.event_risk)
    st.session_state.low_float = st.sidebar.checkbox(
        "Low float / gap risk (-8)", value=st.session_state.low_float)

    st.sidebar.markdown("---")
    st.session_state.auto = st.sidebar.checkbox("Auto-refresh", value=True)
    st.session_state.interval = st.sidebar.slider("Refresh seconds", 1, 15, 3)
    if st.sidebar.button("🔄 Refresh now"):
        st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("⚠️ Reset paper account & log"):
        st.session_state.store.reset()
        st.session_state.account = PaperAccount(st.session_state.store, s.starting_cash)
        st.session_state.trade_test = TradeTest(st.session_state.account, s.trade_test_seconds)
        st.rerun()


# ----------------------------------------------------------------------
# Live panel (auto-refreshing fragment)
# ----------------------------------------------------------------------
def live_panel() -> None:
    feed = st.session_state.feed
    store = st.session_state.store
    account = st.session_state.account

    quote, candles, health, setup, result = compute_signals()
    store.log_feed_health(st.session_state.settings.data_mode, health.status, health.detail)

    # Header row: price + feed health.
    h1, h2, h3 = st.columns([1, 1, 2])
    h1.metric(f"{feed.symbol} price", f"${quote.price:,.4f}" if quote.price else "—")
    h2.markdown(f"**Feed:** {health.label}")
    h2.caption(health.detail)
    if quote.spread_pct is not None:
        h3.caption(f"Spread: {quote.spread_pct:.3f}%  •  Quote age: {quote.age_seconds():.0f}s")

    if candles is None or candles.empty:
        st.info("No candle data yet. In manual mode, submit a price from the sidebar.")
        return

    render_chart(candles, feed.symbol)
    st.markdown("---")
    if result is not None:
        render_score(result)
    st.markdown("---")
    render_trade_test(setup, result, quote, account)
    st.markdown("---")
    render_account(account, quote.price or 0.0, feed.symbol)
    account.snapshot({feed.symbol: quote.price or 0.0})
    st.markdown("---")
    render_trade_log(store)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main() -> None:
    init_state()
    st.title("📈 C5 AI Trading — v1 (Paper)")
    render_disclaimer()
    render_sidebar()

    interval = st.session_state.get("interval", 3) if st.session_state.get("auto", True) else None
    # st.fragment supports run_every for auto-refresh without extra deps.
    if hasattr(st, "fragment"):
        frag = st.fragment(run_every=interval)(live_panel)
        frag()
    else:  # pragma: no cover - very old Streamlit
        live_panel()


if __name__ == "__main__":
    main()
