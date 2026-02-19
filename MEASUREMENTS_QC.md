# Measurements + QC (v1.2.3c)

PSI stores extracted scalar results in `data_measurements` (SQLite) using SQL reflection (no ORM mapping).

## Primary measurement selection

Single source of truth:

- `psi.services.measurements.get_primary_measurement_for_record(db, record_id, include_qc=False)`

Rules:
- Always query DB (no relationship preload assumptions).
- If an `is_primary`-like column exists, prefer rows where it is `1`.
- Otherwise choose deterministically via stable ordering.
- QC-flagged rows are excluded by default when a QC flag column exists.

## Export

Explicitly gated by env var:
- `PSI_ENABLE_EXPORT=1`

Export module:
- `psi.tools.export_measurements.export_csv(...)`

`wide=True` adds stable `primary_*` columns sourced from the primary-measurement helper.

## Backfill

CLI-only tool (SAFE by default):
- `python -m psi.tools.backfill_measurements --dry-run`

Notes:
- Default: no overwrites.
- `--force-overwrite` is explicit.
- Intended to be idempotent and resilient to partial failures.

## QC

CLI-only tool (conservative):
- `python -m psi.tools.qc_measurements --dry-run`

Notes:
- No save-time QC.
- Idempotent: only flags when currently unflagged.
