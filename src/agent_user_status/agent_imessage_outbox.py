"""Bounded receipt and echo-cleanup state for outbound agent messages."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
TERMINAL_DELIVERY_STATES = {"delivered", "responded", "expired", "failed"}
TERMINAL_ECHO_STATES = {"deleted", "unsupported", "failed"}


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
    expires_at: str = ""
    receipt_id: str = ""
    response_id: str = ""
    response_observed_at: str = ""
    retry_count: int = 0
    next_retry_at: str = ""
    cleanup_requested_at: str = ""
    cleanup_completed_at: str = ""
    cleanup_method: str = ""
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
        if self.expires_at:
            payload["expires_at"] = self.expires_at
        if self.receipt_id:
            payload["receipt_id"] = self.receipt_id
        if self.response_id:
            payload["response_id"] = self.response_id
        if self.response_observed_at:
            payload["response_observed_at"] = self.response_observed_at
        if self.retry_count:
            payload["retry_count"] = self.retry_count
        if self.next_retry_at:
            payload["next_retry_at"] = self.next_retry_at
        if self.cleanup_requested_at:
            payload["cleanup_requested_at"] = self.cleanup_requested_at
        if self.cleanup_completed_at:
            payload["cleanup_completed_at"] = self.cleanup_completed_at
        if self.cleanup_method:
            payload["cleanup_method"] = self.cleanup_method
        if self.note:
            payload["note"] = self.note
        return payload


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _record_matches(
    record: dict[str, Any],
    *,
    correlation_id: str | None = None,
    message_id: str | None = None,
    recipient: str | None = None,
) -> bool:
    if correlation_id is not None and record.get("correlation_id") != correlation_id:
        return False
    if message_id is not None and record.get("message_id") != message_id:
        return False
    if recipient is not None and record.get("recipient") != recipient:
        return False
    return True


def _terminal_delivery_state(record: dict[str, Any]) -> bool:
    return str(record.get("delivery_state") or "") in TERMINAL_DELIVERY_STATES


def _latest_history(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    return records[-1] if records else None


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
        expires_at=envelope.expires_at or "",
        receipt_id=receipt_id,
        note=note,
    )


def record_delivery_receipt(
    *,
    message_id: str,
    correlation_id: str,
    recipient: str,
    receipt_id: str,
    note: str = "",
    store_path: Path | None = None,
) -> dict[str, Any]:
    """Append a delivery receipt transition."""

    return append_outbox_record(
        OutboxRecord(
            message_id=message_id,
            correlation_id=correlation_id,
            recipient=recipient,
            delivery_state="delivered",
            echo_state="none",
            observed_at=now_iso(),
            receipt_id=receipt_id,
            note=note[:240],
        ),
        store_path=store_path,
    )


def record_response_received(
    *,
    message_id: str,
    correlation_id: str,
    recipient: str,
    response_id: str,
    response_body: str,
    note: str = "",
    store_path: Path | None = None,
) -> dict[str, Any]:
    """Append a response correlation transition."""

    return append_outbox_record(
        OutboxRecord(
            message_id=message_id,
            correlation_id=correlation_id,
            recipient=recipient,
            delivery_state="responded",
            echo_state="none",
            observed_at=now_iso(),
            response_id=response_id,
            response_observed_at=now_iso(),
            body_hash=stable_hash(response_body),
            note=note[:240],
        ),
        store_path=store_path,
    )


def record_retry_scheduled(
    *,
    message_id: str,
    correlation_id: str,
    recipient: str,
    retry_count: int,
    delay_seconds: int,
    note: str = "",
    store_path: Path | None = None,
) -> dict[str, Any]:
    """Append a retry transition with bounded backoff metadata."""

    if retry_count < 1:
        raise ValueError("retry_count must be positive")
    if delay_seconds < 1:
        raise ValueError("delay_seconds must be positive")
    next_retry_at = (datetime.now(UTC) + timedelta(seconds=delay_seconds)).isoformat()
    return append_outbox_record(
        OutboxRecord(
            message_id=message_id,
            correlation_id=correlation_id,
            recipient=recipient,
            delivery_state="queued",
            echo_state="none",
            observed_at=now_iso(),
            retry_count=retry_count,
            next_retry_at=next_retry_at,
            note=note[:240],
        ),
        store_path=store_path,
    )


def record_echo_cleanup_requested(
    *,
    message_id: str,
    correlation_id: str,
    recipient: str,
    method: str = "configured-command",
    note: str = "",
    store_path: Path | None = None,
) -> dict[str, Any]:
    """Record that echo cleanup was requested for an outbound message."""

    return append_outbox_record(
        OutboxRecord(
            message_id=message_id,
            correlation_id=correlation_id,
            recipient=recipient,
            delivery_state="sent",
            echo_state="delete_requested",
            observed_at=now_iso(),
            cleanup_requested_at=now_iso(),
            cleanup_method=method,
            note=note[:240],
        ),
        store_path=store_path,
    )


def record_echo_cleanup_deleted(
    *,
    message_id: str,
    correlation_id: str,
    recipient: str,
    method: str = "configured-command",
    note: str = "",
    store_path: Path | None = None,
) -> dict[str, Any]:
    """Record that a cleanup request completed successfully."""

    return append_outbox_record(
        OutboxRecord(
            message_id=message_id,
            correlation_id=correlation_id,
            recipient=recipient,
            delivery_state="sent",
            echo_state="deleted",
            observed_at=now_iso(),
            cleanup_requested_at=now_iso(),
            cleanup_completed_at=now_iso(),
            cleanup_method=method,
            note=note[:240],
        ),
        store_path=store_path,
    )


def record_echo_cleanup_failed(
    *,
    message_id: str,
    correlation_id: str,
    recipient: str,
    reason: str,
    method: str = "configured-command",
    store_path: Path | None = None,
) -> dict[str, Any]:
    """Record that cleanup was attempted but failed."""

    return append_outbox_record(
        OutboxRecord(
            message_id=message_id,
            correlation_id=correlation_id,
            recipient=recipient,
            delivery_state="failed",
            echo_state="failed",
            observed_at=now_iso(),
            cleanup_requested_at=now_iso(),
            cleanup_method=method,
            note=reason[:240],
        ),
        store_path=store_path,
    )


def read_outbox_records(
    *,
    store_path: Path | None = None,
    correlation_id: str | None = None,
    message_id: str | None = None,
    recipient: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Read recent outbox records with bounded memory and malformed-line tolerance."""

    path = store_path or OUTBOX_PATH
    bounded_limit = max(1, min(int(limit), MAX_RECENT_RECORDS))
    records: list[dict[str, Any]] = []
    for record in tail_jsonl(path, limit=bounded_limit):
        if not _record_matches(
            record,
            correlation_id=correlation_id,
            message_id=message_id,
            recipient=recipient,
        ):
            continue
        records.append(record)
    return records


def latest_outbox_state(
    *,
    store_path: Path | None = None,
    correlation_id: str | None = None,
    message_id: str | None = None,
    recipient: str | None = None,
) -> dict[str, Any] | None:
    """Return the latest matching state transition."""

    records = read_outbox_records(
        store_path=store_path,
        correlation_id=correlation_id,
        message_id=message_id,
        recipient=recipient,
    )
    return _latest_history(records)


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
            cleanup_requested_at=now_iso(),
            note=reason[:240],
        ),
        store_path=store_path,
    )


def sweep_expired_outbox_records(
    *,
    store_path: Path | None = None,
    now: datetime | None = None,
    grace_seconds: int = 0,
) -> list[dict[str, Any]]:
    """Append expiration records for queued outbound messages past their deadline."""

    timestamp = now or datetime.now(UTC)
    records = read_outbox_records(store_path=store_path, limit=MAX_RECENT_RECORDS)
    seen: set[tuple[str, str]] = set()
    expired: list[dict[str, Any]] = []
    for record in records:
        key = (str(record.get("message_id") or ""), str(record.get("delivery_state") or ""))
        if key in seen:
            continue
        seen.add(key)
        if not record.get("expires_at"):
            continue
        if _terminal_delivery_state(record):
            continue
        deadline = _parse_dt(str(record.get("expires_at")))
        if deadline is None:
            continue
        if (timestamp - deadline).total_seconds() < grace_seconds:
            continue
        expired_record = append_outbox_record(
            OutboxRecord(
                message_id=str(record.get("message_id") or ""),
                correlation_id=str(record.get("correlation_id") or ""),
                recipient=str(record.get("recipient") or ""),
                delivery_state="expired",
                echo_state=str(record.get("echo_state") or "none"),  # type: ignore[arg-type]
                observed_at=now_iso(),
                project=str(record.get("project") or ""),
                task_id=str(record.get("task_id") or ""),
                session_id=str(record.get("session_id") or ""),
                body_hash=str(record.get("body_hash") or ""),
                rendered_hash=str(record.get("rendered_hash") or ""),
                expires_at=str(record.get("expires_at") or ""),
                receipt_id=str(record.get("receipt_id") or ""),
                response_id=str(record.get("response_id") or ""),
                response_observed_at=str(record.get("response_observed_at") or ""),
                retry_count=int(record.get("retry_count") or 0),
                next_retry_at=str(record.get("next_retry_at") or ""),
                cleanup_requested_at=str(record.get("cleanup_requested_at") or ""),
                cleanup_completed_at=str(record.get("cleanup_completed_at") or ""),
                cleanup_method=str(record.get("cleanup_method") or ""),
                note="expired by sweep",
            ),
            store_path=store_path,
        )
        expired.append(expired_record)
    return expired
