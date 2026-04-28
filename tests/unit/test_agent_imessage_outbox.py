from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

import agent_user_status.agent_imessage_outbox as outbox
from agent_user_status.agent_imessage_envelope import AgentMessageEnvelope
from agent_user_status.agent_imessage_outbox import (
    append_outbox_record,
    delivery_record_from_envelope,
    latest_outbox_state,
    read_outbox_records,
    record_delivery_receipt,
    record_echo_cleanup_deleted,
    record_echo_cleanup_requested,
    record_echo_cleanup_unsupported,
    record_response_received,
    record_retry_scheduled,
    sweep_expired_outbox_records,
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
    latest = latest_outbox_state(store_path=store_path, correlation_id="corr-1")

    assert [record["delivery_state"] for record in records] == ["queued", "responded"]
    assert latest is not None
    assert latest["delivery_state"] == "responded"


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


@pytest.mark.requirement("FR-AGENT_USER_STATUS-014")
def test_outbox_records_receipts_responses_and_expiration(tmp_path) -> None:
    store_path = tmp_path / "outbox.jsonl"
    envelope = AgentMessageEnvelope.create(
        "Need approval",
        project="agent-user-status",
        task_id="FR-014",
        session_id="sess-2",
        expires_minutes=1,
        correlation_id="corr-2",
    )

    append_outbox_record(
        delivery_record_from_envelope(
            envelope,
            recipient="koosha",
            rendered_message=envelope.render(),
            delivery_state="sent",
        ),
        store_path=store_path,
    )
    receipt = record_delivery_receipt(
        message_id=envelope.message_id,
        correlation_id=envelope.correlation_id,
        recipient="koosha",
        receipt_id="receipt-1",
        store_path=store_path,
    )
    response = record_response_received(
        message_id=envelope.message_id,
        correlation_id=envelope.correlation_id,
        recipient="koosha",
        response_id="reply-1",
        response_body="A1",
        store_path=store_path,
    )
    requested = record_echo_cleanup_requested(
        message_id=envelope.message_id,
        correlation_id=envelope.correlation_id,
        recipient="koosha",
        store_path=store_path,
    )
    deleted = record_echo_cleanup_deleted(
        message_id=envelope.message_id,
        correlation_id=envelope.correlation_id,
        recipient="koosha",
        store_path=store_path,
    )
    expired = sweep_expired_outbox_records(
        store_path=store_path,
        now=datetime.now(UTC) + timedelta(minutes=2),
    )

    assert receipt["receipt_id"] == "receipt-1"
    assert response["response_id"] == "reply-1"
    assert requested["echo_state"] == "delete_requested"
    assert deleted["echo_state"] == "deleted"
    assert expired[-1]["delivery_state"] == "expired"


@pytest.mark.requirement("FR-AGENT_USER_STATUS-014")
def test_outbox_records_retry_schedule_with_bounded_backoff(monkeypatch, tmp_path) -> None:
    store_path = tmp_path / "outbox.jsonl"
    fixed_now = datetime(2026, 4, 27, 12, 0, tzinfo=UTC)

    class FixedDatetime:
        @classmethod
        def now(cls, tz=None):  # noqa: D401 - test helper
            return fixed_now

    monkeypatch.setattr(outbox, "datetime", FixedDatetime)
    monkeypatch.setattr(outbox, "now_iso", lambda: fixed_now.isoformat())

    record = record_retry_scheduled(
        message_id="msg-3",
        correlation_id="corr-3",
        recipient="koosha",
        retry_count=2,
        delay_seconds=30,
        note="retry later",
        store_path=store_path,
    )

    assert record["delivery_state"] == "queued"
    assert record["retry_count"] == 2
    assert record["next_retry_at"] == (fixed_now + timedelta(seconds=30)).isoformat()
    assert record["note"] == "retry later"
