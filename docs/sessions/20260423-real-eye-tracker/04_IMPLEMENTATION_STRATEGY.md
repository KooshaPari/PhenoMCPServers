# Implementation Strategy

Use the existing repo layout as the initial source of truth:
- keep runtime code in `src/`
- keep LaunchAgents in `launchd/`
- keep bootstrap helpers in `scripts/`
- keep privacy and architecture docs in `docs/`

For GitHub setup:
- attach `origin` to the repo name derived from the checkout
- make the first commit include the docs/session scaffold
- publish the initial tree before any broader cleanup or restructuring
- add a lightweight CI workflow for unit tests
- add a backend smoke CI job that starts `agent-user-statusd` directly
- add issue and PR templates so the remote is usable immediately
- add Dependabot, CODEOWNERS, CONTRIBUTING, and SECURITY surfaces

No runtime behavior changes are needed for this setup pass.

For the next architecture pass:
- build macOS packaging first because it is the live platform and already has a
  native monitor;
- keep app packaging metadata platform-native rather than hiding GUI apps behind
  shell scripts;
- keep the sponsor/user messaging layer recipient-scoped and redacted by
  default;
- add a lightweight session registry inside `statusd` before introducing NATS
  or another external bus;
- prefer self-registration from agent hooks/wrappers over fragile passive
  process guessing, then use passive process/tmux scans to fill gaps.

For eye tracking quality:
- do not add facial recognition or identity matching; use local face/eye
  landmark detection only as an ephemeral feature source;
- publish only derived coordinates, quality scores, projection state, and
  bounded correction metadata;
- when calibration quality degrades, prefer passive drift correction from
  gated cursor/target events while the fit remains reliable;
- allow explicit alignment events to seed correction even when the current
  gaze point is flagged unreliable, because the user is explicitly supplying
  the intended target;
- expose recalibration as a native monitor control, but keep evaluation as the
  first action when passive correction is currently healthy.

For the native/runtime rewrite:
- keep the Swift/AppKit monitor as the macOS control surface;
- move camera capture to AVFoundation before replacing the model layer, because
  TCC, lifecycle, and app packaging are cleaner there than Python/OpenCV under
  launchd;
- evaluate Rust for the smoothing, correction, status payload, and local IPC
  core via Swift FFI, where it can be shared with Windows/Linux clients;
- avoid a partial rewrite that leaves Python, Swift, and Rust all owning
  lifecycle; the target boundary is native UI + native capture + shared Rust
  core + pluggable model inference.

Current concrete implementation:
- MediaPipe-derived head yaw, pitch, roll, frame size, and framing
  quality are computed inside the frame-processing call and published as
  bounded derived telemetry.
- The native monitor displays head-pose and framing summaries beside the gaze
  smoothing metrics, so poor camera framing is visible before blaming the
  calibration model.
- The derived payload schema accepts these abstract values and continues to
  reject raw landmark/camera/biometric data.
