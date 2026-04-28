"""Bounded cache for Codex stop-hook decisions."""

from __future__ import annotations

import os
import threading
from collections.abc import Mapping
from typing import Any

from agent_user_status.ttl_cache import TTLCache

STOP_HOOK_CACHE_TTL_SECONDS = float(os.environ.get("AGENT_USER_STATUS_STOP_HOOK_CACHE_TTL_SECONDS", "2.0"))
STOP_HOOK_DEGRADED_BASE_TTL_SECONDS = float(
    os.environ.get("AGENT_USER_STATUS_STOP_HOOK_DEGRADED_BASE_TTL_SECONDS", "4.0")
)
STOP_HOOK_DEGRADED_MAX_TTL_SECONDS = float(
    os.environ.get("AGENT_USER_STATUS_STOP_HOOK_DEGRADED_MAX_TTL_SECONDS", "30.0")
)

STOP_HOOK_CACHE: TTLCache[dict[str, Any]] = TTLCache(ttl_seconds=STOP_HOOK_CACHE_TTL_SECONDS, max_entries=32)
_FAILURE_COUNTS: dict[str, int] = {}
_LOCK = threading.RLock()


def _degraded_ttl(attempts: int) -> float:
    attempts = max(1, attempts)
    ttl = STOP_HOOK_DEGRADED_BASE_TTL_SECONDS * (2 ** (attempts - 1))
    return min(ttl, STOP_HOOK_DEGRADED_MAX_TTL_SECONDS)


def cache_key(text: str) -> str:
    return text


def cached_decision(fingerprint: str) -> dict[str, Any] | None:
    return STOP_HOOK_CACHE.get(cache_key(fingerprint))


def store_success(fingerprint: str, result: Mapping[str, Any]) -> dict[str, Any]:
    with _LOCK:
        _FAILURE_COUNTS.pop(fingerprint, None)
    return STOP_HOOK_CACHE.set_with_ttl(cache_key(fingerprint), dict(result), STOP_HOOK_CACHE_TTL_SECONDS)


def store_degraded(fingerprint: str, result: Mapping[str, Any]) -> dict[str, Any]:
    with _LOCK:
        _FAILURE_COUNTS[fingerprint] = _FAILURE_COUNTS.get(fingerprint, 0) + 1
        ttl = _degraded_ttl(_FAILURE_COUNTS[fingerprint])
    return STOP_HOOK_CACHE.set_with_ttl(cache_key(fingerprint), dict(result), ttl)


def clear_stop_hook_cache() -> None:
    with _LOCK:
        _FAILURE_COUNTS.clear()
        STOP_HOOK_CACHE.clear()
