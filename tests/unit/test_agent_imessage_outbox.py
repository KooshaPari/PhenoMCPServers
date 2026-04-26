from __future__ import annotations

import json

import pytest

from agent_user_status.agent_imessage_envelope import AgentMessageEnvelope
from agent_user_status.agent_imessage_outbox import (
    append_outbox_record,
    delivery_record_from_envelope,
    latest_outbox_state,
    read_outbox_records,
    record_echo_cleanup_unsupported,
)


@pytest.mark.requirement("FR-AGENT_USER_STATUS-014")
def test_delivery_record_does_not_store_message_body(tmp_path) -> None:
    store_path = tmp_path / "outbox.jsonl"
    envelope = AgentMessageEnvelope.create(
        "private body",
        project="agent-user-status",
        task_id="FR-014",
        session_id="sess-1",
        correlation_id="corr-1",
    )

    record = append_outbox_record(
        delivery_record_from_envelope(
            envelope,
            recipient="koosha",
            rendered_message=envelope.render(),
            delivery_state="sent",
            receipt_id="receipt-1",
        ),
        store_path=store_path,
    )

    persisted = json.loads(store_path.read_text(encoding="utf-8"))
    assert persisted == record
    assert record["correlation_id"] == "corr-1"
    assert record["delivery_state"] == "sent"
    assert record["receipt_id"] == "receipt-1"
    assert "private body" not in json.dumps(record)
    assert record["body_hash"]
    assert record["rendered_hash"]


@pytest.mark.requirement("FR-AGENT_USER_STATUS-014")
def test_outbox_reads_recent_records_and_filters_malformed_lines(tmp_path) -> None:
    store_path = tmp_path / "outbox.jsonl"
    envelope = AgentMessageEnvelope.create("body", correlation_id="corr-1")
    append_outbox_record(
        delivery_record_from_envelope(envelope, recipient="koosha", rendered_message=envelope.render()),
        store_path=store_path,
    )
    with store_path.open("a", encoding="utf-8") as handle:
        handle.write("{not-json\n")
    append_outbox_record(
        delivery_record_from_envelope(
            envelope,
            recipient="koosha",
            rendered_message=envelope.render(),
            delivery_state="responded",
        ),
        store_path=store_path,
    )

    records = read_outbox_records(store_path=store_path, correlation_id="corr-1")

    assert [record["delivery_state"] for record in records] == ["queued", "responded"]
    assert latest_outbox_state(store_path=store_path, correlation_id="corr-1")["delivery_state"] == "responded"


@pytest.mark.requirement("FR-AGENT_USER_STATUS-012")
def test_echo_cleanup_records_unsupported_state(tmp_path) -> None:
    store_path = tmp_path / "outbox.jsonl"

    record = record_echo_cleanup_unsupported(
        message_id="msg-1",
        correlation_id="corr-1",
        recipient="koosha",
        reason="Messages database permission unavailable",
        store_path=store_path,
    )

    assert record["delivery_state"] == "sent"
    assert record["echo_state"] == "unsupported"
    assert record["note"] == "Messages database permission unavailable"
