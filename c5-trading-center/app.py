"""C5 Trading Center — Streamlit app entry point.

First-draft scaffold. Navigable end-to-end with a simulated trading loop.
Every external connection (broker, market data, C5 engine, execution) is a
clearly-labelled mock stub. No real accounts, no real money, no real orders.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

import state
import styles
from views import charts, home, investing, signin, trading

st.set_page_config(page_title="C5 Trading Center", page_icon="📈", layout="wide")

styles.inject()
state.init()

_VIEWS = {
    "home": home.render,
    "signin": signin.render,
    "investing": investing.render,
    "trading": trading.render,
    "charts": charts.render,
}

# Simple top nav for signed-in users (skips the marketing Home).
if st.session_state.signed_in:
    cols = st.columns([1, 1, 1, 1, 5])
    if cols[0].button("Investing", use_container_width=True,
                      disabled=not state.connected()):
        state.go("investing")
    if cols[1].button("Trading", use_container_width=True,
                      disabled=not state.connected()):
        state.go("trading")
    if cols[2].button("Charts", use_container_width=True):   # display-only, no connect needed
        state.go("charts")
    if cols[3].button("Sign out", use_container_width=True):
        for k in ("signed_in", "email", "tv_connected", "wb_connected", "running"):
            st.session_state[k] = False if isinstance(st.session_state.get(k), bool) else None
        state.go("home")

_VIEWS.get(st.session_state.view, home.render)()
