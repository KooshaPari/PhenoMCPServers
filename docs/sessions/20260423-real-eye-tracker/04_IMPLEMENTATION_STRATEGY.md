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
