# Linux Packaging Scaffold

This directory contains desktop discovery metadata for a future Linux package.

## Files

- `agent-user-status.desktop`: freedesktop desktop entry.
- `com.phenotype.AgentUserStatus.metainfo.xml`: AppStream metadata.

Expected install locations for package builders:

```text
/usr/bin/agent-user-status
/usr/share/applications/agent-user-status.desktop
/usr/share/metainfo/com.phenotype.AgentUserStatus.metainfo.xml
/usr/share/icons/hicolor/scalable/apps/com.phenotype.AgentUserStatus.svg
```

Linux native UI work should use GTK4/libadwaita or the agreed Rust-first
fallback. The current scaffold only exposes the Python CLI entrypoint for
discoverability.

## Validation

```bash
desktop-file-validate packaging/linux/agent-user-status.desktop
appstreamcli validate --no-net packaging/linux/com.phenotype.AgentUserStatus.metainfo.xml
```
