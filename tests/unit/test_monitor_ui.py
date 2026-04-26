from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from agent_user_status import statusd
from agent_user_status.monitor_html import MONITOR_HTML


class ElementCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.buttons: dict[str, str] = {}
        self._current_button: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        element_id = values.get("id")
        if element_id:
            self.ids.add(element_id)
        if tag == "button":
            self._current_button = element_id

    def handle_endtag(self, tag: str) -> None:
        if tag == "button":
            self._current_button = None

    def handle_data(self, data: str) -> None:
        if self._current_button:
            self.buttons[self._current_button] = data.strip()


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


def get(authority: str, path: str) -> tuple[int, str, str]:
    connection = http.client.HTTPConnection(authority, timeout=5)
    connection.request("GET", path)
    response = connection.getresponse()
    body = response.read().decode("utf-8")
    content_type = response.getheader("content-type", "")
    connection.close()
    return response.status, content_type, body


def get_json(authority: str, path: str) -> tuple[int, dict[str, object]]:
    status, _content_type, body = get(authority, path)
    return status, json.loads(body)


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


@pytest.mark.requirement("FR-AGENT_USER_STATUS-007")
def test_monitor_html_exposes_status_eye_and_privacy_controls() -> None:
    parser = ElementCollector()
    parser.feed(MONITOR_HTML)

    assert {
        "stage",
        "eyeDot",
        "panel",
        "statusText",
        "confidence",
        "eta",
        "source",
        "eyeState",
        "screenPoint",
        "updated",
        "raw",
    } <= parser.ids
    assert parser.buttons == {
        "center": "Center",
        "hide": "Hide Dot",
        "openPrivacy": "Privacy",
    }
    assert 'aria-label="Eye tracking monitor"' in MONITOR_HTML
    assert 'fetch("/dev/eye"' in MONITOR_HTML
    assert 'window.open("/privacy", "_blank")' in MONITOR_HTML


@pytest.mark.requirement("FR-AGENT_USER_STATUS-007")
def test_statusd_monitor_route_serves_browser_ui(statusd_server: str) -> None:
    status, content_type, body = get(statusd_server, "/monitor")

    assert status == 200
    assert "text/html" in content_type
    assert "<title>Agent User Status</title>" in body
    assert 'id="eyeDot"' in body
    assert 'id="openPrivacy"' in body


@pytest.mark.requirement("FR-AGENT_USER_STATUS-007")
def test_monitor_data_contract_round_trips_derived_eye_state(statusd_server: str, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(statusd, "STATE_DIR", tmp_path)
    monkeypatch.setattr(statusd, "DEV_STATE_PATH", tmp_path / "dev_monitor_state.json")
    monkeypatch.setattr(statusd, "run_agent", lambda _args, timeout=30: {"ok": True, "timeout": timeout})

    status, post_payload = post_json(
        statusd_server,
        "/dev/eye",
        {
            "screen_x": 320,
            "screen_y": 180,
            "screen_width": 1440,
            "screen_height": 900,
            "score": 0.82,
            "state": "looking_at_screen:center",
            "projection_hold_active": True,
            "head_yaw_deg": 7.5,
            "framing_quality": 0.91,
            "max_age_seconds": 30,
        },
    )
    state_status, state_payload = get_json(statusd_server, "/dev/state")

    assert status == 200
    assert post_payload["ok"] is True
    assert state_status == 200
    eye = state_payload["eye"]
    assert isinstance(eye, dict)
    assert eye["screen_x"] == 320.0
    assert eye["projection_hold_active"] is True
    assert eye["head_yaw_deg"] == 7.5
    assert eye["framing_quality"] == 0.91
    assert eye["fresh"] is True


@pytest.mark.requirement("FR-AGENT_USER_STATUS-007")
def test_monitor_privacy_button_targets_policy_route(statusd_server: str) -> None:
    status, payload = get_json(statusd_server, "/privacy")

    assert status == 200
    assert payload["ok"] is True
    policy = payload["policy"]
    assert isinstance(policy, dict)
    assert "accepted" in policy
    assert "rejected" in policy
    assert "camera frames" in policy["rejected"]


@pytest.mark.requirement("FR-AGENT_USER_STATUS-007")
def test_native_monitor_sources_define_persistent_popup_and_tray_controls() -> None:
    root = Path(__file__).resolve().parents[2]
    state_store = (root / "src/native/macos/MonitorUIStateStore.swift").read_text(encoding="utf-8")
    monitor = (root / "src/native/macos/AgentUserStatusMonitor.swift").read_text(encoding="utf-8")

    assert "monitor_ui_state.json" in state_store
    assert "loadPopupVisible" in state_store
    assert "savePopupVisible" in state_store
    assert 'NSMenuItem(title: "Toggle Popup View"' in monitor
    assert 'NSMenuItem(title: "Open Web Monitor"' in monitor
    assert 'NSImage(systemSymbolName: "eye"' in monitor
    assert "uiStateStore.loadPopupVisible" in monitor
