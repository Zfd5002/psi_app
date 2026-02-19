# PSI Patch Notes (append-only)

## 2026-02-18 — v1.2.3f
- UI (molecule detail): add Data Overview (counts + lightweight aggregates) and show batch header headline results.
- UI (molecule detail): move unbatched records into a final “Unassigned” batch panel (batch-first everywhere).
- Deterministic ordering for batch panels and run lists; null-safe rendering and JS (no migrations).

## 2026-02-18 — v1.2.1
- Improved molecule detail readability with collapsible computed run history and run log.
- Continued standardization of experiment inputs/results to support safer downstream tooling.

## 2026-02-18 — v1.2.3c
- Stabilized measurement extraction + storage and centralized "primary measurement" selection.
- Added explicit, env-gated CSV export (with filters + wide-ish primary_* columns).
- Added CLI-only backfill + QC tools (SAFE defaults; idempotent behavior).
- Added localStorage remember-state for run history/log collapsibles.

## 2026-02-18 — v1.2.3d
- Packaging: harden overlay ZIP exclusions (vendor/caches)
- Release: add bump_version helper + smoke_test guardrail
- UI: molecule-scoped <details> persistence + batch expand/collapse

## 2026-02-18 — v1.2.3e
- Measurements: formalize schema-tolerant inserts (PRAGMA-driven, per-DB cache, conservative NOT NULL fallbacks)
- Measurements: add internal self-check to prevent mismatched insert columns/binds
- Smoke test: add compatibility matrix for alternate measurement schemas (numeric-only, text-only, deterministic primary)
- Export: deterministic ordering when data_records.created_at is NULL
- Packaging: exclude editor/backup artifacts from overlay ZIPs

## 2026-02-18 — v1.2.3f
- UI: Molecule detail is batch-first with a Data Overview summary and expandable batch panels showing headline results.
- Deterministic ordering for batches and records; unbatched records appear under an Unassigned panel.
- No migrations.

## 2026-02-19 — v1.2.3g
- Measurements: introduce export-first measurement registry (canonical keys, aliases, deterministic export naming).
- Export: add deterministic registry-driven wide/pivot CSV exporter (CLI: python -m psi.scripts.export_wide).
- Measurements: add additive per-measurement provenance columns on data_measurements (producer, producer_version, source_path, run_id, produced_at, notes).
- Packaging: rsync overlay now excludes vendor/ (ANARCI rehydrate stays via scripts/install_anarci.sh); docs updated.

## 2026-02-19 — v1.2.3g1
- Hotfix: ensure `data_measurements` table exists for fresh DBs (smoke_test + measurement upsert).
- Hotfix: overlay apply script no longer uses rsync --delete (prevents accidental deletion of local-only paths like vendor/).

## 2026-02-19 — v1.2.3g2
- Measurement system evolution (export-ready): schema-driven registry + deterministic wide exporter + per-measurement provenance (additive, backward compatible).
- Overlay workflow hardening: apply script no longer deletes local-only directories; safer rsync behavior.
