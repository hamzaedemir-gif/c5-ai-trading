"""Home page — hero, what C5 is, and entry buttons."""
from __future__ import annotations

import streamlit as st

import state

# C5 in its own words (used verbatim on Home).
WHAT_C5_IS = (
    "C5 is an automated trading system that watches the U.S. market across the "
    "full regular session — from early-market open through the normal close — "
    "and takes trades on its own when its engine rates a setup highly enough. "
    "It does not trade after-hours. A user connects an account, picks how much "
    "to commit, sets a confidence threshold, chooses live or paper mode, and "
    "presses START. C5 then shows every trade it takes, the running balance, "
    "live charts, a reviewable history of past trades, and a day-by-day "
    "profit/loss summary. STOP halts it."
)


def render() -> None:
    st.markdown("<div class='c5-hero'>C5</div>", unsafe_allow_html=True)
    st.markdown("<div class='c5-tag'>C5 Trading Center — automated, threshold-driven trading.</div>",
                unsafe_allow_html=True)
    st.write("")

    with st.container(border=True):
        st.subheader("What C5 is")
        st.write(WHAT_C5_IS)

    st.write("")
    st.caption("Draft / prototype — simulated data only. No real accounts, no real money, no real orders.")

    c1, c2, _ = st.columns([1, 1, 3])
    with c1:
        if st.button("Sign up", use_container_width=True, type="primary"):
            state.go("signin")
    with c2:
        if st.button("Sign in", use_container_width=True):
            state.go("signin")
