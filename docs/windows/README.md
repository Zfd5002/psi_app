# PSI on Windows

This folder contains end-user and support documentation for Windows use of PSI.

Use these guides in order:

1. [Windows Setup](./WINDOWS_SETUP.md)
2. [Windows Launch](./WINDOWS_LAUNCH.md)
3. [Windows Update](./WINDOWS_UPDATE.md)
4. [Windows Troubleshooting](./WINDOWS_TROUBLESHOOTING.md)
5. [Windows Smoke Checklist](./WINDOWS_SMOKE_CHECKLIST.md)

Windows-user release manifest contract:
- `windows_user_release_manifest.json` is the update-channel source of truth for in-app check-only status.
- Releases must package the desktop icon asset path declared by the manifest (`assets/windows/psi_desktop_icon.ico`).

Support boundary (current phase):
- Core PSI workflow is supported on Windows via scripts under `scripts/windows/`.
- Heavy compute (ANARCI/domain-heavy workflows) is optional and may require additional machine-specific setup.

Setup note:
- `bootstrap_psi.cmd` now handles Python acquisition/install when Python 3.10+ is missing.
