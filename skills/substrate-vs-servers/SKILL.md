# Substrate vs servers boundary

Use when placing dispatch, cheap-llm, or MCP tool logic.

## Layer map (ADR-019)

| Layer | Repo | Owns |
|-------|------|------|
| Runtime | substrate | `driver-argv`, `driver-http`, `driver-mcp` dev mirror |
| Implementations | PhenoMCPServers | `servers/substrate/`, catalog SSOT |
| Framework | PhenoFastMCP* | Server builder SDKs |
| Spec SDK | PhenoRMCP | rmcp transports |

## Rules

- **cheap-llm** → substrate `driver-argv` only; do not add a standalone cheap-llm MCP catalog server
- **MCP tool definitions** → PhenoMCPServers `servers/` (canonical)
- **substrate/driver-mcp/** → dev mirror; sync via `scripts/check_driver_mcp_sync.py`
- **Dispatch HTTP** → `cargo run -p driver-http --bin substrate-http`; MCP tools call `/v1/plan` and `/v1/dispatch`

## Anti-patterns

- Forking tool definitions in substrate long-term
- Adding cheap-llm as catalog server entry
- Putting fleet-lead agent config in substrate

## References

- [ADR-019](https://github.com/KooshaPari/PhenoSpecs/blob/main/adrs/019-mcp-runtime-dependency-graph.md)
- [servers/substrate/README.md](../../servers/substrate/README.md)
