# Windows Smoke Checklist

Use this checklist on a real Windows machine after setup/update.

## Setup smoke

1. Run `scripts\windows\bootstrap_psi.cmd`.
2. Confirm bootstrap completes without error.
3. Confirm `.venv\Scripts\python.exe` exists.

## Launch smoke

1. Run `scripts\windows\install_desktop_shortcut.cmd`.
2. Confirm `PSI` shortcut appears on desktop.
3. Launch PSI from shortcut.
4. Confirm browser opens to local PSI app.
5. Confirm homepage loads.

## Port handling smoke

1. Keep PSI running.
2. Launch PSI again from shortcut.
3. Confirm launcher reports port in use and opens existing app URL.

## Update smoke

1. Close PSI.
2. Run `scripts\windows\update_psi.cmd` with a valid overlay ZIP/folder.
3. Confirm update success message.
4. Re-launch PSI from shortcut.
5. Confirm app still loads and local data remains.

## Support-boundary smoke

1. Use core molecule/program/data workflows.
2. Confirm no Windows-specific blockers for core flow.
3. If heavy compute is needed, test separately and treat as optional support track.
