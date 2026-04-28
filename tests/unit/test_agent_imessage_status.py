from __future__ import annotations

import pytest

from agent_user_status import agent_imessage_status as status
from agent_user_status.codex_hook_cache import clear_stop_hook_cache


@pytest.mark.requirement("FR-AGENT_USER_STATUS-016")
def test_hook_decision_result_reuses_cached_result_for_repeated_text(monkeypatch, tmp_path) -> None:
    clear_stop_hook_cache()
    monkeypatch.setattr(status, "STATE_DIR", tmp_path)
    status_calls = {"estimate": 0, "attribution": 0}
    monkeypatch.setattr(
        status,
        "estimate_status",
        lambda _config: status_calls.__setitem__("estimate", status_calls["estimate"] + 1)
        or {"ok": True, "source": "imessage", "status": "active", "confidence": 0.8, "estimated_response": "0-2 min"},
    )
    monkeypatch.setattr(
        status,
        "coarse_attribution_context",
        lambda: status_calls.__setitem__("attribution", status_calls["attribution"] + 1)
        or {"surface": "terminal", "hook_status": "candidate_configured", "reliable": True, "reasons": []},
    )

    first = status.hook_decision_result("Waiting for your response.")
    second = status.hook_decision_result("Waiting for your response.")

    assert first == second
    assert status_calls == {"estimate": 1, "attribution": 1}


@pytest.mark.requirement("FR-AGENT_USER_STATUS-016")
def test_hook_decision_result_degrades_and_caches_error_path(monkeypatch, tmp_path) -> None:
    clear_stop_hook_cache()
    monkeypatch.setattr(status, "STATE_DIR", tmp_path)
    calls = {"estimate": 0}

    def boom(_config):
        calls["estimate"] += 1
        raise RuntimeError("status unavailable")

    monkeypatch.setattr(status, "estimate_status", boom)

    first = status.hook_decision_result("Waiting for your response.")
    second = status.hook_decision_result("Waiting for your response.")

    assert first == second
    assert first["ok"] is False
    assert first["decision"] == "allow_stop"
    assert calls["estimate"] == 1
