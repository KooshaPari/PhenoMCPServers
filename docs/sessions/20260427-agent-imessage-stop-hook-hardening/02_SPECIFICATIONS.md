# Specifications

## Requirements

- Cache stop-hook decisions by stable message fingerprint.
- Use a degraded cache path when the underlying status read fails.
- Keep failure handling fail-open.

## Risks

- Cached decisions can hide short-lived status changes for a small TTL.
- A longer degraded TTL is a tradeoff against repeated failed state reads.

