#!/usr/bin/env bash
set -euo pipefail

wait_for_health() {
  local attempts=15
  local i
  for ((i = 1; i <= attempts; i++)); do
    if curl -fsS --max-time 3 http://127.0.0.1:8765/health >/dev/null; then
      return 0
    fi
    sleep 1
  done
  curl -fsS http://127.0.0.1:8765/health >/dev/null
}

wait_for_health

post_status_code() {
  local file="$1"
  local expected="$2"
  shift 2
  status_code="$(curl -s -o "${file}" -w '%{http_code}' "$@")"
  test "${status_code}" = "${expected}"
}

status_code="$(curl -s -o /tmp/agent-user-status-smoke-eye-get.json -w '%{http_code}' 'http://127.0.0.1:8765/dev/eye?screen_zone=center&score=0.5')"
test "${status_code}" = "405"

status_code="$(curl -s -o /tmp/agent-user-status-smoke-bad-score.json -w '%{http_code}' \
  -X POST http://127.0.0.1:8765/signal \
  -H 'content-type: application/json' \
  -d '{"name":"eye_tracking","score":2,"state":"looking"}')"
test "${status_code}" = "400"

status_code="$(curl -s -o /tmp/agent-user-status-smoke-raw.json -w '%{http_code}' \
  -X POST http://127.0.0.1:8765/dev/eye \
  -H 'content-type: application/json' \
  -d '{"score":0.5,"state":"raw_camera_frame"}')"
test "${status_code}" = "422"

curl -fsS -X POST http://127.0.0.1:8765/dev/eye \
  -H 'content-type: application/json' \
  -d '{"screen_x":720,"screen_y":450,"screen_width":1440,"screen_height":900,"score":0.9,"confidence":0.92,"stability_score":0.91,"targeting_reliable":true,"filter_mode":"tracking","state":"looking_at_screen:smoke","max_age_seconds":5}' \
  | grep -q 'looking_at_screen:smoke'

status_code="$(curl -s -o /tmp/agent-user-status-smoke-recovering-eye.json -w '%{http_code}' \
  -X POST http://127.0.0.1:8765/dev/eye \
  -H 'content-type: application/json' \
  -d '{"screen_x":700,"screen_y":420,"observed_screen_x":910,"observed_screen_y":610,"screen_width":1440,"screen_height":900,"score":0.41,"confidence":0.44,"stability_score":0.38,"targeting_reliable":false,"filter_mode":"projection_hold_recovering","projection_hold_active":true,"projection_hold_reason":"recovering","projection_hold_hint":"recalibrate soon","projection_hold_samples":2,"projection_hold_threshold_px":124,"projection_release_threshold_px":68,"projection_hold_budget_frames":2,"projection_recovery_score":0.5,"projection_recommended_action":"recalibrate","calibration_mean_error_px":18.2,"calibration_p95_error_px":39.8,"calibration_sample_count":42,"calibration_quality_score":0.84,"calibration_recommended_action":"monitor","state":"looking_at_screen:recovering","max_age_seconds":5}')"
test "${status_code}" = "200"
grep -q '"projection_hold_reason": "recovering"' /tmp/agent-user-status-smoke-recovering-eye.json
grep -q '"projection_hold_budget_frames": 2' /tmp/agent-user-status-smoke-recovering-eye.json

curl -fsS -X POST http://127.0.0.1:8765/dev/eye \
  -H 'content-type: application/json' \
  -d '{"screen_x":720,"screen_y":450,"screen_width":1440,"screen_height":900,"score":0.9,"confidence":0.92,"stability_score":0.91,"targeting_reliable":true,"filter_mode":"tracking","state":"looking_at_screen:smoke_reliable","max_age_seconds":60}' \
  >/dev/null

post_status_code /tmp/agent-user-status-smoke-cursor-click.json "200" \
  -X POST http://127.0.0.1:8765/correction/event \
  -H 'content-type: application/json' \
  -d '{"kind":"cursor_click","score":0.9,"state":"smoke_cursor_click","harmony_hint":true,"max_age_seconds":30,"screen_x":780,"screen_y":430,"screen_width":1440,"screen_height":900}'
grep -q '"kind": "cursor_click"' /tmp/agent-user-status-smoke-cursor-click.json
grep -q '"state": "smoke_cursor_click"' /tmp/agent-user-status-smoke-cursor-click.json
grep -q '"gaze_targeting_reliable": true' /tmp/agent-user-status-smoke-cursor-click.json
grep -q '"learnable": true' /tmp/agent-user-status-smoke-cursor-click.json

post_status_code /tmp/agent-user-status-smoke-cursor-target.json "200" \
  -X POST http://127.0.0.1:8765/correction/event \
  -H 'content-type: application/json' \
  -d '{"kind":"cursor_target","score":0.84,"state":"smoke_cursor_target","harmony_hint":true,"max_age_seconds":30,"screen_x":520,"screen_y":240,"screen_width":1440,"screen_height":900}'
grep -q '"kind": "cursor_target"' /tmp/agent-user-status-smoke-cursor-target.json
grep -q '"state": "smoke_cursor_target"' /tmp/agent-user-status-smoke-cursor-target.json
grep -q '"gaze_targeting_reliable": true' /tmp/agent-user-status-smoke-cursor-target.json

post_status_code /tmp/agent-user-status-smoke-keyboard.json "200" \
  -X POST http://127.0.0.1:8765/correction/event \
  -H 'content-type: application/json' \
  -d '{"kind":"keyboard_activity","score":0.66,"state":"smoke_keyboard_activity","harmony_hint":false,"max_age_seconds":30,"window_owner":"smoke_app","window_role":"foreground","input_modality":"keyboard"}'
grep -q '"kind": "keyboard_activity"' /tmp/agent-user-status-smoke-keyboard.json
grep -q '"state": "smoke_keyboard_activity"' /tmp/agent-user-status-smoke-keyboard.json
grep -q '"window_owner": "smoke_app"' /tmp/agent-user-status-smoke-keyboard.json
grep -q '"window_role": "foreground"' /tmp/agent-user-status-smoke-keyboard.json
grep -q '"input_modality": "keyboard"' /tmp/agent-user-status-smoke-keyboard.json
if grep -q '"key"' /tmp/agent-user-status-smoke-keyboard.json; then
  false
fi
if grep -q '"typed_text"' /tmp/agent-user-status-smoke-keyboard.json; then
  false
fi
if grep -q '"text"' /tmp/agent-user-status-smoke-keyboard.json; then
  false
fi

post_status_code /tmp/agent-user-status-smoke-audio.json "200" \
  -X POST http://127.0.0.1:8765/correction/event \
  -H 'content-type: application/json' \
  -d '{"kind":"audio_activity","score":0.62,"state":"smoke_audio_activity","harmony_hint":false,"max_age_seconds":30}'
grep -q '"kind": "audio_activity"' /tmp/agent-user-status-smoke-audio.json
grep -q '"state": "smoke_audio_activity"' /tmp/agent-user-status-smoke-audio.json
if grep -q '"audio"' /tmp/agent-user-status-smoke-audio.json; then
  false
fi
if grep -q '"transcript"' /tmp/agent-user-status-smoke-audio.json; then
  false
fi

status_code="$(curl -s -o /tmp/agent-user-status-smoke-correction-events.json -w '%{http_code}' 'http://127.0.0.1:8765/correction/events?limit=20')"
test "${status_code}" = "200"
grep -q '"smoke_cursor_click"' /tmp/agent-user-status-smoke-correction-events.json
grep -q '"smoke_cursor_target"' /tmp/agent-user-status-smoke-correction-events.json
grep -q '"smoke_keyboard_activity"' /tmp/agent-user-status-smoke-correction-events.json
grep -q '"smoke_audio_activity"' /tmp/agent-user-status-smoke-correction-events.json

curl -fsS -X POST http://127.0.0.1:8765/dev/eye \
  -H 'content-type: application/json' \
  -d '{"screen_x":20,"screen_y":20,"screen_width":1440,"screen_height":900,"score":0.12,"confidence":0.08,"stability_score":0.1,"targeting_reliable":false,"filter_mode":"projection_hold","state":"looking_at_screen:unstable","max_age_seconds":5}' \
  >/dev/null

post_status_code /tmp/agent-user-status-smoke-unstable-correction.json "200" \
  -X POST http://127.0.0.1:8765/correction/event \
  -H 'content-type: application/json' \
  -d '{"kind":"cursor_click","score":0.18,"state":"smoke_cursor_click_unstable","harmony_hint":true,"max_age_seconds":30,"screen_x":120,"screen_y":120,"screen_width":1440,"screen_height":900}'
grep -q '"gaze_targeting_reliable": false' /tmp/agent-user-status-smoke-unstable-correction.json
grep -q '"learnable": false' /tmp/agent-user-status-smoke-unstable-correction.json

curl -fsS -X POST http://127.0.0.1:8765/dev/eye \
  -H 'content-type: application/json' \
  -d '{"screen_x":700,"screen_y":420,"observed_screen_x":910,"observed_screen_y":610,"screen_width":1440,"screen_height":900,"score":0.41,"confidence":0.44,"stability_score":0.38,"targeting_reliable":false,"filter_mode":"projection_hold_recovering","projection_hold_active":true,"projection_hold_reason":"recovering","projection_hold_samples":2,"projection_hold_threshold_px":124,"projection_release_threshold_px":68,"projection_recovery_score":0.5,"calibration_mean_error_px":18.2,"calibration_p95_error_px":39.8,"calibration_sample_count":42,"calibration_quality_score":0.84,"state":"looking_at_screen:recovering","max_age_seconds":5}' \
  >/dev/null

post_status_code /tmp/agent-user-status-smoke-recovering-correction.json "200" \
  -X POST http://127.0.0.1:8765/correction/event \
  -H 'content-type: application/json' \
  -d '{"kind":"cursor_click","score":0.22,"state":"smoke_cursor_click_recovering","harmony_hint":true,"max_age_seconds":30,"screen_x":160,"screen_y":160,"screen_width":1440,"screen_height":900}'
grep -q '"gaze_filter_mode": "projection_hold_recovering"' /tmp/agent-user-status-smoke-recovering-correction.json
grep -q '"gaze_targeting_reliable": false' /tmp/agent-user-status-smoke-recovering-correction.json

status_code="$(curl -s -o /tmp/agent-user-status-smoke-correction-reliable.json -w '%{http_code}' 'http://127.0.0.1:8765/correction/events?limit=50&reliable_only=true')"
test "${status_code}" = "200"
grep -q '"smoke_cursor_click"' /tmp/agent-user-status-smoke-correction-reliable.json
if grep -q '"smoke_cursor_click_unstable"' /tmp/agent-user-status-smoke-correction-reliable.json; then
  false
fi

curl -fsS -X POST http://127.0.0.1:8765/dev/eye \
  -H 'content-type: application/json' \
  -d '{"screen_x":720,"screen_y":450,"screen_width":1440,"screen_height":900,"score":0.9,"confidence":0.92,"stability_score":0.91,"targeting_reliable":true,"filter_mode":"tracking","state":"looking_at_screen:smoke_reliable","max_age_seconds":60}' \
  >/dev/null

if [ "${AGENT_USER_STATUS_SMOKE_SKIP_IMESSAGE:-0}" = "1" ]; then
  echo "smoke passed"
  exit 0
fi

~/.local/bin/agent-imessage action output agent-complete \
  --state smoke_agent_complete \
  --max-age-seconds 60 \
  --note smoke \
  | grep -q '"kind": "agent_complete"'
~/.local/bin/agent-imessage action output agent-complete \
  --state smoke_agent_complete_reliable \
  --max-age-seconds 60 \
  --note smoke \
  | grep -q '"gaze_targeting_reliable": true'

curl -fsS -X POST http://127.0.0.1:8765/dev/eye \
  -H 'content-type: application/json' \
  -d '{"screen_x":20,"screen_y":20,"screen_width":1440,"screen_height":900,"score":0.12,"confidence":0.08,"stability_score":0.1,"targeting_reliable":false,"filter_mode":"projection_hold","state":"looking_at_screen:smoke_unreliable","max_age_seconds":60}' \
  >/dev/null

~/.local/bin/agent-imessage action output agent-complete \
  --state smoke_agent_complete_unreliable \
  --max-age-seconds 60 \
  --note smoke \
  | grep -q '"gaze_targeting_reliable": false'

~/.local/bin/agent-imessage hook-decision --text "waiting for your response" \
  | tee /tmp/agent-user-status-smoke-hook-decision.json \
  | grep -q '"kind": "agent_waiting_user"'
grep -q '"attribution":' /tmp/agent-user-status-smoke-hook-decision.json

~/.local/bin/agent-imessage log-response 7 \
  --source smoke \
  --note smoke \
  | tee /tmp/agent-user-status-smoke-log-response.json \
  | grep -q '"learning_update":'
grep -q '"learned_keys":' /tmp/agent-user-status-smoke-log-response.json

echo "smoke passed"
