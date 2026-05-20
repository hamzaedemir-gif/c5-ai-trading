"""Simple TTL in-memory cache + decorator.

Thread-safe; suitable for FastAPI's threadpool. Keys are derived from the
function name and its positional + keyword arguments, so callers need not
manage cache keys manually.
"""
from __future__ import annotations

import functools
import threading
import time
from typing import Any, Callable, Hashable


class TTLCache:
    def __init__(self, default_ttl: float = 10.0, max_entries: int = 1024):
        self.default_ttl = default_ttl
        self.max_entries = max_entries
        self._lock = threading.Lock()
        self._store: dict[Hashable, tuple[float, Any]] = {}

    def get(self, key: Hashable) -> tuple[bool, Any]:
        now = time.monotonic()
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return False, None
            expires, value = item
            if expires < now:
                self._store.pop(key, None)
                return False, None
            return True, value

    def set(self, key: Hashable, value: Any, ttl: float | None = None) -> None:
        ttl = ttl if ttl is not None else self.default_ttl
        with self._lock:
            if len(self._store) >= self.max_entries:
                # Evict oldest by expiry time.
                oldest = min(self._store.items(), key=lambda kv: kv[1][0])[0]
                self._store.pop(oldest, None)
            self._store[key] = (time.monotonic() + ttl, value)

    def invalidate(self, prefix: str | None = None) -> int:
        with self._lock:
            if prefix is None:
                n = len(self._store)
                self._store.clear()
                return n
            keys = [k for k in self._store if isinstance(k, tuple) and k and k[0] == prefix]
            for k in keys:
                self._store.pop(k, None)
            return len(keys)

    def stats(self) -> dict:
        with self._lock:
            return {"entries": len(self._store), "max_entries": self.max_entries}


def _make_key(name: str, args: tuple, kwargs: dict) -> Hashable:
    # Skip non-hashable args (e.g. fastapi.Request) by replacing with their type name.
    safe_args = tuple(_safe(a) for a in args)
    safe_kw = tuple(sorted((k, _safe(v)) for k, v in kwargs.items()))
    return (name, safe_args, safe_kw)


def _safe(v) -> Hashable:
    try:
        hash(v)
        return v
    except TypeError:
        return f"<{type(v).__name__}>"


def cached(cache: TTLCache, *, ttl: float | None = None,
           skip_first_arg: bool = False) -> Callable:
    """Decorator: cache fn results in `cache`. `skip_first_arg=True` ignores
    the first positional arg in the key (useful for FastAPI `request`)."""
    def deco(fn: Callable):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key_args = args[1:] if skip_first_arg else args
            key = _make_key(fn.__qualname__, tuple(key_args), kwargs)
            hit, value = cache.get(key)
            if hit:
                return value
            value = fn(*args, **kwargs)
            cache.set(key, value, ttl=ttl)
            return value
        return wrapper
    return deco
