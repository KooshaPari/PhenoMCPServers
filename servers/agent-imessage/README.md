# agent-imessage MCP server

Agent iMessage contact via local CLI bridge. Wraps the `agent-imessage` CLI as
MCP tools for Codex, Claude Desktop, Cursor, and other MCP clients.

## Source

Absorbed from `KooshaPari/agent-user-status` (split-absorption 2026-07-28).
Original module: `src/mcp/agent_imessage_mcp.py`.
Underlying CLI library: `src/agent_user_status/agent_imessage_*.py` (8 modules).

## Status

**Migrated placeholder.** Imports need to be rewritten to use the new
`servers/agent-imessage/src/` package layout. The original modules
referenced `agent_user_status.bootstrap_support` and other dependencies
that remained in agent-user-status for the daemon. Future PRs should:

- Convert `from agent_user_status.X import Y` to either package-relative
  imports within `servers/agent-imessage/src/` or extract the bootstrap
  support into this repo.
- Add a real `pyproject.toml` with entry-point for `mcp.run`.
- Add a tool-list to `catalog/registry.yaml` mapping each CLI subcommand
  to an MCP tool.

## Tools exposed (when wired)

The MCP bridge wraps the `agent-imessage` CLI:

| CLI command          | MCP tool          |
|----------------------|-------------------|
| `status`             | `status`          |
| `hook-decision`      | `hook_decision`   |
| `notify`             | `notify`          |
| `wait`               | `wait`            |
| `action input`       | `action_input`    |
| `action output`      | `action_output`   |
| `signal`             | `signal`          |

See `SKILL.md` in `skills/agent-imessage/` for the full agent-tooling guide.
