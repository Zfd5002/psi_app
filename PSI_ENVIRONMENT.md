# PSI Environment (Local Workspace Contract)

This document defines the canonical directories and hygiene rules for PSI on this machine.

## Canonical working directories

### 1) Primary repo (git)
- Path: `~/psi_repo`
- Purpose: canonical PSI source-of-truth working tree (the thing we ship / tag / push)

### 2) Codex sandbox (non-git)
- Path: `~/psi_codex`
- Purpose: scratch / experiments / sanity runs / verification runs
- Rule: Prefer running sanity + verification checks here **before** overlaying changes into `~/psi_repo`.

## Non-canonical working areas (allowed, but not authoritative)

- `~/psi_overlays/`  
  Temporary staging area for unpacked overlay ZIPs (should be safe to delete any time).

- `~/psi_updates/`  
  Historical update work products (not canonical; keep only if actively used).

- `~/psi_stage*`  
  Transitional staging directories (not canonical; keep minimal).

## Archives (authoritative cold storage)

All large/old/incident artifacts live under:

- `~/psi_archives/`
  - `incidents/` : post-mortems (e.g., bad rsync trees) — keep trimmed (no `.venv`)
  - `cold_git_backups/` : compressed git working copies (tar.zst) for true checkpoints
  - `duplicates/` : compressed historical duplicates, then delete the expanded trees
  - `downloads/` : bundles of old overlay/patch ZIPs (tar.zst), then delete `~/Downloads/psi*`

## Hygiene rules

1. Never keep `.venv/` inside any archived repo tree.
2. Never rsync with `--delete` unless the source is a known-good overlay directory (and `.git/` is excluded).
3. Keep `~/Downloads` clean:
   - Bundle historical PSI artifacts into `~/psi_archives/downloads/*.tar.zst`
   - Then delete `~/Downloads/psi*`
4. SQLite DB artifacts are not part of overlays:
   - Never ship `psi/psi.sqlite`, `psi/psi.sqlite-wal`, `psi/psi.sqlite-shm` in update ZIPs.

## Update workflow invariant (codex-first)

1) Validate in codex:
- Make changes and run sanity/verification checks inside `~/psi_codex`

2) Overlay into repo:
- Apply only the minimal patch/overlay into `~/psi_repo` (rsync overlay-safe)

3) Verify in repo:
- Re-run the same verification checks in `~/psi_repo`

4) Archive:
- Compress and store legacy/incident/download artifacts under `~/psi_archives/`
