# Testing Strategy

## Validation performed

- `uv run ruff check ...`
- `PYTHONPATH=/Users/kooshapari/CodeProjects/Phenotype/repos/agent-user-status/src python -m pytest tests/unit/test_agent_imessage_status.py tests/unit/test_bootstrap_support.py tests/unit/test_jsonl_tail.py tests/unit/test_codex_hooks.py -q`

## Coverage targets

- Cached hook decision reuse
- Degraded hook decision reuse
- Bootstrap manifest coverage for the new cache helper

