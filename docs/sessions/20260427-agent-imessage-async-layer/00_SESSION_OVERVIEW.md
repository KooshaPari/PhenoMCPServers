# Session Overview

## Goal

Push `agent-imessage` toward a real async comm layer: structured envelopes, response correlation,
echo cleanup, expiration sweeps, and hook-facing cleanup tooling.

## Success criteria

- Structured outbound messages keep sender/session/task/project metadata.
- Outbox records delivery, response, retry, expiry, and cleanup states.
- Echo cleanup is exposed through CLI and MCP.
- Hooks continue to use the stop-decision path without breaking the existing contract.

## Result

- Queue/lifecycle helpers were extended.
- CLI and MCP now expose echo cleanup.
- Tests for outbox lifecycle and cleanup paths pass.

