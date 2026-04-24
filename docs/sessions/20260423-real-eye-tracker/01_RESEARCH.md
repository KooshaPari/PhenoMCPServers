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

Eye/head/facial-control ecosystem findings:
- OptiKey is the strongest interaction-design reference for assistive
  eye-control UX. Useful patterns are dwell timing, precision mouse/zoom,
  configurable selection sources, and communication-first controls. Its Windows
  stack is not a direct model-layer dependency for this project. Sources:
  `https://optikey.org/`, `https://github.com/Optikey/Optikey/wiki`.
- Tracky Mouse, eViacam, and Apple Head Pointer show that webcam head tracking
  is often more stable than webcam gaze. For this system, head pose should be a
  presence/framing/confidence signal first, not a coordinate source. Sources:
  `https://trackymouse.js.org/`, `https://eviacam.crea-si.com/`,
  `https://support.apple.com/guide/mac-help/mchlb2d4782b/mac`.
- Windows Eye Control is the best OS-level precedent for a native launcher,
  keyboard, mouse, scroll, and speech surface. The relevant lesson is explicit
  tracker permissions plus a small always-available control surface. Sources:
  `https://support.microsoft.com/windows/get-started-with-eye-control-in-windows-1a170a20-1083-2452-8f42-17a7d4fe89a9`,
  `https://support.microsoft.com/windows/windows-eye-tracking-and-privacy-62623324-36cf-04a3-6992-8f329081f20b`.
- MediaPipe is still the practical local baseline because it gives face/eye
  landmarks and iris points with simple deployment. OpenFace/OpenSeeFace are
  useful prior art for richer head pose and action-unit research, but they
  increase runtime and packaging complexity. Sources:
  `https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker`,
  `https://docs.warudo.app/docs/mocap/openseeface`.
- WebGazer, EyeGestures, EyeTheia, and GazeFollower point to the same long-term
  requirement: webcam gaze needs calibration, drift correction, head-motion
  handling, and optional user-specific fine-tuning. A smoother cannot repair a
  bad projection model by itself. Sources: `https://webgazer.cs.brown.edu/`,
  `https://eyegestures.com/`, `https://arxiv.org/abs/2601.06279`,
  `https://pypi.org/project/gazefollower/`.
- Facial recognition/identity matching is explicitly out of scope. Ephemeral
  landmark/head-pose/action signals are acceptable only when reduced to bounded
  derived states and discarded before publishing.
