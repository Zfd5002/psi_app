# APPLY_UPDATE (ZIP overlay workflow)

These steps apply an update ZIP **safely** on top of an existing local install.

## Assumptions

- Your local working directory is: `~/psi_repo`
- Your virtual environment lives at: `~/psi_repo/.venv`
- Your SQLite DB lives at: `~/psi_repo/psi/psi.sqlite`

## Rules

The update ZIP must NOT include:

- `.git/`
- `.venv/`
- `psi/psi.sqlite`

It SHOULD include:

- application code (`psi/`)
- templates / static assets

It MAY exclude:

- vendor code (`vendor/`) — if excluded, rehydrate separately (see Dependencies).

## Apply

From a terminal:

```bash
cd ~/psi_repo

# Inspect contents first
unzip -l /path/to/update.zip | head

# Apply overlay (example)
rsync -av --exclude '.git' --exclude '.venv' --exclude 'psi/psi.sqlite' \
  /path/to/unzipped_update/ ./

# Restart
source .venv/bin/activate
uvicorn psi.web.asgi:app --reload --host 127.0.0.1 --port 8000
```

## Dependencies

After applying an update, you may need to re-install requirements:

Core:

```bash
pip install -r requirements.txt
```

Heavy compute (domains/numbering):

```bash
pip install -r requirements.txt -r requirements-heavy.txt
```

If `vendor/` (ANARCI) is excluded from your update ZIP, rehydrate it:

```bash
./scripts/install_anarci.sh
```

