# Retired MCP repos — routing table

**Status:** active reference (ADR-017/019)  
**SSOT map:** [phenotype-registry ECOSYSTEM_MAP](https://github.com/KooshaPari/phenotype-registry/blob/main/ECOSYSTEM_MAP.md)

| Retired repo | Status | Use instead |
|--------------|--------|-------------|
| [PhenoMCP](https://github.com/KooshaPari/PhenoMCP) | archived 2026-06-17 | [PhenoMCPServers](https://github.com/KooshaPari/PhenoMCPServers) `servers/` + [PhenoFastMCP](https://github.com/KooshaPari/PhenoFastMCP)* |
| [McpKit](https://github.com/KooshaPari/McpKit) | archived 2026-06-17 | PhenoFastMCP-py + PhenoMCPServers catalog |
| cheap-llm standalone MCP | deleted | [substrate](https://github.com/KooshaPari/substrate) `driver-argv` only |
| dispatch-mcp / thegent-dispatch | deleted | substrate `driver-http` + `servers/substrate/dispatch_server.py` |
| phenotype-go-sdk (MCP bucket) | shrink per [#7](https://github.com/KooshaPari/PhenoMCPServers/issues/7) | PhenoFastMCP-go, MCPForge, phenotype-ops-mcp (tier-1 edges) |
| phenotype-rust-sdk (MCP bucket) | retired anti-pattern | PhenoFastMCP-rust + PhenoRMCP |
| [dagctl](https://github.com/KooshaPari/dagctl) | archived 2026-06-17 | [phenodag](https://github.com/KooshaPari/phenodag) v1.0.0-rc.1+ |

## AgentMCP patterns (absorb, not duplicate)

[AgentMCP](https://github.com/KooshaPari/AgentMCP) remains the **agent-runtime** MCP protocol lane (orchestration tools).
Do not re-home AgentMCP into PhenoMCPServers `servers/` — instead:

- Deployable fleet MCP tools → PhenoMCPServers `servers/substrate/`, `servers/pheno-org/`
- Agent orchestration MCP → AgentMCP + Agentora integration (see PhenoSpecs platform spec 016)
- Hexagonal layout for new servers → [HexaKit `mcp-server` template](../HEXAKIT_INTEGRATION.md)

## Validation

- `python scripts/validate_stale_patterns.py` — bans revived bucket repos and mirror-to-empty
- `python scripts/validate_fork_parents.py` — fork_parent must match catalog
