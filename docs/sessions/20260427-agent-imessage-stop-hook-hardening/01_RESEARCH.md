# Research

## Local sources checked

- `src/agent_user_status/agent_imessage_status.py`
- `src/agent_user_status/codex_hooks.py`
- `src/agent_user_status/jsonl_tail.py`
- `src/agent_user_status/ttl_cache.py`
- `src/agent_user_status/statusd_command_cache.py`
- `tests/unit/test_jsonl_tail.py`
- `tests/unit/test_codex_hooks.py`

## Findings

- The hook-decision path was recomputing status and attribution on repeated stop events.
- The repo already has a small bounded TTL cache used by `statusd`.
- `jsonl_tail.py` already reads bounded tails, so the remaining issue is repeated recomputation.

