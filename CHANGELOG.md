# Changelog

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


## v1.1.5
- Batch-first experimental view on molecule detail (SEC-HPLC, BLI/SPR, endotoxin) using existing DataRecord schemas.
- Added SEC_HPLC and Endotoxin schemas; Purity/Aggregation evidence sources now include SEC_HPLC.
- Data entry prefill support for /data/new query params (domain/data_type/method/title).
- Batch ID microcopy updated to TCB001-001 format.
