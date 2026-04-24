# macOS pkg Notes

This folder is a metadata scaffold for a signed product archive. The helper at
`packaging/scripts/build-macos-pkg.sh` validates this metadata, emits dry-run
commands by default, and builds only when `--build` is passed.

Safe package assembly should use staged roots and must not overwrite the live
`~/.local` install unless the operator explicitly chooses that target. Prefer a
current-user package root such as:

```text
~/Applications/Agent User Status.app
~/.local/bin/agent-user-status
~/.local/share/agent-imessage
```

The product archive should be built from a disposable staging directory. Dry-run
validation is side-effect free:

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
