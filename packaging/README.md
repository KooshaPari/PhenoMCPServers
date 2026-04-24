# Agent User Status Packaging

This directory contains platform packaging metadata scaffolds only. The runtime
implementation remains under `src/`, while these files describe how native
installers and app discovery surfaces should identify the project.

## Scope

- `macos/`: app bundle metadata, signing entitlements, and pkg notes.
- `scripts/`: deterministic packaging helpers that default to dry-run
  validation.
- `linux/`: desktop entry and AppStream metadata.
- `windows/`: MSIX manifest scaffold and packaging notes.

These scaffolds are intentionally side-effect free. They do not install files,
start LaunchAgents, request permissions, or overwrite the live `~/.local`
installation.

## macOS pkg Helper

Use the helper to validate metadata and print the exact `pkgbuild` and
`productbuild` commands without creating files:

```bash
packaging/scripts/build-macos-pkg.sh --dry-run
```

Builds are explicit and require a disposable staged payload root:

```bash
packaging/scripts/build-macos-pkg.sh \
  --build \
  --payload-root build/pkg/macos/payload
```

The helper does not install the package and does not require signing secrets by
default. Signing and notarization are enabled only when the documented
environment variables are set.

## Privacy Boundary

Package metadata must describe only the local runtime and its permission needs.
Do not add raw telemetry samples, screenshots, camera frames, biometric data, or
environment-specific identifiers to packaging assets.
