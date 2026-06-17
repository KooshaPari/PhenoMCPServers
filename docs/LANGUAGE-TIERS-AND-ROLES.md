# Language tiers and domain roles (Phenotype fleet)

Last updated: 2026-06-17

This document is the **normative boundary** for where code may live by language
and by **domain role**. Language-based umbrella repos (e.g. a generic
`phenotype-rust-sdk`) are **anti-patterns** unless they own a single narrow role.

Work **in parallel** across tier-0 forks and domain repos; do not serialize on
one language.

---

## Language tiers

```
┌─────────────────────────────────────────────────────────────┐
│ Tier 0 — CORE (max perf, protocol truth, codegen source)    │
│   Rust · Zig · Mojo                                         │
│   PhenoFastMCP-rust (fastmcp_rust) · PhenoRMCP (rmcp) · substrate · phenoUtils │
└───────────────────────────┬─────────────────────────────────┘
                            │ FFI / gRPC / schema / wasm
┌───────────────────────────▼─────────────────────────────────┐
│ Tier 1 — EDGE GATEWAYS (justified Go; not bulk app logic)   │
│   Go — microservices, ops glue, LSP bridges, HTTP MCP       │
│   PhenoFastMCP-go · phenotype-ops-mcp · MCPForge            │
└───────────────────────────┬─────────────────────────────────┘
                            │ thin clients / admin / IDE / scripts
┌───────────────────────────▼─────────────────────────────────┐
│ Tier 2 — BINDINGS & APPS (only where core rebuild ≠ worth it)│
│   Python 3.14+ (uv) · Bun · TS 7 preview · C# · Java · …    │
│   PhenoFastMCP (fastmcp fork) · PhenoMCPServers · agents    │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│ Tier 3 — SCRIPTING                                          │
│   Shell · PowerShell — install, glue, CI one-liners         │
└─────────────────────────────────────────────────────────────┘
```

### Go placement rule

Go is **not** a second core. Use Go only with **written justification**:

| Allowed | Example |
|---------|---------|
| HTTP/SSE MCP edge server | MCPForge, ops-mcp |
| Microservice boundary | gateway in front of Rust substrate |
| Upstream SDK is Go-native | mark3labs/mcp-go fork |

| Not allowed | Move to tier 0/2 |
|-------------|-------------------|
| Business logic duplicated from Rust core | substrate planner, claims |
| “Because we had a Go SDK repo” | phenotype-go-sdk catch-all |

### Python placement rule

- **PhenoFastMCP** = fastmcp fork (framework + rapid server prototyping).
- **PhenoMCPServers** = deployable servers (may be Python today; Rust rewrite when hot).
- **phenotype-python-sdk** = optional **dependency umbrella** for Python apps (`uv` workspace), **not** protocol core.
- Prefer **Python 3.14+** and **uv** for new Python packages.

### TypeScript / Bun

- **TS 7 preview** / **Bun** for IDE plugins, web admin, client wiring — tier 2 edges.
- Do not host protocol core in TS when Rust/Zig exists.

---

## Domain roles (not language buckets)

| Role | Owner repo(s) | Tier | Notes |
|------|---------------|------|-------|
| **MCP framework** | PhenoFastMCP (py), PhenoFastMCP-go, PhenoFastMCP-rust | 0–2 per lang | Fork upstream; superset merges in parallel |
| **MCP implementations** | PhenoMCPServers | 2 (migrate hot paths to 0) | servers, skills, plugins, agents |
| **Fleet runtime** | substrate | 0 Rust | dispatch, argv, cheap-llm CLI, driver-http |
| **Rust utilities / ports** | phenoUtils, phenoShared | 0 | hex ports, crypto, fs — not “rust-sdk” |
| **Project bootstrap** | HexaKit | meta | templates point at roles above |
| **Python dep extras** | phenotype-py-extras → phenotype-python-sdk | 2 | lazy `[mcp]` groups only |
| **Graphics** | phenotype-gfx | 0 Rust + C# edge | model: core in Rust, Unity/interop in C# |

### Retire / avoid

| Pattern | Why | Replacement |
|---------|-----|-------------|
| **phenotype-rust-sdk** (generic) | Language bucket, hides domains | phenoUtils + PhenoFastMCP-rust + substrate crates |
| **phenotype-go-sdk** (catch-all) | Same for Go | PhenoFastMCP-go + justified edge services only |
| **McpKit** as lib warehouse | Duplicates framework forks | PhenoFastMCP* forks + registry |
| Large logic in Python MCP servers | Wrong tier for hot paths | Implement in Rust; thin Python shim until cutover |

---

## Parallel workstreams (MCP framework)

These proceed **simultaneously**; sync weekly on schema/registry only:

| Stream | Repo | Upstream |
|--------|------|----------|
| Py framework | PhenoFastMCP | PrefectHQ/fastmcp |
| Go framework | PhenoFastMCP-go | mark3labs/mcp-go |
| Rust framework | PhenoFastMCP-rust | Dicklesworthstone/fastmcp_rust |
| Rust spec SDK | PhenoRMCP | modelcontextprotocol/rust-sdk |
| Implementations | PhenoMCPServers | catalog/registry.yaml |
| Runtime | substrate | driver-* crates |

Tier-0 **Zig/Mojo** MCP cores are future forks/issues — same fork-parent rules as Rust.

**Trigger to start:** once the **rmcp superset** in `PhenoFastMCP-rust` stabilizes
(API surface + ergonomics layer), evaluate Zig and Mojo in **parallel** as
sibling forks. Each becomes its own gh repo:

| Stream | Future repo | Upstream (planned) | Status |
|--------|-------------|--------------------|--------|
| Zig framework | `PhenoFastMCP-zig` | `modelcontextprotocol/rust-sdk` (rmcp) | future |
| Mojo framework | `PhenoFastMCP-mojo` | `modelcontextprotocol/rust-sdk` (rmcp) | future |

**Anti-pattern guard:** these lanes are **not** added to `phenotype-rust-sdk`.
They are first-class forks with their own GH repos, mirroring the
`PhenoFastMCP-rust` fork-parent rule. The `phenotype-rust-sdk` bucket is the
retired language umbrella; do not reintroduce it via Zig/Mojo.

---

## Decision checklist (new code)

1. **Which domain role?** (framework / implementation / runtime / bootstrap)
2. **Which tier?** Default tier 0 unless edge justification doc exists.
3. **Existing owner?** Extend that repo; do not create `phenotype-<lang>-sdk`.
4. **Parallel?** If another tier-0 lane can proceed independently, start it.

---

## Cross-links

- `catalog/registry.yaml` — framework + server entries
- PhenoFastMCP `PHENO.md` — Python fork policy
- PhenoFastMCP-go / PhenoFastMCP-rust `PHENO.md` — sibling forks
