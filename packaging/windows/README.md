# Windows Packaging Scaffold

This directory contains an MSIX manifest scaffold for future Windows packaging.
It does not define a runtime implementation and does not change the Python
package.

## Files

- `msix/AppxManifest.xml`: package identity, capabilities, application entry,
  and visual metadata placeholders.

Expected package payload shape:

```text
VFS/
  ProgramFilesX64/
    AgentUserStatus/
      agent-user-status.exe
Assets/
  Square44x44Logo.png
  Square150x150Logo.png
```

The executable can later be provided by a native WinUI 3 shell, a packaged
Python launcher, or a Rust-backed Windows App SDK shell. Do not request broad
device or library capabilities without a reviewed privacy and threat model.

## Validation

Run the repository metadata validator on any host:

```bash
packaging/scripts/validate-packaging.sh windows
```

Use Windows SDK tools on a Windows host for the actual MSIX package and
signature path:

```powershell
MakeAppx.exe validate /v /m .\packaging\windows\msix\AppxManifest.xml
MakeAppx.exe pack /d .\staging /p .\AgentUserStatus.msix
SignTool.exe sign /fd SHA256 /a .\AgentUserStatus.msix
```
