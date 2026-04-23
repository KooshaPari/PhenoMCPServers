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
  event bus/policy engine outgrows scripts.
- Windows: WinUI 3 / Windows App SDK UI; `windows-rs` collectors for Win32,
  UI Automation, media, and input APIs.
- Linux: GTK4/libadwaita via `gtk-rs` for native desktop integration. Slint is
  the Rust-first cross-platform fallback. Qt is a fallback, not the default.

## Agent Session Detection

Terminal process detection is insufficient. The target design needs:

- tmux pane/window metadata.
- shell cwd and foreground process per pane.
- Claude/Codex session file discovery.
- repo/worktree identity.
- hook/skill/MCP config validation per agent session.
- last safe summary and prompt-shape metrics without storing full transcripts
  unless explicitly enabled.

## Policy Examples

- Looking at terminal, no input: likely reading; wait or summarize lightly.
- Looking at terminal, keyboard burst: active typing; avoid interrupting.
- Looking at terminal with many active agent sessions: context-pollution risk;
  provide stronger primers and lower-assumption summaries.
- Recent outputs getting terse/dry plus high task-switching: drift risk; agent
  should use heavier handholding and explicit state recap.
