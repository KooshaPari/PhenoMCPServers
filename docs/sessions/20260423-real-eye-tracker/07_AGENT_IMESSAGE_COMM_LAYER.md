# Agent iMessage Async Communication Layer

## Goal

Make `agent-imessage` a reliable async communication layer between agents and
Koosha, not only a notification wrapper. The layer should support structured
message provenance, clear elicitation prompts, response correlation, sender-side
echo cleanup, and Codex hook integration.

## Work Packages

1. Envelope schema
   - Add `AgentMessageEnvelope`.
   - Required fields: `message_id`, `correlation_id`, `sender`, `session_id`,
     `task_id`, `project`, `repo_path`, `created_at`, `expires_at`, `urgency`,
     and `answer_schema`.
   - Render Messages text with a compact header: project, task, session, and
     expected reply style.

2. Elicitation structs
   - Support `single_question`, `multi_question`, `single_answer`, and
     `multi_answer`.
   - Use stable answer IDs (`A1`, `A2`, `A3`, ...) so short replies can be
     parsed deterministically.
   - Store labels, descriptions, defaults, and whether freeform answers are
     allowed.

3. Async lifecycle
   - Persist delivery receipts and response correlations.
   - Track sent, delivered, responded, expired, deleted, failed, and unsupported
     states.
   - Add retries with bounded backoff and stale-message expiration.

4. Echo cleanup
   - Implement best-effort sender-side deletion for agent-sent artifacts.
   - If macOS Messages access is unavailable or deletion semantics are unsafe,
     record `unsupported` instead of retrying forever.
   - Store only receipt IDs, tombstones, timestamps, and redacted body hashes.

5. Codex hooks
   - Repo-local `.codex/hooks.json` maps `SessionStart`, `PreToolUse`,
     `PostToolUse`, `UserPromptSubmit`, and `Stop` into the session bus.
   - `.codex/hooks/agent_imessage_hook.py` delegates to
     `agent_user_status.codex_hooks` and fails open with JSON output.
   - `Stop` hooks call the existing hook-decision path and return Codex
     `decision: "block"` continuation JSON only when a concrete continuation
     prompt is produced.
   - Future expansion: hook-originated elicitation prompts, pause/resume, and
     child-agent lifecycle disambiguation once Codex exposes stable
     agent-id/type fields for all relevant hook events.

6. Performance remediation
   - Replace unbounded JSONL hot-path reads with tail-seek reads.
   - Add log rotation/compaction for action and session logs.
   - Add latency tests for `agent-imessage hook-decision` so regressions fail
     before they reach Claude/Codex stop hooks.

## Acceptance Criteria

- A CLI user can send a structured question with two or more questions and
  multiple choices per question.
- Replies like `A1, A3` map back to structured answer selections with
  confidence and ambiguity notes.
- Every outbound message can be traced to project, task, session, and sender.
- Stop-hook latency stays bounded when action/session logs grow.
- Echo deletion is observable and never silently claims success without a
  receipt/tombstone.
- Codex hook events are recorded as privacy-safe session events and Stop hooks
  can continue Codex through the same user-status decision path.
