# Windows Setup (First-Time)

This guide is for first-time PSI setup on a Windows machine.

## Supported baseline

- Windows 10 or Windows 11
- Internet access for first-time setup (Python/dependency download)
- Writable install folder (for example: `Documents\PSI\psi_repo`)

## One-time setup steps

1. Open the PSI folder in File Explorer.
2. Open `scripts\windows\`.
3. Double-click `bootstrap_psi.cmd`.
4. Wait for setup to finish.

The bootstrap script:
- checks for Python 3.10+ first
- if Python is missing/unsupported, it downloads and runs the official Python installer (guided/passive)
- detects Python (`py -3.11`, then `py -3`, then `python`)
- creates `.venv` if missing
- installs core dependencies from `requirements.txt`
- runs preflight checks for launch imports and schema readiness

## Optional heavy compute setup

Heavy compute is optional in the Windows baseline flow.

To attempt heavy dependency install:
- run `bootstrap_psi.cmd -IncludeHeavyCompute`

If heavy dependencies fail to install, core PSI remains usable.

## Expected success output

At successful completion, bootstrap reports:
- core setup complete
- shortcut installer command
- launcher command

## If setup fails

Use [Windows Troubleshooting](./WINDOWS_TROUBLESHOOTING.md).
