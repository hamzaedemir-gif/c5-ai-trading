"""Black & blue theme — custom CSS injection.

Chrome is black + blue everywhere. The only non-blue colors are green/red,
used solely for profit/loss figures (standard trading convention).
"""
from __future__ import annotations

import streamlit as st

BLUE = "#1E90FF"
BLUE_SOFT = "#3AA0FF"
PROFIT = "#16C784"   # green — P/L only
LOSS = "#EA3943"     # red   — P/L only

_CSS = f"""
<style>
/* Headers: blue with a soft glow */
h1, h2, h3 {{
    color: {BLUE_SOFT} !important;
    text-shadow: 0 0 14px rgba(30,144,255,0.45);
    letter-spacing: 0.3px;
}}

/* Card / panel look on bordered containers */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    border: 1px solid rgba(30,144,255,0.25) !important;
    border-radius: 14px;
    box-shadow: 0 0 18px rgba(30,144,255,0.08);
    background: linear-gradient(180deg, rgba(13,27,42,0.55), rgba(5,7,13,0.55));
}}

/* C5 hero badge */
.c5-hero {{
    font-size: 4rem; font-weight: 800; color: {BLUE_SOFT};
    text-shadow: 0 0 28px rgba(30,144,255,0.6); margin-bottom: 0;
}}
.c5-tag {{ color: #9FB3C8; font-size: 1.1rem; margin-top: -8px; }}

/* Default buttons: blue outline */
.stButton > button {{
    border: 1px solid {BLUE};
    border-radius: 10px;
    transition: all .15s ease-in-out;
}}
.stButton > button:hover {{
    border-color: {BLUE_SOFT};
    box-shadow: 0 0 14px rgba(30,144,255,0.5);
}}

/* START button (blue, filled) — keyed via st.button(key="start_btn") */
.st-key-start_btn .stButton > button, .st-key-start_btn button {{
    background: {BLUE} !important; color: #04101F !important;
    border: 1px solid {BLUE} !important; font-weight: 800 !important;
    box-shadow: 0 0 20px rgba(30,144,255,0.55) !important;
}}
/* STOP button (red, filled) — keyed via st.button(key="stop_btn") */
.st-key-stop_btn .stButton > button, .st-key-stop_btn button {{
    background: {LOSS} !important; color: #1A0205 !important;
    border: 1px solid {LOSS} !important; font-weight: 800 !important;
    box-shadow: 0 0 20px rgba(234,57,67,0.5) !important;
}}

/* Confidence slider: blue track/handle + glow */
div[data-baseweb="slider"] [role="slider"] {{
    box-shadow: 0 0 12px rgba(30,144,255,0.8) !important;
}}

/* Mode badges */
.c5-badge {{
    display:inline-block; padding:4px 12px; border-radius:999px;
    font-weight:700; font-size:0.85rem; border:1px solid {BLUE};
}}
.c5-badge-paper {{ color:{BLUE_SOFT}; background:rgba(30,144,255,0.12); }}
.c5-badge-live  {{ color:#04101F; background:{BLUE}; }}
</style>
"""


def inject() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def money(value: float) -> str:
    """Green/red colored P/L markdown (the only non-blue colors allowed)."""
    color = PROFIT if value >= 0 else LOSS
    return f"<span style='color:{color};font-weight:700'>${value:,.2f}</span>"


def style_pl(df, columns):
    """Return a pandas Styler coloring the given P/L columns green/red."""
    def _color(v):
        try:
            f = float(str(v).replace("$", "").replace(",", "").replace("%", ""))
        except (TypeError, ValueError):
            return ""
        return f"color: {PROFIT}" if f >= 0 else f"color: {LOSS}"
    return df.style.applymap(_color, subset=columns)
