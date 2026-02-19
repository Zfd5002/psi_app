# PSI Patch Notes (append-only)

## 2026-02-18 — v1.2.1
- Improved molecule detail readability with collapsible computed run history and run log.
- Continued standardization of experiment inputs/results to support safer downstream tooling.

## 2026-02-18 — v1.2.3c
- Stabilized measurement extraction + storage and centralized "primary measurement" selection.
- Added explicit, env-gated CSV export (with filters + wide-ish primary_* columns).
- Added CLI-only backfill + QC tools (SAFE defaults; idempotent behavior).
- Added localStorage remember-state for run history/log collapsibles.
