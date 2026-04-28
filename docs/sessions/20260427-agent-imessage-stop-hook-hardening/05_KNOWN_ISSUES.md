# Known Issues

## Current

- Cached stop decisions are intentionally short-lived.
- Degraded cache TTL is heuristic-based and not workload-adaptive yet.

## Follow-up candidates

- Add metrics around hook cache hit rate.
- Tune TTL defaults if stop-hook churn changes.

