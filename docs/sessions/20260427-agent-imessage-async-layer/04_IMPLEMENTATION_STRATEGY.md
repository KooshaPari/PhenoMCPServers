# Implementation Strategy

## Approach

Keep the implementation local and explicit:

- Use the existing JSONL outbox as the durable lifecycle store.
- Add append-only state transitions for queued, sent, delivered, responded, expired,
  and cleanup states.
- Use a configured local helper for deletion when available.

## Why this shape

- No new service process is required.
- The behavior is easy to test and inspect.
- The code stays close to the existing CLI/MCP contract.

