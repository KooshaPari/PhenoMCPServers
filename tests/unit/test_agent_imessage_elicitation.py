from __future__ import annotations

import pytest

from agent_user_status.agent_imessage_elicitation import ElicitationSchema, parse_reply


@pytest.mark.requirement("FR-AGENT_USER_STATUS-013")
def test_schema_renders_stable_answer_ids() -> None:
    schema = ElicitationSchema.from_dict(
        {
            "kind": "single_question",
            "questions": [
                {
                    "id": "Q1",
                    "prompt": "How should I proceed?",
                    "options": [
                        {"label": "Continue"},
                        {"label": "Pause", "description": "Stop after current task"},
                    ],
                }
            ],
        }
    )

    rendered = schema.render()

    assert "A1: Continue" in rendered
    assert "A2: Pause - Stop after current task" in rendered


@pytest.mark.requirement("FR-AGENT_USER_STATUS-013")
def test_parse_multi_answer_reply_with_freeform_text() -> None:
    schema = ElicitationSchema.from_dict(
        {
            "kind": "single_question",
            "questions": [
                {
                    "id": "Q1",
                    "prompt": "Pick targets",
                    "kind": "multi_answer",
                    "allow_freeform": True,
                    "options": [{"label": "AgilePlus"}, {"label": "FocalPoint"}, {"label": "Tracera"}],
                }
            ],
        }
    )

    parsed = parse_reply("A1, A3 first please", schema)

    assert parsed.selected_answer_ids == ["A1", "A3"]
    assert parsed.freeform_text == "first please"
    assert parsed.confidence == 0.95
    assert not parsed.ambiguous


@pytest.mark.requirement("FR-AGENT_USER_STATUS-013")
def test_schema_accepts_text_and_multi_select_aliases() -> None:
    schema = ElicitationSchema.from_dict(
        {
            "questions": [
                {
                    "id": "q1",
                    "text": "Pick targets",
                    "multi_select": True,
                    "options": [
                        {"id": "A1", "label": "One"},
                        {"id": "A2", "label": "Two"},
                        {"id": "A3", "label": "Three"},
                    ],
                }
            ]
        }
    )

    parsed = parse_reply("A1,A3", schema)

    assert schema.questions[0].prompt == "Pick targets"
    assert schema.questions[0].kind == "multi_answer"
    assert parsed.selected_answer_ids == ["A1", "A3"]
    assert parsed.confidence == 0.95
    assert not parsed.ambiguous
