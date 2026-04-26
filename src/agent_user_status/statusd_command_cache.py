"""TTL cache for subprocess-backed statusd reads."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from agent_user_status.ttl_cache import TTLCache

STATUSD_COMMAND_CACHE_TTL_SECONDS = float(
    os.environ.get("AGENT_USER_STATUSD_COMMAND_CACHE_TTL_SECONDS", "1.0")
)

COMMAND_CACHE: TTLCache[dict[str, Any]] = TTLCache(
    ttl_seconds=STATUSD_COMMAND_CACHE_TTL_SECONDS,
    max_entries=8,
)


def cached_command_result(key: str, factory: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    return COMMAND_CACHE.get_or_set(key, factory)


def clear_command_cache() -> None:
    COMMAND_CACHE.clear()
