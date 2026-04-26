"""Small TTL cache for bounded local backend reads."""

from __future__ import annotations

import copy
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class CacheEntry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    """Bounded in-memory cache with monotonic-time expiry."""

    def __init__(
        self,
        *,
        ttl_seconds: float,
        max_entries: int = 128,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self.ttl_seconds = float(ttl_seconds)
        self.max_entries = int(max_entries)
        self._clock = clock
        self._entries: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: str) -> T | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            now = self._clock()
            if entry.expires_at <= now:
                self._entries.pop(key, None)
                return None
            self._entries.move_to_end(key)
            return copy.deepcopy(entry.value)

    def set(self, key: str, value: T) -> T:
        with self._lock:
            self._entries[key] = CacheEntry(
                value=copy.deepcopy(value),
                expires_at=self._clock() + self.ttl_seconds,
            )
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
            return copy.deepcopy(value)

    def get_or_set(self, key: str, factory: Callable[[], T]) -> T:
        cached = self.get(key)
        if cached is not None:
            return cached
        return self.set(key, factory())

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
