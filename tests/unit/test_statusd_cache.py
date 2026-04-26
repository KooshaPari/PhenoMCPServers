from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator
from http.server import ThreadingHTTPServer

import pytest

from agent_user_status import statusd, statusd_command_cache
from agent_user_status.ttl_cache import TTLCache


@pytest.fixture
def statusd_server() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), statusd.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = str(server.server_address[0])
        port = int(server.server_address[1])
        yield f"{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def get_json(authority: str, path: str) -> tuple[int, dict[str, object]]:
    connection = http.client.HTTPConnection(authority, timeout=5)
    connection.request("GET", path)
    response = connection.getresponse()
    body = json.loads(response.read().decode("utf-8"))
    connection.close()
    return response.status, body


def post_json(authority: str, path: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    connection = http.client.HTTPConnection(authority, timeout=5)
    connection.request(
        "POST",
        path,
        body=json.dumps(payload),
        headers={"content-type": "application/json"},
    )
    response = connection.getresponse()
    body = json.loads(response.read().decode("utf-8"))
    connection.close()
    return response.status, body


@pytest.mark.requirement("FR-AGENT_USER_STATUS-004")
def test_status_endpoint_cache_reuses_redacted_status_until_ttl(monkeypatch, statusd_server: str) -> None:
    now = 10.0
    calls: list[list[str]] = []

    def fake_redacted(args: list[str], timeout: int = 30) -> dict[str, object]:
        calls.append(args)
        return {
            "ok": True,
            "returncode": 0,
            "data": {"status": "near", "call_count": len(calls)},
            "stderr": "",
            "timeout": timeout,
        }

    monkeypatch.setattr(statusd, "redacted_agent", fake_redacted)
    monkeypatch.setattr(statusd_command_cache, "COMMAND_CACHE", TTLCache(ttl_seconds=5.0, clock=lambda: now))

    first_status, first = get_json(statusd_server, "/status")
    second_status, second = get_json(statusd_server, "/status")

    assert first_status == 200
    assert second_status == 200
    assert first["data"] == {"status": "near", "call_count": 1}
    assert second["data"] == {"status": "near", "call_count": 1}
    assert calls == [["status", "--json"]]

    now = 16.0
    refreshed_status, refreshed = get_json(statusd_server, "/status")

    assert refreshed_status == 200
    assert refreshed["data"] == {"status": "near", "call_count": 2}
    assert calls == [["status", "--json"], ["status", "--json"]]


@pytest.mark.requirement("FR-AGENT_USER_STATUS-004")
def test_signal_post_invalidates_cached_command_results(monkeypatch, statusd_server: str) -> None:
    calls: list[list[str]] = []

    def fake_run_agent(args: list[str], timeout: int = 30) -> dict[str, object]:
        calls.append(args)
        if args == ["signals"]:
            return {"ok": True, "returncode": 0, "data": {"call_count": len(calls)}, "stderr": ""}
        return {"ok": True, "returncode": 0, "data": {}, "stderr": ""}

    monkeypatch.setattr(statusd, "run_agent", fake_run_agent)
    monkeypatch.setattr(statusd_command_cache, "COMMAND_CACHE", TTLCache(ttl_seconds=60.0))

    assert get_json(statusd_server, "/signals")[1]["data"] == {"call_count": 1}
    assert get_json(statusd_server, "/signals")[1]["data"] == {"call_count": 1}

    post_status, post_payload = post_json(
        statusd_server,
        "/signal",
        {"name": "process_tracker", "score": 0.8, "state": "coding", "max_age_seconds": 30},
    )
    refreshed = get_json(statusd_server, "/signals")[1]

    assert post_status == 200
    assert post_payload["ok"] is True
    assert refreshed["data"] == {"call_count": 3}
