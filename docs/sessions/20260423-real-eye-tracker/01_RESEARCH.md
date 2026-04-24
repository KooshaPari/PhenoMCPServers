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
