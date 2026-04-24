from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator
from http.server import ThreadingHTTPServer

import pytest

from agent_user_status import statusd


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


def post_json(authority: str, path: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    connection = http.client.HTTPConnection(authority, timeout=5)
    body = json.dumps(payload)
    connection.request("POST", path, body=body, headers={"content-type": "application/json"})
    response = connection.getresponse()
    data = json.loads(response.read().decode("utf-8"))
    connection.close()
    return response.status, data


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/dev/eye", {"screen_zone": "center", "score": 0.7, "raw_frame": "base64"}),
        ("/dev/eye", {"screen_zone": "center", "score": 0.7, "landmarks": [1, 2, 3]}),
        ("/signal", {"name": "eye_tracking", "score": 0.7, "state": "derived", "audio": "raw"}),
        ("/signal", {"name": "eye_tracking", "score": 0.7, "state": "derived", "screenshot": "png"}),
        ("/session/heartbeat", {"session_id": "codex", "status": "working", "transcript": "private"}),
        ("/session/heartbeat", {"session_id": "codex", "status": "working", "biometric": "template"}),
        ("/correction/event", {"kind": "audio_activity", "score": 0.6, "audio": "waveform"}),
        (
            "/correction/event",
            {
                "kind": "cursor_click",
                "score": 0.6,
                "screen_x": 1,
                "screen_y": 2,
                "screen_width": 10,
                "screen_height": 10,
                "landmark": "eye",
            },
        ),
    ],
)
def test_privacy_sensitive_routes_reject_raw_payloads(
    statusd_server: str,
    path: str,
    payload: dict[str, object],
) -> None:
    status, data = post_json(statusd_server, path, payload)

    assert status == 422
    assert data["ok"] is False
    assert "raw sensor/biometric payload rejected" in str(data["error"])
    assert "policy" in data


def test_state_export_route_returns_only_derived_json_files(statusd_server: str, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(statusd, "STATE_DIR", tmp_path)
    (tmp_path / "signals.json").write_text('{"signals":[]}', encoding="utf-8")
    (tmp_path / "events.jsonl").write_text('{"kind":"derived"}\n', encoding="utf-8")
    (tmp_path / "face_landmarker.task").write_text("native model", encoding="utf-8")

    connection = http.client.HTTPConnection(statusd_server, timeout=5)
    connection.request("GET", "/state/export")
    response = connection.getresponse()
    data = json.loads(response.read().decode("utf-8"))
    connection.close()

    assert response.status == 200
    assert sorted(data["export"]["files"]) == ["events.jsonl", "signals.json"]


def test_state_delete_route_deletes_selected_derived_file(statusd_server: str, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(statusd, "STATE_DIR", tmp_path)
    keep = tmp_path / "signals.json"
    delete = tmp_path / "response_events.jsonl"
    keep.write_text("{}", encoding="utf-8")
    delete.write_text('{"ok":true}\n', encoding="utf-8")

    status, data = post_json(statusd_server, "/state/delete", {"names": ["response_events.jsonl"]})

    assert status == 200
    assert data["deleted"] == ["response_events.jsonl"]
    assert keep.exists()
    assert not delete.exists()
