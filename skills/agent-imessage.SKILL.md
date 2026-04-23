---
name: agent-imessage
description: Use when an agent needs to contact Koosha by iMessage/SMS, check whether he is likely to respond soon, wait for an async reply, publish eye/process/presence signals, or repair/register the local Messages MCP bridge for Codex or Claude Code.
---

# Agent iMessage

Use this skill when you need user contact or response-likelihood state.

## Tool Order

1. Prefer MCP tools from `agent-imessage` if available.
2. Fall back to the local CLI:
   - `agent-imessage status --json`
   - `agent-imessage hook-decision --text "<last assistant message>"`
   - `agent-imessage notify "message"`
   - `agent-imessage wait --timeout 900 --json`
   - `agent-imessage action input mouse_click --max-age-seconds 60`
   - `agent-imessage action output video_playing --max-age-seconds 120`
   - `agent-imessage signal eye_tracking --score 0.9 --state looking --max-age-seconds 20`
3. Use `agent-imessage-mcp doctor` when the MCP bridge appears unavailable.

## Waiting Policy

Before stopping because you are waiting on Koosha, run:

```bash
agent-imessage hook-decision --text "<last assistant message>"
```

- `reprompt_wait`: say you are waiting only if the answer is genuinely needed.
- `reprompt_default_or_defer`: make a reasonable default decision, skip optional work, or defer the question into the final answer.
- `allow_stop`: stop normally.

Do not stall just because a reply might eventually arrive.

## Manual Presence

Use these when Koosha explicitly sets availability:

```bash
agent-imessage set-status near --eta-minutes 5 --minutes 30
agent-imessage set-status focus --eta-minutes 45 --minutes 90
agent-imessage clear-status
```

## External Signals

Eye tracking, process tracking, meeting status, or other local observers should publish short-lived scores:

```bash
agent-imessage action input mouse_click --max-age-seconds 60
agent-imessage action input key_press --max-age-seconds 60
agent-imessage action output video_playing --max-age-seconds 120
agent-imessage action output meeting_active --max-age-seconds 120
agent-imessage signal eye_tracking --score 0.9 --state looking --max-age-seconds 20
agent-imessage signal process_tracker --score 0.8 --state coding --max-age-seconds 120
agent-imessage clear-signal eye_tracking
agent-imessage signals
agent-imessage actions
```

Scores are `0.0` away to `1.0` active. Always set a short max age for sensor data.

The CLI also reads local process context and macOS power assertions directly. It uses open/active
processes, HID idle time, frontmost app, and media assertions as built-in signals.

For webcam eye tracking, do not start camera capture from an agent. Use an explicit, opt-in local
tracker that publishes only a derived score/state, for example `eye_tracking=looking`, and avoid
storing images or video frames.

## Persistent Backend

Use the local backend when a long-lived observer needs to publish status:

```bash
agent-user-statusd health
curl -s http://127.0.0.1:8765/status
curl -s http://127.0.0.1:8765/privacy
curl -s -X POST http://127.0.0.1:8765/signal \
  -H 'content-type: application/json' \
  -d '{"name":"eye_tracking","score":0.85,"state":"looking_at_screen:center","max_age_seconds":5}'
```

The backend treats eye tracking and sensor data as highly confidential. It accepts derived states
only: score, confidence, screen zone, ETA, and short notes. It rejects raw frames, screenshots,
face/eye images, landmarks, biometric embeddings, raw gaze streams, and medical inference labels.

## Tray Monitor

Use the native status monitor when you need a persistent menu-bar view, top-right panel, and
floating OS-level eye dot:

```bash
agent-user-status-native-monitor
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.phenotype.agent-user-status-tray.plist
launchctl kickstart -k gui/$UID/com.phenotype.agent-user-status-tray
launchctl bootout gui/$UID/com.phenotype.agent-user-status-tray
```

Dev realtime cursor-as-eye stand-in:

```bash
agent-user-status-cursor-tracker --hz 20
launchctl kickstart -k gui/$UID/com.phenotype.agent-user-status-cursor-tracker
launchctl bootout gui/$UID/com.phenotype.agent-user-status-cursor-tracker
```

The cursor tracker is only for UI/process-detection validation. Real eye trackers should POST
derived coordinates to `POST /dev/eye`.

## MCP Management

Repair or install the CLI-backed MCP server:

```bash
agent-imessage-mcp install --client both
agent-imessage-mcp install --client both --with-messages
agent-imessage-mcp status
agent-imessage-mcp doctor
```

`agent-imessage` is the CLI-backed status/control MCP. `messages` is the direct macOS Messages MCP from `mac_messages_mcp`.
