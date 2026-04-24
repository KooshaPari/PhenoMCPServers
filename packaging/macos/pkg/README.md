# macOS pkg Notes

This folder is a metadata scaffold for a future signed product archive.

Safe package assembly should use staged roots and must not overwrite the live
`~/.local` install unless the operator explicitly chooses that target. Prefer a
current-user package root such as:

```text
~/Applications/Agent User Status.app
~/.local/bin/agent-user-status
~/.local/share/agent-imessage
```

The product archive should be built from a disposable staging directory:

```bash
pkgbuild \
  --identifier com.phenotype.agent-user-status.pkg \
  --version 0.1.0 \
  --root /tmp/agent-user-status-pkg-root \
  /tmp/agent-user-status.pkg

productbuild \
  --distribution packaging/macos/pkg/Distribution.xml \
  --package-path /tmp \
  /tmp/AgentUserStatus.pkg
```

Signing, notarization, icon assets, and installer HTML resources are intentionally
left out until release ownership is defined.
