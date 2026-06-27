"""Central configuration for C5 Trading Center.

Every tunable value lives here so it's easy to find and change.

NOTE: This is a first-draft scaffold. No real money, no real orders. All
external integrations are mock stubs (see stubs/). Real wiring points are
marked with `# TODO:` throughout the codebase.
"""
from __future__ import annotations

from datetime import datetime, time as _time
from typing import Optional

try:
    from zoneinfo import ZoneInfo
    _TZ_OK = True
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore
    _TZ_OK = False

# --------------------------------------------------------------------------
# Session window (no after-hours trading)
# --------------------------------------------------------------------------
# CONFIRM TIMEZONE before wiring real data. U.S. regular hours are
# 09:30–16:00 ET (08:30–15:00 CT); pre-market opens 04:00 ET / 03:00 CT.
# The 03:00 start below matches CT pre-market open, so this is bound to CT.
# (Re-confirm SESSION_END: 16:00 ET close = 15:00 CT — adjust if needed.)
SESSION_TIMEZONE   = "America/Chicago"   # CONFIRM: one timezone for both bounds
SESSION_START      = "03:00"   # market-watch start  (CT pre-market open)
SESSION_END        = "14:30"   # normal close        (CONFIRM vs 15:00 CT)
TRADE_AFTER_HOURS  = False

# --------------------------------------------------------------------------
# Money committed
# --------------------------------------------------------------------------
INVEST_MIN         = 100
INVEST_MAX         = 1_000_000
INVEST_DEFAULT     = 10_000

# --------------------------------------------------------------------------
# Confidence threshold — labelled a "confluence score" in the UI (10–99),
# a transparent confluence reading, NOT a statistical probability/percent.
# --------------------------------------------------------------------------
CONFIDENCE_MIN     = 10
CONFIDENCE_MAX     = 99
CONFIDENCE_DEFAULT = 70         # preferred default

# --------------------------------------------------------------------------
# Run mode
# --------------------------------------------------------------------------
MODES              = ["paper", "live"]
DEFAULT_MODE       = "paper"    # draft starts in paper for safety

# --------------------------------------------------------------------------
# Offered C5 versions (placeholder list shown in the screener)
# --------------------------------------------------------------------------
C5_VERSIONS        = ["C5 v1 — Core"]

C5_VERSION_INFO = {
    "C5 v1 — Core": (
        "The core C5 engine. Watches the regular U.S. session, reads each "
        "candidate's live chart, and produces a transparent confluence score "
        "(10–99). Takes a trade only when a ticker scores at or above your "
        "chosen threshold."
    ),
}

# --------------------------------------------------------------------------
# Draft simulation tuning (mock only — not real trading parameters)
# --------------------------------------------------------------------------
SIM_TICK_SECONDS   = 2          # how often the simulated loop ticks
SIM_MAX_OPEN       = 6          # max simultaneous simulated open trades
SIM_TRADE_SLICE    = 0.10       # fraction of committed amount per trade


def _parse_hhmm(s: str) -> _time:
    h, m = s.split(":")
    return _time(int(h), int(m))


def now_in_session_tz() -> datetime:
    if _TZ_OK:
        return datetime.now(ZoneInfo(SESSION_TIMEZONE))
    return datetime.now()


def session_is_open(now: Optional[datetime] = None) -> bool:
    """True if the current time is within the regular session window.

    Weekends are closed. After-hours is never tradable (TRADE_AFTER_HOURS).
    """
    now = now or now_in_session_tz()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return _parse_hhmm(SESSION_START) <= t < _parse_hhmm(SESSION_END)
