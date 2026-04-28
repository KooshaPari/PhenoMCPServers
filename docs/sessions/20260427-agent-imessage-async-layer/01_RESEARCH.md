# Research

## Local sources checked

- `src/agent_user_status/agent_imessage_envelope.py`
- `src/agent_user_status/agent_imessage_outbox.py`
- `src/agent_user_status/agent_imessage_comm_commands.py`
- `src/agent_user_status/agent_imessage_commands.py`
- `src/agent_user_status/agent_imessage_mcp_comm.py`
- `src/agent_user_status/codex_hooks.py`
- `docs/FUNCTIONAL_REQUIREMENTS.md`
- `docs/reference/fr_coverage_matrix.md`

## Findings

- Structured envelopes already existed and already carried sender, session, task, project, and repo path.
- Elicitation schemas already supported stable `A1/A2/A3` answer IDs and multi-answer parsing.
- The outbox only tracked basic delivery and unsupported echo cleanup before this session.
- The local `imsg` binary exposes send/history/watch/rpc, but not a built-in delete verb.

