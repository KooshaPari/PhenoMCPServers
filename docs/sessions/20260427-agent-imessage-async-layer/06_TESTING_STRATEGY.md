# Testing Strategy

## Validation performed

- `PYTHONPATH=/Users/kooshapari/CodeProjects/Phenotype/repos/agent-user-status/src python -m pytest tests/unit/test_agent_imessage_outbox.py tests/unit/test_agent_imessage_recipients.py tests/unit/test_agent_imessage_mcp.py -q`
- `uv run ruff check src/agent_user_status/agent_imessage_outbox.py src/agent_user_status/agent_imessage_comm_commands.py src/agent_user_status/agent_imessage_commands.py src/agent_user_status/agent_imessage_mcp_comm.py tests/unit/test_agent_imessage_outbox.py tests/unit/test_agent_imessage_recipients.py tests/unit/test_agent_imessage_mcp.py`

## Coverage targets

- Outbox lifecycle transitions
- Echo cleanup command path
- MCP cleanup tool dispatch
- Structured envelope and elicitation compatibility

