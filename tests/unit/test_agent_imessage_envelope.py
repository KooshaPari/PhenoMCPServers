from __future__ import annotations

import json

import pytest

from agent_user_status.agent_imessage_elicitation import ElicitationSchema
from agent_user_status.agent_imessage_envelope import AgentMessageEnvelope, envelope_from_json


@pytest.mark.requirement("FR-AGENT_USER_STATUS-011")
def test_envelope_renders_sender_project_task_and_reply_ref() -> None:
    envelope = AgentMessageEnvelope.create(
        "Need direction.",
        sender_name="codex-worker",
        session_id="sess-1",
        task_id="TASK-7",
        project="agent-user-status",
        repo_path="/repo/agent-user-status",
        urgency="high",
        correlation_id="corr-fixed",
    )

    rendered = envelope.render()

    assert "Project: agent-user-status" in rendered
    assert "Task: TASK-7" in rendered
    assert "Session: sess-1" in rendered
    assert "From: codex-worker (codex)" in rendered
    assert "Reply ref: corr-fixed" in rendered
    assert "Need direction." in rendered


@pytest.mark.requirement("FR-AGENT_USER_STATUS-011")
@pytest.mark.requirement("FR-AGENT_USER_STATUS-013")
def test_envelope_round_trips_answer_schema_from_json() -> None:
    schema = ElicitationSchema.from_dict(
        {"questions": [{"prompt": "Pick one", "options": [{"label": "A"}, {"label": "B"}]}]}
    )
    envelope = AgentMessageEnvelope.create("Question", answer_schema=schema, correlation_id="corr-json")

    restored = envelope_from_json(json.dumps(envelope.to_dict()))

    assert restored.correlation_id == "corr-json"
    assert restored.answer_schema is not None
    assert "A2: B" in restored.render()
