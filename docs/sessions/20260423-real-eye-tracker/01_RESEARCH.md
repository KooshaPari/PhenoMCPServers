# Research

Repo-local findings:
- `README.md` already documents the packaging boundary, privacy boundary, and
  webcam tracker behavior.
- `docs/architecture/LONG_TERM_PLAN.md` and `docs/security/PRIVACY.md` already
  exist as canonical reference docs.
- The checkout now has `origin` configured at
  `https://github.com/KooshaPari/agent-user-status.git`.
- Native monitor evaluation originally mixed coordinate conventions: Python
  gaze publishing uses local screen coordinates, while AppKit screen/window
  lookup uses absolute `NSScreen` coordinates. Native parsing now converts
  published gaze points into AppKit coordinates before rendering, window lookup,
  and calibration evaluation.
- A saved calibration with high fit-time error is not usable as proof of eye
  tracker quality. Current local calibration state showed poor aggregate fit
  before live evaluation, so follow-up work needs better collection diagnostics
  and a stronger gaze model path, not just visual smoothing.

Operational findings:
- `gh auth status` succeeds for `KooshaPari`.
- The repo name `agent-user-status` was used as the remote target.
- GitHub Actions successfully ran the initial `CI / unit-tests` check.
- PR hardening added a separate backend smoke check for the privacy-sensitive
  HTTP contract: raw `/dev/eye` payload rejection, derived eye payload accept,
  correction-event learning, and reliable-only correction feed behavior.

Next setup step:
- Keep automation and docs aligned as setup expands.

Packaging and app-discoverability findings:
- The current macOS monitor is compiled directly to
  `~/.local/bin/agent-user-status-native-monitor`; it is not an `.app` bundle
  and is therefore not a normal Spotlight/Finder application.
- LaunchAgents are already template-driven and validated, but the tray job
  launches the bare executable instead of an app bundle executable.
- Platform guidance:
  - Apple distribution should use a proper app bundle and Developer ID
    notarization for software distributed outside the App Store.
  - Microsoft documents MSIX as the modern Windows app package format and the
    right first target for Start Menu/package-manager discoverability.
  - Freedesktop/AppStream guidance requires `.desktop` entries and AppStream
    metadata for Linux desktop/menu/software-center discoverability.

Sponsor messaging findings:
- The default CLI/MCP surface is mostly scoped: `notify`, `inbox`, and `wait`
  resolve the configured recipient and do not expose arbitrary contact search.
- The generic `messages` MCP path is the main leak risk because it can expose
  non-scoped Messages access. It is now admin-gated by
  `AGENT_IMESSAGE_ALLOW_GENERIC_MESSAGES_MCP=1`.
- MCP `user_status` now redacts message preview and chat metadata by default.

Session-bus findings:
- Existing process attribution is coarse and global-process based; it does not
  yet map agent processes to TTYs, tmux panes, repos, cwd, or session files.
- `statusd` is the right control-plane anchor, but it currently bridges to the
  CLI rather than owning a session registry.
- The next session layer should add self-registration/heartbeat first, then
  passive process/tmux discovery, and only later evaluate SSE/UDS/NATS.
