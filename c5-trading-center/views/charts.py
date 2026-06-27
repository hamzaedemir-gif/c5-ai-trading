"""Charts page — pull up a TradingView chart for any US ticker (display only)."""
from __future__ import annotations

import streamlit as st

import state
from stubs import data_feed
from tradingview import to_tv_symbol, tv_chart


def render() -> None:
    if not st.session_state.signed_in:
        st.warning("Please sign in first.")
        st.button("Go to Sign in", on_click=lambda: state.go("signin"))
        return

    st.header("Charts")
    st.caption("Display-only TradingView charts. C5's analysis and trades use the "
               "market-data provider (Webull OpenAPI / Finnhub) — never TradingView.")

    candidates = data_feed.candidate_tickers()
    c1, c2, c3 = st.columns([2, 3, 1])
    with c1:
        pick = st.selectbox("Pick a ticker", candidates, index=0)
    with c2:
        typed = st.text_input("…or type any US ticker (e.g. NASDAQ:AAPL or AAPL)",
                              value="").upper().strip()
    with c3:
        interval = st.selectbox("Interval", ["1", "5", "15", "60", "D"], index=1)

    symbol = typed or pick
    st.caption(f"Showing **{to_tv_symbol(symbol)}**")
    tv_chart(symbol, height=600, interval=interval)
