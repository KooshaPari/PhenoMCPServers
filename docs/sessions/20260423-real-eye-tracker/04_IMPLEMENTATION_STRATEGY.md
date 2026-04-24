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
