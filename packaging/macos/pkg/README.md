# macOS pkg Notes

This folder is a metadata scaffold for a signed product archive. The helper at
`packaging/scripts/build-macos-pkg.sh` validates this metadata, emits dry-run
commands by default, and builds only when `--build` is passed.

Safe package assembly should use staged roots and must not overwrite the live
`~/.local` install. The staging helper copies current install artifacts into a
disposable root under `build/`:

```bash
packaging/scripts/stage-macos-payload.sh --stage
```

The staged package payload currently uses system package paths:

```text
/Applications/Agent User Status.app
/usr/local/bin/agent-user-status
/usr/local/bin/agent-imessage
/usr/local/bin/agent-user-statusd
```

The helper intentionally does not copy the live
`~/.local/share/agent-imessage` support directory because it can contain local
state, logs, virtual environments, and calibration artifacts. Future signed and
package-manager routes should assemble clean support files from source or build
outputs, not from the operator's runtime state directory.

The product archive should always be built from that disposable staging
directory. Dry-run validation is side-effect free:

```bash
packaging/scripts/build-macos-pkg.sh --dry-run
```

Builds must opt in explicitly:

```bash
packaging/scripts/build-macos-pkg.sh \
  --build \
  --payload-root build/pkg/macos/payload
```

By default, the helper does not sign, notarize, install, start LaunchAgents, or
read secrets. Optional release hooks are controlled through environment
variables:

```bash
AGENT_USER_STATUS_PKG_SIGN_IDENTITY="Developer ID Installer: Example" \
AGENT_USER_STATUS_PRODUCT_SIGN_IDENTITY="Developer ID Installer: Example" \
AGENT_USER_STATUS_NOTARY_PROFILE="agent-user-status-release" \
packaging/scripts/build-macos-pkg.sh --build --payload-root build/pkg/macos/payload
```

Apple ID notarization is also supported with
`AGENT_USER_STATUS_NOTARY_APPLE_ID`, `AGENT_USER_STATUS_NOTARY_PASSWORD`, and
`AGENT_USER_STATUS_NOTARY_TEAM_ID`. Set `AGENT_USER_STATUS_SKIP_STAPLE=1` to
skip stapling after a successful notarization submission.
