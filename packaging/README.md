# Agent User Status Packaging

This directory contains platform packaging metadata scaffolds only. The runtime
implementation remains under `src/`, while these files describe how native
installers and app discovery surfaces should identify the project.

## Scope

- `macos/`: app bundle metadata, signing entitlements, and pkg notes.
- `linux/`: desktop entry and AppStream metadata.
- `windows/`: MSIX manifest scaffold and packaging notes.

These scaffolds are intentionally side-effect free. They do not install files,
start LaunchAgents, request permissions, or overwrite the live `~/.local`
installation.

## Privacy Boundary

Package metadata must describe only the local runtime and its permission needs.
Do not add raw telemetry samples, screenshots, camera frames, biometric data, or
environment-specific identifiers to packaging assets.
