"""Simulated trading-day clock.

Lets the prototype run like a realistic US trading day even when the real
market is closed. It is a CLEARLY-LABELLED demo: prices are synthetic and this
is NOT real market data. The clock starts at 08:30 ET (pre-market) and advances
on a time-compression factor so a full 08:30->16:00 session plays out in a
watchable span.
"""
from __future__ import annotations

import time as _time
from datetime import datetime, time, timedelta
from typing import Optional

try:
    from zoneinfo import ZoneInfo

    _ET: Optional[ZoneInfo] = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover
    _ET = None

DEMO_START = time(8, 30)      # 8:30 AM ET
DEMO_END = time(16, 0)        # 4:00 PM ET close
DEFAULT_COMPRESSION = 6.0     # 1 real second = 6 simulated seconds (~75 min/day)

SESSION_PRE = "PRE-MARKET"
SESSION_OPEN = "OPEN"
SESSION_CLOSED = "CLOSED (demo day complete)"


def _today_at(t: time) -> datetime:
    base = datetime.now(_ET) if _ET else datetime.now()
    return base.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)


def demo_clock(real_start: float, compression: float = DEFAULT_COMPRESSION,
               now: Optional[float] = None) -> datetime:
    """Map real elapsed time to a simulated clock starting at 08:30 ET.

    The simulated time is clamped at the 16:00 close.
    """
    now = now if now is not None else _time.time()
    elapsed = max(0.0, now - real_start)
    sim = _today_at(DEMO_START) + timedelta(seconds=elapsed * compression)
    close = _today_at(DEMO_END)
    return min(sim, close)


def demo_session(dt: datetime) -> str:
    t = dt.time()
    if t < DEMO_START:
        return SESSION_PRE
    if t < time(9, 30):
        return SESSION_PRE
    if t < DEMO_END:
        return SESSION_OPEN
    return SESSION_CLOSED


def session_progress(dt: datetime) -> float:
    """0..1 through the 08:30->16:00 window."""
    start = _today_at(DEMO_START)
    total = (_today_at(DEMO_END) - start).total_seconds()
    done = (dt - start).total_seconds()
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, done / total))
