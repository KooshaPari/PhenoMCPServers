# Privacy Model

Agent User Status handles user-attention telemetry. Treat it as highly
confidential local data.

## Data Tiers

- Tier 0 raw: camera frames, screenshots, biometric embeddings, raw gaze streams,
  key contents, prompt transcripts. These are rejected by default and must not be
  stored.
- Tier 1 derived: screen coordinates, screen zone, focus confidence, fixation
  state, input/output activity counters. These are accepted with short freshness
  windows.
- Tier 2 aggregate: session-level rates and policy outcomes. These can persist
  longer if encrypted and user-controlled.

## Current Runtime Contract

- Backend binds to `127.0.0.1`.
- `/dev/eye` accepts `POST` only for mutation.
- `/privacy` exposes the active privacy policy served by the local backend.
- `/status` returns redacted status and removes message preview/chat metadata.
- `/signals` and `/actions` expose derived signal/action records only.
- `/correction/events` returns derived correction anchors and supports
  `reliable_only=true`.
- Raw sensor payloads are rejected.
- Numeric scores are bounded.
- `/status` served by `statusd` redacts message preview and chat metadata.
- `/correction/event` accepts `cursor_click`, `cursor_target`, `keyboard_activity`,
  `audio_activity`, and `explicit_alignment` events.
- `/correction/events` exposes only derived correction events with bounded fields
  and no raw content.

## Correction-Grade Event Privacy Envelope

- Cursor correction is allowed only through derived coordinates:
  `screen_x`, `screen_y`, `screen_width`, and `screen_height`.
- Keyboard correction events must omit key contents (for example `key`, `typed_text`,
  `text`, `chords`, or any raw characters).
- Audio correction events must omit waveforms and transcripts (no `audio`,
  `samples`, `transcript`, or text stream fields).
- `harmony_hint` is an advisory flag. Only when true should coordinate events be
  used as high-confidence drift-correction anchors.
- Optional context fields (`window_owner`, `window_role`, `input_modality`) are
  retained as low-risk metadata only.
- All correction events are short-lived and scoped by `max_age_seconds`.

## Future Hardening

- Move durable state to encrypted SQLite or SQLCipher.
- Add per-collector consent and kill switches.
- Add schema-versioned event envelopes.
- Add local-only auth token before any non-loopback transport exists.
- Add explicit retention/delete/export commands.
