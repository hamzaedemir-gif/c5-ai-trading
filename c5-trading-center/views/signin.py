"""Sign in / Connect page — mock auth + mock broker connections."""
from __future__ import annotations

import streamlit as st

import state
from stubs import auth, brokers


def render() -> None:
    st.header("Sign in")

    # --- Step 1: email sign-in (mock) ---
    if not st.session_state.signed_in:
        with st.container(border=True):
            st.write("Enter your email to continue. (Draft: any email works.)")
            with st.form("signin_form"):
                email = st.text_input("Email", placeholder="you@example.com")
                submitted = st.form_submit_button("Continue", type="primary")
            if submitted:
                result = auth.sign_in(email)          # mock auth stub
                if result["ok"]:
                    st.session_state.email = result["email"]
                    st.session_state.signed_in = True
                    st.rerun()
                else:
                    st.error("Please enter a valid email address.")
        st.button("← Back to Home", on_click=lambda: state.go("home"))
        return

    # --- Step 2: connect accounts (mock) ---
    st.success(f"Signed in as {st.session_state.email}")
    st.subheader("Connect your accounts")

    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("**TradingView**")
            st.caption("Connect / execution path (not a C5 data source).")
            if st.session_state.tv_connected:
                st.success("Connected ✓")
            elif st.button("Connect TradingView", use_container_width=True):
                st.session_state.tv_connected = brokers.connect_tradingview()
                st.rerun()
    with c2:
        with st.container(border=True):
            st.markdown("**Webull**")
            st.caption("Primary market data + (later) execution.")
            if st.session_state.wb_connected:
                st.success("Connected ✓")
            elif st.button("Connect Webull", use_container_width=True):
                st.session_state.wb_connected = brokers.connect_webull()
                st.rerun()

    st.write("")
    if state.connected():
        st.info("Both accounts connected.")
        if st.button("Continue to Investing →", type="primary"):
            state.go("investing")
    else:
        st.caption("Connect both TradingView and Webull to continue.")
