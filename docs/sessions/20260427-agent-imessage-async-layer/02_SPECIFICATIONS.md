# Specifications

## Requirements

- Preserve privacy-safe outbox records without storing raw message bodies.
- Record response correlation separately from delivery state.
- Add a cleanup path that can mark echo cleanup requested, deleted, unsupported, or failed.
- Surface cleanup through CLI and MCP.

## Assumptions

- Native Messages deletion is not universally available.
- A configured local helper is acceptable for the actual deletion action.

## Risks

- Cleanup semantics depend on local Messages tooling and permissions.
- Expiration is still record-based, not a daemon-backed scheduler.

