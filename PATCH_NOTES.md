## v1.2.5b
- Hotfix: fix indentation bug in export_wide QC attach block (SyntaxError return outside function).
- Hotfix: ensure scripts/start_psi.sh is executable in overlays.

# PSI Patch Notes (append-only)


## 2026-02-19 — v1.2.5a
- QC & Governance foundation:
  - New append-only QC event log for measurements (`measurement_qc_events`) with reviewer attribution.
  - Latest-state QC cache (`measurement_qc`) for fast UI badges.
  - Data record detail: show extracted measurements and allow minimal QC review actions.
  - Molecule batch panels: show per-batch QC counts (pending/rejected/quarantined).
- Exporter: `psi/scripts/export_wide.py` supports `--qc-mode none|model_safe|strict` (default `none`).


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

## 2026-02-19 — v1.2.4a
- Export: --as-of leakage-safe wide export + ignore_for_model QC flag
- DecisionSnapshot: add as_of_ts + notes; add OutcomeLabel table for supervised outcomes
- Release: bump_version helper can update footer version automatically

## v1.2.5a (2026-02-19)
- Hotfix: fix SyntaxError in export_wide QC filtering block (indentation / continue outside loop).

## 2026-02-19 — v1.2.6
- Raw File Registry & Provenance foundation:
  - Files: add provenance metadata columns (source_kind, source_path, collected_at, imported_at, instrument, operator, run_id, tags_json, notes).
  - File links: add typed link roles + optional label (raw_input, processed_output, report, plot, protocol, other).
  - Provenance graph: introduce file_derivations (parent→child) with optional transform/tool metadata.
  - UI: add /files registry page with basic search + source_kind/sha prefix filters and deterministic ordering.
  - UI: attachment lists display role badges; key upload forms capture role + provenance fields.
  - CLI: add import-from-path helper (python -m psi.scripts.import_file) to register and link local raw files.

## 2026-02-19 — v1.2.7
- Molecule detail (batch-first): add QC selection mode toggle (All / Model-safe / Approved-only) that affects batch headline metric selection.
- Molecule detail: show minimal per-run QC badges in batch tables when runs contain pending/rejected/quarantined measurements.
- Performance: avoid per-batch measurement count queries by computing counts in a single grouped query.
