# macOS Packaging Scaffold

This directory holds metadata for the current local `.app` bundle and future
signed installer/package-manager routes. It does not replace the current
`scripts/install.sh` workflow.

## Files

- `Info.plist`: app bundle identity, category, version, privacy descriptions,
  and menu-bar app behavior.
- `entitlements.plist`: hardened-runtime signing entitlements for local camera
  access, local Apple Events automation, and dynamically loaded native support.
- `pkg/Distribution.xml`: product archive distribution metadata for `productbuild`.
- `pkg/resources/`: installer resource HTML referenced by the distribution file.
- `pkg/README.md`: notes for safe package assembly.
- `../scripts/stage-macos-payload.sh`: copies current install artifacts into a
  disposable package payload root.
- `../scripts/build-macos-pkg.sh`: validation, dry-run, and explicit build helper.

## Bundle Shape

Current local app bundle layout:

```text
Agent User Status.app/
  Contents/
    Info.plist
    MacOS/
      AgentUserStatusMonitor
    Resources/
      agent-user-status.icns
```

The app should remain a local status monitor. It must not embed raw camera
frames, screenshots, face landmarks, raw gaze streams, or biometric data.

## Routes

- Local install: `scripts/install.sh` installs launch helpers and the current
  `.app` under the user's local tree.
- Unsigned package validation: stage current artifacts with
  `packaging/scripts/stage-macos-payload.sh --stage`, then run
  `packaging/scripts/build-macos-pkg.sh --dry-run`.
- Signed release package: use the same staged payload root and opt in to
  signing/notarization with release environment variables.
- Future package-manager routes: reuse the same metadata and payload contract,
  but keep permissions and privacy descriptions in this directory as the source
  of truth.

## Validation

```bash
plutil -lint packaging/macos/Info.plist
plutil -lint packaging/macos/entitlements.plist
xmllint --noout packaging/macos/pkg/Distribution.xml
packaging/scripts/validate-packaging.sh macos
packaging/scripts/stage-macos-payload.sh --dry-run
packaging/scripts/build-macos-pkg.sh --dry-run
```
