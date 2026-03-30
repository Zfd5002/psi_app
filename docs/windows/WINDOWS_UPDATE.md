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

## In-app check-only status (d167)

PSI now supports a safe, read-only update check on the Home page:
- it compares local `PSI_VERSION` with the Windows-user release manifest version
- it does not download updates
- it does not apply updates
- it does not run the updater

Manifest channel source of truth:
- `windows_user_release_manifest.json` on the `windows-user` distribution channel.

Current default manifest URL contract used by app check:
- `https://raw.githubusercontent.com/zach/psi_repo/windows-user/docs/windows/windows_user_release_manifest.json`
- override for deployment if needed: `PSI_WINDOWS_USER_MANIFEST_URL`

Required manifest fields:
- `channel` (must be `windows-user`)
- `version`
- `download_url` (reserved for future phases)
- `sha256` (reserved for future phases)
- `required_assets.desktop_icon`

Desktop icon packaging requirement (release/update contract):
- every Windows-user release/update package must include `assets/windows/psi_desktop_icon.ico`
- shortcut logic must rely on packaged asset, not external runtime icon URLs

## Recommended update sequence

1. Close any running PSI window.
2. Run `update_psi.cmd`.
3. Provide update package path when prompted.
4. Wait for completion message.
5. Launch PSI again from desktop shortcut.

## If update fails

Use [Windows Troubleshooting](./WINDOWS_TROUBLESHOOTING.md).
