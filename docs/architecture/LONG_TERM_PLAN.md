# Long-Term Architecture

The current runtime is a working local bridge. The target architecture is a
typed, replayable local event system.

## Streams

- `input.eyes`: derived gaze coordinates, confidence, fixation/saccade state.
- `input.keyboard`: key activity counters and cadence, not typed content by
  default.
- `input.mouse`: pointer coordinates, clicks, scrolls, movement entropy.
- `output.windows`: z-order, focused app, window-under-gaze, process metadata.
- `output.av`: audio/video playback state, meeting/screen-share state.
- `env.project`: cwd, repo, worktree, tmux pane, terminal/session metadata.
- `agent.state`: Claude/Codex session id, repo, last safe summary, hook state.
- `policy.decisions`: wait, summarize, handhold, quiet, defer.

## Core Runtime

1. Native collectors per OS.
2. Normalizer with strict schema validation and sensitivity labels.
3. Local event bus with bounded queues and replay.
4. Hot state graph for seconds/minutes of state.
5. Encrypted warm store for aggregate history and policy learning.
6. Policy engine with deterministic constraints before any learned model.
7. Native monitor UI plus audit/privacy control surface.

## Platform Direction

- macOS: Swift/AppKit collector and UI; Rust core via UniFFI/cbindgen when the
  event bus/policy engine outgrows scripts. The monitor must ship as a real
  `.app` bundle that can live in `/Applications`, appear in Spotlight, and be
  wrapped by a signed/notarized `.pkg` for managed installs.
- Windows: WinUI 3 / Windows App SDK UI; `windows-rs` collectors for Win32,
  UI Automation, media, and input APIs. Prefer MSIX for Start Menu integration,
  identity, update, and package-manager distribution; keep MSI only as an
  enterprise fallback.
- Linux: GTK4/libadwaita via `gtk-rs` for native desktop integration. Slint is
  the Rust-first cross-platform fallback. Qt is a fallback, not the default.
  Ship Freedesktop `.desktop` and AppStream metainfo before Flatpak/deb/rpm
  routes so desktop shells and software centers can discover the app.

## Application Packaging

The user-facing monitor and controls are applications, not helper binaries.
Every GUI client must have:

- a platform-native app identity, icon, display name, and launch surface;
- package-manager-friendly metadata;
- service lifecycle controls for the local backend and collectors;
- a privacy/control surface for camera, gaze, process, and message status;
- installer validation in `doctor`.

Packaging tracks:

- macOS: `Agent User Status.app`, `Info.plist`, entitlements, icon assets,
  optional helper-tool install, signed/notarized `.pkg`, Homebrew cask path.
- Windows: WinUI 3 app, MSIX manifest/signing, winget manifest, MSI fallback
  only for managed environments that cannot use MSIX.
- Linux: GTK4/libadwaita app, `.desktop`, AppStream metainfo, icons,
  systemd/user-service integration, Flatpak first, deb/rpm after metadata is
  stable.

## Agent Session Detection

Terminal process detection is insufficient. The target design needs:

- tmux pane/window metadata.
- shell cwd and foreground process per pane.
- Claude/Codex session file discovery.
- repo/worktree identity.
- hook/skill/MCP config validation per agent session.
- last safe summary and prompt-shape metrics without storing full transcripts
  unless explicitly enabled.

## Agent Session Bus

`statusd` remains the local control plane. Add an `AgentSessionRegistry` behind
it before introducing heavier infrastructure:

- Sync RPC: keep loopback HTTP now; add Unix-domain socket parity for local-only
  clients that should avoid TCP exposure.
- Async events: append schema-versioned JSONL under the state directory and keep
  an in-memory ring buffer for the native monitor.
- Subscriptions: add SSE or long-poll `GET /events/stream` before evaluating
  NATS. NATS is only justified when local fanout, durability, or multi-machine
  routing outgrows the lightweight bus.
- Session identity: `session_id`, agent kind, PID tree, TTY, terminal app PID,
  tmux pane, cwd, repo root, worktree, branch, hook/MCP status, last seen,
  confidence, and source.
- Preferred detection: self-registration from hooks/wrappers first, passive
  process/tmux/session-file discovery second.

Agents should use sponsor/user messaging only for true external blockers:
secrets, destructive approval, product ambiguity, or decisions with real
cost/risk. Repo scans, code research, independent validation, and parallel
context gathering should stay in subagents and publish session events instead
of texting by default.

## Policy Examples

- Looking at terminal, no input: likely reading; wait or summarize lightly.
- Looking at terminal, keyboard burst: active typing; avoid interrupting.
- Looking at terminal with many active agent sessions: context-pollution risk;
  provide stronger primers and lower-assumption summaries.
- Recent outputs getting terse/dry plus high task-switching: drift risk; agent
  should use heavier handholding and explicit state recap.
