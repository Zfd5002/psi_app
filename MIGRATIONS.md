
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
