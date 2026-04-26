# Specifications

Scope for this setup pass:
- Establish a GitHub remote for the repository.
- Preserve the existing privacy-first runtime contract.
- Keep the session docs under `docs/sessions/20260423-real-eye-tracker/`.
- Define the next app-packaging and session-bus direction for GUI clients and
  agent/process attachment.
- Keep messaging scoped to the configured sponsor/user recipient, not general
  contact management.

Acceptance criteria:
- `origin` points at the GitHub repo.
- The repo can be pushed without mutating the privacy boundary.
- The session docs are present in the initial tree.
- PR and issue templates force privacy/runtime classification.
- Runtime binary lookup honors install-prefix overrides.
- MCP status redacts message preview/chat metadata by default.
- Generic Messages MCP registration is admin-gated and not part of the default
  polished sponsor/user messaging path.
- Agent-to-user messages use a structured envelope that identifies sender,
  session, task, project/repo, urgency, expected answer shape, expiration, and
  correlation IDs.
- Elicitation messages support clear multi-question and multi-answer structures
  with stable answer IDs (`A1`, `A2`, `A3`, ...), optional freeform fallback,
  defaults, and machine-readable parsing for follow-up agents.
- User-side echo cleanup is implemented as a first-class lifecycle with send
  receipt tracking, best-effort local deletion of the sender-side artifact,
  tombstone logging, and an explicit unsupported-permission state when Messages
  storage cannot be modified safely.
- Async communication supports notify, inbox, wait, receipts, response
  correlation, retries, stale-message expiration, and non-blocking degradation
  when Messages or local hooks are unavailable.
- Codex experimental hooks are used for lifecycle capture where available:
  session start, tool call, stop decision, user elicitation, pause, resume, and
  child-agent spawn/close events.
- Stop-hook hot paths must stay bounded and should not read unbounded JSONL logs
  or block on slow macOS probes without caching/backoff.
- Webcam tracker publishes derived head pose/framing state without raw frames,
  screenshots, landmarks, identity, or biometric templates.
- Native monitor exposes calibration health, passive correction status,
  head-pose summary, and camera framing state in the pinned panel.

Privacy constraints for eye/head/facial-control signals:
- Allowed: bounded gaze coordinates, confidence, smoothing/projection state,
  approximate head yaw/pitch/roll, framing quality/state, correction
  offsets, and calibration quality.
- Forbidden: raw frames, screenshots, raw landmarks, identity recognition,
  facial recognition labels, biometric embeddings/templates, raw gaze streams,
  audio waveforms, transcripts, and typed text.
- Message deletion and echo cleanup may store only local receipt IDs,
  timestamps, sender/project/session metadata, and redacted body hashes. Never
  store full user replies in hook logs unless an explicit debug mode is enabled.
