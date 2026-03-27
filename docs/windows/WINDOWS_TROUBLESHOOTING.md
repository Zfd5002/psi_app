# Windows Troubleshooting

Use this page for common setup/launch/update issues.

## Setup: Python not found

Symptom:
- bootstrap reports Python was not found.

Action:
1. Re-run `scripts\windows\bootstrap_psi.cmd` and allow it to run the Python installer.
2. If Python download/install still fails, install Python 3.11 manually from python.org.
3. Re-open the PSI folder and re-run bootstrap.

## Setup: unsupported Python version

Symptom:
- bootstrap reports an unsupported Python version.

Action:
1. Let bootstrap run the guided Python installer.
2. If needed, install Python 3.11 manually from python.org.
3. Re-run bootstrap.

## Setup: install location not writable

Symptom:
- bootstrap reports install folder is not writable.

Action:
1. Move PSI to a writable user folder (for example: `Documents\PSI\psi_repo`).
2. Re-run bootstrap.

## Setup: dependency install failure

Symptom:
- bootstrap fails during `pip install -r requirements.txt`.

Action:
1. Confirm internet access.
2. Re-run bootstrap.
3. If failure persists, share the full error text with support.

## Launch: setup missing

Symptom:
- launcher reports `.venv` missing.

Action:
1. Run `bootstrap_psi.cmd`.
2. Re-run launcher.

## Launch: port in use

Symptom:
- launcher reports `port_in_use`.

Action:
1. If PSI is already running, use the opened browser tab.
2. Otherwise close the conflicting app/process and launch PSI again.

## Update: update path not found

Symptom:
- update script cannot find the provided ZIP/folder.

Action:
1. Re-run `update_psi.cmd`.
2. Paste the exact path from File Explorer address bar.

## Update: copy failure

Symptom:
- update reports robocopy failure.

Action:
1. Close PSI if running.
2. Re-run update.
3. If still failing, provide the exact error output to support.

## Heavy compute support boundary

- Core PSI workflows are supported on Windows baseline.
- Heavy compute installation is optional and may fail on some machines.
- Heavy compute failure does not block core PSI usage.
