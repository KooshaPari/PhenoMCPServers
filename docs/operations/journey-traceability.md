# Journey Traceability

**Repo:** agent-user-status: user status tracking  
**Standard:** [phenotype-infra journey-traceability standard](https://github.com/kooshapari/phenotype-infra/blob/main/docs/governance/journey-traceability-standard.md)  
**Schema:** [phenotype-journeys Manifest schema](https://github.com/kooshapari/phenotype-journeys/blob/main/schema/manifest.schema.json)

## User-facing flows

- CLI command invocation and flag handling
- Configuration and initialization
- Output rendering and formatting
- Error handling patterns

## Keyframe capture schedule

Keyframes: command entry, flag parsing, output rendering, error states, completion.

## Icon set

`docs/operations/iconography/` — Fluent + Material SVG icons. See `SPEC.md`.

## Manifest location

Journey manifests: `docs/journeys/manifests/`  
Manifest schema: `manifest.schema.json` (from phenotype-journeys)

## CI Gate

`.github/workflows/journey-gate.yml` — **Stub, populate manifests to pass CI**
