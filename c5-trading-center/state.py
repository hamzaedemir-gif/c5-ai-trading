"""Session-state initialization and small navigation helpers."""
from __future__ import annotations

import streamlit as st

from config import C5_VERSIONS, CONFIDENCE_DEFAULT, DEFAULT_MODE, INVEST_DEFAULT

_DEFAULTS = {
    "view": "home",
    # auth / connections
    "email": None,
    "signed_in": False,
    "tv_connected": False,
    "wb_connected": False,
    # run settings
    "c5_version": C5_VERSIONS[0],
    "invest_amount": INVEST_DEFAULT,
    "confidence_threshold": CONFIDENCE_DEFAULT,
    "mode": DEFAULT_MODE,
    # trading state
    "running": False,
    "balance": 0.0,          # available cash
    "start_balance": 0.0,    # committed amount at session start
    "open_trades": [],
    "past_trades": [],
    "daily_pnl": [],
    "price_history": {},
    "selected_trade": None,
    "trade_seq": 0,
}


def init() -> None:
    for key, value in _DEFAULTS.items():
        st.session_state.setdefault(key, value)


def go(view: str) -> None:
    st.session_state.view = view
    st.rerun()


def connected() -> bool:
    return bool(st.session_state.tv_connected and st.session_state.wb_connected)
