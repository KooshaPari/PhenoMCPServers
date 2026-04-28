from __future__ import annotations

import importlib.util
import sys
import types
from collections.abc import Iterator
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[2] / "src" / "agent_user_status"


def _load_local_module(module_name: str, file_name: str):
    spec = importlib.util.spec_from_file_location(module_name, SRC_DIR / file_name)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


package = types.ModuleType("agent_user_status")
package.__path__ = [str(SRC_DIR)]
sys.modules["agent_user_status"] = package
_load_local_module("agent_user_status.ttl_cache", "ttl_cache.py")
hook_cache = _load_local_module("agent_user_status.codex_hook_cache", "codex_hook_cache.py")


class FakeStopHookCache:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object], float]] = []
        self.clear_calls = 0

    def set_with_ttl(self, key: str, value: dict[str, object], ttl_seconds: float) -> dict[str, object]:
        self.calls.append((key, dict(value), ttl_seconds))
        return dict(value)

    def clear(self) -> None:
        self.clear_calls += 1


@pytest.fixture
def fake_stop_hook_cache(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeStopHookCache]:
    fake_cache = FakeStopHookCache()
    monkeypatch.setattr(hook_cache, "STOP_HOOK_CACHE", fake_cache)
    monkeypatch.setattr(hook_cache, "STOP_HOOK_DEGRADED_BASE_TTL_SECONDS", 4.0)
    monkeypatch.setattr(hook_cache, "STOP_HOOK_DEGRADED_MAX_TTL_SECONDS", 30.0)
    hook_cache.clear_stop_hook_cache()
    yield fake_cache
    hook_cache.clear_stop_hook_cache()


@pytest.mark.requirement("FR-AGENT_USER_STATUS-016")
def test_store_degraded_progressively_increases_ttl(fake_stop_hook_cache: FakeStopHookCache) -> None:
    result = {"ok": False, "decision": "allow_stop"}

    hook_cache.store_degraded("fingerprint-1", result)
    hook_cache.store_degraded("fingerprint-1", result)
    hook_cache.store_degraded("fingerprint-1", result)

    assert [call[2] for call in fake_stop_hook_cache.calls] == [4.0, 8.0, 16.0]
    assert [call[0] for call in fake_stop_hook_cache.calls] == ["fingerprint-1"] * 3


@pytest.mark.requirement("FR-AGENT_USER_STATUS-016")
def test_clear_stop_hook_cache_resets_degraded_backoff(fake_stop_hook_cache: FakeStopHookCache) -> None:
    result = {"ok": False, "decision": "allow_stop"}

    hook_cache.store_degraded("fingerprint-2", result)
    hook_cache.store_degraded("fingerprint-2", result)
    hook_cache.clear_stop_hook_cache()
    hook_cache.store_degraded("fingerprint-2", result)

    assert [call[2] for call in fake_stop_hook_cache.calls] == [4.0, 8.0, 4.0]
