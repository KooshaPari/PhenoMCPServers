# DAG / WBS

1. Confirm GitHub auth and remote target. Done.
2. Create or attach the `origin` remote. Done.
3. Add session docs scaffold. Done.
4. Commit the initial repo state. Done.
5. Push to GitHub. Done.
6. Add backend privacy smoke checks in CI. Done in PR #1.
7. Fix native gaze coordinate parity. Done in PR #1.
8. Merge PR #1 after owned CI checks pass. Done.
9. Require both `unit-tests` and `backend-smoke` in branch protection. Done.
10. Extend governance templates with structured telemetry/privacy checklist. Done.
11. Add a dedicated security-report path and expand `SECURITY.md` handling steps. Done.
12. Build the packaging/runtime lane:
   - centralized executable path resolution. Done.
   - installed plist validation in doctor. Done.
   - documented environment override matrix. Done.
13. Build the next eye-tracker quality lane:
   - shared native/CLI evaluation counters. Done.
   - per-target accepted/rejected sample counts. Done.
   - stale/repeated sample rejection. CLI confidence-settle reasons done;
     native stale/low-confidence/unreliable counters done; repeated/stuck sample
     detection done.
   - projection-hold rejection metrics. CLI hold-candidate counts done.
   - coordinate parity tests,
   - stronger calibration collection/model upgrade.
14. Build the app-packaging/discoverability lane:
   - macOS `.app` bundle with `Info.plist`, icon, entitlements, and app identity.
     Done for local install bundle without icon/signing.
   - update LaunchAgent tray launch to app-bundle executable or intentional
     `open -a` flow. Done with direct app-bundle executable launch.
   - macOS `.pkg` dry-run packaging with signing/notarization hooks. Metadata
     scaffold, payload staging, validators, and build helper done;
     signing/notarization remain opt-in release inputs.
   - Windows WinUI 3/MSIX manifest plan and installer scaffold. Done.
   - Linux GTK4/libadwaita `.desktop` and AppStream scaffold. Done.
15. Build the scoped sponsor/user messaging lane:
   - first-class recipient roles for `koosha` and `sponsor`. Done.
   - no arbitrary contact/search/send APIs. Done.
   - sync notify, async inbox, and wait APIs across CLI/MCP. Done.
   - redacted status by default with explicit local debug escape hatch only. Done.
16. Build the agent-session bus lane:
   - `session-scan` command for process tree, TTY, repo/cwd hints, and tmux
     metadata. Done; full cwd is opt-in with `--include-cwd`.
   - `POST /session/heartbeat`, `GET /sessions`, and `POST /event`. Done.
   - in-memory event ring plus schema-versioned JSONL. Done.
   - hook/subagent spawn/close event publishing. Stop-hook event publishing done;
     explicit child spawn/close CLI events done.
   - policy guidance for when to text versus use subagents. Done in long-term
     architecture guidance.
17. Build the quality-gate lane:
   - close current Ruff findings. Done.
   - close current Pyright findings. Done.
   - enable lint/type CI gates after green. Done.
18. Build the state-retention/privacy lane:
   - derived JSON/JSONL export, delete, and age-retention helpers. Done.
   - backend route coverage for raw sensor/audio/session payload rejection. Done.
19. Build the native monitor session lane:
   - runtime metadata loading for eye tracker controls. Done.
   - active session/stale hook/child-agent display in native panel. Done.
20. Build the modularity lane for files above the 350-line target after gates
   are stable.
21. Build the agent-imessage async comm-layer lane:
   - define `AgentMessageEnvelope` with `message_id`, `correlation_id`,
     `sender`, `session_id`, `task_id`, `project`, `repo_path`, `urgency`,
     `expires_at`, `answer_schema`, and redacted preview/hash fields.
   - add CLI/MCP send paths that accept the envelope and render human-readable
     text with project/session/task context at the top.
   - persist delivery receipts, response correlation, retry state, expiration,
     and deletion/tombstone state in bounded JSONL or SQLite storage.
   - add best-effort user-side echo deletion for sender artifacts, with an
     explicit `unsupported` state when macOS Messages permissions or schema
     changes make deletion unsafe.
   - implement elicitation structs for `single_question`, `multi_question`,
     `single_answer`, and `multi_answer`, using stable `A1`/`A2`/`A3` option IDs
     plus optional freeform fallback.
   - expose parsing helpers that turn user replies back into structured answer
     selections and preserve uncertainty/confidence.
22. Build the Codex hooks integration lane:
   - inventory current Codex experimental hook payloads and map them to the
     session bus schema.
   - publish session start/stop, tool call, stop-decision, user-elicitation,
     pause/resume, and child-agent spawn/close events.
   - replace blocking stop-hook behavior with cached/bounded reads, degraded-mode
     backoff, and explicit timeout telemetry.
   - add hook contract tests and local doctor checks for installed hook scripts.
23. Build the stop-hook performance remediation lane:
   - replace unbounded `read_text().splitlines()[-limit:]` reads with tail-seek
     bounded reads.
   - cache repeated recent-action reads within one hook process.
   - rotate or compact action/session JSONL logs by size and retention policy.
   - add a latency regression test for `agent-imessage hook-decision`.

Critical path:
- Governance template hardening blocks consistent review of privacy-sensitive
  telemetry and runtime changes.
- The live `~/.local` install must be refreshed before `doctor` can pass the
  installed-layout check for newly added support/native files.
- Subagent wrappers still need to call the new child lifecycle helpers.
- The async comm-layer envelope should land before broad hook expansion so hook
  events and iMessage prompts share one schema instead of diverging.
- Stop-hook O(N) log reads must be fixed before expanding Codex hook usage,
  otherwise more lifecycle events will amplify the current timeout mode.
- Full release distribution still needs real signing identities, notarization
  credentials, icon assets, and final install-channel manifests.
