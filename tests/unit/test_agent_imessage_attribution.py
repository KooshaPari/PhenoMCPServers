from __future__ import annotations

from agent_user_status import agent_imessage_learning as learning


@pytest.mark.requirement("FR-age-006")
def test_coarse_attribution_marks_unresolved_terminal_as_uncertain(monkeypatch) -> None:
    monkeypatch.setattr(
        learning,
        "action_environment_context",
        lambda: {
            "frontmost_app": "Ghostty",
            "terminal_active": True,
            "agent_processes": [],
            "coding_processes": [],
            "gaze_targeting_reliable": False,
        },
    )
    monkeypatch.setattr(
        learning,
        "hook_configuration_context",
        lambda: {"claude_stop_hook": False, "codex_hook_guidance": False},
    )

    attribution = learning.coarse_attribution_context()

    assert attribution["surface"] == "unresolved_terminal"
    assert attribution["hook_status"] == "unreliable_terminal_identity"
    assert attribution["reliable"] is False
    assert learning.attribution_status_text(attribution).startswith("uncertain:unresolved_terminal")


@pytest.mark.requirement("FR-age-006")
def test_coarse_attribution_marks_gui_chat_without_terminal_guessing(monkeypatch) -> None:
    monkeypatch.setattr(
        learning,
        "action_environment_context",
        lambda: {
            "frontmost_app": "Messages",
            "terminal_active": False,
            "agent_processes": ["claude_code"],
            "coding_processes": ["codex_cli"],
            "gaze_targeting_reliable": True,
        },
    )
    monkeypatch.setattr(
        learning,
        "hook_configuration_context",
        lambda: {"claude_stop_hook": True, "codex_hook_guidance": True},
    )

    attribution = learning.coarse_attribution_context()

    assert attribution["surface"] == "gui_chat"
    assert attribution["hook_status"] == "gui_chat"
    assert attribution["reliable"] is True
    assert "frontmost_messages_chat" in attribution["reasons"]


@pytest.mark.requirement("FR-age-006")
def test_classify_window_role_prefers_terminal_and_chat_contexts() -> None:
    assert (
        learning.classify_window_role("Ghostty", {"agent": ["codex"], "coding": ["python"]})
        == "multi_agent_terminal"
    )
    assert learning.classify_window_role("Messages", {"agent": ["claude"], "coding": []}) == "gui_chat"
    assert learning.classify_window_role("Safari", {}) == "browser"
