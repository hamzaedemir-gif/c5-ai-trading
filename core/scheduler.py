"""Async background scheduler for periodic refresh tasks."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, List

log = logging.getLogger(__name__)

Job = Callable[[], Awaitable[None]]


@dataclass
class _ScheduledJob:
    name: str
    job: Job
    interval: float
    enabled: bool = True


class BackgroundScheduler:
    """Run a list of async coroutines on individual schedules.

    Failures are logged but never propagate; the next tick will try again.
    """

    def __init__(self) -> None:
        self._jobs: List[_ScheduledJob] = []
        self._tasks: List[asyncio.Task] = []
        self._stop = asyncio.Event()

    def add(self, name: str, job: Job, *, interval_s: float,
            enabled: bool = True) -> None:
        self._jobs.append(_ScheduledJob(name=name, job=job,
                                        interval=interval_s, enabled=enabled))

    def start(self) -> None:
        for sj in self._jobs:
            if sj.enabled:
                t = asyncio.create_task(self._run_job(sj), name=f"sched-{sj.name}")
                self._tasks.append(t)

    async def stop(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks.clear()

    async def _run_job(self, sj: _ScheduledJob) -> None:
        # Stagger an initial small delay so jobs don't all fire at t=0.
        await asyncio.sleep(min(sj.interval, 2.0))
        while not self._stop.is_set():
            try:
                await sj.job()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.error("scheduler job %s failed: %s", sj.name, exc)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=sj.interval)
                return     # stop was set
            except asyncio.TimeoutError:
                continue
