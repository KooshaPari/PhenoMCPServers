#!/usr/bin/env python3
"""HTTP helpers for privacy-safe agent session endpoints."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs

from agent_user_status.eye_state_payload import bounded_int
from agent_user_status.session_registry import (
    append_session_event,
    append_session_heartbeat,
    recent_session_events,
    session_snapshot,
    session_summaries,
    session_timeline,
)


def session_get_payload(path: str, query: dict[str, list[str]]) -> dict[str, Any] | None:
    if path == "/sessions":
        limit = bounded_int(query.get("limit", [200])[0], 200, 1, 2000, "limit")
        session_id = query.get("session_id", [None])[0]
        if session_id:
            return {"ok": True, "records": session_timeline(session_id, limit=limit)}
        return {"ok": True, "sessions": session_summaries(limit=limit)}

    if path == "/session/events":
        limit = bounded_int(query.get("limit", [80])[0], 80, 1, 500, "limit")
        kind = query.get("kind", [None])[0]
        session_id = query.get("session_id", [None])[0]
        return {"ok": True, "events": recent_session_events(limit=limit, kind=kind, session_id=session_id)}

    if path == "/session/snapshot":
        session_limit = bounded_int(query.get("session_limit", [200])[0], 200, 1, 2000, "session_limit")
        event_limit = bounded_int(query.get("event_limit", [80])[0], 80, 1, 500, "event_limit")
        kind = query.get("kind", [None])[0]
        session_id = query.get("session_id", [None])[0]
        return {
            "ok": True,
            "snapshot": session_snapshot(
                session_id=session_id,
                session_limit=session_limit,
                event_limit=event_limit,
                kind=kind,
            ),
        }

    return None


def session_post_payload(path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if path == "/session/heartbeat":
        record = append_session_heartbeat(
            str(payload["session_id"]),
            agent_id=str(payload.get("agent_id") or payload.get("agent_kind") or "agent"),
            status=str(payload.get("status") or "active"),
            state=str(payload["state"]) if payload.get("state") is not None else None,
            note=str(payload["note"]) if payload.get("note") is not None else None,
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None,
            ttl_seconds=bounded_int(payload.get("ttl_seconds"), 300, 1, 86400, "ttl_seconds"),
        )
        return {"ok": True, "record": record}

    if path in {"/event", "/session/event"}:
        record = append_session_event(
            str(payload["session_id"]),
            str(payload["event_type"]),
            agent_id=str(payload.get("agent_id") or payload.get("agent_kind") or "agent"),
            state=str(payload["state"]) if payload.get("state") is not None else None,
            note=str(payload["note"]) if payload.get("note") is not None else None,
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None,
        )
        return {"ok": True, "record": record}

    return None


def parsed_query(query: str) -> dict[str, list[str]]:
    return parse_qs(query)
