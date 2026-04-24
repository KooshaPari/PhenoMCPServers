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

## Validation

Validate all packaging metadata without building platform packages:

```bash
packaging/scripts/validate-packaging.sh all
packaging/scripts/validate-python-dist.sh --dry-run
```

The Linux path uses `desktop-file-validate` and `appstreamcli` when available,
then falls back to deterministic Python checks. The Windows path validates the
MSIX XML and manifest contract on non-Windows CI hosts; Windows SDK packaging
and signing remain explicit release steps.

Python distribution validation supports both dry-run metadata checks and real
wheel/sdist builds:

```bash
python3 -m pip install build
packaging/scripts/validate-python-dist.sh --build
```

## macOS pkg Helper

Use the helper to validate metadata and print the exact `pkgbuild` and
`productbuild` commands without creating files:

```bash
packaging/scripts/build-macos-pkg.sh --dry-run
```

Builds are explicit and require a disposable staged payload root. To stage the
current local install artifacts without modifying `~/.local`, run:

```bash
packaging/scripts/stage-macos-payload.sh --stage
```

Then build from that staged root:

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
