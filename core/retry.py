"""Retry-with-exponential-backoff decorator + graceful-fallback helper."""
from __future__ import annotations

import functools
import logging
import time
from typing import Callable, Iterable, Type

log = logging.getLogger(__name__)


def retry_with_backoff(*, attempts: int = 4, base_delay: float = 0.5,
                       max_delay: float = 10.0, factor: float = 2.0,
                       exceptions: Iterable[Type[BaseException]] = (Exception,),
                       fallback: Callable | None = None,
                       name: str | None = None) -> Callable:
    """Retry `attempts` times on listed exceptions with exponential backoff.

    If all retries are exhausted, call `fallback(*args, **kwargs)` if
    provided (must return the same shape as the wrapped function), else
    re-raise the last exception. Every failure is logged at WARNING.
    """
    exc_tuple = tuple(exceptions)

    def deco(fn: Callable) -> Callable:
        fn_name = name or fn.__qualname__

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            delay = base_delay
            last_exc: BaseException | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exc_tuple as exc:
                    last_exc = exc
                    log.warning(
                        "%s attempt %d/%d failed: %s",
                        fn_name, attempt, attempts, exc,
                    )
                    if attempt == attempts:
                        break
                    time.sleep(delay)
                    delay = min(delay * factor, max_delay)
            if fallback is not None:
                log.warning("%s exhausted retries, using fallback", fn_name)
                return fallback(*args, **kwargs)
            assert last_exc is not None
            raise last_exc

        return wrapper

    return deco
