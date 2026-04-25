# Real Webcam Eye Tracker

Goal: replace the cursor-only dev stand-in with an opt-in MacBook webcam gaze
collector that publishes only derived screen coordinates to the existing local
status daemon.

Implementation:
- `agent-user-status-webcam-eye-tracker check` reports optional dependency and
  calibration state.
- `agent-user-status-webcam-eye-tracker calibrate` runs a 9-point calibration
  and stores regression weights in `~/.local/share/agent-imessage/state/eye_calibration.json`.
- `agent-user-status-webcam-eye-tracker run` reads webcam frames in memory,
  extracts MediaPipe iris/face features, smooths calibrated coordinates, and
  posts only `screen_x`, `screen_y`, dimensions, confidence, and short-lived
  freshness to `POST /dev/eye`.
- The runtime now uses a projection-hold gate with separate hold and release
  thresholds derived from the saved calibration. Single bad frames no longer
  force a hold immediately, and recovery requires several stable samples.
- `agent-user-status-webcam-eye-tracker evaluate` opens the same 9-point test
  canvas without rewriting the calibration file and reports mean/P95 error,
  projection-hold risk, and calibration quality fields.
- The live tracker now uses an adaptive One Euro style screen-coordinate filter
  instead of a fixed low-pass filter. Small jitter is damped while large gaze
  moves get a higher cutoff, reducing jaggedness without adding a constant delay.

Research summary:
- MediaPipe Face Landmarker supports video and live-stream modes, and Google
  documents using OpenCV `VideoCapture` for webcam input.
- MediaPipe Iris provides single-RGB-camera iris landmarks but explicitly does
  not directly infer gaze location; screen gaze needs user calibration.
- WebGazer validates the browser-side regression pattern, including 9-point
  calibration, but its browser/licensing/runtime shape is not the right core
  for this native status daemon.
- EyeTheia (submitted January 2026) is the closest current research direction:
  MediaPipe landmark extraction plus a lightweight CNN and optional user
  fine-tuning. That is the long-term upgrade path after the local calibrated
  regression collector is stable.

Privacy:
- Camera frames are not written to disk or sent to statusd.
- Calibration stores only regression weights and aggregate calibration error.
- Calibration now also exposes derived quality metadata and projection-hold
  thresholds so the runtime can recover more gracefully from outliers.
- statusd still rejects raw image, landmark, biometric, and medical payloads.
- On macOS, Camera permission is tied to the exact interpreter path used by the
  LaunchAgent, usually `~/.local/share/agent-imessage/eye-tracker-venv/bin/python`.
  `launchd` does not display the permission prompt for this service, so the grant
  has to be applied to that binary directly.

## Correction-Grade Inputs (Privacy-Preserving)

To reduce gaze drift without adding sensitive collection, status inference uses only
derived, low-risk correction inputs:

The correction event contract is now explicit in the backend (`POST /correction/event`).

- Cursor correction:
  - `kind: cursor_click` and `kind: cursor_target` are the only cursor events.
  - Payload includes bounded coordinates: `screen_x`, `screen_y`, `screen_width`,
    `screen_height`.
  - Coordinate events are treated as valid corrections only when `harmony_hint`
    is true (local gaze-to-behavior alignment is plausible).
- Keyboard correction:
  - `kind: keyboard_activity` records only timing/state metadata and optional
    context (no raw keys, no text payloads).
  - Use `score`, `max_age_seconds`, `state`, `window_owner`, `window_role`,
    `input_modality`, and optional `harmony_hint`.
- Audio correction:
  - `kind: audio_activity` records only coarse attention-state cues.
  - Use only envelope-style fields such as `score`, `max_age_seconds`, `state`,
    and optional `harmony_hint`; never audio content or transcripts.

Current minimum payloads:

- cursor_click:
  `{"kind":"cursor_click","score":0.88,"max_age_seconds":30,"harmony_hint":true,"screen_x":780,"screen_y":430,"screen_width":1440,"screen_height":900}`
- cursor_target:
  `{"kind":"cursor_target","score":0.82,"max_age_seconds":30,"harmony_hint":true,"screen_x":520,"screen_y":240,"screen_width":1440,"screen_height":900}`
- keyboard_activity:
  `{"kind":"keyboard_activity","score":0.65,"max_age_seconds":30,"state":"keyboard_activity","window_owner":"Chrome","window_role":"browser","harmony_hint":false}`
- audio_activity:
  `{"kind":"audio_activity","score":0.58,"max_age_seconds":30,"state":"speech_detected","harmony_hint":false}`

The tracker still never persists or transmits raw camera frames, raw audio, raw text,
or biometric streams. Correction events are short-lived context hints, stored as
derived state in `correction_events.jsonl`, and returned via `GET /correction/events`.

## Source-Side Gating

The source-side learning lane now carries only derived gaze reliability metadata:

- `statusd` persists `gaze_targeting_reliable`, `gaze_stability_score`, `gaze_confidence`,
  `gaze_state`, `gaze_filter_mode`, calibration quality, and freshness metadata
  on action/correction events.
- ETA learning only updates from action contexts where the gaze sample is still fresh
  and the tracker marked it reliable.
- Process/app-specific action keys are only learned when the gaze sample is reliable;
  unstable samples keep the base action key but drop terminal/app specialization.
- Reliable-only correction feeds are available through `GET /correction/events?reliable_only=true`.
- The Swift monitor now derives a coarse workspace role from existing `/status`
  signals so terminal-agent contexts can be labeled without adding raw capture.

This keeps the learning pipeline aligned with the privacy boundary while avoiding
sample poisoning from projection holds, `no_face` frames, or other unstable gaze periods.

## ETA Learning Anchors

Stop-hook and terminal completion events are now regular action events:

- `output:agent_complete` records a finished agent turn.
- `output:agent_waiting_user` records a stop hook that appears to be waiting for
  Koosha.
- Each action stores privacy-safe environment context such as frontmost app,
  whether a terminal is active, and coarse agent/coding process names.

When `agent-imessage log-response <minutes>` is recorded, response learning now
updates base action keys plus state/app/terminal-specific keys. Status ETA can
then use those learned action medians when Messages access is unavailable or when
the latest message is stale.

## Packaging Boundary

The installable CLI surface is declared in `pyproject.toml` via console scripts
for `agent-user-status`, `agent-imessage`, `agent-user-statusd`,
`agent-user-status-cursor-tracker`, `agent-user-status-webcam-eye-tracker`, and
`agent-imessage-mcp`. The shell bootstrap scripts now only pin the source root
and hand off to `agent_user_status.bootstrap`; it is a compatibility shim that
delegates to `agent_user_status.bootstrap_cli`. They are not the primary package
boundary.

- `agent_imessage_core.py` for config, message, signal, and shared utility helpers
- `agent_imessage_learning.py` for action learning and workspace attribution
- `agent_imessage_status.py` for status estimation and stop-hook decisions
- `agent_imessage_commands.py` for CLI command handlers and parser wiring

The install, uninstall, doctor, and setup-eye-tracker scripts validate the
staged layout around those entrypoints, while `agent_imessage.py` remains the
thin wrapper that launches the packaged CLI.

Runtime binary lookup now flows through `agent_user_status.bootstrap_support`.
`AGENT_USER_STATUS_BIN_DIR` controls the default command prefix, while
`AGENT_IMESSAGE_BIN` and `IMSG_BIN` can override individual binaries for
packaging tests or alternate local installs.
