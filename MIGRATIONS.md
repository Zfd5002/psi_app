## v1.2.5b
- Hotfix: fix indentation bug in export_wide QC attach block (SyntaxError return outside function).
- Hotfix: ensure scripts/start_psi.sh is executable in overlays.


## v1.2.5a (2026-02-19)
- Add QC governance tables (additive):
  - `measurement_qc_events` (append-only)
  - `measurement_qc` (latest-state cache)
- No destructive changes to `data_measurements` (legacy fields remain).
- Wide exporter: add `--qc-mode none|model_safe|strict` (default `none`, no behavior change unless explicitly set).

## v1.2.3g1 (2026-02-19)
- No new migration steps. Ensures `data_measurements` table exists on fresh DB creation.

# MIGRATIONS

## v1.1.0

- **Database migrations:** none required.
- Existing databases (`psi/psi.sqlite`) remain compatible.

Notes:
- v1.1.0 adds an additional field (`labels_by_raw_index`) inside the cached numbering artifact payload (JSON). This does **not** change the DB schema.

## v1.1.1

- **No database migrations required.**


## v1.2.3g

- **Additive migration (auto-applied on startup):** If your DB already has the `data_measurements` table, PSI will add the following nullable provenance columns (if missing):
  - `producer`, `producer_version`, `source_path`, `run_id`, `produced_at`, `notes`

Notes:
- PSI remains compatible with older DBs that do not have these columns.
- If `data_measurements` does not exist in your DB, PSI will not create it (no destructive changes).

## 2026-02-19 — v1.2.4a
- data_measurements: add ignore_for_model (INTEGER NOT NULL DEFAULT 0)
- decision_snapshots: add as_of_ts, notes
- new table: outcome_labels (snapshot_id, name, value_*)
- export_wide: add --as-of leakage-safe selection (produced_at/created_at <= as_of)


### v1.2.5a (2026-02-19)
- No schema changes. Exporter hotfix only.
