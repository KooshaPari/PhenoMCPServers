# HexaKit integration

The `templates/mcp-server/` directory is a [HexaKit](https://github.com/KooshaPari/HexaKit)
template targeting this catalog. HexaKit's `hexakit init` consumes it via:

```bash
hexakit init mcp-server --catalog phenomcp --id <my-server>
```

`scripts/render.py` inside the template is the local-rendering counterpart
HexaKit invokes; running it produces a layout that passes
`scripts/validate_catalog.py` end-to-end.

## What gets generated

For a single `--id echo` invocation:

| Path | Purpose |
|------|---------|
| `servers/echo/echo_server.py` | Runnable `fastmcp` server with one tool |
| `servers/echo/pyproject.toml` | `phenomcp-server-echo` Python package |
| `servers/echo/README.md` | Quick-start usage |
| `skills/echo-skill/SKILL.md` | Agent skill frontmatter + body |
| `skills/echo-skill/skill.yaml` | Skill manifest (id, path, entry) |
| `plugins/echo-bundle/plugin.yaml` | IDE plugin manifest |
| `plugins/echo-bundle/mcp.json` | Cursor/Claude `mcpServers` snippet |
| `agents/echo-lead/agent.yaml` | Default agent persona |
| `catalog/registry.yaml` | Appends `servers`/`skills`/`plugins`/`agents` entries |

## Validation

After rendering, run:

```bash
python scripts/validate_catalog.py
```

The validator checks two things:

1. **Schema** — every rendered entry conforms to
   `schemas/registry.schema.json` (Draft 2020-12).
2. **Path existence** — `active` entries must point to real files. Scaffolded
   entries use `status: template`, so the path-existence check is skipped
   until you flip the entry to `active` after filling in the server.

## Trying the template locally

```bash
python templates/mcp-server/scripts/render.py \
  --id echo --title "Echo MCP" --description "Echoes input back" \
  --env ECHO_TOKEN --out /tmp/phenomcp-render
ls /tmp/phenomcp-render
```

To verify the rendered entries pass the catalog validator, copy them into
a real PhenoMCPServers checkout and re-run the validator (see
`tests/test_hexakit_template.py::test_validate_catalog_script_passes` for
the exact recipe).

## Promoting template entries to active

1. Implement the server's tools in `servers/<id>/<id>_server.py`.
2. Add a `README.md` and at least one pytest under `servers/<id>/tests/`.
3. Edit `catalog/registry.yaml` and change the entry's `status` from
   `template` to `active`.
4. Re-run `python scripts/validate_catalog.py` — the path-existence check
   now applies.
