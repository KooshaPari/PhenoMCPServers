from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from agent_user_status.session_registry import (
    append_child_session_event,
    append_session_event,
    append_session_heartbeat,
    recent_session_events,
    recent_session_records,
    session_event_ring,
    session_snapshot,
    session_summaries,
    session_timeline,
)


@pytest.mark.requirement("FR-age-004")
def test_heartbeat_appends_privacy_safe_jsonl(tmp_path) -> None:
    store_path = tmp_path / "sessions.jsonl"

    record = append_session_heartbeat(
        session_id="codex-123",
        agent_id="codex",
        status="working",
        note="editing scoped files",
        metadata={"repo": "agent-user-status", "branch": "session-registry"},
        store_path=store_path,
    )

    persisted = json.loads(store_path.read_text(encoding="utf-8").strip())
    assert persisted == record
    assert record["kind"] == "heartbeat"
    assert record["session_id"] == "codex-123"
    assert record["agent_id"] == "codex"
    assert record["metadata"] == {"branch": "session-registry", "repo": "agent-user-status"}
    assert "transcript" not in json.dumps(record)
    assert "screenshot" not in json.dumps(record)


@pytest.mark.requirement("FR-age-003")
def test_event_rejects_raw_transcript_or_screenshot_payloads(tmp_path) -> None:
    store_path = tmp_path / "sessions.jsonl"

    with pytest.raises(ValueError, match="raw session payload"):
        append_session_event(
            session_id="codex-123",
            event_type="model_output",
            metadata={"raw_transcript": "full conversation text"},
            store_path=store_path,
        )

    with pytest.raises(ValueError, match="raw session payload"):
        append_session_event(
            session_id="codex-123",
            event_type="artifact",
            metadata={"artifact": "desktop screenshot captured"},
            store_path=store_path,
        )

    assert not store_path.exists()


@pytest.mark.requirement("FR-age-003")
def test_recent_records_skip_malformed_lines_and_filter(tmp_path) -> None:
    store_path = tmp_path / "sessions.jsonl"
    append_session_heartbeat("a", status="working", store_path=store_path)
    with store_path.open("a", encoding="utf-8") as handle:
        handle.write("{not-json\n")
    append_session_event("b", "blocked", state="waiting_user", store_path=store_path)
    append_session_event("a", "checkpoint", state="tests_running", store_path=store_path)

    records = recent_session_records(store_path=store_path, session_id="a")

    assert [record["session_id"] for record in records] == ["a", "a"]
    assert [record["kind"] for record in records] == ["heartbeat", "event"]


@pytest.mark.requirement("FR-age-006")
def test_session_summaries_use_latest_heartbeat_and_event(tmp_path) -> None:
    store_path = tmp_path / "sessions.jsonl"
    stale_time = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()

    append_session_heartbeat(
        "codex-old",
        status="working",
        ttl_seconds=30,
        observed_at=stale_time,
        store_path=store_path,
    )
    append_session_heartbeat("codex-new", status="working", ttl_seconds=300, store_path=store_path)
    append_session_event("codex-new", "validation", state="pytest_passed", store_path=store_path)

    summaries = session_summaries(store_path=store_path)

    assert [summary["session_id"] for summary in summaries] == ["codex-new", "codex-old"]
    assert summaries[0]["fresh"] is True
    assert summaries[0]["last_event"]["event_type"] == "validation"
    assert summaries[1]["fresh"] is False


@pytest.mark.requirement("FR-age-006")
def test_session_timeline_returns_oldest_to_newest_for_one_session(tmp_path) -> None:
    store_path = tmp_path / "sessions.jsonl"
    append_session_heartbeat("codex-123", status="starting", store_path=store_path)
    append_session_event("other", "noise", store_path=store_path)
    append_session_event("codex-123", "implementation", state="in_progress", store_path=store_path)

    timeline = session_timeline("codex-123", store_path=store_path)

    assert [record["kind"] for record in timeline] == ["heartbeat", "event"]
    assert timeline[-1]["event_type"] == "implementation"


@pytest.mark.requirement("FR-age-006")
def test_session_event_ring_returns_recent_records(tmp_path) -> None:
    store_path = tmp_path / "sessions.jsonl"
    heartbeat = append_session_heartbeat("codex-ring", status="working", store_path=store_path)
    event = append_session_event("codex-ring", "checkpoint", state="tests_running", store_path=store_path)

    assert session_event_ring(limit=2)[-2:] == [heartbeat, event]
    assert recent_session_events(store_path=store_path, limit=2)[-2:] == [heartbeat, event]
    assert session_event_ring(limit=2, kind="event")[-1]["event_type"] == "checkpoint"
    assert event["schema_version"] == 1


@pytest.mark.requirement("FR-age-006")
def test_session_snapshot_includes_summaries_events_and_timeline(tmp_path) -> None:
    store_path = tmp_path / "sessions.jsonl"
    append_session_heartbeat("parent", status="working", store_path=store_path)
    append_session_event("parent", "checkpoint", state="implementation", store_path=store_path)
    append_session_event("other", "noise", store_path=store_path)

    snapshot = session_snapshot(session_id="parent", store_path=store_path, event_limit=10)

    assert [summary["session_id"] for summary in snapshot["sessions"]] == ["parent"]
    assert [event["session_id"] for event in snapshot["events"]] == ["parent", "parent"]
    assert [record["kind"] for record in snapshot["timeline"]] == ["heartbeat", "event"]
    assert snapshot["generated_at"]


@pytest.mark.requirement("FR-age-006")
def test_child_session_events_are_structured_and_privacy_safe(tmp_path) -> None:
    store_path = tmp_path / "sessions.jsonl"

    record = append_child_session_event(
        "parent",
        "child-a",
        "spawn",
        agent_id="codex-manager",
        child_agent_id="worker-a",
        metadata={"repo": "agent-user-status"},
        store_path=store_path,
    )

    assert record["session_id"] == "parent"
    assert record["event_type"] == "child_spawn"
    assert record["metadata"] == {
        "child_agent_id": "worker-a",
        "child_session_id": "child-a",
        "repo": "agent-user-status",
    }
