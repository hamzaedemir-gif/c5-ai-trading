import asyncio
import time

import pytest

from core import BackgroundScheduler, TTLCache, retry_with_backoff
from core.cache import cached


def test_ttlcache_set_get_expiry():
    c = TTLCache(default_ttl=0.05)
    c.set(("k",), "v")
    hit, v = c.get(("k",))
    assert hit and v == "v"
    time.sleep(0.08)
    hit, v = c.get(("k",))
    assert not hit


def test_cached_decorator_caches_results():
    c = TTLCache(default_ttl=10.0)
    calls = {"n": 0}

    @cached(c)
    def square(x):
        calls["n"] += 1
        return x * x

    assert square(3) == 9
    assert square(3) == 9
    assert calls["n"] == 1
    assert square(4) == 16
    assert calls["n"] == 2


def test_cached_handles_unhashable_first_arg():
    c = TTLCache()

    class Req:
        pass

    @cached(c, skip_first_arg=True)
    def handler(req, x):
        return x + 1

    r = Req()
    assert handler(r, 5) == 6
    assert handler(r, 5) == 6   # cached


def test_invalidate_clears_cache():
    c = TTLCache()
    c.set(("a",), 1)
    c.set(("b",), 2)
    assert c.invalidate() == 2
    hit, _ = c.get(("a",))
    assert not hit


def test_retry_succeeds_after_failures():
    state = {"n": 0}

    @retry_with_backoff(attempts=3, base_delay=0.0)
    def flaky():
        state["n"] += 1
        if state["n"] < 3:
            raise RuntimeError("transient")
        return "ok"

    assert flaky() == "ok"
    assert state["n"] == 3


def test_retry_uses_fallback_when_exhausted():
    @retry_with_backoff(attempts=2, base_delay=0.0, fallback=lambda: "fallback-value")
    def always_fail():
        raise RuntimeError("boom")

    assert always_fail() == "fallback-value"


def test_retry_reraises_when_no_fallback():
    @retry_with_backoff(attempts=2, base_delay=0.0)
    def always_fail():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        always_fail()


def test_scheduler_runs_job_then_stops():
    async def run():
        s = BackgroundScheduler()
        counter = {"n": 0}

        async def job():
            counter["n"] += 1

        s.add("counter", job, interval_s=0.05)
        s.start()
        await asyncio.sleep(0.25)
        await s.stop()
        return counter["n"]

    n = asyncio.run(run())
    assert n >= 1  # ran at least once


def test_scheduler_keeps_running_after_failure():
    async def run():
        s = BackgroundScheduler()
        counter = {"ok": 0, "fail": 0}

        async def job():
            if counter["fail"] < 2:
                counter["fail"] += 1
                raise RuntimeError("die")
            counter["ok"] += 1

        s.add("flaky", job, interval_s=0.03)
        s.start()
        await asyncio.sleep(0.3)
        await s.stop()
        return counter

    out = asyncio.run(run())
    assert out["ok"] >= 1
    assert out["fail"] >= 1
