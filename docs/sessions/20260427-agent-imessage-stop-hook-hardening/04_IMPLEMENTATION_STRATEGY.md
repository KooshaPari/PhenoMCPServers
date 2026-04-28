# Implementation Strategy

## Approach

- Add a small dedicated cache module for stop-hook decisions.
- Cache successful decisions briefly.
- Cache degraded failures with exponential backoff.
- Keep the hook path fail-open.

## Why this shape

- The hook path becomes cheaper on repeated calls.
- The behavior stays local and easy to test.
- No new background process is required.

