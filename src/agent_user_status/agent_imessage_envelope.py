"""Structured message envelopes for agent-to-user communication."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from agent_user_status.agent_imessage_core import stable_hash
from agent_user_status.agent_imessage_elicitation import ElicitationSchema

Urgency = Literal["low", "normal", "high", "urgent"]


@dataclass(frozen=True)
class AgentMessageSender:
    """Identity of the agent or hook producing a message."""

    name: str
    kind: str = "codex"

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "kind": self.kind}

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> AgentMessageSender:
        payload = payload or {}
        return cls(name=str(payload.get("name") or "agent"), kind=str(payload.get("kind") or "codex"))


@dataclass(frozen=True)
class AgentMessageEnvelope:
    """Structured metadata and renderable body for an outbound user message."""

    body: str
    message_id: str
    correlation_id: str
    sender: AgentMessageSender
    session_id: str
    task_id: str
    project: str
    repo_path: str
    created_at: str
    expires_at: str | None = None
    urgency: Urgency = "normal"
    answer_schema: ElicitationSchema | None = None

    def __post_init__(self) -> None:
        if self.urgency not in {"low", "normal", "high", "urgent"}:
            raise ValueError(f"Unsupported urgency: {self.urgency}")
        if not self.body.strip() and self.answer_schema is None:
            raise ValueError("Message body or answer schema is required")

    @classmethod
    def create(
        cls,
        body: str,
        *,
        sender_name: str = "codex",
        sender_kind: str = "codex",
        session_id: str | None = None,
        task_id: str = "",
        project: str = "",
        repo_path: str = "",
        urgency: Urgency = "normal",
        expires_minutes: int | None = None,
        answer_schema: ElicitationSchema | None = None,
        correlation_id: str | None = None,
    ) -> AgentMessageEnvelope:
        created = datetime.now(UTC)
        resolved_repo = repo_path or os.getcwd()
        resolved_project = project or Path(resolved_repo).name
        expires_at = (created + timedelta(minutes=expires_minutes)).isoformat() if expires_minutes else None
        message_id = f"msg_{uuid.uuid4().hex[:16]}"
        return cls(
            body=body.strip(),
            message_id=message_id,
            correlation_id=correlation_id or f"corr_{uuid.uuid4().hex[:16]}",
            sender=AgentMessageSender(sender_name, sender_kind),
            session_id=session_id or os.environ.get("AGENT_USER_STATUS_SESSION_ID", ""),
            task_id=task_id,
            project=resolved_project,
            repo_path=resolved_repo,
            created_at=created.isoformat(),
            expires_at=expires_at,
            urgency=urgency,
            answer_schema=answer_schema,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "message_id": self.message_id,
            "correlation_id": self.correlation_id,
            "sender": self.sender.to_dict(),
            "session_id": self.session_id,
            "task_id": self.task_id,
            "project": self.project,
            "repo_path": self.repo_path,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "urgency": self.urgency,
            "body_hash": stable_hash(self.body),
            "body": self.body,
        }
        if self.answer_schema:
            payload["answer_schema"] = self.answer_schema.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AgentMessageEnvelope:
        answer_schema = None
        if isinstance(payload.get("answer_schema"), dict):
            answer_schema = ElicitationSchema.from_dict(payload["answer_schema"])
        return cls(
            body=str(payload.get("body") or ""),
            message_id=str(payload.get("message_id") or f"msg_{uuid.uuid4().hex[:16]}"),
            correlation_id=str(payload.get("correlation_id") or f"corr_{uuid.uuid4().hex[:16]}"),
            sender=AgentMessageSender.from_dict(payload.get("sender")),
            session_id=str(payload.get("session_id") or ""),
            task_id=str(payload.get("task_id") or ""),
            project=str(payload.get("project") or ""),
            repo_path=str(payload.get("repo_path") or ""),
            created_at=str(payload.get("created_at") or datetime.now(UTC).isoformat()),
            expires_at=str(payload["expires_at"]) if payload.get("expires_at") else None,
            urgency=str(payload.get("urgency") or "normal"),  # type: ignore[arg-type]
            answer_schema=answer_schema,
        )

    def render(self) -> str:
        """Render a compact human-readable message for iMessage/SMS."""

        metadata = [
            f"Project: {self.project or 'unknown'}",
            f"Task: {self.task_id or 'n/a'}",
            f"Session: {self.session_id or 'n/a'}",
            f"From: {self.sender.name} ({self.sender.kind})",
            f"Urgency: {self.urgency}",
            f"Reply ref: {self.correlation_id}",
        ]
        if self.expires_at:
            metadata.append(f"Expires: {self.expires_at}")
        lines = ["[Agent Request]", *metadata, "", self.body]
        if self.answer_schema:
            lines.extend(["", self.answer_schema.render()])
        return "\n".join(line for line in lines if line is not None)


def envelope_from_json(text: str) -> AgentMessageEnvelope:
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("Envelope JSON must be an object")
    return AgentMessageEnvelope.from_dict(payload)
