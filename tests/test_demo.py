"""Tests for the simulated trading-day clock."""
from c5.demo import (
    DEMO_END,
    DEMO_START,
    SESSION_CLOSED,
    SESSION_OPEN,
    SESSION_PRE,
    demo_clock,
    demo_session,
    session_progress,
)


def test_clock_starts_at_0830():
    start = 1_000_000.0
    dt = demo_clock(start, compression=6.0, now=start)  # zero elapsed
    assert dt.hour == DEMO_START.hour and dt.minute == DEMO_START.minute


def test_clock_advances_with_compression():
    start = 1_000_000.0
    # 10 real minutes * 6x = 60 sim minutes -> 09:30.
    dt = demo_clock(start, compression=6.0, now=start + 600)
    assert dt.hour == 9 and dt.minute == 30


def test_clock_clamps_at_close():
    start = 1_000_000.0
    dt = demo_clock(start, compression=100.0, now=start + 100_000)
    assert dt.hour == DEMO_END.hour and dt.minute == DEMO_END.minute


def test_sessions():
    start = 1_000_000.0
    assert demo_session(demo_clock(start, 6.0, start)) == SESSION_PRE          # 08:30
    assert demo_session(demo_clock(start, 6.0, start + 600)) == SESSION_OPEN   # 09:30
    assert demo_session(demo_clock(start, 100.0, start + 100_000)) == SESSION_CLOSED


def test_progress_monotonic():
    start = 1_000_000.0
    p0 = session_progress(demo_clock(start, 6.0, start))
    p1 = session_progress(demo_clock(start, 6.0, start + 1200))
    assert 0.0 <= p0 < p1 <= 1.0
