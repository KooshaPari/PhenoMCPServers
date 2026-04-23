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

No runtime behavior changes are needed for this setup pass.
