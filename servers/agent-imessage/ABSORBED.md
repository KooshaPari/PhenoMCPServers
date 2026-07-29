# agent-user-status → split absorption (2026-07-28)

## Source

`KooshaPari/agent-user-status` (33 branches, 318 Python files, 11 macOS
Swift files, 4 launchd plists, packaging scripts).

## Migration state: SPLIT-ABSORBED

### Component 1: Skill + MCP server + iMessage agent → THIS repo (PhenoMCPServers)

- `skills/agent-imessage/SKILL.md` and `skill.yaml`
- `servers/agent-imessage/agent_imessage_mcp.py` (the MCP bridge)
- `servers/agent-imessage/src/agent_imessage_*.py` (8 iMessage CLI/library modules)
- `servers/agent-imessage/tests/test_agent_imessage_*.py` (5 unit tests)

### Component 2: Eye-tracker Python libs + macOS Swift → `KooshaPari/eyetracker`

- Eye/gaze/webcam/cursor Python modules
- macOS Swift native files (`src/native/macos/*.swift`)
- launchd plists for `*-cursor-tracker` and `*-webcam-eye-tracker`
- `scripts/setup-eye-tracker.sh`

### Remained in source repo (preserved in archive)

The macOS status-daemon SwiftUI app (`AgentUserStatusApp.swift`,
`AgentSessions.swift`, `EyeTrackerControls.swift`, etc.), the `statusd*.py` and
`session_*.py` daemon orchestration, `bootstrap*.py` CLI, `monitor_html.py`,
packaging (`packaging/`), the daemon launchd plists, and all governance
files (`.github/`, `AGENTS.md`, `CLAUDE.md`, `LICENSE*`, etc.).

## Branch preservation

All 33 source-repo branches preserved as historical refs under
`refs/sources/agent-user-status/<branch>` in this repo.

## Superseded by

- `KooshaPari/PhenoMCPServers` (this repo) — for tooling components
- `KooshaPari/eyetracker` — for upstream eye-tracking libraries
