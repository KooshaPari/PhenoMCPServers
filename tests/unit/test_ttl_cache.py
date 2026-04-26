from __future__ import annotations

import pytest

from agent_user_status.ttl_cache import TTLCache


@pytest.mark.requirement("FR-AGENT_USER_STATUS-004")
def test_ttl_cache_reuses_value_until_expiry() -> None:
    now = 100.0
    calls = 0
    cache: TTLCache[dict[str, int]] = TTLCache(ttl_seconds=5.0, clock=lambda: now)

    def factory() -> dict[str, int]:
        nonlocal calls
        calls += 1
        return {"value": calls}

    assert cache.get_or_set("status", factory) == {"value": 1}
    assert cache.get_or_set("status", factory) == {"value": 1}
    assert calls == 1

    now = 106.0
    assert cache.get_or_set("status", factory) == {"value": 2}
    assert calls == 2


@pytest.mark.requirement("FR-AGENT_USER_STATUS-004")
def test_ttl_cache_returns_copies_to_protect_cached_state() -> None:
    cache: TTLCache[dict[str, list[str]]] = TTLCache(ttl_seconds=10.0)

    first = cache.set("status", {"messages": ["redacted"]})
    first["messages"].append("mutated")
    second = cache.get("status")

    assert second == {"messages": ["redacted"]}


@pytest.mark.requirement("FR-AGENT_USER_STATUS-004")
def test_ttl_cache_evicts_oldest_entry_when_full() -> None:
    cache: TTLCache[int] = TTLCache(ttl_seconds=10.0, max_entries=2)

    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)

    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3
