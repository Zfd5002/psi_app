# Windows Launch (Daily Use)

This guide covers normal daily launch after setup is complete.

## Install desktop shortcut (recommended once)

1. Open `scripts\windows\`.
2. Double-click `install_desktop_shortcut.cmd`.

This creates a desktop shortcut named `PSI`.

## Daily launch

- Double-click the `PSI` desktop shortcut.

Equivalent direct launcher command:
- `scripts\windows\launch_psi.cmd`

## Launch behavior

- Launch mode is user mode by default (no reload).
- App entrypoint is `psi.web.asgi:app`.
- Default bind is `127.0.0.1:8000` (unless environment overrides are set).
- Browser auto-open is enabled by default.

## Common launcher outcomes

- Setup missing:
  - Launcher reports `.venv` missing and tells you to run bootstrap.
- Port already in use:
  - Launcher reports port-in-use.
  - If PSI is already running, launcher opens the existing app URL.
- Runtime failure:
  - Launcher reports runtime failure and keeps the window open for the error message.
