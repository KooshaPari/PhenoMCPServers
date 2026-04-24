# macOS Packaging Scaffold

This directory holds metadata for a future native `.app` and signed installer
package. It does not replace the current `scripts/install.sh` workflow.

## Files

- `Info.plist`: app bundle identity, category, version, privacy descriptions,
  and menu-bar app behavior.
- `entitlements.plist`: hardened-runtime signing entitlements for local camera
  access, local Apple Events automation, and dynamically loaded native support.
- `pkg/Distribution.xml`: product archive distribution metadata for `productbuild`.
- `pkg/README.md`: notes for safe package assembly.

## Bundle Shape

Expected app bundle layout:

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

## Validation

```bash
plutil -lint packaging/macos/Info.plist
plutil -lint packaging/macos/entitlements.plist
xmllint --noout packaging/macos/pkg/Distribution.xml
```
