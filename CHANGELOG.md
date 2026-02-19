## v1.2.6
- Raw File Registry & Provenance foundation:
  - Add provenance fields on `files` (source_kind/source_path/collected_at/imported_at/instrument/operator/run_id/tags_json/notes).
  - Add typed link roles on `file_links` (role/label).
  - Add `file_derivations` table for raw→derived lineage.
- UI:
  - Add Files registry page at `/files` with basic search/filters.
  - Add role + provenance capture on Molecule and Batch file upload forms; show role badges in file tables.

## v1.2.5b
- Hotfix: fix indentation bug in export_wide QC attach block (SyntaxError return outside function).
- Hotfix: ensure scripts/start_psi.sh is executable in overlays.

# Changelog
## v1.2.1
- Molecule detail: make **Property run history** and **Latest run log** collapsible using `<details>` (collapsed by default); `#computed_log` auto-opens the log section.
- Experimental tab: batch-first quick-add (list batches; add SEC/BLI/Endotoxin per batch).
- Assay schema normalization: add `psi/core/assays.py` and surface `result_text` for batch trees and molecule-level records to reduce assay-specific template logic.


## v1.1.0

- Sequence Viewer v2: text-first selectable sequence with aligned numbering rows.
- Unified span-based feature model for Domains + Reference matches (foundation for Engineering/Liabilities).
- Confidence threshold + per-feature enable/disable persisted in localStorage.
- UI footer shows PSI version.

## v1.1.1

- Viewer v2: wrap long component sequences into multiple rows (fixed column width) with feature bars segmented per row to preserve alignment.
- Antibody numbering UX: removed the long "Antibody numbering" list and integrated numbering into Viewer v2.
- Added a collapsed-by-default, wrapped "Numbering map" panel with block/tile layout and per-residue vertical column highlighting.


- Molecule viewer: replaced Index digits with 1-based position ruler (labels 1 and every 10th residue), centered over residues.

## v1.1.2

- Split dependencies into core vs heavy: added `requirements-heavy.txt` and removed heavy scientific deps from `requirements.txt`.
- Added centralized dependency/capability gating (`psi/core/deps.py`) and updated domains + numbering to respect it.
- Introduced "skipped" artifact semantics for heavy compute when disabled/missing deps (no schema change).
- Added per-molecule "Recompute domains" action and made "Compute numbering" idempotent recompute.
- Prevented misleading "success" numbering artifacts when no labels are produced.


## v1.1.6

- Molecule page: batch-first expandable panels with nested Assay → Condition → Runs tree; result summaries shown first (supports multiple conditions/runs per batch).
- Data record entry: standardized condition fields for SEC/SEC-HPLC and SPR/BLI binding; free-text notes preserved.
- Annotations viewer: sequence-only viewer (no Pos or Ab # lanes). Numbering lanes remain only in Numbering Map.

## v1.1.5
- Batch-first experimental view on molecule detail (SEC-HPLC, BLI/SPR, endotoxin) using existing DataRecord schemas.
- Added SEC_HPLC and Endotoxin schemas; Purity/Aggregation evidence sources now include SEC_HPLC.
- Data entry prefill support for /data/new query params (domain/data_type/method/title).
- Batch ID microcopy updated to TCB001-001 format.

## v1.1.9
- Molecule detail: Latest run now shows quick-glance Developability + Immunogenicity summaries; raw computed properties table collapsed by default.
- Sequence risk analyses now holds raw/audit outputs for developability and immunogenicity.

## v1.1.9a
- Hide redundant FAST developability outputs from “All computed properties (raw)” (already summarized in dashboard).


## v1.2.5a (2026-02-19)
- Hotfix: fix SyntaxError in export_wide QC filtering block (indentation / continue outside loop).
