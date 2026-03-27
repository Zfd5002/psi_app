# Windows Update

This guide covers applying PSI code updates on Windows without Linux tools.

## Update command

Run:

- `scripts\windows\update_psi.cmd`

If no path is passed, the script prompts for an update source path.

Accepted update sources:
- a `.zip` overlay package
- an unpacked overlay folder

## Update behavior

The update helper:
- detects overlay root
- copies update content into the current PSI folder
- preserves local mutable runtime data:
  - `.venv`
  - `uploads` and `psi/uploads`
  - sqlite/db files
  - cache/bytecode files

This keeps local data and local environment intact while applying additive code/script updates.

## Recommended update sequence

1. Close any running PSI window.
2. Run `update_psi.cmd`.
3. Provide update package path when prompted.
4. Wait for completion message.
5. Launch PSI again from desktop shortcut.

## If update fails

Use [Windows Troubleshooting](./WINDOWS_TROUBLESHOOTING.md).
