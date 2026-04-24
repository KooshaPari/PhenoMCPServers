# Specifications

Scope for this setup pass:
- Establish a GitHub remote for the repository.
- Preserve the existing privacy-first runtime contract.
- Keep the session docs under `docs/sessions/20260423-real-eye-tracker/`.
- Define the next app-packaging and session-bus direction for GUI clients and
  agent/process attachment.
- Keep messaging scoped to the configured sponsor/user recipient, not general
  contact management.

Acceptance criteria:
- `origin` points at the GitHub repo.
- The repo can be pushed without mutating the privacy boundary.
- The session docs are present in the initial tree.
- PR and issue templates force privacy/runtime classification.
- Runtime binary lookup honors install-prefix overrides.
- MCP status redacts message preview/chat metadata by default.
- Generic Messages MCP registration is admin-gated and not part of the default
  polished sponsor/user messaging path.
