"""Bounded receipt and echo-cleanup state for outbound agent messages."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from agent_user_status.agent_imessage_core import STATE_DIR, stable_hash
from agent_user_status.agent_imessage_envelope import AgentMessageEnvelope
from agent_user_status.jsonl_tail import tail_jsonl

OUTBOX_SCHEMA_VERSION = 1
OUTBOX_PATH = STATE_DIR / "message_outbox.jsonl"
MAX_RECENT_RECORDS = 2000

DeliveryState = Literal["queued", "sent", "delivered", "responded", "expired", "failed"]
EchoState = Literal["none", "delete_requested", "deleted", "unsupported", "failed"]


@dataclass(frozen=True)
class OutboxRecord:
    """Privacy-safe state for one outbound message lifecycle transition."""

    message_id: str
    correlation_id: str
    recipient: str
    delivery_state: DeliveryState
    echo_state: EchoState
    observed_at: str
    project: str = ""
    task_id: str = ""
    session_id: str = ""
    body_hash: str = ""
    rendered_hash: str = ""
    receipt_id: str = ""
    note: str = ""
    schema_version: int = OUTBOX_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "message_id": self.message_id,
            "correlation_id": self.correlation_id,
            "recipient": self.recipient,
            "delivery_state": self.delivery_state,
            "echo_state": self.echo_state,
            "observed_at": self.observed_at,
            "project": self.project,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "body_hash": self.body_hash,
            "rendered_hash": self.rendered_hash,
        }
        if self.receipt_id:
            payload["receipt_id"] = self.receipt_id
        if self.note:
            payload["note"] = self.note
        return payload


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def append_outbox_record(record: OutboxRecord, store_path: Path | None = None) -> dict[str, Any]:
    """Append one state transition to the outbox JSONL store."""

    path = store_path or OUTBOX_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = record.to_dict()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return payload


def delivery_record_from_envelope(
    envelope: AgentMessageEnvelope,
    *,
    recipient: str,
    rendered_message: str,
    delivery_state: DeliveryState = "queued",
    echo_state: EchoState = "none",
    receipt_id: str = "",
    note: str = "",
) -> OutboxRecord:
    """Create a privacy-safe outbox record without storing message bodies."""

    return OutboxRecord(
        message_id=envelope.message_id,
        correlation_id=envelope.correlation_id,
        recipient=recipient,
        delivery_state=delivery_state,
        echo_state=echo_state,
        observed_at=now_iso(),
        project=envelope.project,
        task_id=envelope.task_id,
        session_id=envelope.session_id,
        body_hash=stable_hash(envelope.body),
        rendered_hash=stable_hash(rendered_message),
        receipt_id=receipt_id,
        note=note,
    )


def read_outbox_records(
    *,
    store_path: Path | None = None,
    correlation_id: str | None = None,
    message_id: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Read recent outbox records with bounded memory and malformed-line tolerance."""

    path = store_path or OUTBOX_PATH
    bounded_limit = max(1, min(int(limit), MAX_RECENT_RECORDS))
    records: list[dict[str, Any]] = []
    for record in tail_jsonl(path, limit=bounded_limit):
        if correlation_id is not None and record.get("correlation_id") != correlation_id:
            continue
        if message_id is not None and record.get("message_id") != message_id:
            continue
        records.append(record)
    return records


def latest_outbox_state(
    *,
    store_path: Path | None = None,
    correlation_id: str | None = None,
    message_id: str | None = None,
) -> dict[str, Any] | None:
    """Return the latest matching state transition."""

    records = read_outbox_records(store_path=store_path, correlation_id=correlation_id, message_id=message_id)
    return records[-1] if records else None


def record_echo_cleanup_unsupported(
    *,
    message_id: str,
    correlation_id: str,
    recipient: str,
    reason: str,
    store_path: Path | None = None,
) -> dict[str, Any]:
    """Record that sender-side echo deletion is unavailable or unsafe."""

    return append_outbox_record(
        OutboxRecord(
            message_id=message_id,
            correlation_id=correlation_id,
            recipient=recipient,
            delivery_state="sent",
            echo_state="unsupported",
            observed_at=now_iso(),
            note=reason[:240],
        ),
        store_path=store_path,
    )
