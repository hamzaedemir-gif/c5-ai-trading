"""Trading page — START/STOP, the simulated trade loop, and all live sections.

The trade loop is a SIMULATION built on mock stubs. No real orders, no real
money. Real wiring points live in stubs/ and are marked `# TODO:`.
"""
from __future__ import annotations

import random
import time
from collections import OrderedDict

import pandas as pd
import streamlit as st

import state
import styles
from config import (
    SIM_MAX_OPEN,
    SIM_TICK_SECONDS,
    SIM_TRADE_SLICE,
    INVEST_MIN,
    session_is_open,
)
from stubs import broker, c5_engine, data_feed


# ----------------------------------------------------------------------
# Simulation tick
# ----------------------------------------------------------------------
def _tick() -> None:
    ss = st.session_state
    tickers = data_feed.candidate_tickers()
    prices = (data_feed.live_prices(tickers) if ss.mode == "live"
              else data_feed.yesterday_prices(tickers))

    # Update rolling price history (keep last 60 points per ticker).
    for t, p in prices.items():
        hist = ss.price_history.setdefault(t, [])
        hist.append(p)
        del hist[:-60]

    now = time.time()

    # --- update / close open trades ---
    still_open = []
    for tr in ss.open_trades:
        p = prices.get(tr["ticker"], tr["last"])
        tr["last"] = p
        tr["live_pl"] = (p - tr["entry"]) * tr["qty"]
        reason = None
        if p >= tr["target"]:
            reason = "target hit"
        elif p <= tr["stop"]:
            reason = "stop hit"
        elif now >= tr["deadline"]:
            reason = "time exit"
        if reason:
            broker.close_order(tr["id"], p, ss.mode)        # mock close
            pl = (p - tr["entry"]) * tr["qty"]
            tr.update({
                "exit": p, "exit_ts": now,
                "closed_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
                "pl": pl,
                "pl_pct": 100.0 * (p - tr["entry"]) / tr["entry"] if tr["entry"] else 0.0,
                "reason": reason,
                "hold_secs": int(now - tr["opened_ts"]),
            })
            ss.balance += tr["size"] + pl                   # return reserved cash + P/L
            ss.past_trades.insert(0, tr)
        else:
            still_open.append(tr)
    ss.open_trades = still_open

    # --- look for new entries (only while in-session for LIVE; paper anytime) ---
    can_enter = ss.mode == "paper" or session_is_open()
    if can_enter:
        per_trade = max(INVEST_MIN, ss.start_balance * SIM_TRADE_SLICE)
        open_tickers = {tr["ticker"] for tr in ss.open_trades}
        for t in tickers:
            if len(ss.open_trades) >= SIM_MAX_OPEN:
                break
            if t in open_tickers or ss.balance < per_trade:
                continue
            score = c5_engine.get_confluence(t)             # mock confluence engine
            if score >= ss.confidence_threshold:
                entry = prices[t]
                size = min(per_trade, ss.balance)
                qty = size / entry if entry else 0.0
                if qty <= 0:
                    continue
                broker.place_order(t, qty, entry, ss.mode)  # mock order
                ss.balance -= size                          # reserve cash
                ss.trade_seq += 1
                ss.open_trades.append({
                    "id": ss.trade_seq, "ticker": t, "entry": entry, "qty": qty,
                    "size": size, "score": score, "opened_ts": now,
                    "opened_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
                    "target": round(entry * (1 + random.uniform(0.004, 0.015)), 2),
                    "stop": round(entry * (1 - random.uniform(0.003, 0.010)), 2),
                    "deadline": now + random.randint(20, 60),
                    "last": entry, "live_pl": 0.0,
                })
                open_tickers.add(t)

    _recompute_daily()


def _recompute_daily() -> None:
    ss = st.session_state
    by_day = OrderedDict()
    for tr in reversed(ss.past_trades):  # chronological
        day = tr["closed_str"][:10] if tr.get("closed_str") else "—"
        d = by_day.setdefault(day, {"date": day, "trades": 0, "wins": 0, "pl": 0.0})
        d["trades"] += 1
        d["pl"] += tr["pl"]
        if tr["pl"] > 0:
            d["wins"] += 1
    rows = []
    cumulative = ss.start_balance
    for day, d in by_day.items():
        cumulative += d["pl"]
        rows.append({
            "date": day, "trades": d["trades"],
            "win_rate": round(100.0 * d["wins"] / d["trades"], 1) if d["trades"] else 0.0,
            "pl": round(d["pl"], 2), "cumulative": round(cumulative, 2),
        })
    ss.daily_pnl = rows


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------
def _equity() -> float:
    ss = st.session_state
    return ss.balance + sum(tr["size"] + tr["live_pl"] for tr in ss.open_trades)


def _render_sections() -> None:
    ss = st.session_state

    # --- Balance ---
    st.subheader("Balance")
    equity = _equity()
    total_pl = equity - ss.start_balance
    c1, c2, c3 = st.columns(3)
    c1.metric("Account balance", f"${equity:,.2f}", f"{total_pl:+,.2f}")
    c2.metric("Cash available", f"${ss.balance:,.2f}")
    c3.metric("Open / Closed", f"{len(ss.open_trades)} / {len(ss.past_trades)}")

    # --- Live trades being taken ---
    st.subheader("Live trades being taken")
    if ss.open_trades:
        df = pd.DataFrame([{
            "Ticker": tr["ticker"], "Entry": round(tr["entry"], 2),
            "Size $": round(tr["size"], 2), "Score @ entry": tr["score"],
            "Last": round(tr["last"], 2), "Live P/L": round(tr["live_pl"], 2),
        } for tr in ss.open_trades])
        st.dataframe(styles.style_pl(df, ["Live P/L"]), hide_index=True, use_container_width=True)
    else:
        st.caption("No open trades right now." if ss.running
                   else "Press START to begin taking trades.")

    # --- Live charts ---
    st.subheader("Live charts")
    chart_tickers = [tr["ticker"] for tr in ss.open_trades] or data_feed.candidate_tickers()[:3]
    series = {t: ss.price_history.get(t, []) for t in chart_tickers if ss.price_history.get(t)}
    if series:
        maxlen = max(len(v) for v in series.values())
        data = {t: ([None] * (maxlen - len(v)) + v) for t, v in series.items()}
        st.line_chart(pd.DataFrame(data))
    else:
        st.caption("Charts appear once the loop is running.")

    # --- Past trades (clickable detail) ---
    st.subheader("Past trades")
    if not ss.past_trades:
        st.caption("Closed trades will appear here.")
    else:
        for tr in ss.past_trades[:40]:
            head = (f"{tr['ticker']}  ·  {tr['reason']}  ·  "
                    f"P/L ${tr['pl']:+,.2f} ({tr['pl_pct']:+.2f}%)")
            with st.expander(head):
                st.markdown(
                    f"**{tr['ticker']}** — score at entry **{tr['score']}**  \n"
                    f"Entry ${tr['entry']:,.2f} → Exit ${tr['exit']:,.2f}  ·  "
                    f"qty {tr['qty']:.4f}  ·  held {tr['hold_secs']}s  \n"
                    f"Opened {tr['opened_str']}  ·  Closed {tr['closed_str']}  \n"
                    f"What happened: **{tr['reason']}**", unsafe_allow_html=True)
                st.markdown("P/L: " + styles.money(tr["pl"]), unsafe_allow_html=True)

    # --- Profit & Loss (day by day) ---
    st.subheader("Profit & Loss — day by day")
    if ss.daily_pnl:
        df = pd.DataFrame(ss.daily_pnl)
        df.columns = ["Date", "Trades", "Win rate %", "Daily P/L", "Cumulative balance"]
        st.dataframe(styles.style_pl(df, ["Daily P/L"]), hide_index=True, use_container_width=True)
    else:
        st.caption("Daily summary appears after the first closed trade.")


def render() -> None:
    ss = st.session_state
    if not state.connected():
        st.warning("Connect your accounts first.")
        st.button("Go to Sign in / Connect", on_click=lambda: state.go("signin"))
        return

    # --- Header: mode badge, version, START / STOP ---
    badge_cls = "c5-badge-live" if ss.mode == "live" else "c5-badge-paper"
    badge_txt = "LIVE" if ss.mode == "live" else "PAPER"
    h1, h2, h3, h4 = st.columns([2, 2, 1, 1])
    with h1:
        st.markdown(f"### Trading &nbsp; <span class='c5-badge {badge_cls}'>{badge_txt}</span>",
                    unsafe_allow_html=True)
    with h2:
        st.markdown(f"**Engine:** {ss.c5_version}  \n**Threshold:** confluence ≥ {ss.confidence_threshold}")
    with h3:
        if st.button("▶ START", key="start_btn", use_container_width=True, disabled=ss.running):
            ss.running = True
            st.rerun()
    with h4:
        if st.button("■ STOP", key="stop_btn", use_container_width=True, disabled=not ss.running):
            ss.running = False
            st.rerun()

    # Session-window note (no after-hours trading in LIVE).
    in_session = session_is_open()
    if ss.mode == "live" and not in_session:
        st.warning("Outside the regular session — LIVE mode does not trade after-hours. "
                   "Switch to Paper Trade Trial to preview anytime.", icon="🌙")
    st.caption(f"Status: {'🟢 RUNNING' if ss.running else '⏸ stopped'}  ·  "
               f"session window {'OPEN' if in_session else 'closed'}  ·  "
               "simulated data — no real orders.")
    st.markdown("---")

    # Auto-refreshing loop fragment.
    run_every = SIM_TICK_SECONDS if ss.running else None

    @st.fragment(run_every=run_every)
    def _loop():
        if st.session_state.running:
            _tick()
        _render_sections()

    if hasattr(st, "fragment"):
        _loop()
    else:  # pragma: no cover
        if ss.running:
            _tick()
        _render_sections()

    st.markdown("---")
    st.button("← Back to Investing settings", on_click=lambda: state.go("investing"))
