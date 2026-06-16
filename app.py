"""C5 v1 — Streamlit paper-trading dashboard (simulation only).

Run with:  streamlit run app.py

This app does NOT place real trades, does NOT execute orders, and makes NO
profit guarantees. All prices, trades, and P/L are simulated. The $1,000
account is paper money only.
"""
from __future__ import annotations

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
from c5.data import build_feed
from c5.data.finnhub_feed import FinnhubFeed
from c5.data.manual_feed import ManualFeed
from c5.data.webull_feed import WebullFeed
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
from c5.market_hours import AFTER_HOURS_WARNING, is_after_hours, market_session
from c5.paper import PaperAccount, TradeTest

st.set_page_config(page_title="C5 v1 — Paper Trading", layout="wide", page_icon="📈")

MIN_CANDLES_FOR_CHART = 8  # below this in Finnhub mode, fall back to TradingView


# ----------------------------------------------------------------------
# State init / feed building
# ----------------------------------------------------------------------
def make_feed(mode: str, symbol: str):
    """Build a feed for the chosen mode, returning (feed, note).

    `note` is a non-empty string when the requested mode could not be used
    (e.g. Finnhub selected with no API key -> mock fallback).
    """
    s = st.session_state.settings
    if mode == MODE_FINNHUB:
        if s.finnhub_available:
            return FinnhubFeed(s.finnhub_api_key, symbol), ""
        from c5.data.mock_feed import MockFeed

        return MockFeed(symbol), "no_key"
    if mode == MODE_MANUAL:
        return ManualFeed(symbol), ""
    if mode == MODE_WEBULL:
        return WebullFeed(symbol), ""
    from c5.data.mock_feed import MockFeed

    return MockFeed(symbol), ""


def init_state() -> None:
    if "settings" not in st.session_state:
        st.session_state.settings = get_settings()
    s = st.session_state.settings

    if "store" not in st.session_state:
        st.session_state.store = Store(s.db_path)
    if "account" not in st.session_state:
        st.session_state.account = PaperAccount(st.session_state.store, s.starting_cash)
    if "mode" not in st.session_state:
        st.session_state.mode = s.data_mode  # default: MOCK
    if "feed" not in st.session_state:
        feed, note = make_feed(st.session_state.mode, s.default_symbol)
        st.session_state.feed = feed
        st.session_state.feed_note = note
    if "trade_test" not in st.session_state:
        st.session_state.trade_test = TradeTest(st.session_state.account, s.trade_test_seconds)
    st.session_state.setdefault("event_risk", False)
    st.session_state.setdefault("low_float", False)
    st.session_state.setdefault("feed_note", "")


def switch_mode(mode: str) -> None:
    symbol = st.session_state.feed.symbol
    feed, note = make_feed(mode, symbol)
    st.session_state.mode = mode
    st.session_state.feed = feed
    st.session_state.feed_note = note


# ----------------------------------------------------------------------
# Mode label  (MOCK / MANUAL / FINNHUB LIVE / FINNHUB DELAYED / WEBULL PENDING)
# ----------------------------------------------------------------------
def mode_label(health) -> str:
    mode = st.session_state.mode
    note = st.session_state.get("feed_note", "")
    if mode == MODE_MOCK:
        return "🧪 MOCK"
    if mode == MODE_MANUAL:
        return "✍️ MANUAL"
    if mode == MODE_WEBULL:
        return "🚧 WEBULL PENDING"
    if mode == MODE_FINNHUB:
        if note == "no_key":
            return "🟠 FINNHUB — NO KEY (mock fallback)"
        if health is not None and health.delayed:
            return "🟡 FINNHUB DELAYED"
        if health is not None and health.is_live:
            return "🟢 FINNHUB LIVE"
        return "🔴 FINNHUB DISCONNECTED"
    return mode.upper()


# ----------------------------------------------------------------------
# Signal computation
# ----------------------------------------------------------------------
def derive_regime(df: pd.DataFrame, direction: str) -> str:
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
        "no brokerage execution, no profit guarantees. The $1,000 account is paper "
        "money only. The Confluence Score is decision-support and **not history validated**.",
        icon="⚠️",
    )


def band_color(band: str) -> str:
    return {BAND_HIGH: "🟢", BAND_MEDIUM: "🟡", BAND_LOW: "🔴"}.get(band, "⚪")


def render_tradingview(symbol: str) -> None:
    st.caption("📺 TradingView chart (visual reference only — paper P/L uses the Finnhub quote).")
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


def render_chart_panel(candles: pd.DataFrame, symbol: str) -> None:
    mode = st.session_state.mode
    enough = candles is not None and len(candles) >= MIN_CANDLES_FOR_CHART
    if mode == MODE_FINNHUB and not enough:
        st.info(
            "Finnhub is still accumulating intraday candles from live quotes — "
            "showing a TradingView chart for visual reference meanwhile."
        )
        render_tradingview(symbol)
    else:
        render_chart(candles, symbol)


def render_score(result) -> None:
    st.subheader("Confluence Score")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric(f"{band_color(result.band)} Score", f"{result.total}/100", result.band)
        st.caption("🟢 LIVE" if result.is_live else "⚪ not live")
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
    st.subheader("Paper Account  ·  $1,000 paper money")
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
                "Last": round(last_price, 4),
                "UPnL": round(p.unrealized_pnl(last_price), 2),
                "Test": "✓" if p.is_test else "",
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def render_trade_test(setup, result, quote, account, health) -> None:
    s = st.session_state.settings
    tt: TradeTest = st.session_state.trade_test
    symbol = st.session_state.feed.symbol
    price = quote.price
    mode = st.session_state.mode

    st.subheader("10-Minute Paper-Trade Test")
    price_src = "Finnhub quote" if mode == MODE_FINNHUB and st.session_state.feed_note != "no_key" else f"{mode} price"
    st.caption(f"Marks to market on every refresh using the **{price_src}**.")

    # After-hours warning (real-session relevance).
    if mode == MODE_FINNHUB and is_after_hours():
        st.warning(AFTER_HOURS_WARNING, icon="🌙")

    # Keep a running test marked-to-market on the live price.
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
        return

    if tt.state.status == "done":
        pnl = tt.state.final_pnl or 0.0
        st.success(
            f"Test complete — **{tt.state.closed_reason}**. "
            f"P/L: ${pnl:+,.2f} ({tt.state.final_pnl_pct or 0:+.2f}%)."
        )
        if st.button("Run another test"):
            tt.reset()
            st.rerun()
        return

    # --- No running/finished test: require a VALID setup, else NO TRADE ---
    valid = (setup is not None and setup.detected and price > 0)
    if not valid:
        st.error("🚫 **NO TRADE** — no valid setup at the current price. "
                 "C5 will not force a trade; wait for a qualifying setup.", icon="🚫")
        if setup is not None and setup.notes:
            st.caption(setup.notes[-1])
        return

    side = setup.direction
    default_stop = setup.stop if setup.stop else round(price * 0.99, 4)
    default_target = setup.target if setup.target else round(price * 1.02, 4)
    st.caption(
        f"Proposed: **{side}** {symbol} @ ${price:,.4f}  •  "
        f"stop ${default_stop:,.4f}  •  target ${default_target:,.4f}"
    )
    cash_to_risk = st.number_input(
        "Cash to allocate (USD)", min_value=10.0,
        max_value=max(10.0, float(account.cash)),
        value=min(200.0, max(10.0, float(account.cash))), step=10.0,
    )
    if st.button("▶ Start 10-minute paper-trade test", type="primary"):
        pos = tt.start(
            symbol=symbol, side=side, price=price,
            stop=default_stop, target=default_target,
            confluence=result.total if result else None,
            band=result.band if result else None,
            mode=mode, cash_to_risk=cash_to_risk,
        )
        if pos:
            st.rerun()


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
        MODE_FINNHUB: "Finnhub (live/delayed)",
        MODE_WEBULL: "Webull (placeholder)",
    }
    chosen = st.sidebar.selectbox(
        "Data mode",
        ALL_MODES,
        index=ALL_MODES.index(st.session_state.mode),
        format_func=lambda m: mode_names.get(m, m),
    )
    if chosen != st.session_state.mode:
        switch_mode(chosen)
        st.rerun()

    if st.session_state.mode == MODE_FINNHUB:
        if s.finnhub_available:
            st.sidebar.success("FINNHUB_API_KEY detected.")
        else:
            st.sidebar.error(
                "No FINNHUB_API_KEY found — running on mock fallback. "
                "Add it to .env and restart to use real prices."
            )
    if st.session_state.mode == MODE_WEBULL:
        st.sidebar.warning("Webull is a placeholder — pending OpenAPI approval. No data, no execution.")

    new_symbol = st.sidebar.text_input("Symbol", value=feed.symbol).upper().strip()
    if new_symbol and new_symbol != feed.symbol:
        feed.set_symbol(new_symbol)

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
    mode = st.session_state.mode

    quote, candles, health, setup, result = compute_signals()
    store.log_feed_health(mode, health.status, health.detail)

    # Header: mode label + price + feed health.
    label = mode_label(health)
    h1, h2, h3 = st.columns([1, 1, 2])
    h1.metric(f"{feed.symbol} price", f"${quote.price:,.4f}" if quote.price else "—")
    h2.markdown(f"**Mode:** {label}")
    h2.caption(f"Feed: {health.label} — {health.detail}")
    if quote.spread_pct is not None:
        h3.caption(f"Spread: {quote.spread_pct:.3f}%  •  Quote age: {quote.age_seconds():.0f}s")
    h3.caption(f"US market session: **{market_session().upper()}**")

    if mode == MODE_FINNHUB and is_after_hours():
        st.warning(AFTER_HOURS_WARNING, icon="🌙")
    if mode == MODE_WEBULL:
        st.info("Webull mode is a placeholder pending OpenAPI approval — no data, no execution, no order routing.")

    if candles is None or candles.empty:
        if mode == MODE_MANUAL:
            st.info("No candle data yet. Submit a price from the sidebar to begin.")
        elif mode == MODE_FINNHUB:
            st.info("Waiting for the first Finnhub quote. Showing TradingView reference chart:")
            render_tradingview(feed.symbol)
        else:
            st.info("No candle data yet.")
        return

    render_chart_panel(candles, feed.symbol)
    st.markdown("---")
    if result is not None:
        render_score(result)
    st.markdown("---")
    render_trade_test(setup, result, quote, account, health)
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
    if hasattr(st, "fragment"):
        frag = st.fragment(run_every=interval)(live_panel)
        frag()
    else:  # pragma: no cover - very old Streamlit
        live_panel()


if __name__ == "__main__":
    main()
