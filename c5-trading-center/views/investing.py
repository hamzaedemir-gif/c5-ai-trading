"""Investing page — Trading Screener + the 4 run settings."""
from __future__ import annotations

import streamlit as st

import state
from config import (
    C5_VERSION_INFO,
    C5_VERSIONS,
    CONFIDENCE_DEFAULT,
    CONFIDENCE_MAX,
    CONFIDENCE_MIN,
    INVEST_MAX,
    INVEST_MIN,
)
from stubs import c5_engine


def render() -> None:
    if not st.session_state.signed_in:
        st.warning("Please sign in first.")
        st.button("Go to Sign in", on_click=lambda: state.go("signin"))
        return

    top = st.columns([3, 1])
    top[0].header("Investing — Trading Screener")
    if top[1].button("📈 Open Charts", use_container_width=True):
        state.go("charts")

    # --- Screener: available C5 versions ---
    with st.container(border=True):
        st.subheader("Available C5 versions")
        for v in C5_VERSIONS:
            st.markdown(f"**{v}**")
            st.caption(C5_VERSION_INFO.get(v, ""))

    st.subheader("Configure your run")

    # 1) C5 version
    version = st.selectbox("1 · C5 version", C5_VERSIONS,
                           index=C5_VERSIONS.index(st.session_state.c5_version))

    # 2) Amount invested
    amount = st.slider("2 · Amount invested ($)", min_value=INVEST_MIN, max_value=INVEST_MAX,
                       value=int(st.session_state.invest_amount), step=100)
    st.caption(f"Committing **${amount:,.0f}**.")

    # 3) Confidence threshold (confluence score 10–99)
    threshold = st.slider("3 · Confidence threshold (confluence score)",
                          min_value=CONFIDENCE_MIN, max_value=CONFIDENCE_MAX,
                          value=int(st.session_state.confidence_threshold))
    st.caption(
        f"C5 only takes a trade when a ticker's **confluence score** is at or above "
        f"**{threshold}**. This is the core setting — the C5 engine reads each "
        f"candidate's live chart/prices and produces a transparent confluence "
        f"score (10–99). _Default {CONFIDENCE_DEFAULT}._"
    )
    # Live demo of the (mock) engine reading.
    with st.expander("Preview a confluence reading (mock engine)"):
        sample = st.text_input("Ticker", value="AAPL")
        if st.button("Read confluence"):
            st.metric(f"{sample.upper()} confluence", c5_engine.get_confluence(sample.upper()))

    # 4) Mode
    mode_label = st.radio("4 · Mode", ["Paper Trade Trial", "Live"],
                          index=0 if st.session_state.mode == "paper" else 1,
                          help="Paper uses yesterday's numbers; Live uses real market prices.")
    mode = "paper" if mode_label.startswith("Paper") else "live"
    if mode == "live":
        st.warning("Live mode would place real orders in production. This draft is simulated only.")

    st.write("")
    if st.button("Save / Continue →", type="primary"):
        st.session_state.c5_version = version
        st.session_state.invest_amount = amount
        st.session_state.confidence_threshold = threshold
        st.session_state.mode = mode
        # Initialize the (simulated) account balance to the committed amount.
        st.session_state.balance = float(amount)
        st.session_state.start_balance = float(amount)
        st.session_state.open_trades = []
        st.session_state.past_trades = []
        st.session_state.daily_pnl = []
        st.session_state.running = False
        state.go("trading")
