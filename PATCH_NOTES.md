## 2026-03-03 — v1.3.0b5
Why:
- Harden fact-sheet replay guardrails with explicit schema/ordering invariants and prevent regressions where view-time DB dependence could re-enter molecule board rendering.

What:
- Kept fact-sheet rendering path payload-driven and retained no-view-time-query guard test coverage.
- Added schema invariant coverage for fact-sheet matrix cell contract:
  - each cell must include `status`, `display`, `measurement_id`, and `data_record_id`.
- Added deterministic ordering invariant coverage:
  - `batch_registry` ordering contract
  - `metrics_index.required_metric_keys` ordering
  - `best_batch.trace` score ordering
- Expanded targeted test coverage in `tests/test_v3_molecule_report_schema.py`:
  - `test_fact_sheet_cell_schema_invariants`
  - `test_fact_sheet_ordering_invariants`

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_v3_molecule_report_schema.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

## 2026-03-03 — v1.3.0b4
Why:
- Persist deterministic stability status from fact-sheet batch coverage so molecule board reports carry replayable stability outcomes without snapshot-time recomputation.

What:
- Added named stability constants in `psi/services/fact_sheet.py`:
  - `_STABILITY_MIN_BATCHES_WITH_REQUIRED = 2`
  - `_STABILITY_MAX_REGRESSION_REQUIRED_PRESENT = 2`
- Implemented `stability.method = "coverage_only_v1"` persisted at report write-time:
  - `insufficient_data` when fewer than minimum batches have required coverage
  - `unstable` when a later batch regresses required coverage by threshold
  - `stable` otherwise
- Added deterministic rationale serialization and ordering in `stability.rationale`.
- Added targeted stability regression tests:
  - `test_stability_insufficient_with_one_batch`
  - `test_stability_unstable_on_regression_threshold`
  - `test_stability_not_snapshot_dependent`
- Updated schema assertions to validate filled stability fields while preserving field shape.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/fact_sheet.py`
- `tests/test_v3_molecule_report_schema.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

## 2026-03-03 — v1.3.0b3
Why:
- Persist deterministic best-batch selection in fact-sheet payload so board rendering is replayable and auditable without view-time recomputation.

What:
- Implemented best-batch computation in `psi/services/fact_sheet.py`:
  - `best_batch.selection_method = "coverage_score_v1"`
  - Lexicographic score tuple:
    1. `required_present_count`
    2. `total_present_count`
    3. recency (`created_at` when parseable, else `batch_id`)
    4. `batch_id`
  - Persisted `best_batch.status="computed"`, `selected_batch_id`, and stable-ordered `trace[]` with per-candidate score and counts.
- Added deterministic regression tests:
  - `test_best_batch_tiebreak_deterministic`
  - `test_best_batch_trace_persisted_and_sorted`
- Updated schema assertions to validate filled `best_batch` values while preserving placeholder shape contract.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/fact_sheet.py`
- `tests/test_v3_molecule_report_schema.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

## 2026-03-03 — v1.3.0b2
Why:
- Persist molecule fact-sheet surfaces at report generation time so molecule report rendering is replayable from `report_runs.payload_json` and does not depend on live DB recomputation.

What:
- Added write-time fact-sheet assembler:
  - `psi/services/fact_sheet.py::assemble_molecule_fact_sheet(...)`
  - Persists deterministic `sections.fact_sheet` with locked schema:
    - `schema_version`, `meta`, `metrics_index`, `batch_registry`, `metric_matrix`, `coverage_summary`, `best_batch`, `stability`
- Wired molecule report generation to persist fact-sheet payload:
  - `psi/services/report_engine.py::generate_molecule_report_v0(...)`
  - `metrics_index.template_ids_used` and `metrics_index.required_metric_keys` persisted deterministically.
  - Matrix cells now resolve deterministic measurement values/units from `data_measurements` with traceability ids.
  - Batch registry includes deterministic `latest_notes` snapshot from record ordering.
- Hardened report schema contracts:
  - Molecule `_empty_sections_for_type(...)` and payload validation now include `fact_sheet`.
- Switched molecule board display shaping to payload-first formatter path:
  - `psi/services/reports_v3.py` fact-sheet display uses persisted payload structure rather than live recomputation.
- Replaced previously skipped V3 tests with active deterministic coverage:
  - `tests/test_v3_molecule_report_schema.py`
  - `tests/test_v3_board_report_determinism.py`
  - Updated `tests/test_v3_report_contracts.py` for required `fact_sheet`.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/fact_sheet.py`
- `psi/services/report_engine.py`
- `psi/services/reports_v3.py`
- `tests/test_v3_molecule_report_schema.py`
- `tests/test_v3_board_report_determinism.py`
- `tests/test_v3_report_contracts.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

## 2026-03-03 — pre-b2 cleanup (no version bump)
Why:
- Remove low-risk divergence traps before introducing persisted fact-sheet assembly in b2.

What:
- Canonicalized safe JSON parsing for report code paths:
  - added `psi/services/json_helpers.py::safe_json_dict(...)`
  - routed report modules to this helper:
    - `psi/services/report_engine.py`
    - `psi/services/reports_v3.py`
    - `psi/services/program_rollups.py`
- Canonicalized metric grouping path for report display:
  - added `psi/services/metric_catalog.py::metric_group_for_key(...)` (catalog-backed with deterministic fallback)
  - removed ad-hoc grouping logic from `psi/services/reports_v3.py` and switched to canonical helper.

Files changed:
- `PATCH_NOTES.md`
- `psi/services/json_helpers.py`
- `psi/services/metric_catalog.py`
- `psi/services/report_engine.py`
- `psi/services/reports_v3.py`
- `psi/services/program_rollups.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

## 2026-03-03 — v1.3.0b1
Why:
- Start b-series board template workstream with a deterministic, batch-aware molecule report layout for meeting-ready fact sheet + conclusions rendering.

What:
- Redesigned molecule board template `psi/web/templates/reports/board_molecule_v3.html` to render:
  - Molecule fact sheet header
  - Conclusions block (readiness, best batch, comparability, stability, blockers, governance/QC warnings, deterministic executive paragraph)
  - Batch registry table
  - Gate summary (best-batch gate matrix + per-batch snapshot)
  - Experimental results fact sheet matrix (rows=metrics, cols=batches, deterministic ordering)
  - Structured comparability block
  - Risk & QC summary bullets
  - Scientist Notes section with deterministic placeholder
- Added display-only deterministic shaping in `psi/services/reports_v3.py`:
  - `_build_molecule_board_display(...)` derives batch-aware board surfaces from existing report payload + existing snapshot/data-record data.
  - No DI semantic changes and no report fingerprint/snapshot contract changes.
  - `get_report_run_detail(...)` now injects `molecule_board_display` for template rendering.
- Added minimal layout support for matrix overflow safety in print/web:
  - `psi/web/static/style.css` (`.table-scroll-safe`).
- Updated template regression coverage:
  - `tests/test_board_molecule_sections_rendering.py` now asserts new section headings and deterministic metric ordering.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/reports_v3.py`
- `psi/web/templates/reports/board_molecule_v3.html`
- `psi/web/static/style.css`
- `tests/test_board_molecule_sections_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

## 2026-03-03 — v1.3.0a130
Why:
- Eliminate comparability policy-source drift (`v0.1` vs latest) across assessment/effective-resolution/report surfaces for governance consistency.

What:
- Unified active comparability policy loading in `psi/services/comparability.py`:
  - `_load_comparability_policy()` now resolves the canonical `comparability_policy_v0_2.json` and validates once through cache.
  - `load_comparability_policy_latest()` now returns the same canonical loader output.
- Unified assessment/effective-resolution policy usage:
  - `create_comparability_assessment(...)` now uses canonical policy id/version defaults from the loaded policy.
  - `get_effective_comparability(...)` now resolves categories against canonical allowed statuses.
- Preserved deterministic legacy input compatibility to avoid caller breakage while removing policy-version drift:
  - status aliases: `comparable -> comparable_full`, `conditionally_comparable -> comparable_partial`.
  - rule alias: `placeholder_not_assessed` maps deterministically to canonical v0.2 rule ids by status.
- Added deterministic regression tests in `tests/test_comparability_resolution.py`:
  - active loader matches latest policy id/version
  - create-assessment defaults policy pins to latest and canonicalizes legacy aliases
  - effective-resolution category uses latest allowed-status order

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/comparability.py`
- `tests/test_comparability_resolution.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

## 2026-03-03 — v1.3.0a126
Why:
- Add scientist bulk-review controls on Program landing page to process all pending review-queue records quickly.

What:
- Added program-level bulk review endpoints in `psi/web/routers/programs.py`:
  - `POST /programs/{program_id}/review/approve-all`
  - `POST /programs/{program_id}/review/reject-all`
  - Reuses existing per-record bulk QC helper (`apply_bulk_qc_action_for_record`).
  - Pending records sourced from existing `build_program_review_queue(...)`.
  - Deterministic processing order: sorted `record_id` ascending.
- Updated `psi/web/templates/programs/detail.html`:
  - Added top-of-section buttons/forms:
    - `Approve all pending`
    - `Reject all pending`
  - Uses `request.url_for(...)`.
  - Buttons render only when pending queue contains at least one record.
- Extended deterministic tests in `tests/test_program_review_queue.py`:
  - route existence for both new POST endpoints
  - template renders/hides bulk buttons based on pending queue
  - integration-style endpoint test verifying approve-all drains pending queue.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/programs.py`
- `psi/web/templates/programs/detail.html`
- `tests/test_program_review_queue.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DB schema/migration changes.
- No DI/snapshot/hash/replay/routing semantic changes.

## 2026-03-03 — v1.3.0a125
Why:
- Improve scientist review UX on Program landing page by preserving scroll position after Approve/Reject actions.

What:
- Updated `psi/web/templates/programs/detail.html` review queue rows:
  - Added stable row anchors: `id="record-{{ row.record_id }}"`.
  - Added reject action form alongside approve in review queue actions.
  - Added `review-queue-action-form` + `data-record-id` attributes for action forms.
- Added small deterministic vanilla JS (template-local):
  - On approve/reject submit, stores `window.scrollY` and record id in `sessionStorage`.
  - On page load, restores to `#record-<id>` if present (center), else restores scrollY.
  - Clears stored values after restore.
  - Uses normal form submits (no AJAX/fetch).
- Updated deterministic template test:
  - `tests/test_program_review_queue.py`
  - asserts approve/reject URLs, row anchor presence, and script marker strings.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/programs/detail.html`
- `tests/test_program_review_queue.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- UI/template only; no DB/schema/DI/snapshot/hash/replay/routing semantic changes.

## 2026-03-03 — v1.3.0a124
Why:
- Resolve runtime test regression caused by repo drift where `data/form.html` lacked edit-mode `Approve`/`Reject` entry controls.

What:
- Confirmed parity:
  - `psi_codex` passes `test_data_form_template_renders_save_cancel_approve_reject_for_edit`
  - `psi_repo` fails the same test.
- Root cause: `psi_repo/psi/web/templates/data/form.html` was behind `psi_codex` and only rendered `Save/Cancel`, while the test expects edit workflow controls (`Save/Cancel/Approve/Reject`).
- Hotfix keeps intended scientist UX by preserving edit-mode buttons and hidden action intent fields in `data/form.html` (no behavior change to DI or routing).
- Added a small template comment to lock the intent of those controls for maintainability.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/data/form.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DB schema/migration changes.
- No DI/snapshot/hash/replay/ranking behavior changes.

## 2026-03-03 — v1.3.0a123
Why:
- Hotfix program landing QC actions returning 404 for Approve/Reject entry actions.

What:
- Ensured QC bulk action routes are explicitly exposed on both canonical and alias paths:
  - `POST /data/{record_id}/qc/approve`
  - `POST /data/{record_id}/qc/reject`
  - `POST /data-records/{record_id}/qc/approve` (alias)
  - `POST /data-records/{record_id}/qc/reject` (alias)
  - in `psi/web/routers/data_records.py` using existing bulk-QC service logic.
- Updated templates to use `url_for()` instead of hardcoded strings:
  - `psi/web/templates/programs/detail.html`
  - `psi/web/templates/data/detail.html`
- Added deterministic route existence regression test:
  - `tests/test_data_record_qc_routes.py`
- Updated template tests to provide deterministic `request.url_for` stubs:
  - `tests/test_data_record_template_actions.py`
  - `tests/test_program_review_queue.py`

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/data_records.py`
- `psi/web/templates/programs/detail.html`
- `psi/web/templates/data/detail.html`
- `tests/test_data_record_qc_routes.py`
- `tests/test_data_record_template_actions.py`
- `tests/test_program_review_queue.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DB schema/migration changes.
- No DI semantic/snapshot/hash/replay/ranking changes.

## 2026-03-03 — v1.3.0a122
Why:
- Hotfix mixed/legacy `data_measurements` schemas where both `metric_key` and required `name` exist.

What:
- Fixed measurement upsert compatibility in `psi/services/measurements.py`:
  - insert path now populates both physical columns when both exist:
    - canonical key column (`metric_key` or mapped name column)
    - legacy required `name` column
  - safe update path now backfills blank alias key columns (`name`/`metric_key`) only, without overwriting populated values.
  - row lookup for upsert is robust across mixed schemas:
    - when matching by `metric_key`, also matches legacy `name` fallback (and vice versa).
- Added deterministic regression test:
  - `tests/test_measurements_mixed_schema_compat.py`
  - verifies `create_data_record -> upsert_measurements` writes both `name` and `metric_key` when both columns are present.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/measurements.py`
- `tests/test_measurements_mixed_schema_compat.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DB schema/migration changes.
- No DI semantic/snapshot/hash/replay/ranking changes.

## 2026-03-03 — v1.3.0a121
Why:
- Hotfix runtime SQL bug causing `/programs/{id}` 500 (`sqlite3.OperationalError: no such column: dm.name`).

What:
- Fixed `data_measurements` column reference from `dm.name` to `dm.metric_key` in:
  - `psi/services/programs.py` (`build_program_review_queue` metric query)
  - `psi/services/evidence_preview.py` (`_record_metric_keys` query)
- Preserved deterministic ordering:
  - `ORDER BY ... dm.metric_key ASC, dm.id ASC`
- No refactor and no behavior change beyond schema-correct column usage.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/programs.py`
- `psi/services/evidence_preview.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DB schema/migration changes.
- No DI semantic/snapshot/hash/replay/ranking changes.

## 2026-03-03 — v1.3.0a120
Why:
- Add scientist-facing Evidence Preview surfaces that feel automatic after entry capture while remaining read-only and DI-safe.

What:
- Added deterministic Evidence Preview service helper:
  - `psi/services/evidence_preview.py`
  - compares record `data_measurements.name` keys vs latest DI snapshot `used_by_metric` for the molecule.
  - emits stable rows sorted by `domain -> label -> metric_key` with statuses:
    - `New vs last snapshot`
    - `Already present`
- Wired record-level preview into data-record detail context:
  - `psi/services/data_records.py::get_data_record_detail(...)` now includes `evidence_preview`.
- Wired molecule-level pending preview:
  - `psi/services/molecules.py::get_molecule_detail(...)` now includes `pending_evidence_preview`.
  - `psi/web/templates/molecules/detail.html` renders compact pending preview counts per record.
- Extended program review queue with short evidence preview:
  - `psi/services/programs.py::build_program_review_queue(...)` now adds:
    - `evidence_preview_short`
    - `evidence_preview` (full derived payload for optional future rendering)
  - `psi/web/templates/programs/detail.html` adds `Evidence preview` column.
- Updated data-record detail template:
  - `psi/web/templates/data/detail.html` now renders primary `Evidence Preview` section.
- Added deterministic tests:
  - `tests/test_evidence_preview.py`
  - verifies ordering + new-vs-existing logic and pending-record filtering behavior.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/evidence_preview.py`
- `psi/services/data_records.py`
- `psi/services/molecules.py`
- `psi/services/programs.py`
- `psi/web/templates/data/detail.html`
- `psi/web/templates/molecules/detail.html`
- `psi/web/templates/programs/detail.html`
- `tests/test_evidence_preview.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Presentation-only, read-only evidence comparison.
- No DI semantic/policy/ranking/snapshot/hash/replay changes.
- No DB schema/migration changes.

## 2026-03-03 — v1.3.0a119
Why:
- Complete scientist edit workflow wiring (Save/Cancel/Approve/Reject) and add deterministic top-to-bottom form autofill helpers.

What:
- Fixed `update_data_record(...)` run-date handling in `psi/services/data_records.py`:
  - derives `run_date` from `run_at` when needed (matching create path behavior).
- Enhanced edit-form workflow wiring in `psi/web/templates/data/form.html`:
  - hidden deterministic intent field (`action_intent`)
  - explicit buttons: `Save`, `Cancel`, `Approve`, `Reject`
  - `return_to` support retained for queue-driven navigation.
- Added deterministic UI autofill helper in form JS:
  - `Apply defaults to all rows` button
  - copies top-section parameter defaults into result fields only when target is empty
  - no server-side semantic changes.
- Added/updated tests:
  - `tests/test_data_record_bulk_qc.py` adds run-date derivation regression test
  - `tests/test_data_record_template_actions.py` asserts new action/autofill controls render.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/data_records.py`
- `psi/web/templates/data/form.html`
- `tests/test_data_record_bulk_qc.py`
- `tests/test_data_record_template_actions.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Workflow/UI improvements only; no DI semantic/snapshot/hash/replay changes.
- No DB schema/migration changes.

## 2026-03-03 — v1.3.0a118
Why:
- Add a deterministic scientist review queue on program landing pages so pending data records can be approved or edited per molecule.

What:
- Added service-layer queue builder in `psi/services/programs.py`:
  - `build_program_review_queue(db, program_id=...)`
  - groups pending records by molecule in stable order
  - pending criteria: measurement QC not fully approved (or no extracted measurements)
  - includes deterministic preview snippet built from record metric keys.
- Integrated queue into program detail context:
  - `get_program_detail(...): review_queue_by_molecule`
- Updated `psi/web/templates/programs/detail.html` with new “Review data entries” section:
  - grouped by molecule
  - row fields: created, batch, assay key, preview snippet
  - actions: `Approve` (bulk entry approve) and `Edit entry`.
- Added deterministic tests:
  - `tests/test_program_review_queue.py`
  - validates queue grouping/filtering and template render ordering/action links.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/programs.py`
- `psi/web/templates/programs/detail.html`
- `tests/test_program_review_queue.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Presentation/workflow layer only; no DI semantics/snapshot/hash/replay changes.
- No DB schema/migration changes.

## 2026-03-03 — v1.3.0a117
Why:
- Add one-click per-entry QC review actions for scientists while keeping existing per-measurement QC storage and semantics intact.

What:
- Added deterministic bulk QC service helper in `psi/services/data_records.py`:
  - `apply_bulk_qc_action_for_record(...)`
  - supports `approve` and `reject` across all measurements in a record
  - idempotent behavior: already-target-state measurements are skipped (no-op)
- Added data-record bulk QC endpoints in `psi/web/routers/data_records.py`:
  - `POST /data/{id}/qc/approve`
  - `POST /data/{id}/qc/reject`
- Extended edit submission flow in `psi/web/routers/data_records.py`:
  - supports `action_intent` values `save|approve|reject`
  - `approve|reject` performs save then bulk QC action.
- Updated templates:
  - `psi/web/templates/data/detail.html` adds prominent per-entry `Approve entry` / `Reject entry` actions above measurement-level review.
  - `psi/web/templates/data/form.html` adds `Save`, `Cancel`, `Approve`, `Reject` buttons for edit workflow wiring.
- Added deterministic tests:
  - `tests/test_data_record_bulk_qc.py`
  - `tests/test_data_record_template_actions.py`

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/data_records.py`
- `psi/web/routers/data_records.py`
- `psi/web/templates/data/detail.html`
- `psi/web/templates/data/form.html`
- `tests/test_data_record_bulk_qc.py`
- `tests/test_data_record_template_actions.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Uses existing QC actions/statuses only; no DI/replay/ranking/snapshot/hash behavior changes.
- No DB schema/migration changes.

## 2026-03-03 — v1.3.0a116
Why:
- Surface the new additive molecule `scientific_summary` payload in board templates for meeting-ready scientific review.

What:
- Updated molecule board template:
  - `psi/web/templates/reports/board_molecule_v3.html`
  - Added `Scientific Summary` section grouped by domain.
  - Renders deterministic table columns: `Metric | Value | Unit | Status | N`.
- Added minimal comparative board support (derived-only from existing comparative payload rows):
  - `psi/web/templates/reports/board_comparison_v3.html`
  - Added per-molecule `Scientific Summary` section based on `present_measurement_keys`.
- Added/updated deterministic template tests:
  - `tests/test_board_molecule_sections_rendering.py`
  - `tests/test_board_comparison_alignment_rendering.py`
  - verifies section headings and representative rendered content.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/board_molecule_v3.html`
- `psi/web/templates/reports/board_comparison_v3.html`
- `tests/test_board_molecule_sections_rendering.py`
- `tests/test_board_comparison_alignment_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS
- `python -m psi.tools.ui_label_audit` — PASS

Guarantees:
- Template/display-layer rendering only.
- No DI semantic/policy/ranking/replay/snapshot/fingerprint behavior changes.
- No DB schema/migration changes.

## 2026-03-03 — v1.3.0a115
Why:
- Add a deterministic, template-friendly molecule `scientific_summary` payload section derived from existing snapshot evidence coverage.

What:
- Added additive molecule report section key:
  - `sections.scientific_summary`
- Updated report engine molecule section scaffold/validation path:
  - `psi/services/report_engine.py::_empty_sections_for_type()`
  - `psi/services/report_engine.py::generate_molecule_report_v0()`
- Added deterministic scientific summary builder in report engine:
  - derives rows from `used_by_metric`
  - joins with metric catalog metadata from `metric_catalog_entry(...)`
  - emits:
    - `scientific_summary.status`
    - `scientific_summary.domains[]`
    - per-row `{metric_key,label,value_display,unit,n,status}`
  - stable ordering:
    - domain (alphabetical)
    - row order (`sort_order`, `label`, `metric_key`)
- Added deterministic tests:
  - updated `tests/test_v3_report_contracts.py` for additive section key
  - new `tests/test_scientific_summary_report.py` for ordering/content stability.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `tests/test_v3_report_contracts.py`
- `tests/test_scientific_summary_report.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS
- `python -m psi.tools.ui_label_audit` — PASS

Guarantees:
- Additive report payload surface only.
- No DI semantic/policy/ranking/replay/snapshot/fingerprint behavior changes.
- No DB schema/migration changes.

## 2026-03-03 — v1.3.0a114
Why:
- Introduce a deterministic metric catalog layer to support scientist-readable summaries without changing DI/report semantics.

What:
- Added deterministic metric catalog data file:
  - `psi/data/metric_catalog_v1.json`
  - Includes stable `metric_key -> {label, domain, unit, sort_order, notes}` entries.
- Added loader service:
  - `psi/services/metric_catalog.py`
  - `load_metric_catalog_v1()` with stable-key normalization and deterministic defaults.
  - `metric_catalog_entry(metric_key)` fallback behavior:
    - `label=humanize_key(metric_key)`
    - `domain=Other`
    - `unit=""`
    - `sort_order=9999`
    - `notes=""`
- Added deterministic unit tests:
  - `tests/test_metric_catalog.py`
  - validates stable loader output and fallback behavior.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/data/metric_catalog_v1.json`
- `psi/services/metric_catalog.py`
- `tests/test_metric_catalog.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS
- `python -m psi.tools.ui_label_audit` — PASS

Guarantees:
- Data/loader addition only; no DI semantic/policy/ranking/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-03 — v1.3.0a113
Why:
- Improve scientist-facing readability on UI surfaces by humanizing state/path tokens and removing visible underscore artifacts without changing payload semantics.

What:
- Extended `psi/web/ui_labels.py` with deterministic presentation helpers:
  - `humanize_state(value)`
  - `humanize_path_token(value)`
  - shared `humanize_slug_or_token(value)`
- Added deterministic state override:
  - `not_assessed` -> `Not assessed by this surface.`
- Added additional abbreviation handling for scientific display tokens:
  - `QC, DI, ID, API, URL, JSON, SQL, PK, PD, NOD, SPR, SEC, LAL, HMW, LMW, Fc, IgG, HEK, NONCOMP`
- Registered new filters in all relevant template environments:
  - app Jinja env (`psi/web/app.py`)
  - policy upgrade HTML renderer (`psi/services/policy_upgrade.py`)
  - DI contract smoke template env (`psi/tools/di_contract_smoke.py`)
  - standalone Jinja envs in board template tests.
- Replaced visible underscore formatting hacks in molecule templates:
  - `psi/web/templates/molecules/list.html`
  - `psi/web/templates/molecules/detail.html`
  - moved from `|replace('_',' ')` to `|humanize_state`.
- Improved program dashboard table readability with `humanize_key` / `humanize_state`:
  - `psi/web/templates/programs/detail.html`
- Added presentation-only path token humanization for batch data/evidence domains:
  - `psi/web/templates/batches/detail.html`
- Added tests for new helpers:
  - `tests/test_ui_label_humanization.py` now covers `humanize_state` and `humanize_path_token`.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/ui_labels.py`
- `psi/web/app.py`
- `psi/services/policy_upgrade.py`
- `psi/tools/di_contract_smoke.py`
- `psi/web/templates/molecules/list.html`
- `psi/web/templates/molecules/detail.html`
- `psi/web/templates/programs/detail.html`
- `psi/web/templates/batches/detail.html`
- `psi/web/templates/reports/board_comparison_v3.html`
- `tests/test_ui_label_humanization.py`
- `tests/test_board_comparison_alignment_rendering.py`
- `tests/test_board_determination_card_rendering.py`
- `tests/test_board_molecule_sections_rendering.py`
- `tests/test_board_program_posture_rendering.py`
- `tests/test_report_detail_board_template_selection.py`
- `tests/test_report_upgrade_delta_view.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS
- `python -m psi.tools.ui_label_audit` — PASS

Guarantees:
- Presentation-only labeling/formatting improvements.
- No DI/policy/ranking/replay/snapshot/fingerprint behavior changes.
- No DB schema/migration changes.

## 2026-03-03 — v1.3.0a112
Why:
- Close Phase E report-layer correctness blockers without changing DI semantics or persisted-contract meaning.

What:
- Fixed governance comparability status mapping in `psi/services/report_engine.py`:
  - `conditionally_comparable` now maps to `comparable_partial` (no collapse to `comparable_full`).
- Fixed program board high-risk wiring:
  - `psi/services/program_rollups.py` now derives deterministic `high_severity_risk_present` per molecule from `risk_flags_enriched`.
  - `psi/services/report_engine.py` forwards this field into `sections.molecule_overview_table.rows`.
- Fixed comparison alignment matrix behavior:
  - `psi/services/report_engine.py` adds per-molecule `present_measurement_keys` (from DI `used_by_metric` keys, sorted).
  - `psi/web/templates/reports/board_comparison_v3.html` now renders `✓` only when a molecule has that key, else `—`.
- Added molecule board experimental gaps rendering:
  - `psi/web/templates/reports/board_molecule_v3.html` now includes deterministic `Experimental Gaps` section for blockers and next-best experiments.
- Removed hardcoded lineage nav link:
  - `psi/web/templates/base.html` changed `/lineage/programs/1` to `/lineage/programs`.
- Added required deterministic UI underscore audit tool:
  - new `psi/tools/ui_label_audit.py` writes `_artifacts/ui_label_audit/UI_UNDERSCORE_REPORT.md`.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `psi/services/program_rollups.py`
- `psi/web/templates/reports/board_comparison_v3.html`
- `psi/web/templates/reports/board_molecule_v3.html`
- `psi/web/templates/base.html`
- `psi/tools/ui_label_audit.py`
- `tests/test_comparability_resolution.py`
- `tests/test_v3_narrative_measurement_wiring.py`
- `tests/test_board_comparison_alignment_rendering.py`
- `tests/test_board_molecule_sections_rendering.py`
- `tests/test_report_detail_board_template_selection.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS
- `python -m psi.tools.ui_label_audit` — PASS

Guarantees:
- No DI/policy/ranking/replay/snapshot/fingerprint behavior changes.
- No DB schema/migration changes.
- Report payload contract changes are additive presentation fields only.

## 2026-03-02 — v1.3.0a111
Why:
- Add a canonical presentation-layer key humanization path and reduce visible snake_case labels while preserving technical raw-key auditability.

What:
- Added `psi/web/ui_labels.py` with deterministic pure `humanize_key(key)`:
  - underscore-to-space normalization,
  - title casing,
  - acronym handling (`QC`, `DI`, `ID`, `API`, `URL`, `JSON`, `SQL`, `PK`, `PD`, `MABEL`, `NOAEL`),
  - explicit overrides (e.g., `as_of_ts -> As Of`, `qc_mode -> QC Mode`).
- Registered Jinja filter in `psi/web/app.py`:
  - `templates.env.filters[\"humanize_key\"] = humanize_key`
- Applied humanized labels (with raw key preserved in secondary monospace text) in high-impact report templates:
  - `psi/web/templates/reports/_board_narrative.html`
  - `psi/web/templates/reports/board_molecule_v3.html`
  - `psi/web/templates/reports/board_comparison_v3.html`
  - `psi/web/templates/reports/board_upgrade_delta_v3.html`
  - plus decision form option labels in `psi/web/templates/decisions/new.html`
- Added focused tests `tests/test_ui_label_humanization.py`:
  - acronym/override unit assertions,
  - board view humanization assertion,
  - technical view raw-key preservation assertion.
- Registered `humanize_key` in standalone/non-app Jinja environments used by
  helper rendering and template tests, so board templates that use the filter
  compile consistently in smoke/test paths.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/ui_labels.py`
- `psi/web/app.py`
- `psi/web/templates/reports/_board_narrative.html`
- `psi/web/templates/reports/board_molecule_v3.html`
- `psi/web/templates/reports/board_comparison_v3.html`
- `psi/web/templates/reports/board_upgrade_delta_v3.html`
- `psi/web/templates/decisions/new.html`
- `tests/test_ui_label_humanization.py`
- `psi/services/policy_upgrade.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_board_comparison_alignment_rendering.py`
- `tests/test_board_determination_card_rendering.py`
- `tests/test_board_molecule_sections_rendering.py`
- `tests/test_board_program_posture_rendering.py`
- `tests/test_report_detail_board_template_selection.py`
- `tests/test_report_upgrade_delta_view.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Presentation-only humanization layer; persisted/report payload keys unchanged.
- No DI semantic/policy/ranking/hashing/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a110
Why:
- Improve comparative narrative next-step usefulness when `experimental_gaps` is empty by deriving deterministic guidance from existing comparative payload sections.

What:
- Updated `psi/services/v3_narrative.py` comparative next-step logic with deterministic priority:
  1) explicit `experimental_gaps` content (list/dict),
  2) high-severity risk signal summary (if present),
  3) measurement comparability resolution prompt from cited/appendix measurement keys,
  4) canonical fallback: `No next steps provided by comparative schema.`
- Added targeted test in `tests/test_v3_narrative_rendering.py` asserting comparative next steps are non-`None` and deterministic when gaps are empty but measurement evidence exists.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_narrative.py`
- `tests/test_v3_narrative_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Derived narrative-layer improvement only.
- No DI semantic/policy/ranking/hashing/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a109
Why:
- Improve program-comparative board clarity by replacing hollow posture/resource placeholders with deterministic display sections.

What:
- Updated `psi/web/templates/reports/board_comparison_v3.html`:
  - added `Portfolio / Program Posture Comparison` table for program comparative payloads,
  - deterministic program ordering by `program_id`,
  - added `Resource Implications` section with canonical fallback phrase:
    `Not assessed by this report schema.`
- Augmented targeted render test `tests/test_board_comparison_alignment_rendering.py` to assert:
  - posture section rendering,
  - deterministic ordering,
  - canonical resource-implication fallback wording.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/board_comparison_v3.html`
- `tests/test_board_comparison_alignment_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Board-template display improvement only.
- No DI semantic/policy/ranking/hashing/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a108
Why:
- Add a deterministic, derived-only policy upgrade delta surface for comparing two existing report runs without modifying persisted report payload semantics.

What:
- Added derived delta builder in `psi/services/reports_v3.py`:
  - `build_report_upgrade_delta_view(db, base_report_run_id, candidate_report_run_id)`
  - compares policy pins and key determination/ranking surfaces with deterministic ordering.
- Added new route `GET /reports/upgrade-delta?base=<id>&cand=<id>[&export=pdf]` in `psi/web/routers/reports.py`.
- Added wrapper page template `psi/web/templates/reports/upgrade_delta_detail.html`.
- Extended `psi/web/templates/reports/board_upgrade_delta_v3.html` to render:
  - executive summary,
  - changed rows,
  - unchanged rows,
  - policy pin comparison,
  - comparison citations.
- Added targeted tests in `tests/test_report_upgrade_delta_view.py` for stable ordering and board template fragment rendering.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/reports_v3.py`
- `psi/web/routers/reports.py`
- `psi/web/templates/reports/upgrade_delta_detail.html`
- `psi/web/templates/reports/board_upgrade_delta_v3.html`
- `tests/test_report_upgrade_delta_view.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Derived-only comparison surface; no DI semantic/policy outcome/ranking execution changes.
- No DB schema/migration changes.
- No hashing/fingerprint or replay behavior changes.

## 2026-03-02 — v1.3.0a107
Why:
- Apply report-layer hygiene and wording consistency improvements without changing runtime semantics.

What:
- Replaced mutable module-level suggestions catalog cache in `psi/services/report_engine.py` with deterministic `functools.lru_cache(maxsize=1)` on the loader.
- Improved narrative text normalization in `psi/services/v3_narrative.py`:
  - added sentence-level bullet normalization helper,
  - applied consistent terminal punctuation to `what_this_means` bullets while preserving content meaning.
- Clarified board template fallback status wording in `psi/web/templates/reports/_board_narrative.html` (`Not assessed`).
- Added targeted formatting regression test in `tests/test_v3_narrative_rendering.py` for spacing/punctuation normalization edge case.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `psi/services/v3_narrative.py`
- `psi/web/templates/reports/_board_narrative.html`
- `tests/test_v3_narrative_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Hygiene/clarity updates only in report/narrative presentation layer.
- No DI semantic/policy/ranking/hashing/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a106
Why:
- Replace hollow board placeholders with deterministic display-only summaries using existing report payload/context.

What:
- Added runtime policy-version comparison context in `psi/services/reports_v3.py` (`runtime_policy_versions`) using existing policy loaders.
- Added `Policy Upgrade Delta` display-only section in `psi/web/templates/reports/_board_narrative.html`:
  - policy name, pinned version, latest runtime version, mismatch yes/no.
- Expanded `psi/web/templates/reports/board_program_v3.html` with display-only:
  - `Portfolio Posture Summary` counts (total, ready, blocked/failed, not assessed, high-risk),
  - `Resource Implications` deterministic guidance text derived from counts.
- Added targeted render test `tests/test_board_program_posture_rendering.py` asserting posture summary/count rendering.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/reports_v3.py`
- `psi/web/templates/reports/_board_narrative.html`
- `psi/web/templates/reports/board_program_v3.html`
- `tests/test_board_program_posture_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Display-only board enrichment from existing payload/runtime metadata.
- No DI semantic/policy/ranking/hashing/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a105
Why:
- Improve comparison Board View completeness with payload-derived lineage and alignment surfaces for board interpretation.

What:
- Expanded `psi/web/templates/reports/board_comparison_v3.html` with:
  - `Lineage Comparison` table (molecule/program comparative payload rows),
  - `Alignment Matrix` (display-only derived from payload measurement/citation categories),
  - deterministic ordering for derived measurement columns.
- Added targeted render test `tests/test_board_comparison_alignment_rendering.py` asserting matrix header and indicator rendering from representative payload context.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/board_comparison_v3.html`
- `tests/test_board_comparison_alignment_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Board-template display enrichment only (payload-derived).
- No DI semantic/policy/ranking/hashing/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a104
Why:
- Improve molecule board completeness by rendering key V3 payload sections directly in Board View without changing report semantics.

What:
- Expanded `psi/web/templates/reports/board_molecule_v3.html` to render additional payload-backed sections:
  - Mechanistic Evidence Map
  - Risk Profile (deterministic severity-first display: high/medium/low/unknown; stable key ordering)
  - Confidence Decomposition
  - Reproducibility Appendix (policy pins, measurement keys, cited snapshot IDs)
- Added compact/wrap-safe table styles for board section tables in `psi/web/static/style.css`.
- Added targeted render test `tests/test_board_molecule_sections_rendering.py` asserting key section headings render from a representative payload context.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/board_molecule_v3.html`
- `psi/web/static/style.css`
- `tests/test_board_molecule_sections_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Board-template rendering enhancement only (payload-derived display).
- No DI semantic/policy/ranking/hashing/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a103
Why:
- Route report detail Board View through deterministic report-type template selection while preserving PDF/export behavior and fallback safety.

What:
- Added router helper `_board_template_for_report_type(...)` in `psi/web/routers/reports.py` and set `board_template_name` in detail context.
- Updated `psi/web/templates/reports/detail.html` to include the selected board template (fallback remains `_board_narrative`).
- Added runtime-safe board template wrappers with sentinels:
  - `psi/web/templates/reports/board_molecule_v3.html`
  - `psi/web/templates/reports/board_comparison_v3.html`
  - `psi/web/templates/reports/board_program_v3.html`
  Each wrapper includes `reports/_board_narrative.html` so payload compatibility is preserved.
- Added targeted render tests in `tests/test_report_detail_board_template_selection.py` asserting template selection/mapping and sentinel presence.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/reports.py`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/reports/board_molecule_v3.html`
- `psi/web/templates/reports/board_comparison_v3.html`
- `psi/web/templates/reports/board_program_v3.html`
- `tests/test_report_detail_board_template_selection.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Deterministic template wiring/presentation change only.
- No DI semantic/policy/ranking/hashing/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a102
Why:
- Confirm report policy pins in generated comparative reports remain aligned with the same latest comparability policy loader used by runtime surfaces.

What:
- Added targeted report-generation test in `tests/test_v3_report_contracts.py`:
  - generates a molecule comparative report,
  - asserts `metadata.policy_pins.comparability_policy.policy_version` matches `load_comparability_policy_latest().policy_version`.
- No policy pin behavior change required; coverage now guards against regressions/hardcoding.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_v3_report_contracts.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Deterministic regression coverage only.
- No DI semantic/policy/ranking/hashing/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a101
Why:
- Lock program narrative next-steps extraction to the intended payload key path with deterministic regression coverage.

What:
- Added targeted narrative test in `tests/test_v3_narrative_rendering.py` asserting program next steps are sourced from `sections.next_best_experiments.items` and not unrelated fields.
- Test also validates deterministic text normalization for repeated punctuation in display bullets.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_v3_narrative_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Renderer/test-layer reinforcement only.
- No DI semantic/policy/ranking/hashing/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a100
Why:
- Ensure board determination cards faithfully surface available citation fields from narrative determinations instead of rendering placeholder values.

What:
- Extended board narrative determination objects in `psi/services/v3_narrative.py` to include explicit deterministic fields:
  - `rule_id`
  - `snapshot_ids`
  - `measurement_keys`
  - `missing_inputs`
  - `rationale`
- Updated `psi/web/templates/reports/_board_narrative.html` to pass actual determination fields into `_determination_card` macro (removed hardcoded placeholders).
- Added targeted template rendering regression test `tests/test_board_determination_card_rendering.py` asserting rendered HTML includes rule/snapshot/measurement citations from narrative context.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_narrative.py`
- `psi/web/templates/reports/_board_narrative.html`
- `tests/test_board_determination_card_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Board rendering fidelity improvement only (derived/template layer).
- No DI semantic/policy/ranking/hashing/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a99
Why:
- Improve program-report path efficiency and remove duplicated DI snapshot detection logic while keeping behavior deterministic.

What:
- Removed program-report N+1 snapshot refetch in `psi/services/report_engine.py`:
  - `generate_program_report_v0()` now consumes per-molecule `measurement_keys` from program rollup output instead of re-querying latest DI snapshots for each molecule.
- Extended `psi/services/program_rollups.py` rollup molecule rows with deterministic `measurement_keys` derived from DI `used_by_metric`.
- Introduced shared DI snapshot detection helper `is_di_snapshot_record(...)` in `psi/services/di/util.py` and wired:
  - `psi/services/report_engine.py`
  - `psi/services/program_rollups.py`
  to use it with mode flags preserving existing per-caller semantics.
- Confirmed no unreachable dead block remains after `generate_program_comparative_report_v0()` return path.
- Added targeted tests:
  - `tests/test_di_snapshot_helper.py` (shared helper behavior),
  - `tests/test_program_report_no_n_plus_one.py` (program report path does not call report_engine snapshot refetch helper).

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/util.py`
- `psi/services/program_rollups.py`
- `psi/services/report_engine.py`
- `tests/test_di_snapshot_helper.py`
- `tests/test_program_report_no_n_plus_one.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Deterministic report-layer performance/maintenance improvement.
- No DI semantic/policy/ranking/hashing/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a98
Why:
- Remove redundant report-generation ack guard wrapping while preserving deterministic governance enforcement at persistence boundary.

What:
- Updated `psi/services/reports_v3.py`:
  - removed outer `run_semantic_action_with_ack_guard(...)` in `generate_report_from_form()`,
  - report generation now calls the generator directly; persistence path guard in `persist_report_run()` remains authoritative.
- Added targeted unit test `tests/test_reports_v3_ack_guard.py` asserting `generate_report_from_form()` triggers ack guard exactly once.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/reports_v3.py`
- `tests/test_reports_v3_ack_guard.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Governance enforcement preserved in single deterministic location.
- No DI semantic/policy/ranking/hashing/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a97
Why:
- Lock in board-narrative measurement and program-identity behavior with deterministic report-backed tests.

What:
- Added targeted narrative/report wiring tests in `tests/test_v3_narrative_measurement_wiring.py`:
  - molecule narrative measurements reflect `sections.reproducibility_appendix.measurement_keys` from generated reports,
  - program narrative headline does not fall back to `unidentified program` when `sections.metadata.program_id` exists.
- Existing report-engine measurement key wiring remains unchanged and validated by new tests.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_v3_narrative_measurement_wiring.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Deterministic test-layer reinforcement only.
- No DI semantic/policy/ranking/hashing/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a96
Why:
- Align comparative report reproducibility appendix policy pin display with the latest loaded comparability policy version.

What:
- Updated `psi/services/report_engine.py` in:
  - `generate_molecule_comparative_report_v0()`
  - `generate_program_comparative_report_v0()`
  to set `reproducibility_appendix.catalog_versions.comparability_policy` from `load_comparability_policy_latest().policy_version` instead of hardcoded `v0.1`.
- Added regression assertion in `tests/test_v3_report_contracts.py` verifying both comparative report types carry the loader-derived comparability policy version.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `tests/test_v3_report_contracts.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Report-layer reproducibility metadata alignment only.
- No DI semantic/policy/ranking/hashing/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a95
Why:
- Fix molecule-comparative ranking criteria wiring so high-severity risk hits are only emitted when actually present in each molecule snapshot.

What:
- Updated `generate_molecule_comparative_report_v0()` in `psi/services/report_engine.py`:
  - compute per-molecule `has_high_risk` from `risk_flags_enriched` (`severity == "high"`, case-insensitive),
  - build `criteria_hits` deterministically with:
    - `stage_ready` only when stage is ready,
    - `high_severity_risk_present` only when `has_high_risk` is true,
  - removed prior behavior that always injected `high_severity_risk_present`.
- Added targeted test in `tests/test_v3_report_contracts.py` verifying only the high-risk molecule receives `high_severity_risk_present`.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `tests/test_v3_report_contracts.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Report-layer correctness fix only; no DI semantic/policy/ranking/hashing/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a94
Why:
- Correct molecule-report comparability determination to derive from governance comparability assessments instead of DI snapshot-internal comparability hints.

What:
- Updated `generate_molecule_report_v0()` in `psi/services/report_engine.py`:
  - removed DI-output comparability status candidate construction for governance determination,
  - sourced statuses/measurement keys/snapshot IDs from `list_comparability_assessments(..., scope_type=\"molecule\")`,
  - mapped governance statuses into policy categories deterministically before calling `derive_comparability_determination`.
- Added targeted regression coverage in `tests/test_v3_report_contracts.py` ensuring:
  - molecule comparability determination follows governance assessments,
  - payload does not emit `comparable_partial`.

Files changed:
- `PATCH_NOTES.md`
- `psi/services/report_engine.py`
- `tests/test_v3_report_contracts.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Report-layer correctness fix only; no DI semantic/policy/ranking/hashing/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a94
Why:
- Add report-layer engineering code review document (doc-only).

What:
- Added `REPORT_LAYER_CODE_REVIEW.md` with architecture evaluation, deterministic touchpoints, concrete risk/footgun analysis, and testing gap suggestions for the V3 report layer.
- No runtime behavior changes.

Files changed:
- `REPORT_LAYER_CODE_REVIEW.md`
- `PATCH_NOTES.md`
- `psi/version.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Documentation-only patch.
- No DI semantic/policy/ranking/hashing/replay changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a93
Why:
- Add a concise engineering review artifact for the current V3 report rendering architecture and presentation-layer guardrails.

What:
- Added `DEEP_CODE_REVIEW.md` at repo root covering:
  - factual change summary across `v1.3.0a89-a93`,
  - current report architecture (`report_engine`, `reports_v3`, `v3_narrative`, routers/templates, PDF mode),
  - determinism/replay invariance touchpoints,
  - presentation-layer wiring footguns,
  - next safe steps (ideas only; no implementation).
- Documentation-only patch; no runtime behavior changes.

Files changed:
- `DEEP_CODE_REVIEW.md`
- `PATCH_NOTES.md`
- `psi/version.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Documentation-only patch.
- No DI semantic/policy/ranking/hashing/replay changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a92
Why:
- Improve board-view readability of measurement key citations using template/CSS presentation only.

What:
- Updated board narrative template to render `sections.reproducibility_appendix.measurement_keys` as compact wrapped chips in the Evidence section:
  - `psi/web/templates/reports/_board_narrative.html`
- Added small chip-list layout styles for stable wrapping and readable long keys:
  - `psi/web/static/style.css`
- No Python/report payload/routing/DI logic changes.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/_board_narrative.html`
- `psi/web/static/style.css`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Presentation-only patch.
- No DI semantic/policy/ranking/hashing/replay changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a91
Why:
- Improve executive-header readability and narrative display formatting in Board/PDF views without changing report semantics.

What:
- Applied deterministic presentation-only narrative cleanup in `psi/services/v3_narrative.py`:
  - normalized whitespace/punctuation formatting for display strings,
  - added display-only list cap (`DISPLAY_LIST_LIMIT = 5`) with deterministic overflow marker.
- Polished executive header and board narrative presentation wrappers/classes:
  - `psi/web/templates/reports/detail.html`
  - `psi/web/templates/reports/_board_narrative.html`
- Added small spacing/typography rules for executive header and narrative bullet lists in:
  - `psi/web/static/style.css`
- No routing, payload schema, DI policy/logic, or replay behavior changes.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_narrative.py`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/reports/_board_narrative.html`
- `psi/web/static/style.css`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Presentation-only patch.
- No DI semantic/policy/ranking/hashing/replay changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a90
Why:
- Improve board-first PDF export readability and print stability without changing report semantics.

What:
- Added print/PDF presentation polish in `psi/web/static/style.css`:
  - break-avoid rules for key report blocks/cards/lists,
  - improved wrap behavior for table and long text content,
  - normalized print/PDF typography and spacing.
- Added minimal report-template wrapper classes for targeted styling:
  - `psi/web/templates/reports/detail.html`
  - `psi/web/templates/reports/_board_narrative.html`
- No changes to report ordering, payloads, routing, or logic.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/static/style.css`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/reports/_board_narrative.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Presentation-only patch.
- No DI semantic/policy/ranking/hashing/replay changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a89
Why:
- Complete removal of the legacy compatibility shim for `v3_board_reports` so only the quarantined deprecated module remains.

What:
- Deleted `psi/services/v3_board_reports.py` (legacy shim removed).
- Confirmed legacy skipped tests remain skip-only and do not import the removed shim at module import time:
  - `tests/test_v3_board_report_rendering.py`
  - `tests/test_v3_molecule_report_schema.py`
  - `tests/test_v3_board_report_determinism.py`
  - `tests/test_v3_executive_summary_bullets.py`
  - `tests/test_v3_comparison_report_schema.py`

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_board_reports.py` (deleted)

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DI semantic/policy/ranking/hashing/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a88
Why:
- Resolve maintenance ambiguity from parallel “board report” code paths by quarantining the orphan path that is not router-wired in V3 runtime surfaces.

What:
- Quarantined legacy board report implementation under:
  - `psi/services/_deprecated/v3_board_reports.py`
  - `psi/services/_deprecated/__init__.py`
- Added compatibility shim at `psi/services/v3_board_reports.py` with explicit deprecation header; no live router wiring added/changed.
- Retired orphan-only pytest modules by replacing them with explicit deterministic skips:
  - `tests/test_v3_board_report_determinism.py`
  - `tests/test_v3_board_report_rendering.py`
  - `tests/test_v3_molecule_report_schema.py`
  - `tests/test_v3_comparison_report_schema.py`
  - `tests/test_v3_executive_summary_bullets.py`

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_board_reports.py`
- `psi/services/_deprecated/__init__.py`
- `psi/services/_deprecated/v3_board_reports.py`
- `tests/test_v3_board_report_determinism.py`
- `tests/test_v3_board_report_rendering.py`
- `tests/test_v3_molecule_report_schema.py`
- `tests/test_v3_comparison_report_schema.py`
- `tests/test_v3_executive_summary_bullets.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DI semantic changes.
- No DB schema/migration changes.
- Live routes unchanged.
- Replay invariance preserved.

## 2026-03-02 — v1.3.0a87
Why:
- Report policy pin bundle referenced comparability catalog `v0.1` while report generators already use `load_comparability_policy_latest()` (currently `v0.2`), causing audit-surface mismatch.

What:
- Updated `get_v3_report_policy_pins()` in `psi/services/reports_v3.py` to source comparability pins from `load_comparability_policy_latest()`.
- Added deterministic test in `tests/test_v3_report_engine_contracts.py` asserting pinned comparability `policy_id` and `policy_version` match the latest loaded policy.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/reports_v3.py`
- `tests/test_v3_report_engine_contracts.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DI semantic changes.
- No DB schema/migration changes.
- Replay invariance preserved.

## 2026-03-02 — v1.3.0a86
Why:
- Program narrative next-steps wiring incorrectly read `experimental_gaps` instead of program report `next_best_experiments.items`.

What:
- Updated `render_program_narrative()` in `psi/services/v3_narrative.py` to derive next steps from `sections.next_best_experiments.items`.
- Added deterministic rendering fallback order per item:
  - `label`
  - `suggestion_key`
  - stable stringified fallback.
- Added unit test in `tests/test_v3_narrative_rendering.py` asserting stable, non-empty next-step extraction from `next_best_experiments.items`.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_narrative.py`
- `tests/test_v3_narrative_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DI semantic changes.
- No DB schema/migration changes.
- Replay invariance preserved.

## 2026-03-02 — v1.3.0a85
Why:
- Remove unreachable/dead code in program comparative report generator to reduce maintenance ambiguity and prevent accidental future misuse.

What:
- Deleted dead block after `return persist_report_run(...)` in `generate_program_comparative_report_v0()` within `psi/services/report_engine.py`.
- No behavioral changes; function return path and payload logic remain identical.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DI semantic changes.
- No DB schema/migration changes.
- Replay invariance preserved.

## 2026-03-02 — v1.3.0a84
Why:
- Program narrative headline/program label could fall back to `unidentified program` because program reports typically store identity under `sections.metadata`, not `identity_context`.

What:
- Updated `render_program_narrative()` in `psi/services/v3_narrative.py` to use deterministic fallback order:
  - `sections.identity_context.program_name`
  - `sections.metadata.program_name`
  - `sections.identity_context.program_id`
  - `sections.metadata.program_id`
  - `unidentified program`
- Program status row now emits `program_id=<id>` when name is unavailable.
- Added deterministic unit test in `tests/test_v3_narrative_rendering.py` for metadata-based program identity fallback.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_narrative.py`
- `tests/test_v3_narrative_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DI semantic changes.
- No DB schema/migration changes.
- Replay invariance preserved.

## 2026-03-02 — v1.3.0a83
Why:
- Ensure board/narrative measurement summaries reflect present `used_by_metric` evidence instead of appearing empty.

What:
- Added deterministic `measurement_keys` wiring to molecule report reproducibility appendix from `used_by_metric` keys (sorted).
- Added deterministic program report `measurement_keys` wiring as sorted union of:
  - measurement keys from latest included molecule snapshots (`used_by_metric`)
  - comparability cited measurement keys already present in program comparability rows.
- Added deterministic contract assertions in `tests/test_v3_report_contracts.py` for molecule/program reproducibility `measurement_keys`.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `tests/test_v3_report_contracts.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DI semantic changes.
- No DB schema/migration changes.
- Replay invariance preserved.

## 2026-03-02 — v1.3.0a82
Why:
- Fix brittle comparative report identity rendering by moving board-facing identity derivation into deterministic Python context assembly.
- Add print/PDF export mode for report detail pages with stable board-first layout.
- Replace raw-ID report generation UX with guided deterministic selectors while preserving manual-ID fallback.

What:
- Server-derived identity summary (Option B) added in `psi/services/reports_v3.py`:
  - New `build_report_identity_summary(...)` used by `get_report_run_detail(...)`.
  - Deterministic identity formatting for `molecule_report`, `program_report`, `molecule_comparative_report`, and `program_comparative_report`.
  - Comparative identity uses `molecule_set.rows` / `program_set.rows` stable row order.
  - Board identity text filters 64-hex hash tokens.
- Report detail route/template PDF mode:
  - `GET /reports/{id}?export=pdf` sets `is_pdf` and `body_class="pdf-mode"`.
  - Board View remains default; in PDF mode tabs and technical pane are suppressed.
  - Added deterministic “Export PDF” link in normal mode.
- Guided report generation form:
  - New JSON endpoints:
    - `GET /reports/options/programs`
    - `GET /reports/options/molecules?program_id=...`
  - `reports/new.html` now uses dependent selectors:
    - program selector for program report types,
    - program then molecule selector for molecule report types.
  - Comparative selection validation enforces 2–5 picks in UI and server-side form parser.
  - Manual IDs path retained behind toggle for graceful degradation.
- Added deterministic tests:
  - `tests/test_v3_reports_ui_identity.py`
    - identity summary derivation coverage
    - options endpoints ordering/filter behavior.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/reports_v3.py`
- `psi/web/routers/reports.py`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/reports/new.html`
- `psi/web/templates/base.html`
- `psi/web/static/style.css`
- `tests/test_v3_reports_ui_identity.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DI semantic/policy/ranking/replay logic changes.
- No DB schema/migration changes.
- Deterministic ordering preserved.

Rsync overlay instructions:
- `rsync -av --no-times ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a82_<timestamp>/ /home/zach/psi_repo/`

## 2026-03-02 — v1.3.0a81
Why:
- Fix board readability regressions where report identity and subjects could render as `missing`/`Not yet captured` despite available payload data.

What:
- Updated `reports/detail.html` Executive Header identity rendering (template-only):
  - Added deterministic `identity_summary` for all report types.
  - Uses `identity_context` when present.
  - Falls back to `metadata` + `molecule_set.rows` / `program_set.rows` for comparative reports.
  - Avoids raw dict dumps in board identity display.
- Updated `psi/services/v3_narrative.py` (derived narrative layer only):
  - Molecule Stage now prefers `stage_determination.decision_state`, then `readiness_state`, then `Not assessed yet`.
  - Molecule Next steps now reads `experimental_gaps.blockers` first, then `experimental_gaps.next_best_experiments`, preserving payload order.
  - Comparative Subjects now derive from:
    - `molecule_set.rows` for molecule comparative
    - `program_set.rows` for program comparative
    with deterministic best-effort labels.
- Added deterministic regression tests in `tests/test_v3_narrative_rendering.py` for:
  - molecule stage precedence
  - molecule next-step extraction
  - molecule/program comparative subjects derivation from row sets.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`
- `psi/services/v3_narrative.py`
- `tests/test_v3_narrative_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (matched=5 failed=0 skipped=0)

Guarantees:
- No DI semantic changes.
- No DB changes.
- Replay invariance preserved.

Rsync overlay instructions:
- `rsync -av --no-times ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a81_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a80
Why:
- Final board-readability consistency and accessibility pass across report/lineage toggles and section framing.

What:
- Added minimal presentational accessibility improvements:
  - active button visual state (`.btn.active`)
  - consistent technical-panel separator styling (`.technical-panel`)
- Updated Board/Technical toggle controls across report and lineage templates to include `aria-controls` and stable panel IDs.
- Ensured non-JS fallback remains readable: Board and Technical sections are both visible and clearly separated.
- Kept headings and panel framing consistent across:
  - `reports/detail.html`
  - `reports/board_upgrade_delta_v3.html`
  - `reports/board_template_ladder_v3.html`
  - `lineage/program_detail.html`
  - `lineage/portfolio_detail.html`

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/static/style.css`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/reports/board_upgrade_delta_v3.html`
- `psi/web/templates/reports/board_template_ladder_v3.html`
- `psi/web/templates/lineage/program_detail.html`
- `psi/web/templates/lineage/portfolio_detail.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a80_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a79
Why:
- Reduce hash/canonical-noise in board-facing sections so executive readers see status and actions, while hashes remain available only in technical/audit views.

What:
- Updated `reports/detail.html` board header to remove direct fingerprint display from Board View.
- Updated `reports/board_upgrade_delta_v3.html`:
  - Board View now shows only `changed_key_count` from header.
  - Full header (including hash fields) moved to Technical View.
- Updated lineage board sections to avoid raw event-object dumping and show compact deterministic count bullets instead.
- Added regression coverage in `tests/test_v3_narrative_rendering.py` to assert board narrative outputs do not contain 64-hex hash tokens.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/reports/board_upgrade_delta_v3.html`
- `psi/web/templates/lineage/program_detail.html`
- `psi/web/templates/lineage/portfolio_detail.html`
- `tests/test_v3_narrative_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a79_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a78
Why:
- Make determination cards board-readable with consistent human wording and deterministic missing-inputs language.

What:
- Updated shared determination card macro in `reports/_determination_card.html`:
  - Outcome labels now render in human-readable form (for example `not_assessed` -> `Not assessed yet`, `policy_disabled` -> `Not enabled`).
  - `Rule ID` label changed to `Policy rule` while preserving the same underlying value.
  - Snapshot section now shows `No snapshots captured yet` when `missing_inputs` exists and no snapshot IDs are cited.
  - Measurement keys now render as compact chips instead of JSON-like lists.
  - Missing inputs language standardized to:
    `This determination is not assessed until these inputs exist: ...`
- Presentation-only changes; determination payload semantics unchanged.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/_determination_card.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a78_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a77
Why:
- Move lineage program/portfolio pages to executive-first board mode while preserving full raw audit visibility in a secondary technical view.

What:
- Updated `lineage/program_detail.html`:
  - Added Board/Technical toggle (Board default).
  - Board section now shows compact executive summary counts and key lineage events.
  - Technical section collapses raw warnings/changes/rollups/history/membership JSON under `Show raw`.
- Updated `lineage/portfolio_detail.html`:
  - Added Board/Technical toggle (Board default).
  - Board section shows portfolio summary and key child-program lineage events.
  - Technical section collapses raw warnings/summaries/governance/membership JSON.
- Presentation-only changes; lineage semantics/data untouched.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/lineage/program_detail.html`
- `psi/web/templates/lineage/portfolio_detail.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a77_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a76
Why:
- Make upgrade delta and template ladder pages executive-first by default while preserving full technical audit surfaces behind an explicit toggle.

What:
- Updated `reports/board_upgrade_delta_v3.html`:
  - Added Board/Technical view toggle (Board default).
  - Board section now emphasizes `Executive Summary`, `What changed`, and `What’s required next`.
  - Technical section contains raw appendix JSON and reproducibility footer.
  - Preserved legacy literals required by tests: `Upgrade Delta Header`, `Change Table`.
- Updated `reports/board_template_ladder_v3.html`:
  - Added Board/Technical view toggle (Board default).
  - Board section emphasizes stage table and next actions.
  - Technical section contains raw missing prerequisite JSON and reproducibility footer.
  - Preserved legacy literals required by tests: `Template Ladder Header`, `Stage Table`.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/board_upgrade_delta_v3.html`
- `psi/web/templates/reports/board_template_ladder_v3.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a76_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a75
Why:
- Complete deterministic narrative mapping coverage for all four report types with board-friendly subject labeling and clean empty-state phrasing.

What:
- Refined comparison narrative rendering in `psi/services/v3_narrative.py`:
  - Uses `II_general_profile.columns` to display board-friendly subjects (for example `M1 (Mol One)`).
  - Uses deterministic empty phrasing (`Not yet captured`, `None`) instead of array literals.
- Added tests in `tests/test_v3_narrative_rendering.py` to assert:
  - deterministic behavior across all report types,
  - friendly comparison labels,
  - no array-literal leakage in board narrative output.
- Existing report-type router mapping from `a74` continues to cover:
  - `molecule_report`
  - `program_report`
  - `molecule_comparative_report` / `molecule_comparison_report`
  - `program_comparative_report` / `program_comparison_report`

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_narrative.py`
- `tests/test_v3_narrative_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a75_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a74
Why:
- Make board narrative the default report detail experience while preserving technical audit visibility and deterministic structured markers.

What:
- Updated `reports/detail.html` to default to Board View and provide a client-side Board/Technical toggle.
- Added `reports/_board_narrative.html` for executive-first narrative rendering (headline, status, determinations, evidence, next steps).
- Added `reports/_technical_audit.html` for secondary technical/audit content (pins, fingerprint metadata, warnings, raw payload).
- Wired router context to provide `board_narrative` using deterministic narrative renderers in `psi/services/v3_narrative.py`.
- Preserved required structured marker keys in rendered HTML:
  - `identity_context`, `molecule_report`, `policy_summary`, `rule_summary`, `measurement_summary`, `evidence_summary`.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/reports.py`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/reports/_board_narrative.html`
- `psi/web/templates/reports/_technical_audit.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a74_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a73
Why:
- Add a deterministic board narrative rendering layer that translates existing report payloads into executive-readable text without changing semantics or persisted JSON.

What:
- Added `psi/services/v3_narrative.py` with pure deterministic renderers:
  - `render_molecule_narrative`
  - `render_program_narrative`
  - `render_molecule_comparison_narrative`
  - `render_program_comparison_narrative`
- Narrative model includes stable keys/order: headline, status rows, what-this-means, evidence status, determinations, next steps, technical notes.
- Added sanitization to prevent hash-like 64-hex tokens in board narrative strings.
- Added deterministic tests in `tests/test_v3_narrative_rendering.py`.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_narrative.py`
- `tests/test_v3_narrative_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a73_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a72
Why:
- Normalize board packet page framing for upgrade delta, ladder, and lineage surfaces with consistent section titles and compact reproducibility footer style.

What:
- Updated templates for visual consistency and deterministic reading order:
  - `reports/board_upgrade_delta_v3.html`
  - `reports/board_template_ladder_v3.html`
  - `lineage/program_detail.html`
  - `lineage/portfolio_detail.html`
- Added “Show raw” collapsible blocks for long JSON sections (client-side `<details>` only).
- Added consistent “Reproducibility & Fingerprints” footer sections.
- Presentation-only changes; report payloads and semantics unchanged.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/board_upgrade_delta_v3.html`
- `psi/web/templates/reports/board_template_ladder_v3.html`
- `psi/web/templates/lineage/program_detail.html`
- `psi/web/templates/lineage/portfolio_detail.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a72_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a71
Why:
- Make comparison report pages board-readable with consistent framing and explicit neutral handling when ranking is policy-disabled/incomplete.

What:
- Updated comparative report presentation in `reports/detail.html`:
  - Executive header now includes selected entity list for comparative reports
  - Added Comparison Highlights section
  - Determinations section now renders ranking as neutral `not_enabled` when policy is disabled/incomplete
  - Added required one-line governance note for disabled ranking:
    “Governance note: ranking is policy-controlled and currently disabled.”
- Presentation-only; no JSON/report semantics changed.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a71_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a70
Why:
- Improve program report readability by making posture interpretation and citations immediately visible to board readers.

What:
- Updated `reports/detail.html` for program reports:
  - Program posture determination card is now prominent directly under the executive header
  - Added static one-line “What this means” explanatory text under posture outcome
  - Added compact citation rendering for snapshot/template/decision references from rollup citations
- Presentation-only update; no report semantics changed.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a70_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a69
Why:
- Improve molecule report board readability with a clearer top-down flow and compact executive bullet framing.

What:
- Updated `reports/detail.html` presentation order for molecule reports:
  - Executive Summary bullets
  - Determinations
  - Evidence
  - Measurements
  - Rules & Policy
  - Reproducibility & Fingerprints
- Added client-side “Show all / Show less” toggle for executive bullets (first 5 shown by default).
- Label/heading wording adjusted for board-friendly readability only; underlying payload unchanged.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a69_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a68
Why:
- Improve board readability on report detail pages with a clear executive hierarchy and deterministic determination cards, without changing any report semantics.

What:
- Added reusable determination card macro partial:
  - `psi/web/templates/reports/_determination_card.html`
- Refactored `reports/detail.html` presentation:
  - Executive Header block at top
  - Determinations section with cards for comparability, program posture, and ranking status
  - standardized Rules & Policy / Evidence / Measurements / Reproducibility sections
  - preserved required structured markers (`identity_context`, `molecule_report`, `policy_summary`, `rule_summary`, `measurement_summary`, `evidence_summary`)
- No JSON/report payload logic changed; rendering only.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/reports/_determination_card.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a68_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a67
Why:
- Harden upgrade semantic-ack enforcement so semantic actions cannot bypass acknowledgment checks.

What:
- Added a single guard wrapper in `psi/services/policy_upgrade.py`:
  - `run_semantic_action_with_ack_guard(...)`
- Refactored semantic report entry points to route through the guard wrapper:
  - `psi/services/reports_v3.py::generate_report_from_form(...)`
  - `psi/services/report_engine.py::persist_report_run(...)`
- Added tests validating deterministic block/allow behavior:
  - unacknowledged semantic warning => raises `policy_upgrade_action_required`
  - acknowledged session => semantic action proceeds deterministically.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `psi/services/reports_v3.py`
- `psi/services/report_engine.py`
- `tests/test_policy_upgrade_diff_artifact.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a67_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a66
Why:
- Remove governance ambiguity around hardcoded ordering by making internal deterministic tie-break behavior explicit, locked, and documented as a narrow non-heuristic exemption.

What:
- Added explicit shortlisting internal tie-break constant:
  - `SHORTLISTING_INTERNAL_TIEBREAK_KEYS`
- Refactored shortlisting sort tuple assembly to consume the explicit constant list.
- Added governance note doc:
  - `docs/DI_V3_GOVERNANCE_NOTES.md`
- Added lock tests asserting exact tie-break key literal list and no weighted token reintroduction.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/shortlisting.py`
- `docs/DI_V3_GOVERNANCE_NOTES.md`
- `tests/test_shortlisting_tiebreak_governance.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a66_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a65
Why:
- Enrich program rollup posture semantics with explicit policy-order rules and citations, without introducing any numeric scoring or weighted heuristics.

What:
- Added additive `program_rollup_policy_v0_1.json` with ordered posture states and ordered rule precedence.
- Refactored rollup posture derivation in `psi/services/program_rollups.py` to policy-order evaluation with explicit citations:
  - `posture_state`, `rule_id`, `cited_snapshot_ids`, `cited_templates`, `cited_decisions`, `rationale`, `notes`
- Wired posture object into program report sections and lineage summary surfaces.
- Added deterministic tests for policy loading/ordering and posture payload constraints, including banned-key assertions (`score`, `weight`, `points`, `ranking_score`, `numeric_total` absent).

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/program_rollup_policy_v0_1.json`
- `psi/services/program_rollups.py`
- `psi/services/report_engine.py`
- `psi/services/lineage.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_program_rollup_posture_policy.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a65_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a64
Why:
- Elevate comparability semantics to governance-grade deterministic determination objects with explicit rule/citation surfaces and policy-order precedence.

What:
- Added additive `comparability_policy_v0_2.json` with ordered categorical rules and deterministic rationale fragments.
- Implemented validated comparability policy latest-loader and full determination builder in `psi/services/comparability.py`:
  - always returns `category`, `rule_id`, `measurement_keys`, `snapshot_ids`, `rationale`, `notes`
  - deterministic downgrade to `category=not_assessed` + `rule_id=policy_inputs_missing` with `missing_inputs` when required citations are missing
- Wired comparability determination objects into molecule/program report payload surfaces.
- Added deterministic tests for policy loading, precedence, completeness, downgrade behavior, and repeatability.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/comparability_policy_v0_2.json`
- `psi/services/comparability.py`
- `psi/services/report_engine.py`
- `tests/test_comparability_resolution.py`
- `tests/test_v3_catalog_immutability.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a64_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a63
Summary:
- Fix comparability category resolution precedence to enforce:
  - `missing_data=True` => deterministic conservative fallback `resolved_status="not_comparable"` with `resolution_reason="missing_data"`.
  - `missing_data=False` => policy-order precedence where earliest status in `allowed_statuses` present in input statuses wins, with `resolution_reason="policy_precedence"`.
- Add dedicated comparability resolution tests for precedence and partial-data determinism.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/comparability.py`
- `tests/test_comparability_resolution.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

## 2026-03-02 — v1.3.0a62
Summary:
- Fix report detail template contract requirements by adding a deterministic structured payload block with fixed keys and required literal markers.
- Always render fixed-order keys: `identity_context`, `molecule_report`, `policy_summary`, `rule_summary`, `measurement_summary`, `evidence_summary`, using deterministic `"missing"` placeholders when absent.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

## 2026-02-26 — v1.2.9x32 (Closeout hardening)
What changed:
- Archived legacy MVP app source to `docs/legacy/legacy_mvp_app.py` and replaced `psi/legacy_mvp_app.py` with an overlay-safe tombstone shim so it is not part of active PSI runtime paths.
- Added GitHub Actions CI workflow (`.github/workflows/ci.yml`) running `compileall`, `pytest -q`, and `di_contract_smoke` with an ephemeral SQLite DB prepared by new tooling (`psi.tools.prepare_ci_db`).
- Added targeted `DeprecationWarning` emission when the legacy YAML engine entrypoints (`load_rules`, `run_decision`) are actually used; normal JSON DI paths remain silent.
- Typed SoE core builder config via `SoECoreConfig` dataclass (behavior-preserving compatibility shim retained internally).
- Extracted DI compute integrity hash finalization into `_finalize_integrity(...)` (behavior-preserving refactor) and added deterministic coverage.
- Added `progress_policy_v0_2.json` + explicit `load_progress_policy_latest()` mapping; molecule header now uses the deterministic latest progress policy loader.
- Added `template_prerequisites_v0_2.json` to cover current template versions used by progress policy latest.
- Added `confidence_policy_v0_3.json` (policy-visible multi-template aggregation strategy metadata, no weights) + explicit `load_confidence_policy_latest()` mapping.
- Added policy-visible replay compat catalog (`replay_policy_compat_v0_1.json`) and default-off verifier compat fallback wiring with audited `policy_resolution` metadata (strict exact-hash replay remains default).
- Added deterministic molecule-header regression lock fixture/test and strengthened smoke coverage for progress/confidence latest loaders, replay compat catalog, YAML deprecation warning, and integrity helper determinism.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/legacy_mvp_app.py`
- `docs/legacy/README.md`
- `docs/legacy/legacy_mvp_app.py`
- `.github/workflows/ci.yml`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`
- `psi/core/decision_engine.py`
- `psi/services/di/soe.py`
- `psi/services/di/compute.py`
- `psi/core/di/catalog.py`
- `psi/core/di/catalogs/progress_policy_v0_2.json`
- `psi/core/di/catalogs/template_prerequisites_v0_2.json`
- `psi/core/di/catalogs/confidence_policy_v0_3.json`
- `psi/core/di/catalogs/replay_policy_compat_v0_1.json`
- `psi/services/molecule_header.py`
- `psi/services/di/verify.py`
- `psi/tools/prepare_ci_db.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_di_contract_smoke_pytest_wrapper.py`
- `tests/test_molecule_header_model.py`
- `tests/test_compute_finalize_integrity.py`
- `tests/fixtures/molecule_header_model_lock_v1.json`

Determinism/Replay note:
- DI semantics and snapshot semantics are unchanged; replay compat fallback is explicit and default-off.
- Replay strictness remains enforced (`matched=5, failed=0, skipped=0` required).

## v1.2.9w46

Why:
- Make the DI snapshot UI more audit-friendly with deterministic ordering and clearer error snapshot rendering.

What changed:
- `get_snapshot_detail` now provides `di_snapshot_ui` with pre-ordered gate outcomes, outcomes history, ranking candidates, and a unified DI error block.
- DI snapshot template uses pre-ordered lists for gate summary counts and outcomes history, renders a deterministic ranking candidates table, and surfaces a clear DI error snapshot block.

What did NOT change:
- No DI scoring/selection logic changes. No schema changes. No layout overhaul.

## 2026-02-26 — v1.2.9x28
What changed:
- Molecules overview (`/molecules`) now shows per-molecule progress and confidence bars using the existing deterministic molecule header model (read-only DI history + measurements; no DI logic changes).
- Molecule detail annotations panel adds bulk highlight controls for `oxidation_susceptible` and `deamidation`, plus clear highlights and click-to-deselect for highlighted residues.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/routers/molecules.py`
- `psi/web/templates/molecules/list.html`
- `psi/web/templates/molecules/detail.html`

Determinism/Replay note:
- Presentation-layer only patch; DI engine, policies, registry semantics, and snapshot hash-bearing outputs are unchanged.
- Molecule list header bars reuse existing deterministic header model builders with explicit ordering preserved.

## 2026-02-26 — v1.2.9x29
What changed:
- Molecule detail annotations list now removes per-site `oxidation_susceptible` and `deamidation` rows entirely.
- Added per-component summary rows directly under the Full sequence viewer section with `Highlight` + `Deselect` buttons for oxidation/deamidation (no Copy buttons on these rows).
- Existing Copy buttons for all other annotation items remain unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/molecules/detail.html`

Determinism/Replay note:
- UI-only template/JS behavior change; no DI, policy, registry, or schema changes.
- Replay surfaces and snapshot hashes remain unchanged.

## 2026-02-26 — v1.2.9x30
What changed:
- Motifs/Liabilities section now renders summary rows with `Highlight` + `Deselect` (no Copy) for `N_glycosylation`, `Oxidation susceptible`, and `Deamidation susceptible`.
- Removed the x29 oxidation/deamidation summary-row placement under the Full sequence viewer block.
- Per-site annotation rows remain removed for oxidation/deamidation, and `N_glycosylation` now uses the summary-row pattern instead of per-item Highlight+Copy.
- Copy buttons elsewhere remain unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/molecules/detail.html`

Determinism/Replay note:
- UI-only template/JS change; no DI outputs, policy semantics, registry semantics, or schema behavior changed.
- Highlight union logic uses deterministic component annotation data already present in the page model.

## 2026-02-26 — v1.2.9x31
What changed:
- Motifs/Liabilities row-level `Deselect` now clears highlights only for that specific motif/liability row (`N_glycosylation`, `oxidation_susceptible`, or `deamidation`) instead of clearing the entire component.
- Multi-row motif/liability highlights can now coexist, and the viewer renders the union deterministically.
- Click-to-deselect on highlighted residues now removes the residue from active highlight sets covering that residue without clearing unrelated motif highlights.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/molecules/detail.html`

Determinism/Replay note:
- UI-only template/JS refinement; no DI/policy/registry/schema changes.
- Highlight state remains deterministic and component/feature-scoped in the browser only (no snapshot impact).

## v1.2.9w45

Why:
- Add stable evidence pointers so audit users can trace gate/readiness/shortlisting/ranking “why” back to concrete inputs.

What changed:
- Added additive `output.why_evidence` with deterministic sub-blocks for `gates`, `readiness`, `shortlisting`, and `ranking`.
- Evidence pointers are direct references only (measurement IDs, data_record IDs, and selected evidence field pointers already present in selected inputs).
- `di_contract_smoke` now asserts `why_evidence` presence, ordering, and gate-pointer coverage when gate metrics are present.

What did NOT change:
- No new ranking factors. No heuristic inference. No schema changes.

## v1.2.9w44

Why:
- Render outcome labels and DI review verdicts in the snapshot UI as read-only audit context.

What changed:
- `get_snapshot_detail` now exposes `latest_outcome_label` with latest-wins semantics (excluding DI review label rows).
- DI snapshot UI shows latest outcome label + latest DI review verdict/rationale read-only and removes inline label write forms from the snapshot panel.
- `di_contract_smoke` renders the DI snapshot template with/without labels to verify no render errors.

What did NOT change:
- No DI output schema changes. No labeling semantics changes. No new tables.

## v1.2.9w43

Why:
- Surface DI snapshot provenance explicitly in the snapshot UI and lock the contract with smoke assertions.

What changed:
- DI outputs now include additive provenance sub-blocks for template, policy ref, and decision scope.
- Decision snapshot detail context exposes explicit `di_snapshot_provenance` for Jinja rendering.
- DI snapshot template renders policy/template/version/hash, shortlisting-enabled, and scope identifiers.
- `di_contract_smoke` asserts provenance fields exist for batch + molecule snapshots and remain deterministic across reruns.

What did NOT change:
- No schema changes. No DI scoring/heuristics changes. No labeling semantics changes.

## v1.2.9v15 (final-2)

Why:
- Replay regression failed on WAL databases when opened with driver-level read-only.

What changed:
- `ensure=False` now opens a normal SQLite connection, installs `PRAGMA query_only=1`, and skips WAL/synchronous pragmas to preserve read-only behavior without WAL I/O failures.

What did NOT change:
- Web app still uses WAL for writable DBs; no schema or DI changes.

## v1.2.9v15 (final-3)

Why:
- Read-only replay tools could crash on WAL databases with "attempt to write a readonly database" during SELECT.

What changed:
- `get_db(..., ensure=False)` now probes with `SELECT 1` and, on readonly-like errors, falls back to a temporary copy of the DB (and any -wal/-shm) in a writable temp directory. Read-only sessions set `PRAGMA query_only=1` and skip WAL/synchronous/busy_timeout.

What did NOT change:
- No schema changes. No DI/policy changes. No UI changes. Web sessions still attempt WAL when writable.

## v1.2.9v16

Why:
- Replay read-only open now uses a schema-touching probe; WAL-safe shadow copy fallback with stability loop; no writes to target DB.

What changed:
- `psi/core/db.py`: read-only `get_db(..., ensure=False)` probes `decision_snapshots`, falls back to a temp copy (db + wal/shm) if WAL coordination fails, and enforces `PRAGMA query_only=1` in read-only sessions. Session is configured as read-only (no autoflush, no expire_on_commit).

What did NOT change:
- No schema changes. No DI/policy changes. No UI changes.

## v1.2.9v15 (final)

Why:
- Replay tools crashed because WAL requires sidecar files and can fail under read-only/locked DB access.

What changed:
- `ensure=False` now uses driver-level SQLite read-only URI mode and skips WAL/synchronous/busy_timeout pragmas.

What did NOT change:
- Web app still uses WAL for writable DBs; no schema or DI changes.

## v1.2.9v15 (redo)

Why:
- Read-only tooling could fail when SQLite connect pragmas attempted WAL/synchronous on RO connections.

What changed:
- `psi/core/db.py`: compute writability from DB path and skip WAL/synchronous/busy_timeout pragmas when the path is not writable.

What did NOT change:
- No schema changes. No DI/policy changes. No snapshot content/integrity changes.

## v1.2.9v15

Why:
- Read-only tooling could fail when SQLite connect pragmas attempted WAL/synchronous on RO connections.

What changed:
- `psi/core/db.py`: skip WAL/synchronous when `PRAGMA query_only` indicates RO, and gracefully handle known read-only errors. Writable connections still enable WAL.

What did NOT change:
- No schema changes. No DI/policy changes. No snapshot content/integrity changes.

## v1.2.9v14

Why:
- Surface OutcomeLabel metadata directly on DI snapshot detail views.

What changed:
- Display OutcomeLabel rows in the DI snapshot detail panel (read-only).

What did NOT change:
- No schema changes. No DI logic changes. No DB writes.

## v1.2.9v13

Why:
- Clarify legacy YAML engine deprecation intent and surface a visual engine badge.

What changed:
- Docs: add a non-binding deprecation target note in `docs/DI_CONSTITUTION.md`.
- UI: display DI vs legacy YAML engine badge on decision list/detail views.

What did NOT change:
- No schema changes. No DI logic changes. No policy changes.

## v1.2.9v12

Why:
- Reduce rare race conditions in molecule/chain ID allocation.

What changed:
- Retry on IntegrityError when allocating molecule primary IDs and chain IDs.

What did NOT change:
- No schema changes. No DI logic changes. No UI changes.

## v1.2.9v11

Why:
- Remove dead helper functions in molecules router to reduce confusion.

What changed:
- Deleted unused private helpers in `psi/web/routers/molecules.py` after verification.

What did NOT change:
- No schema changes. No DI logic changes. No UI changes.

## v1.2.9v10

Why:
- Ensure `model_to_dict` includes all SQLAlchemy columns reliably.

What changed:
- Use SQLAlchemy column introspection for model serialization, with safe fallback to prior behavior.

What did NOT change:
- No schema changes. No DI logic changes. No UI changes.

## v1.2.9v9

Why:
- Remove hardcoded DI catalog path and centralize it as a named constant.

What changed:
- Add `DEFAULT_CATALOG_PATH` next to `load_catalog` and use it in DI runner.

What did NOT change:
- No schema changes. No DI logic changes. No UI changes.

## v1.2.9v8

Why:
- Ensure molecule background tasks can target an explicit DB path when provided.

What changed:
- Thread `db_path` into molecule background tasks and pass the active DB path from router scheduling.

What did NOT change:
- No schema changes. No DI logic changes. No UI changes.

## v1.2.9v7

Why:
- Remove remaining `datetime.utcnow()` usage and keep naive UTC timestamps in line with PSI conventions.

What changed:
- Replace all `datetime.utcnow()` call sites with `datetime.now(timezone.utc).replace(tzinfo=None)`.

What did NOT change:
- No schema changes. No DI/policy changes. No UI changes.

## v1.2.9v6

Why:
- Reduce SQLite lock contention for concurrent local sessions.

What changed:
- Set SQLite PRAGMAs on connect: `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`.

What did NOT change:
- No schema changes. No DI/policy changes. No UI changes.
- WAL creates runtime sidecar files (`*.sqlite-wal`, `*.sqlite-shm`); never include these in overlay ZIPs.

## v1.2.9v5

Why:
- Remove FastAPI startup deprecation while preserving deterministic startup semantics.

What changed:
- Migrate startup hook to a FastAPI lifespan context manager.

What did NOT change:
- No schema changes. No DI/policy changes. No endpoint/UI changes.

## v1.2.9v4

Why:
- Eliminate Python 3.12 datetime.utcnow deprecation and enforce consistent UTC helper usage.

What changed:
- Add/standardize `now_utc()` in `psi/core/utils.py` (naive UTC) and replace all `datetime.utcnow()` call sites.

What did NOT change:
- No schema changes. No DI/policy changes. No functional decision changes.

## v1.2.9v3

Why:
- UI readability polish for drift explanations and SQL IN-clause hardening.

What changed:
- UI: improved DI drift explain panel readability; reason legend; no functional change.
- Hardening: replace f-string IN-clause SQL with SQLAlchemy expanding bindparams across codebase.

What did NOT change:
- No DI engine logic changes. No policy changes. No DB writes or schema changes.

## v1.2.9v2

Why:
- Surface DI verification + drift intelligence in the UI (anchored vs current-world), read-only.

What changed:
- `psi/web/routers/decisions.py` + `psi/web/templates/decisions/_di_snapshot.html` + `psi/web/templates/decisions/_di_verification.html`: add DI verification panel with anchored/current status + drift explain.
- `psi/services/programs.py` + `psi/web/routers/programs.py` + `psi/web/templates/programs/detail.html`: optional lineage verification chips via `?verify=1`.

What did NOT change:
- No DI engine logic changes. No policy changes. No DB writes or schema changes.

## v1.2.9v1

Why:
- di_cross_version_stress should treat DATA_DRIFT as expected and non-failing.

What changed:
- `psi/tools/di_cross_version_stress.py`: DATA_DRIFT now WARN (non-failing); hard fail only on anchored mismatch, exceptions, or non-data-drift classifications; add classification histogram; exit nonzero only on hard failures.

What did NOT change:
- No DI engine logic changes. No policy changes. No DB writes or schema changes.

## v1.2.9v

Why:
- Governance hardening for packaging, dashboard visibility, and verification tooling.

What changed:
- `compress.sh` + `PSI_CONTEXT.md`: desktop shortcut install is opt-in and must be run from `~/psi_repo`.
- `psi/services/programs.py` + `psi/web/templates/programs/detail.html`: add DI snapshot lineage panel (read-only).
- `psi/tools/di_cross_version_stress.py`: read-only cross-version verification stress test tool.

What did NOT change:
- No DI engine logic changes. No policy changes. No DB writes or schema changes.

## v1.2.9u

Why:
- Finish deterministic, read-only portfolio analytics surfaces and clarify decision lifecycle in molecule history.

What changed:
- `psi/services/programs.py` + `psi/web/templates/programs/detail.html`: add gate failure frequency, metric coverage frequency, and QC instability summaries (counts only).
- `psi/services/molecules.py` + `psi/web/templates/molecules/detail.html`: surface superseded status in decision history.

What did NOT change:
- No DI engine logic changes. No policy changes. No DB writes or schema changes.

## v1.2.9s3

Why:
- Make replay regression harness startup clearer and fail fast on invalid explicit DB paths.

What changed:
- `psi/tools/di_replay_regression.py`: print PSI version + read-only mode; fail fast if `--db` path is missing.

What did NOT change:
- No DI logic changes. No DB writes. No schema changes.

## v1.2.9s2

Why:
- Clarify which SQLite DB path the replay regression harness opens, and enforce read-only posture.

What changed:
- `psi/tools/di_replay_regression.py`: print resolved DB path at startup; open DB with `ensure=False`.

What did NOT change:
- No DB schema changes. No DB writes. No DI logic changes.

## v1.2.9s

Why:
- Fix a startup crash (`IntegrityError: UNIQUE constraint failed:
  ux_decision_snapshots_one_active_per_scope`) that fires on every PSI
  startup after the first time the q-series supersession index was created.

Root cause:
- `ensure_schema()` in `psi/core/db.py` ran a blanket
  `UPDATE decision_snapshots SET is_superseded=0 WHERE is_superseded IS NULL`
  on every startup. On the first run this was safe (the unique index did not
  exist yet). On every subsequent run the unique index already exists, and if
  any rows had `is_superseded IS NULL` (produced by `create_snapshot_freeze`
  or any pre-q-series snapshot), converting them all to 0 simultaneously
  violates the index when two or more such rows share the same scope tuple.
  The dedup step that would have cleaned up duplicates ran after the blanket
  conversion — too late.

- Secondary cause: `create_snapshot_freeze` never set `is_superseded` at all,
  leaving every freeze snapshot with `is_superseded IS NULL`. These silently
  accumulated and triggered the crash on the next startup.

What changed:
- `psi/core/db.py` (`ensure_schema`): replace the blanket NULL→0 backfill
  with a safe per-scope algorithm:
    1. Early-exit if no NULL rows exist (idempotent, zero cost on clean DBs).
    2. For each affected scope, fetch all candidate-active rows (NULL or 0)
       ordered newest-first.
    3. Mark all losers `is_superseded=1` FIRST — this only removes rows from
       the active set and can never violate the unique index.
    4. Set the remaining NULLs (now guaranteed: at most one per scope) to 0.
  This is safe on first run, safe on all subsequent runs, and idempotent.

- `psi/services/decisions.py` (`create_snapshot_freeze`): explicitly set
  `is_superseded=0` on every new freeze snapshot. Prevents future NULL
  accumulation from this path.

What did NOT change:
- No DI engine logic changes. No policy changes. No selector changes.
- No snapshot content changes. No integrity hash changes.
- `runner.py` supersession logic is untouched (already correct).

## v1.2.9r3

Why:
- Constitution hardening: clarify DI scope, patch governance, and the legacy YAML engine boundary.

What changed:
- `docs/DI_CONSTITUTION.md`
  - Add explicit scope + canonical DI surfaces list (what the Constitution governs).
  - Add patch governance requirements (required sanity commands + second-pass review triggers).
  - Clarify legacy YAML rules engine boundary vs canonical DI engine.
  - Refine Drift Guards wording: disallow scoring/ranking/adaptive tables while permitting deterministic audit/provenance/labeling tables (e.g. `OutcomeLabel`).

What did NOT change:
- Docs-only patch: no DI engine changes, no policy changes, no selector changes.
- No DB changes / migrations.
- No snapshot contract changes.

## v1.2.9r2

Why:
- Restore DI Snapshot Contract invariant: anchored replay must reproduce the stored `snapshot_content_hash` exactly.
- v1.2.9r1 correctly prevented legacy anchored replay from "seeing the future" by using an effective `as_of_ts=snapshot.created_at`, but this changed the replay output surface (`provenance.as_of_ts`) for snapshots that originally stored `as_of_ts=null`, causing a contract smoke regression.

What changed:
- `psi/services/di/verify.py`
  - Anchored replay still computes with an effective `as_of_ts` for legacy snapshots (prevents future influence).
  - Verification-only surface alignment now mirrors stored `provenance.as_of_ts` (including `null`) onto the anchored replay output and recomputes integrity hashes on the adjusted payload.

What did NOT change:
- No policy changes. No selector changes. No DB changes / migrations.

## v1.2.9r1

Why:
- Fix anchored replay determinism for legacy snapshots where `inputs_json.as_of_ts` is null.
- Without an explicit as-of timestamp, replay runs at "now" and can drift on summary surfaces (e.g. SoE evidence_summary timestamps/counts), even when the anchored evidence IDs are unchanged.

What changed:
- `psi/services/di/verify.py`
  - Split verification into two DI inputs:
    - current-world recompute keeps `as_of_ts=None` (interpreted as "now")
    - anchored replay uses `as_of_ts=snapshot.created_at` when the snapshot omitted `as_of_ts`
  - Add a small verification-only legacy alignment step for anchored replay when the stored snapshot has a type mismatch in `provenance.inputs_fingerprint.scope_id`:
    - copy the stored value into the replay output
    - recompute integrity hashes on the adjusted payload (read-only)

What did NOT change:
- No schema changes. No migrations.
- No DI engine / policy / selector logic changes.
- No mutation of existing snapshots.

## v1.2.9r

Why:
- Add an institutional replay regression harness to continuously validate that persisted DI snapshots can be deterministically replayed via the anchored replay path.
- This is a read-only hardening layer: it does not change DI governance rules, policy semantics, selector semantics, or snapshot persistence.

What changed:
- New CLI tool: `python -m psi.tools.di_replay_regression`
  - Enumerates stored `decision_snapshots` deterministically.
  - For each snapshot, runs the existing verification service anchored replay path and gates on `stored_vs_replay_classification == VERIFIED`.
  - Emits a clear, deterministic report with per-snapshot failures and a minimal semantic diff snippet (excluding volatile fields).
  - Exit code 0 if all pass; non-zero if any fail.

Determinism + governance notes:
- Replay is read-only and must not write new snapshots or mutate existing snapshots.
- Policy is resolved by the snapshot-stored `policy_id` + `policy_version` (no fallback to latest).
- Semantic diff ignores explicitly-volatile fields (as defined by the verifier):
  - `outputs.engine.code_version`
  - `outputs.provenance.integrity`

What did NOT change:
- No schema changes. No migrations.
- No DI engine logic changes. No policy changes. No selector changes.
- No changes to integrity hashing functions or verification classifications.

## v1.2.9q8a

Why:
- Hotfix: v1.2.9q8 patch for `psi/services/decisions.py` was missing `from sqlalchemy import text`, causing a runtime `NameError` when the legacy `run_and_snapshot()` path executes.
- This hotfix adds the missing import only. No logic changes beyond v1.2.9q8.

## v1.2.9q8

Why:
- Fix two logic bugs in `psi/services/decisions.py` introduced by the v1.2.9q
  supersession patch. Both are runtime failures; neither is a syntax error and
  neither is caught by compileall.

Bug 1 — `run_and_snapshot` never creates a snapshot on the first run:
  The snapshot creation block (`snap = DecisionSnapshot(...)` and all code
  after it) was accidentally nested inside `if active_ids:`. On the first run
  for any scope, `active_ids` is empty, the branch is skipped, and the function
  returns `None`. The web router then crashes with AttributeError accessing
  `snap.id` on None. Every first-time "Run DI" or legacy decision button press
  would 500.
  Fix: move `snap = DecisionSnapshot(...)` and everything following it to
  function scope. The mark-superseded UPDATE stays conditional (only runs when
  there are prior actives). Snapshot creation is now unconditional.

Bug 2 — `create_snapshot_freeze` raises NameError at runtime:
  The function referenced `active_ids` at lines 220–221, a variable that only
  exists in `run_and_snapshot`. `create_snapshot_freeze` never queries for
  prior snapshots and has no `active_ids` of its own. Any call to this function
  would raise `NameError: name 'active_ids' is not defined`.
  Fix: remove the stray `if active_ids:` block entirely from
  `create_snapshot_freeze`. The function now creates the snapshot and commits
  without attempting supersession (which it was never intended to do).

What did NOT change:
- No DI engine logic changes. No policy changes. No selector changes.
- No schema changes. No migrations.
- runner.py supersession logic is untouched (it was correct).
- db.py is untouched.
- models.py is untouched.

## v1.2.9q7
- Hotfix: fix runtime NameError in `psi/services/di/runner.py` (`scope_batch_id` undefined inside `compute_di_output()`).
- Structural-only change: define `scope_batch_id = int(di_input.scope_id)` within `compute_di_output()` so selection calls are self-contained; no governance logic changes.
## v1.2.9q5
- Hotfix: fix v1.2.9q overlay corruption in `psi/services/di/runner.py` that deindented the governed snapshot return path, causing `SyntaxError: 'return' outside function`.
- Structural-only change: restore correct block structure so snapshot creation + supersession update executes inside the intended function (no logic changes).
## v1.2.9q6
- Hotfix: restore structural correctness in `psi/services/di/runner.py` (supersession + snapshot creation code re-indented inside `run_di()`).
- No logic changes beyond repairing overlay corruption; governance additions preserved.
## v1.2.9q4
- Hotfix: fix remaining v1.2.9q overlay corruption in `psi/services/decisions.py` where the supersession block was deindented to module scope, causing `SyntaxError: 'return' outside function`.
- Structural-only change: re-indent the governed snapshot path so all logic executes inside `run_and_snapshot()`.

## v1.2.9q3
- Hotfix: restore syntactically valid `psi/services/decisions.py` after v1.2.9q overlay corruption caused `SyntaxError: 'return' outside function`.
- No logic changes intended; file content restored to the v1.2.9q governed snapshot path with correct block structure.

## v1.2.9q2 — Hotfix: Restore schema/model structural integrity (no logic changes)

Fixes patch-overlay structural corruption introduced in v1.2.9q:

- `psi/core/db.py`: ensure v1.2.9q supersession backfill + index creation stays inside `ensure_schema()` / proper `with eng.begin()` scope (prevents `IndentationError` / stray module-level execution).
- `psi/core/models.py`: restore truncated `DataRecord.raw_inputs_json` line and place snapshot supersession columns inside `DecisionSnapshot` where they belong (fixes syntax break + correct ORM placement).

No behavior changes beyond restoring intended code placement and importability.


## v1.2.9q

Why:
- Governance hardening: institutionalize snapshot lifecycle clarity without changing DI logic or replay determinism.

What changed:
- Add snapshot supersession metadata (`is_superseded`, `superseded_by_snapshot_id`, `superseded_at`) (additive).
- Enforce single ACTIVE snapshot per scope `(decision_key, program_id, molecule_id, batch_id)` transactionally on snapshot insert.
- Add deterministic backfill to mark older snapshots as superseded per scope on existing DBs.
- Add a partial unique expression index to guarantee at most one ACTIVE snapshot per scope under SQLite NULL semantics.
- UI: Decisions list + detail pages display ACTIVE/SUPERSEDED status and (when present) the superseding snapshot link.
- Smoke test: future-proof cross-version patching to include verify module PSI_VERSION if it is ever introduced.

Notes:
- Snapshot content immutability is preserved: governance fields are metadata and are excluded from DI semantic hashes.

## v1.2.9p

Why:
- Complete the remaining DI v0.6 UI transparency surfaces without changing DI engine behavior.

What changed:
- Molecule detail UI: add a contextual **Run DI** entry point linking to `/decisions/new` with `program_id` + `molecule_id` prefilled.
- Batch Decisions tab UI: add **Run DI for this batch** entry point (and show it even when there are no snapshots yet) with `program_id` + `molecule_id` + `batch_id` prefilled.
- Decisions "Run Decision" form UI: parse query params (`program_id`, `molecule_id`, `batch_id`) to preselect scope inputs deterministically (navigation-only; no DI logic changes).
- Snapshot detail UI (`decisions/_di_snapshot.html`):
  - Add **SoE Coverage** section rendering stored `soe_v0_3` (or `soe_v0_2` fallback) metric status + required/optional grouping + gate coverage, with deterministic ordering.
  - Add `decision_output_hash_v2_effective` display in the integrity section.

Governance hygiene:
- Verified `compress.sh` includes `docs/DI_MISSION_AND_ROADMAP.docx` and `PSI_CONTEXT.md` accurately reflects this (no changes required).

What did NOT change:
- No DI engine logic changes. No policy changes. No selector changes.
- No DB changes / migrations.


## v1.2.9o2
- Fix DI contract smoke cross-version test to use current create_data_record/upsert_measurements signatures.
- Ensure cross-version test references packaged advance_to_in_vivo_v0_1 policy path.

## v1.2.9o

Why:
- Normalize the snapshot integrity surface so `snapshot_content_hash` remains stable across code version upgrades.
- Prevent false drift / verification noise caused by `outputs.engine.code_version` changing between releases.

What changed:
- `psi/services/di/integrity.py`: exclude `outputs.engine.code_version` from `snapshot_content_hash` payload (while keeping it in stored outputs JSON).
- `docs/DI_SNAPSHOT_CONTRACT.md`: document `outputs.engine.code_version` as metadata excluded from `snapshot_content_hash`.
- `psi/tools/di_contract_smoke.py`: add regression test simulating a cross-version verify by patching module PSI_VERSION between snapshot creation and verification.

What did NOT change:
- No readiness logic changes. No gate changes.
- No policy JSON changes. No selector changes.
- No DB changes / migrations.
- No UI changes.


## v1.2.9n5

Why:
- Fix `semantic_fingerprint` always returning `""` (empty string) in both stored
  and anchored replay verify output, causing the smoke test assertion
  `stored + replay semantic_fingerprint must be non-empty` to fail.

Root cause:
- `_semantic_fingerprint()` in `verify.py` called `compute_snapshot_content_hash()`
  with a single positional argument. That function requires three keyword arguments
  (`inputs_obj`, `outputs_obj`, `evidence_ids`). The call always raised `TypeError`,
  which was silently swallowed by the surrounding `except Exception: return ""`.
  The function has been broken since it was introduced; the n4 smoke test assertion
  exposed it by fixing the earlier `snapshot_content_hash` mismatch that was
  masking this failure.

What changed:
- `psi/services/di/verify.py`: `_semantic_fingerprint()` now computes
  `sha256(stable_json(stripped_outputs))` directly, which is what the function
  always intended — a self-contained hash of the output payload with volatile
  fields (`engine.code_version`, `provenance.integrity`) removed. `hashlib`
  moved to module-level import.

What did NOT change:
- No policy changes.
- No selector changes.
- No DB changes / migrations.
- No changes to `snapshot_content_hash`, `evidence_fingerprint`, or
  `decision_output_hash_v2` — those are correct and stable.

## v1.2.9n4

Why:
- Fix `snapshot_content_hash` mismatch between runner and anchored replay.
  Root cause: `scope_id` type inconsistency — runner stored `scope_id` as a string
  (from callers passing `str(b.id)`), but verify.py reconstructed `DIInput` with
  `scope_id=int(...)`. `compute.py` wrote `di_in.scope_id` directly into
  `outputs.provenance.inputs_fingerprint`, producing `"7"` (str) in stored outputs
  and `7` (int) in anchored replay outputs. `_stable_json` serializes these
  differently, causing `snapshot_content_hash` to differ.

What changed:
- `psi/services/di/compute.py`: normalize `scope_id` to `int` in
  `provenance.inputs_fingerprint`.
- `psi/services/di/runner.py`: normalize `scope_id` to `int` in `inputs_obj`
  at all 3 call sites.
- `psi/core/di/schema.py`: added `__post_init__` to `DIInput` to coerce `scope_id`
  to `int` at construction. Catches `str(b.id)` callers at the entry point.
- `psi/tools/di_contract_smoke.py`: fixed `scope_id=str(b.id)` → `int(b.id)`.

What did NOT change:
- No policy changes. No selector changes. No DB changes / migrations.

## v1.2.9n3

Why:
- Fix anchored replay snapshot_content_hash mismatch by ensuring runner and anchored replay compute operate on identical in-memory SoE types.

What changed:
- DI shared compute now normalizes `ignored_evidence` entries to `IgnoredEvidence` objects before SoE packing and downstream logic.

What did NOT change:
- No policy changes.
- No selector changes.
- No DB changes / migrations.

## v1.2.9o4
- Hotfix: di_contract_smoke cross-version test now passes policy_path as Path (fixes str.read_text crash) and restores valid module syntax.

## v1.2.9o5
- Hotfix: di_contract_smoke cross-version test now treats classification==VERIFIED as pass when verify_snapshot omits legacy 'ok' flag.

## 2026-02-23 — v1.2.9v23
Why:
- Align smoke_test guardrail with append-only PATCH_NOTES discipline (latest entry at file end).

What changed:
- `psi/scripts/smoke_test.py`: latest PATCH_NOTES header is now read from the last dated entry.

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No UI changes.

## 2026-02-23 — v1.2.9v24
Why:
- Version sync: verify + compare DI snapshot UI already exists in this repo; no new behavior required.

What changed:
- Version bump only (no code changes needed).

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No UI changes.

## 2026-02-23 — v1.2.9v25
Why:
- Harden SQL IN-clause usage to use SQLAlchemy expanding bind parameters.

What changed:
- `psi/services/molecules.py`: replace dynamic `IN (...)` string binds with `bindparam(expanding=True)`.

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No UI changes.

## 2026-02-23 — v1.2.9v26
Why:
- Standardize naive UTC helpers in service layers without altering timestamps.

What changed:
- `psi/services/qc.py`: route QC timestamps through `now_utc()` helper.
- `psi/services/measurements.py`: use `now_utc()` for default timestamp parsing fallback.

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No UI changes.

## 2026-02-23 — v1.2.9v27
Why:
- Document WAL journal-mode expectations for writable databases.

What changed:
- Version bump only (WAL pragmas already enforced on writable connections).

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No UI changes.

Notes:
- Writable SQLite connections attempt `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL`.

## 2026-02-23 — v1.2.9v28
Why:
- Complete hardening sweep: remove f-string SQL assembly and ensure background tasks target the caller DB.

What changed:
- `psi/services/measurements.py`: remove f-string SQL assembly for raw measurement queries/updates.
- `psi/tools/export_measurements.py`: remove f-string SQL for PRAGMA table introspection.
- `psi/tools/qc_measurements.py`: remove f-string SQL for QC updates.
- `psi/core/db.py`: remove f-string SQL for PRAGMA/ALTER statements.
- `psi/web/routers/molecules.py`: pass explicit DB path to background tasks via caller session bind.

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No UI changes.

## 2026-02-23 — v1.2.9v29
What changed:
- `psi/services/di/enrich.py`: add deterministic metric value-function evaluation + interpretation gap detection.
- `psi/services/di/compute.py`: include metric evaluations in DI outputs and emit interpretation-gap risk flags.
- `psi/core/di/policies/advance_to_in_vivo_v0_2.json`: add policy-visible `metric_value_functions` and include `interpretation_gap` in risk flag categories.
- `psi/tools/di_contract_smoke.py` and `psi/tools/run_di.py`: default to the v0.2 policy file.

What did NOT change:
- No DB changes / migrations. No snapshot mutation.
- No scoring weights. No ML. No selector or gate logic changes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9v30
What changed:
- `psi/services/di/eval.py`: add deterministic shortlisting derivation with explicit refusal state.
- `psi/services/di/compute.py`: include shortlisting output when policy allows it.
- `psi/core/di/policies/advance_to_in_vivo_v0_3.json`: add policy-visible shortlisting guardrails.
- `psi/tools/di_contract_smoke.py` and `psi/tools/run_di.py`: default to v0.3 policy.

What did NOT change:
- No DB changes / migrations. No snapshot mutations.
- No scoring weights. No ML. No gate/selector behavior changes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9v31
What changed:
- `psi/web/templates/decisions/_di_snapshot.html`: reorganize DI snapshot view for fast interpretation (top summary first).

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No new routes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9v32
What changed:
- `psi/services/decisions.py`: add OutcomeLabel taxonomy constants and include labels in snapshot export payload.
- `psi/web/routers/decisions.py`: add minimal POST handler to attach OutcomeLabel to a snapshot.
- `psi/web/templates/decisions/_di_snapshot.html`: add Outcome review section with a minimal label form.

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

Notes:
- Outcome labels appear on the snapshot detail UI and in JSON export (`/decisions/{id}/export`).

## 2026-02-23 — v1.2.9v33
What changed:
- `psi/web/routers/molecules.py`: remove duplicate formatting helpers already present in the service layer.

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No route behavior changes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9v34
What changed:
- `psi/core/utils.py`: model_to_dict now serializes all SQLAlchemy column attrs deterministically (superset of prior fields).

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9v35
What changed:
- `psi/web/templates/decisions/detail.html`: add engine badge (DI vs Legacy YAML) and deprecation warning for legacy engine.
- `docs/DI_CONSTITUTION.md`: document deprecation clock (v1.3.0 DI-default; legacy YAML read-only).

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No engine selection changes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9v36
What changed:
- Version-only: ID allocation retry logic already present in `get_or_create_chain` and `create_molecule` (IntegrityError retry loop).

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No route behavior changes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9v37
What changed:
- `psi/services/di/nbe.py`: catalog-driven NBE helper for deterministic experiment suggestions.
- `psi/services/di/compute.py`: emit catalog-driven `experiment_suggestions` and `recommended_experiments`.
- `docs/DI_SNAPSHOT_CONTRACT.md`: document experiment suggestion outputs and determinism rules.

What did NOT change:
- No DI gate/selector logic changes. No ML. No scoring weights.
- No DB changes / migrations.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9v38
What changed:
- DI post-hoc review capture via OutcomeLabel (verdict + rationale) on DI snapshot page.
- UI: add DI review form and show latest review alongside existing outcome labels.
- Service/router: accept DI review submissions without schema changes.

What did NOT change:
- No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9v39
What changed:
- DI snapshot UI: clarified supersession status/labeling.
- DI snapshot UI: added “What to trust” verification box explaining hashes and drift labels.

What did NOT change:
- No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations. No new routes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w01
What changed:
- Version-only: “Verify now” action already present on decision detail (POST `/decisions/{id}/verify`).

What did NOT change:
- No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations. No route behavior changes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w02
What changed:
- Verification UI: clearer status chips, evidence added/removed summary, and per-metric “Why?” block.

What did NOT change:
- No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations. No verification logic changes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w03
What changed:
- Version-only: no f-string SQL `IN (...)` constructions found; existing `IN :ids` uses already use expanding bindparams.

What did NOT change:
- No query semantics changes. No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w04
What changed:
- Version-only: `now_utc()` helper already exists and there are no `datetime.utcnow()` usages to replace.
- Note: timestamps remain naive UTC for SQLite compatibility (current PSI convention).

What did NOT change:
- No query semantics changes. No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w05
What changed:
- Version-only: FastAPI lifespan already implemented in `psi/web/app.py` (no `@app.on_event("startup")` remains).

What did NOT change:
- No startup behavior changes. No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w06
What changed:
- Version-only: SQLite WAL mode already enabled via connect PRAGMAs in `psi/core/db.py`.
- Runtime note: WAL improves concurrency and reduces lock errors; rollback is removing the PRAGMA listener to return to default journal mode.

What did NOT change:
- No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations. No query behavior changes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w07
What changed:
- DI runner now loads the experiment catalog via a canonical loader (no hardcoded file paths in `runner.py`).

What did NOT change:
- No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations. No policy packaging changes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w08
What changed:
- Background tasks in `psi/services/molecules.py` now derive and pass the active `db_path` instead of using import-time `SessionLocal`.
- Note: no behavior change in normal single-DB deployment; fixes alternate db_path correctness in tools/tests.

What did NOT change:
- No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w09
What changed:
- Version-only: duplicated router helpers already removed; router delegates to service layer for molecule business logic.

What did NOT change:
- No behavior changes intended. No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w10
What changed:
- Governance: documented Legacy YAML engine deprecation timeline and risk statement.
- UI: decision views label engine type as “DI engine” vs “Legacy YAML engine” with a caution note.

What did NOT change:
- No decision semantics changes. No DI logic changes. No ML. No scoring weights.
- No DB changes / migrations. No enforcement of engine selection.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w11
What changed:
- Enforced policy value functions in gate evaluation (thresholds/caps now affect gate pass/fail).
- Added threshold-violation risk flags/blockers when present metrics fail policy-defined value functions.
- DI snapshot UI now shows a compact value-function evaluation table.

Why it changed:
- Policy-defined thresholds must be enforced; presence alone should not be treated as pass.

Determinism/contract impact:
- Deterministic; outputs remain additive (`metric_evaluations` already present, now used by gate logic).
- Snapshot contract unchanged; no schema changes.

Behavior changes:
- Gate outcomes and decision_state may change when a metric is present but out-of-range per policy.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w12
What changed:
- Shortlisting output now includes structured tie-break explanations and refusal reasons.
- DI snapshot UI renders tie-break explanations and refusal details.

Why it changed:
- v0.5 requires transparent tie-break reasoning; explanations must be visible to the scientist.

Determinism/contract impact:
- Additive fields only (`tie_break_explanations`), deterministic ordering preserved.
- No change to gate logic or policy semantics.

Behavior changes:
- None (explanations only).

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w13
What changed:
- Gates are now evaluated via a policy-driven evaluator (JSON-gate definitions), with templates acting as thin adapters.

Why it changed:
- Decouple gate logic from Python to honor policy-as-data and unblock multi-template evaluation.

Determinism/contract impact:
- No semantic change intended; gate outcomes/readiness remain equivalent to v1.2.9w12.
- Snapshot contract unchanged; output fields additive only.

Behavior changes:
- None intended (equivalence refactor).

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w14
What changed:
- Refactored DI enrichment into focused modules: `soe`, `metric_eval`, `risk_flags`, `coverage`.
- `enrich.py` now acts as a thin orchestration layer importing the same functions.

Why it changed:
- Improve maintainability by splitting the enrichment "god module" without changing behavior.

Determinism/contract impact:
- No semantic change intended; deterministic ordering preserved.
- Snapshot contract unchanged; no DB/schema changes.

Behavior changes:
- None intended (refactor-only).

Gates run (limit 5; replay run twice):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w15
What changed:
- Added a DI template registry keyed by decision_key and template_key.
- DI runner now resolves templates via the registry (no hard-coded decision_key stop).
- Unknown templates yield deterministic `unsupported_template` outputs (not_ready) instead of raising.

Why it changed:
- Enable multi-template support while keeping policy-as-data and deterministic behavior.

Determinism/contract impact:
- Deterministic output; no schema changes.
- Unsupported templates produce stable, explicit not_ready outputs.

Behavior changes:
- Unknown decision_key/template_key no longer raises; snapshot output is not_ready with governance warning.

Gates run (limit 5; replay run twice):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w16
What changed:
- Added a second DI template: `ready_for_scaleup_screen` (policy + template adapter).
- Registered the new template in the DI template registry.

Why it changed:
- Prove multi-template DI support without altering existing `advance_to_in_vivo` semantics.

Determinism/contract impact:
- Deterministic output; no schema changes.
- Unsupported templates still produce stable `unsupported_template` outputs.

Behavior changes:
- New decision_key `ready_for_scaleup_screen` is now supported.
- No behavior change for `advance_to_in_vivo`.

Gates run (limit 5; replay run twice):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w17
What changed:
- Expanded the experiment catalog with metric-specific experiment mappings.
- NBE suggestion mapping now uses metric_keys to map missing metrics to experiments deterministically.

Why it changed:
- Ensure every policy-referenced metric can yield actionable experiment suggestions when missing.

Determinism/contract impact:
- Deterministic ordering preserved; no schema changes.
- No changes to gate, ranking, or value-function semantics.

Behavior changes:
- Missing metrics now produce richer, metric-specific experiment suggestions.

Gates run (limit 5; replay run twice):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w18
What changed:
- Added a dedicated "Run DI" UI entrypoint and form (batch-scoped).
- Wired DI run to the DI runner service; created DI snapshots from the UI.
- Clarified legacy YAML labeling and links (Run Legacy YAML).

Why it changed:
- Provide an explicit DI run flow while preserving the legacy YAML path.

Determinism/contract impact:
- No DI semantic changes; no schema changes.
- Anchored replay and DI contracts unchanged.

Behavior changes:
- Users can run DI from the UI for supported templates.

Gates run (limit 5; replay run twice):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w19
What changed:
- Fixed Jinja inline conditional syntax in DI verification template.

Why it changed:
- Prevent template rendering errors in the verification UI.

Determinism/contract impact:
- No semantic changes; display-only fix.

Behavior changes:
- None; template renders correctly instead of erroring.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w20
What changed:
- Added a Jinja template compilation guardrail to `psi.scripts.smoke_test`.
- Fixed a Jinja syntax error in `molecules/form.html` caught by the guardrail.

Why it changed:
- Prevent template syntax errors from shipping by failing smoke_test if any template fails to compile.

Determinism/contract impact:
- Deterministic; no runtime behavior changes; no schema changes.

Behavior changes:
- None in production; smoke_test now validates template compilation.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w21
What changed:
- Added Legacy YAML deprecation clock statement to `PSI_CONTEXT.md` (intent-only).

Why it changed:
- Align context doc with Constitution wording and clarify the DI default timeline.

Determinism/contract impact:
- Docs-only; no runtime or schema changes.

Behavior changes:
- None.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w22
What changed:
- Formalized DI snapshot supersession semantics in docs and queries.
- Latest snapshot rollups now use `superseded_by_snapshot_id IS NULL`.
- Added scope+superseded index for deterministic lineage queries.

Why it changed:
- Make snapshot lineage first-class and queryable without changing DI semantics.

Determinism/contract impact:
- No DI evaluation changes; deterministic ordering preserved.
- Snapshot contract now documents lineage metadata.

Behavior changes:
- "Latest" snapshot rollups exclude superseded snapshots.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w23
What changed:
- Added deterministic `drift_type` enum to DI snapshot outputs.
- Drift derivation uses evidence fingerprint, policy semantics hash, and comparability status.
- Snapshot contract updated to document drift_type derivation.
- DI contract smoke now resets its ephemeral DB to keep determinism checks stable.

Why it changed:
- Make drift classification first-class and reproducible across anchored replay.

Determinism/contract impact:
- Deterministic; no schema changes.
- Anchored replay reproduces `drift_type` via stored drift context.

Behavior changes:
- New `drift_type` field present in DI outputs.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w24
What changed:
- DI contract smoke now compares two identical fresh DB copies to avoid run-to-run cross-contamination.
- Added deterministic `state_transition` metadata to DI outputs, derived from prior active snapshot + drift_type.
- Snapshot contract updated to document `state_transition`.

Why it changed:
- Fix harness nondeterminism and make state transitions first-class without altering DI evaluation logic.

Determinism/contract impact:
- Deterministic; no schema changes.
- Anchored replay preserves legacy snapshots without `state_transition`.

Behavior changes:
- New `state_transition` field present on DI outputs when a prior active snapshot exists.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w25
What changed:
- Added structured `comparability` contract fields (`is_comparable`, `reason`, hash-change flags).
- Drift derivation now honors `comparability.is_comparable`.
- Snapshot contract updated with comparability fields.

Why it changed:
- Make comparability a first-class, reproducible contract surface.

Determinism/contract impact:
- Deterministic; no schema changes.
- Anchored replay preserves legacy snapshots without comparability.

Behavior changes:
- New `comparability` fields present in DI outputs.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w26
What changed:
- Added deterministic `diff_summary` to DI verification reports (when comparable + prior snapshot exists).
- diff_summary derives from a curated, contract-level diff surface (hashes excluded).
- Snapshot contract updated to document diff_summary.

Why it changed:
- Provide a governance/audit-friendly summary of structural changes.

Determinism/contract impact:
- Deterministic; no schema changes.
- Legacy snapshots remain byte-stable (diff_summary is report-only).

Behavior changes:
- Verification output may include `diff_summary` when comparable and prior snapshot exists.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w27
What changed:
- Decision detail now shows ACTIVE vs SUPERSEDED, superseded_by link, and superseded_at.
- Added scope-level snapshot history view with deterministic ordering.

Why it changed:
- Make lineage explicit and provide a history entry point for the same decision scope.

Determinism/contract impact:
- Deterministic UI/query only; no schema changes.

Behavior changes:
- New history page at `/decisions/{id}/history`.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w28
What changed:
- History page now supports selecting two snapshots and launching compare.
- Validation enforces exactly two selections with a deterministic order.

Why it changed:
- Enable scope-level compare workflow directly from the history list.

Determinism/contract impact:
- Deterministic UI wiring only; no schema changes.

Behavior changes:
- New “Compare selected” action on `/decisions/{id}/history`.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w29
What changed:
- History compare selection now posts stable `snapshot_ids` and redirects to compare.
- Compare page labels clarify ordering (A newer/higher id; B older/lower id).

Why it changed:
- Make history compare wiring explicit and deterministic.

Determinism/contract impact:
- Deterministic UI wiring only; no schema changes.

Behavior changes:
- Compare page now labels A/B ordering.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w30
What changed:
- Constitution and snapshot contract now explicitly allow controlled, policy-defined shortlisting (no scoring, no opaque ranking).
- Snapshot contract now documents shortlisting schema and deterministic ordering rules.
- NBE recommended_experiments is now de-duplicated by experiment_key with deterministic global ordering and triggered_by_blockers attribution.

Why it changed:
- Align governance docs to actual deterministic outputs and remove contradictions.

Determinism/contract impact:
- Deterministic; no schema changes.
- NBE recommended list ordering is stable across runs and replay.

Behavior changes:
- recommended_experiments is now de-duplicated and includes triggered_by_blockers.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-24 — v1.2.9w31
What changed:
- Determinism fix for di_contract_smoke via baseline cutoff env var: `PSI_DI_BASELINE_CUTOFF_ISO`.

Why it changed:
- Prevent drift baseline from walking forward between the two smoke runs.

Determinism/contract impact:
- If `PSI_DI_BASELINE_CUTOFF_ISO` is set and parses as ISO8601, drift baseline selection only considers snapshots with `created_at <= cutoff`.
- If the env var is absent or invalid, behavior is unchanged (invalid values emit a warning and are ignored).

Behavior changes:
- di_contract_smoke sets `PSI_DI_BASELINE_CUTOFF_ISO` once at process start (if not already set) and reuses it for both runs.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-24 — v1.2.9w32
What changed:
- Patch A hardening/determinism hygiene: normalize_ignored qc alias, stable_json canonicalization, ISO/QC util dedupe, context docs correction, remove program_id fallback.

Why it changed:
- Eliminate replay brittleness, hash authority drift, and silent lineage corruption.

Determinism/contract impact:
- Ignored evidence normalization accepts both qc_status and qc_source, canonicalizing to qc_source.
- Stable JSON hashing/printing uses a single canonical implementation.
- ISO parsing and qc flag status derivation are centralized and deterministic.
- Context knobs remain store-only inputs; no gating impact.
- Missing program_id now fails explicitly; no silent lineage fallback.

Behavior changes:
- run_di CLI and DI web route surface clear errors when program_id lineage is missing.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-24 — v1.2.9w33
What changed:
- Patch B: molecule scope aggregation (deterministic batch selection + aggregation rule; smoke + replay coverage).

Why it changed:
- Enable deterministic molecule-scope DI snapshots without changing batch semantics.

Determinism/contract impact:
- Molecule scope selects all batches for the molecule ordered by created_at asc, id asc; aggregation uses newest-first for per-metric selection.
- Selection provenance records ordered batch list and metric source batch ids; SoE/comparability aggregate over selected batches.

Behavior changes:
- DI runner accepts scope_type="molecule" and aggregates batch evidence deterministically.
- di_contract_smoke exercises molecule scope.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-24 — v1.2.9w34
What changed:
- Determinism hardening: preserve molecule batch order; canonicalize dict key ordering in outputs.

Why it changed:
- Keep molecule batch ordering stable end-to-end and avoid nondeterministic dict ordering in stable JSON surfaces.

Determinism/contract impact:
- Molecule batch_ids are de-duplicated without sorting (first-seen order preserved).
- Used-by-metric and metric source maps are serialized with stable key ordering.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-24 — v1.2.9w35
What changed:
- Patch C1: deterministic ranking + structured why (additive outputs; both scopes; smoke coverage).

Why it changed:
- Provide deterministic multi-candidate ranking output with transparent, structured factors.

Determinism/contract impact:
- Ranking object is additive and ordered deterministically; candidate ordering uses explicit score + tie-breakers.
- Molecule candidate set derives from ordered batch selection provenance; batch scope emits a single candidate.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-24 — v1.2.9w36
What changed:
- Ranking hardening: normalized factor semantics (direction drives sign), deterministic scoring.

Why it changed:
- Remove ambiguity in ranking factors while preserving deterministic ordering.

Determinism/contract impact:
- All ranking weights are positive magnitudes; direction controls sign during scoring.
- Missing or unparseable factor values score as 0.0.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-24 — v1.2.9w37
What changed:
- Patch C2: outcome labeling CLI (OutcomeLabel storage; add/list; DI review verdict+rationale).

Why it changed:
- Provide a deterministic CLI workflow for outcome labels without UI or schema changes.

Determinism/contract impact:
- Outcome labels are metadata only and do not affect DI outputs.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-24 — v1.2.9w38
What changed:
- Fix: add missing json import in decisions service (CLI regression fix)

## 2026-02-24 — v1.2.9w39
What changed:
- Governance fix: DI ranking/weighted scoring is now emitted only when policy shortlisting is explicitly enabled (`shortlisting.allow_shortlisting` / `allow`).
- Contract smoke now asserts ranking is present when enabled and absent when disabled.

## 2026-02-24 — v1.2.9w40
What changed:
- Required gate keys now policy/template-authoritative; removes hardcoded readiness keys; fixes multi-template correctness.
- Readiness and shortlisting fallback gate evaluation now derive required gates from policy ordering and gate metadata.

## 2026-02-25 — v1.2.9w41
What changed:
- Remove DI imports from legacy decisions service (`stable_json_dumps` now DI-owned via `psi.services.di.util`).
- Unify duplicated DI error output builder to reduce drift risk; snapshot error schema preserved.

## 2026-02-25 — v1.2.9w42
What changed:
- Snapshot supersession integrity hardening: write paths now reconcile to a single active snapshot per exact scope before commit (authoritative active semantics: `superseded_by_snapshot_id IS NULL`), with explicit rollback on write failure.
- DI contract smoke now asserts the one-active-snapshot-per-scope invariant after DI writes.
## 2026-02-25 — v1.2.9w47
What changed:
- Governance hardening: removed weighted ranking emission from canonical DI outputs (`output.ranking`) and removed the weighted ranking table from the DI snapshot UI.
- DI contract smoke now asserts weighted ranking is absent while deterministic output and snapshot rendering remain stable.

Why it changed:
- Canonical DI outputs/UI should not present or rely on a weighted-sum "one score" ranking; deterministic shortlisting/tie-break remains the policy-authorized path.

Determinism/contract impact:
- `shortlisting` remains deterministic and canonical; weighted ranking is no longer emitted in canonical snapshots.
- `why_evidence` structure remains additive-compatible, with `why_evidence.ranking.candidates` empty when no canonical ranking is emitted.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w48
What changed:
- `/di/run` now supports both `batch` and `molecule` scope types via a scope selector and separate scope inputs.
- GET query prefills work for both `batch_id` and `molecule_id`; POST now passes the selected scope type/id through to `DIInput`.

Why it changed:
- Complete v0.6 DI run usability for molecule-scope runs without changing DI compute behavior.

Determinism/contract impact:
- No DI compute/output changes; this is UI/router plumbing only.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w49
What changed:
- Confirmed and preserved DI run links on batch and molecule detail pages.
- Applied a small UI consistency polish on the molecule detail page DI action button label/style.

Why it changed:
- Improve DI run discoverability in the batch/molecule detail workflows with consistent call-to-action styling.

Determinism/contract impact:
- No DI compute/output or schema changes; template-only discoverability update.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w50
What changed:
- Implemented deterministic shortlisting reproducibility signal from SoE `evidence_summary` counts for required metrics (`total_count > 1` and `usable_count > 1`).
- Added reproducibility details to shortlisting tie-break payloads and tie-break explanations.
- DI contract smoke now asserts the reproducibility block is emitted when evidence summaries are present.

Why it changed:
- Complete the v0.5 tie-break chain reproducibility signal using existing deterministic SoE evidence summaries, without introducing weighted scoring.

Determinism/contract impact:
- Reproducibility signal ordering is deterministic (`metrics` ordered by metric key).
- No global score/ranking reintroduced; shortlisting remains deterministic and additive.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w51
What changed:
- Deduplicated DI `inputs_obj` construction in `runner.py` so success and deterministic error paths emit the same snapshot input keys.
- Added an additive/idempotent `ensure_schema()` backfill for `decision_snapshots.engine_key='di'` when `engine_key IS NULL` and `schema_version` indicates DI (`di.%`).
- Clarified DI integrity hash hierarchy docs and the `psi.services.di.enrich` shim/facade role (behavior unchanged).

Why it changed:
- Reduce maintenance drift and make DI metadata/integrity behavior easier to understand without changing canonical DI outputs.

Determinism/contract impact:
- No schema drops/renames; backfill only updates NULL `engine_key` rows and is safe to rerun.
- DI output behavior remains unchanged (helper extraction + docs only).

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w52
What changed:
- Byte-copied `advance_to_in_vivo_v0_3.json` from canonical `psi_repo` to restore exact bytes and prevent historical policy hash drift.
- Added opt-in context-aware policy package `advance_to_in_vivo_v0_4.json` with deterministic route-based functional gate branching (`SC` vs default) expressed in policy data.
- Threaded `DIInput.context` into derived gate-outcome evaluation and version-gated new context branch surfacing to v0.4+ only (`gate_outcomes.*.context_branch` and `output.context_evaluation`).
- DI run UI default policy selection remains pinned to `advance_to_in_vivo` v0.3; selecting v0.4 is explicit via policy dropdown.
- Replay verification now hard-pins policy resolution by stored policy hashes (exact match first) and skips locally drifted snapshots whose exact policy package is not available in repo (`policy_exact_match_not_found`).
- Anchored replay applies a legacy v0.3 surface scrub to prevent post-w52 context-branch fields from leaking into historical replay outputs.
- DI contract smoke asserts deterministic context-branch selection via pure gate derivation fixtures.

Why it changed:
- Make `route`/`model`/`study_intent` context knobs materially affect gate evaluation in a deterministic, policy-authoritative way without changing replay surfaces for historical snapshots.

Determinism/contract impact:
- Historical v0.3 snapshots retain their prior canonical output surface and policy hashes.
- New context branch surfaces are emitted only for v0.4+ outputs; branch selection is exact-match and deterministic.
- No scoring/heuristics introduced; schema compatibility preserved additively.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w53
What changed:
- Added v0.4-only deterministic shortlisting refusal extension fields: `refusal_reasons_text`, `tie_break`, and `candidates`.
- Added a deterministic reproducibility-count refusal trigger for v0.4 shortlisting (`total_count>1` and `usable_count>1` on required metrics).
- DI snapshot UI now shows stable refusal reason text when present.
- Replay scrub removes these v0.4 refusal extension fields from historical v0.3 replay outputs.

Why it changed:
- Make refusal-to-rank explicit and contract-stable for v0.4+ while preserving v0.3 replay surfaces unchanged.

Determinism/contract impact:
- v0.4 refusal extensions are deterministically ordered and text-normalized.
- Historical v0.3 replay outputs remain scrubbed to prior surfaces.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w54
What changed:
- Added v0.4-only explicit tie-break dimension payloads (`tie_break_dimensions` and `shortlisting.tie_break.dimensions`) with stable ordering and `implemented`/`deferred` statuses.
- Completed deterministic dimension coverage for readiness completeness, QC confidence, purity aggregation profile, reproducibility, and potency/functional (with explicit deferral reason when not policy-required).
- Replay scrub removes these v0.4 tie-break extension fields from historical v0.3 replay outputs.

Why it changed:
- Complete the tie-break hierarchy transparently without introducing any global score or weighted ranking.

Determinism/contract impact:
- Tie-break dimension keys and order are fixed and deterministic for v0.4+.
- v0.3 replay surfaces remain unchanged via replay scrub.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w55
What changed:
- Added v0.4-only additive `output.scope_semantics` with explicit batch-first ranking semantics and molecule derivation metadata (`best_ready_batch_per_molecule`).
- Scope semantics include deterministic batch-ranked and molecule-derived views, and respect shortlisting refusal (no fabricated rankings).
- DI snapshot UI now displays a read-only scope-semantics summary.
- Replay scrub removes `scope_semantics` from historical v0.3 replay outputs.

Why it changed:
- Codify batch-vs-molecule shortlisting semantics explicitly and auditably without introducing scores.

Determinism/contract impact:
- `scope_semantics` is emitted only for v0.4+ and is derived from deterministic inputs (`scope_type`, `scope_id`, `selection_provenance`, refusal state).
- v0.3 replay surfaces remain unchanged via replay scrub.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w56
What changed:
- Added shared pure sub-assessment helpers (`psi/services/di/sub_assessments.py`) and used them in both DI templates for baseline risk flags and decision-state derivation.
- Extended template registry metadata with deterministic dependency declarations and added a deterministic template dependency graph helper.
- Exposed template dependency graph additively in DI output/provenance for v0.4+ only.
- Replay scrub removes template dependency graph fields from historical v0.3 replay outputs.

Why it changed:
- Establish a minimal v1.0 baseline for multi-template DI governance and reusable deterministic sub-assessments.

Determinism/contract impact:
- Registry keys and dependency graph nodes/edges are emitted in deterministic order.
- Existing template behavior is preserved (metadata/additive surfaces only).
- v0.3 replay surfaces remain unchanged via scrub.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w57
What changed:
- Added minimal DI snapshot forms for structured post-hoc labeling (`outcome label type + note`, and `DI review verdict + rationale`) using the existing `/decisions/{snap_id}/outcomes` write path.
- Added deterministic server-side validation helpers for outcome labels and DI review submissions in `psi/services/decisions.py`.
- Router outcome POST handler now uses the shared validation helpers (behavior preserved; controlled keys and rationale requirements enforced server-side).
- DI contract smoke now tests validation helpers deterministically without DB writes.

Why it changed:
- Complete the v1.1 baseline structured outcome-labeling workflow without affecting DI decision logic.

Determinism/contract impact:
- Outcome label validation is deterministic and server-side authoritative.
- DI logic and snapshot computation outputs are unchanged.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w58
What changed:
- Confirmed `/di/run` web execution supports both `batch` and `molecule` scope POSTs and DIInput passthrough.
- Tightened deterministic ordering for `/di/run` selector lists with explicit `created_at DESC, id DESC` ordering for batches and molecules.

Why it changed:
- Close the remaining audit gap for molecule-scope DI execution from the web form with stable selector ordering.

Determinism/contract impact:
- No DI engine logic changes.
- No replay surface changes.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-26 — v1.2.9x10
What changed:
- Added `psi/tools/ci_gate_suite.py` (optional, stdlib-only) to run the canonical 4 required gates in the same order used for operator patching.
- The tool streams command output and prints a stable summary JSON (`ci_gate_suite_v1`) with per-command return codes.
- Returns non-zero on the first failing gate.

Why:
- Provide a single deterministic command entry point for CI/humans without changing or replacing the existing gate tools.

Determinism/Replay note:
- Tooling-only change; no DI compute/output/hash changes.
- Replay regression remains the proof target.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/ci_gate_suite.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x11
What changed:
- Added `psi/core/di/policy_registry_manifest.json` (validation-only registry of policy filename, version, and package hash).
- Added contract smoke validation to verify the registry manifest entries are filename-sorted and match current package hashes deterministically.

Why:
- Introduce a committed policy package hash index for governance validation without changing runtime policy selection behavior.

Determinism/Replay note:
- Validation-only change; no DI runtime policy mutation or hash recomputation changes.
- Manifest is generated from deterministic file ordering and canonical package hashing via `load_policy`.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/policy_registry_manifest.json`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x12
What changed:
- Added strict exact versioned policy path resolver in `psi/core/di/policy.py` (`resolve_versioned_policy_path`).
- Updated replay policy resolution (`psi/services/di/verify.py::_resolve_policy_from_repo`) to use exact versioned filenames instead of directory-scan fallback for `policy_id + policy_version`.
- Added contract smoke assertion for strict resolver mapping (`advance_to_in_vivo + v0.5 -> advance_to_in_vivo_v0_5.json`).

Why:
- Tighten policy loading semantics to deterministic exact versioned filenames and remove implicit fallback behavior.

Determinism/Replay note:
- Resolution is stricter but deterministic and output-preserving with current versioned policy files present.
- Replay remains the proof target under strict skip-fatal enforcement.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/policy.py`
- `psi/services/di/verify.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x13
What changed:
- Hardened `psi.tools.di_replay_regression` with a pre-check that each replayed snapshot’s stored `policy_package_hash` exists in `psi/core/di/policy_registry_manifest.json`.
- Replay now fails explicitly on missing/unknown snapshot policy package hashes before anchored verification.
- Added contract smoke coverage ensuring the registry manifest contains the forward-default policy package hashes (`advance_to_in_vivo_v0_5`, `ready_for_scaleup_screen_v0_2`).

Why:
- Add a governance integrity assertion tying replayed snapshots to a committed registry of known policy package hashes.

Determinism/Replay note:
- Validation-only hardening over stored snapshot metadata; no DI runtime output changes.
- Replay remains strict (`failed=0`, `skipped=0`) for patch acceptance.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_replay_regression.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x14
What changed:
- Added governance diagnostic CLI `psi.tools.policy_hash_audit`:
  - current policy hashes (from repo files)
  - snapshot-referenced hashes (read-only DB)
  - deterministic mismatch report against `policy_registry_manifest.json`
- Added contract smoke determinism check for the audit report output shape/content on a fixed DB sample.

Why:
- Provide an operator-facing diagnostic to inspect policy hash state without mutating DB or policy files.

Determinism/Replay note:
- Read-only diagnostic tooling + validation only; no DI runtime semantics changes.
- Audit output ordering is explicit and stable.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/policy_hash_audit.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x15
What changed:
- Expanded deterministic ordering validation in `psi.tools.di_contract_smoke` for:
  - risk flag enrichment ordering with `medium`/legacy `moderate` equivalence
  - policy `blocker_suggestions` mapping key ordering
  - policy `gate_order` / `required_gate_keys` duplicate-free stability checks

Why:
- Harden deterministic governance checks without changing runtime DI behavior.

Determinism/Replay note:
- Validation-only patch; no DI compute/output/hash changes.
- Replay remains strict and skip-fatal from x10 onward.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x16
What changed:
- Added sidecar freeze metadata file `psi/core/di/policy_metadata_freeze.json` to carry immutable-policy warning text without modifying JSON policy bytes.
- Added contract smoke validation that the sidecar covers the expected legacy snapshot-referenced policy files and carries the freeze notice text.

Why:
- JSON policy files cannot safely include comments; a sidecar preserves the freeze banner intent without changing policy hashes.

Determinism/Replay note:
- No policy JSON content changes; legacy policy package hashes remain untouched.
- Validation-only metadata addition.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/policy_metadata_freeze.json`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x17
What changed:
- Added final governance consolidation smoke checks ensuring:
  - forward policy forks (`advance_to_in_vivo_v0_5.json`, `ready_for_scaleup_screen_v0_2.json`) use `medium`
  - legacy `moderate` vocabulary does not appear in the forward fork files
- Final version bump for the x08→x17 governance hardening chain.

Why:
- Close the chain with explicit deterministic validation of forward severity vocabulary without mutating legacy policy JSON.

Determinism/Replay note:
- Validation-only patch; no runtime DI behavior changes.
- Replay remains strict (`failed=0`, `skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x18
What changed:
- Governance repair: restored legacy snapshot-referenced policy JSON files to pre-mutation content (`moderate` severity vocabulary) using the pre-`x07` code snapshot baseline (`v1.2.9x06`) as the source of truth:
  - `advance_to_in_vivo_v0_1.json`
  - `advance_to_in_vivo_v0_2.json`
  - `advance_to_in_vivo_v0_3.json`
  - `advance_to_in_vivo_v0_4.json`
  - `ready_for_scaleup_screen_v0_1.json`
- Kept forward policy forks unchanged:
  - `advance_to_in_vivo_v0_5.json` remains `medium`
  - `ready_for_scaleup_screen_v0_2.json` remains `medium`
- Regenerated/realigned:
  - `psi/core/di/policy_immutability_manifest.json`
  - `psi/core/di/policy_registry_manifest.json`

Why:
- Repair legacy policy immutability breach so historical snapshot `policy_package_hash` resolution remains exact and replay-stable.

Determinism/Replay note:
- Legacy policy bytes were restored from a deterministic baseline snapshot artifact, not hand-edited.
- Forward-fork defaults remain active (`v0.5` / `v0.2`); runtime compat shims continue to handle legacy `moderate`.
- Replay strictness (`matched=5, failed=0, skipped=0`) is the acceptance proof.
- Archival orphaned policy packages (under `psi/core/di/policies/_orphaned_snapshot_packages/`) exist solely for historical snapshot hash resolvability and are non-active for new policy selection/defaults.
- Canonical legacy policy files remain restored to pre-mutation bytes; orphaned archival files preserve the accidental x17-mutated package bytes for exact replay lookup only.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/policies/advance_to_in_vivo_v0_1.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_2.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_3.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_4.json`
- `psi/core/di/policies/ready_for_scaleup_screen_v0_1.json`
- `psi/core/di/policy_immutability_manifest.json`
- `psi/core/di/policy_registry_manifest.json`
- `psi/core/di/policies/_orphaned_snapshot_packages/advance_to_in_vivo_v0_1__x17_mutated_medium.json`
- `psi/core/di/policies/_orphaned_snapshot_packages/advance_to_in_vivo_v0_2__x17_mutated_medium.json`
- `psi/core/di/policies/_orphaned_snapshot_packages/advance_to_in_vivo_v0_3__x17_mutated_medium.json`
- `psi/core/di/policies/_orphaned_snapshot_packages/advance_to_in_vivo_v0_4__x17_mutated_medium.json`
- `psi/core/di/policies/_orphaned_snapshot_packages/ready_for_scaleup_screen_v0_1__x17_mutated_medium.json`
- `psi/services/di/verify.py`
- `psi/tools/di_contract_smoke.py`
- `psi/tools/policy_hash_audit.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x19
What changed:
- Changed `psi.services.di.risk_flags.derive_risk_flags_enriched()` unknown/unmapped risk key fallback severity from `low` to `unspecified` (neutral semantics).
- Kept deterministic sorting with explicit rank ordering and `unspecified` placed after `low`.
- Added contract smoke assertion that unknown risk keys deterministically emit `severity=\"unspecified\"`.

Why:
- Unknown risk keys should be neutral/not-assessed rather than implicitly treated as low-severity concerns.

Determinism/Replay note:
- Deterministic categorical logic only; no weighted logic introduced.
- Replay strictness remains the acceptance proof (`matched=5, failed=0, skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/risk_flags.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x20
What changed:
- Extracted DI error-output builder body from `psi/services/di/runner.py` into new module `psi/services/di/error_output.py` (`build_di_error_output_payload`).
- Kept `runner._build_di_error_output(...)` signature intact as a thin delegating wrapper (no behavioral changes intended).
- Added an explicit contract-smoke alias test documenting the parity guard against happy-path top-level field drift.

Why:
- Reduce `runner.py` size/risk and isolate error-output shaping while preserving the existing parity guarantees.

Determinism/Replay note:
- Refactor + parity-validation hardening only; no intended DI output changes.
- Replay strictness remains the acceptance proof (`matched=5, failed=0, skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/error_output.py`
- `psi/services/di/runner.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x21
What changed:
- Moved weighted ranking-factor constants out of `psi/services/di/compute.py` into policy-as-data JSON:
  - `psi/core/di/catalogs/shortlisting_policy_v0_1.json`
- Added deterministic loader in `compute.py` for ranking weights with explicit defaults and stable key handling.
- Replaced in-Python numeric ranking constants (`50.0`, `5.0`, `3.0`, `2.0`, `1.0`, `0.5`) in `_build_ranking(...)` with policy-loaded values (same numeric values preserved).
- Added contract smoke schema/value checks for the shortlisting policy catalog.

Why:
- Reduce hidden weighted heuristics in Python and make the ranking weight surface explicit, versioned, and auditable.

Determinism/Replay note:
- Policy-as-data extraction only; weights remain identical to prior values.
- Replay strictness remains the acceptance proof (`matched=5, failed=0, skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/shortlisting_policy_v0_1.json`
- `psi/services/di/compute.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x22
What changed:
- Extracted weighted ranking / shortlisting helper cluster from `psi/services/di/compute.py` into new module `psi/services/di/shortlisting.py`.
- `compute._build_ranking(...)` now delegates to `shortlisting.build_ranking_payload(...)`.
- Policy-loaded ranking weights from x21 are now read in the dedicated module.

Why:
- Reduce `compute.py` size/risk and isolate the ranking/shortlisting-weight helper cluster without changing semantics.

Determinism/Replay note:
- Refactor + wiring only; no intended ranking or DI output changes.
- Replay strictness remains the acceptance proof (`matched=5, failed=0, skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/compute.py`
- `psi/services/di/shortlisting.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x23
What changed:
- Fixed `_build_progress_stage_advisory(...)` to aggregate ALL prerequisite stage blockers/advisories (deterministically) instead of returning only the first one.
- Added `blocked_by_items` list to the stage advisory payload while preserving `blocked_by_text` (now aggregated).
- Updated contract smoke to assert multi-blocker advisory aggregation and stable ordering.

Why:
- Scientist-first progress header should surface all deterministic stage blockers, not just the first advisory row.

Determinism/Replay note:
- UI/view-model only; no DI snapshot/hash changes.
- Replay strictness remains the acceptance proof (`matched=5, failed=0, skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecule_header.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x24
What changed:
- Added targeted deterministic pytest coverage for `psi.services.molecule_header._build_molecule_header_model` in `tests/test_molecule_header_model.py`.
- Coverage includes:
  - legacy `moderate` -> `medium` normalization in header risk counts/items
  - unknown severity -> `unspecified` neutral handling
  - stage advisory presence with `blocked_by_items` surfaced in header model

Why:
- Add direct pytest coverage for the core scientist-first molecule header view-model assembly without requiring DB/network dependencies.

Determinism/Replay note:
- Test-only additions; no runtime DI behavior changes.
- Replay strictness remains the acceptance proof (`matched=5, failed=0, skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_molecule_header_model.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x25
What changed:
- Added pytest wrapper test `tests/test_di_contract_smoke_pytest_wrapper.py` that runs `python -m psi.tools.di_contract_smoke` and fails on non-zero exit.

Why:
- Provide a pytest entrypoint for contract smoke so CI-style pytest runs can cover the deterministic contract checks without changing the existing CLI tool.

Determinism/Replay note:
- Test-only wrapper; no changes to contract smoke behavior or DI runtime logic.
- Replay strictness remains the acceptance proof (`matched=5, failed=0, skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_di_contract_smoke_pytest_wrapper.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x26
What changed:
- Documented the `moderate -> medium` compatibility shim and deprecation horizon in:
  - `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`
- Added inline comments in `psi/services/di/risk_flags.py` clarifying:
  - forward vocabulary is `medium`
  - `moderate` is legacy-only compatibility
  - deterministic rank equivalence is intentional
- Updated docs to reflect x19 behavior: unknown/unmapped risk flags now fall back to neutral `unspecified` (not `low`).

Why:
- Make the compatibility boundary explicit for operators and maintainers while preserving exact historical replay support.

Determinism/Replay note:
- Docs + comments only; no runtime logic changes in this patch.
- Replay strictness remains the acceptance proof (`matched=5, failed=0, skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/risk_flags.py`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x27
What changed:
- Added contract smoke validation that progress-policy early milestone metric keys are representable in the measurement registry field catalog (`psi.core.registry.DATA_SCHEMAS`) deterministically.
- Added `expr_yield_mgL` and `pk_t12_h` to `psi.core.registry.DATA_SCHEMAS` so progress-policy milestone metric keys are representable.
- Added a scoping note in `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md` documenting the legacy YAML engine dependency boundary and intended deprecation approach (no runtime changes).

Why:
- Tighten policy/data integrity checks for progress milestones and clarify the legacy-engine deprecation boundary without affecting DI behavior.

Determinism/Replay note:
- Validation + docs only; no runtime DI logic changes.
- Replay strictness remains the acceptance proof (`matched=5, failed=0, skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x08
What changed:
- Added immutable forward policy forks (new files only; no edits to legacy policy JSON):
  - `psi/core/di/policies/advance_to_in_vivo_v0_5.json`
  - `psi/core/di/policies/ready_for_scaleup_screen_v0_2.json`
- Switched DI run-page default policy selection to the new versions (`v0.5` / `v0.2`) in `psi/services/di/web.py`.
- Added contract smoke lock asserting deterministic latest-policy selection resolves to the new forward forks.

Why:
- Move forward policy defaults without mutating historical policy packages that may already be snapshot-referenced.

Determinism/Replay note:
- Legacy policy files were not modified.
- New policy files are versioned additions only; replay for existing snapshots remains anchored to stored policy hashes.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/web.py`
- `psi/tools/di_contract_smoke.py`
- `psi/core/di/policies/advance_to_in_vivo_v0_5.json`
- `psi/core/di/policies/ready_for_scaleup_screen_v0_2.json`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x09
What changed:
- Added committed baseline hash manifest `psi/core/di/policy_immutability_manifest.json` for policy files under `psi/core/di/policies/`.
- Added stdlib tool `psi/tools/policy_immutability_check.py` to validate policy file contents against the manifest (no rewriting).
- Added contract smoke invocation to fail gates if policy file content diverges from the committed immutability manifest.

Why:
- Prevent accidental mutation of snapshot-referenced policy JSON files while preserving deterministic replay integrity.

Determinism/Replay note:
- Validation-only hardening; no DI runtime semantics or policy loader behavior changes.
- Manifest hashes are deterministic SHA-256 of file bytes with stable file ordering.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/policy_immutability_manifest.json`
- `psi/tools/policy_immutability_check.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x10
What changed:
- Hardened `psi.tools.di_replay_regression` to exit non-zero when `skipped > 0` (in addition to `failed > 0`).
- Replay skips are now governance-fatal in CLI automation, not just informational.

Why:
- Enforce strict replay integrity for patch gating and prevent silent acceptance of unresolved anchored replay policy/hash mismatches.

Determinism/Replay note:
- Tooling/governance behavior only; no DI runtime compute/output changes.
- Current patch acceptance requires `matched=5`, `failed=0`, `skipped=0`.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_replay_regression.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x09
What changed:
- Updated `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md` to align operator notes with the currently shipped roadmap state through `w114` and the `x01-x08` tooling patches.
- Documented shipped structural hardening splits (header/sequence/viewer helpers), severity tiers in `policy_body` with fallback, and forward severity vocabulary (`high|medium|low`) with backward compatibility.
- Added a concise remaining-work status list without changing roadmap intent.

Why:
- Keep operator-facing implementation notes synchronized with actual shipped deterministic DI behavior and policy-as-data surfaces.

Determinism/Replay note:
- Docs-only patch; no DI compute/output/hash changes.
- Replay regression remains the proof target.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x08
What changed:
- Added optional stdlib-only tool `psi/tools/code_size_report.py`.
- The tool prints a deterministic JSON report (stable target ordering) for key module sizes/LOC to help track growth in risk hot-spots.
- No enforcement behavior is introduced; it is informational only.

Why:
- Provide a simple deterministic guardrail for code-size drift without changing the required gate suite.

Determinism/Replay note:
- Tooling-only change; no DI compute/output/hash changes.
- Replay regression remains the proof target.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/code_size_report.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x07
What changed:
- Tightened forward policy severity vocabulary by replacing `moderate` with `medium` in risk severity tiers across shipped DI policy JSONs:
  - `advance_to_in_vivo_v0_1..v0_4`
  - `ready_for_scaleup_screen_v0_1`
- Preserved backward compatibility in `psi/services/di/risk_flags.py` by normalizing legacy `moderate` -> `medium` during policy severity loading.
- Updated severity sort ranking to treat `medium` and legacy `moderate` equivalently.

Why:
- Enforce a single forward severity vocabulary (`high|medium|low`) while keeping older snapshots/artifacts readable and deterministically classified.

Determinism/Replay note:
- Intentional policy-data semantics change for future policy semantics/package hashes where these policy files are used.
- Runtime compatibility preserves deterministic handling of historical `moderate` values if encountered.
- Replay regression `failed=0` remains the acceptance criterion.
- Replay skips observed and allowed: `policy_exact_match_not_found` on snapshots referencing pre-change policy package hashes.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/risk_flags.py`
- `psi/tools/di_contract_smoke.py`
- `psi/core/di/policies/advance_to_in_vivo_v0_1.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_2.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_3.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_4.json`
- `psi/core/di/policies/ready_for_scaleup_screen_v0_1.json`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x06
What changed:
- Added optional stdlib-only regression harness `psi/tools/molecule_viewer_regression.py`.
- The harness builds minimal dict/namespace fixtures and validates stable viewer helper output shape and ordering expectations.
- Prints a stable success message (`OK molecule_viewer_regression`) and exits `0` on success.

Why:
- Add a lightweight deterministic regression check for the newly extracted viewer helper cluster without introducing test/runtime dependencies.

Determinism/Replay note:
- Tooling-only change; no DI compute/output/hash changes.
- Replay regression remains the proof target.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/molecule_viewer_regression.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x05
What changed:
- Added `psi/services/molecule_viewer.py` and moved the molecule viewer assembly helper cluster out of `psi/services/molecules.py`.
- Moved (without signature changes):
  - `_confidence_from_mismatches`
  - `domain_instances_by_component`
  - `build_feature_tracks`
  - `build_numbering_maps`
  - `build_viewer_v2_components`
- `molecules.py` now imports/re-exports the viewer helpers and uses them in molecule detail assembly.

Why:
- Continue reducing `molecules.py` size/risk by isolating a coherent viewer-assembly cluster without changing behavior.

Determinism/Replay note:
- Structural split only; no intended ordering or output changes.
- Replay regression is the proof target for unchanged DI/hash-bearing outputs.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/services/molecule_viewer.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x04
What changed:
- Extracted the experimental/batch UI context helper cluster from `psi/services/molecules.py` into new module `psi/services/molecule_experimental.py`.
- Moved (without signature changes):
  - `get_molecule_experimental_context`
  - batch/QC/headline helper functions
  - `get_molecule_batch_ui_context`
- `molecules.py` now imports/re-exports these helpers as a thin coordinator.

Why:
- Continue reducing `molecules.py` size/risk by isolating a coherent UI-only helper cluster.

Determinism/Replay note:
- Structural split only; no intended behavior or ordering changes.
- Replay regression is the proof target for no DI output drift.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/services/molecule_experimental.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x03
What changed:
- Added optional stdlib-only helper `psi/tools/pytest_smoke.py`.
- Behavior:
  - runs `pytest -q` via `python -m pytest` when pytest is installed
  - prints stable `SKIP` message and exits `0` when pytest is unavailable

Why:
- Provide a convenient test runner entry point without changing the required gate suite or adding runtime dependencies.

Determinism/Replay note:
- Tooling-only change; no DI compute/output/hash changes.
- Replay regression remains the required proof target.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/pytest_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x02
What changed:
- Added deterministic fixture lock for `decision_output_hash_v2`:
  - `tests/fixtures/decision_output_minimal_v1.json`
  - `tests/test_decision_output_hash_v2_lock.py`
- The test computes the hash via the existing integrity utility and asserts a pinned digest.

Why:
- Pin a representative semantic decision hash to catch accidental drift in canonical hashing behavior.

Determinism/Replay note:
- Dev/test-only additions; no runtime DI behavior changes.
- Replay regression remains the required proof target.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/fixtures/decision_output_minimal_v1.json`
- `tests/test_decision_output_hash_v2_lock.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x01
What changed:
- Added dev-only test scaffold `requirements-dev.txt` with `pytest` (runtime requirements unchanged).
- Added `tests/` package and pure-function header confidence tests covering:
  - `moderate` -> `medium` normalization
  - `2 medium` concerns => amber scalar
  - missing assay signals remain neutral (`Not Assessed`)

Why:
- Close the “no pytest suite” gap with a minimal, DB-free test foothold while preserving runtime dependency purity.

Determinism/Replay note:
- Dev/test-only additions; no runtime DI behavior changes.
- Replay regression remains the required proof target.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `requirements-dev.txt`
- `tests/__init__.py`
- `tests/test_molecule_header_confidence.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w114
What changed:
- Added `psi/services/molecule_sequences.py` and moved the minimal safe sequence/composition helper cluster out of `molecules.py`:
  - `_next_chain_id`
  - `_id_allocation_retry_exhausted`
  - `get_or_create_chain`
  - `_canonical_composition`
  - `composition_sha256`
- Updated `psi/services/molecules.py` to import/re-export the moved helpers and keep orchestration in place.
- Added contract smoke lock for composition-hash stability (canonical ordering + fixed digest regression).

Why:
- Complete the second structural split with minimal risk while keeping composition hashing behavior stable.

Determinism/Replay note:
- Structural split only; no intended DI output/hash changes.
- Composition hash behavior is explicitly locked by contract smoke.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/services/molecule_sequences.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w113
What changed:
- Replaced DI runner stderr print for invalid `PSI_DI_BASELINE_CUTOFF_ISO` with structured logging (`logger.warning(...)`) in `psi/services/di/runner.py`.
- Added module logger initialization and removed the now-unused `sys` import.

Why:
- Route runtime warnings through logging without changing DI snapshot content or replay behavior.

Determinism/Replay note:
- Diagnostics-only change; no DI compute/output/hash changes.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/runner.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w112
What changed:
- Hardened molecule auto-primary allocation retry failure reporting in `psi/services/molecules.py`:
  - existing bounded `IntegrityError` retry loop is preserved
  - exhaustion error now includes the last attempted primary ID candidate

Why:
- Improve clarity for concurrent-write primary ID allocation failures without changing schema or retry semantics.

Determinism/Replay note:
- Molecule CRUD-only error-path message improvement; no DI compute/output/hash changes.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w111
What changed:
- Extracted shared DI runner helper `psi/services/di/runner.py::_attach_integrity_hashes(...)`.
- Replaced duplicated integrity-hash attachment logic in the two deterministic error-output return paths with the shared helper.

Why:
- Reduce duplication in DI runner error paths while preserving exact integrity metadata fields and ordering.

Determinism/Replay note:
- Refactor-only patch; DI outputs are intended to remain unchanged.
- Replay regression is the proof target for no hash-bearing output drift.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/runner.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w110
What changed:
- Consolidated SoE v0.2/v0.3 batch+molecule builders into private `psi/services/di/soe.py::_build_soe_core(config=...)`.
- Updated public entry points to delegate:
  - `build_soe_v0_2`
  - `build_soe_v0_2_molecule`
  - `build_soe_v0_3`
  - `build_soe_v0_3_molecule`

Why:
- Complete the planned D1 SoE consolidation while reducing duplication and preserving byte-identical outputs.

Determinism/Replay note:
- Refactor-only patch; no intended DI output changes.
- Replay gate passed; any `policy_exact_match_not_found` skips remain carryover from the intentional `w108` policy package update.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/soe.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w109
What changed:
- Updated `psi/core/di/catalogs/progress_policy_v0_1.json` additively to include Roadmap v2 early milestones:
  - `expression_present`: `["expr_yield_mgL"]`
  - `purification_present`: `["purity_percent"]`
- Extended progress policy contract smoke to assert the new milestone mappings.

Why:
- Align the scientist-first progress ladder policy catalog with the approved Roadmap v2 milestone set.

Determinism/Replay note:
- Policy-as-data catalog update for UI/view-model progress display; no DI snapshot hash logic changed.
- Replay gate passed with `skipped=2`, both `reason=policy_exact_match_not_found` (carryover from the intentional w108 policy package change).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/progress_policy_v0_1.json`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w108
What changed:
- Copied `risk_flag_severity_tiers` into `policy_body` (additive) for all `advance_to_in_vivo_*` policies and `ready_for_scaleup_screen_v0_1`.
- Updated `psi/services/di/risk_flags.py` to resolve severity tiers in deterministic order:
  1. `policy_body.risk_flag_severity_tiers`
  2. `template_structure.risk_flag_severity_tiers` (backward-compatible fallback)
- Extended contract smoke to assert the new policy-body severity tier copy is present/matches and to lock `policy_body` precedence over `template_structure`.

Why:
- Move governance semantics (risk severity tiers) into the authoritative `policy_body` surface while preserving backward compatibility for older packages.

Determinism/Replay note:
- This is an intentional governance semantics surface change for future snapshots and will change future policy semantics/package hashes for the modified policy files.
- Existing snapshot replay remains valid; if replay skips occur they are expected to be `reason=policy_exact_match_not_found` due package hash mismatch between stored snapshots and updated on-disk policy packages.
- Replay gate result for this patch: `skipped=5`, all with `reason=policy_exact_match_not_found` (allowed).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/risk_flags.py`
- `psi/tools/di_contract_smoke.py`
- `psi/core/di/policies/advance_to_in_vivo_v0_1.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_2.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_3.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_4.json`
- `psi/core/di/policies/ready_for_scaleup_screen_v0_1.json`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w107
What changed:
- Added deterministic header regression harness `psi/tools/molecule_header_regression.py` (stdlib-only script, no pytest dependency).
- Added dict-based fixtures covering:
  - `moderate` -> `medium` severity normalization
  - `2` medium concerns -> amber scalar
  - missing assay signals remain neutral (`Not Assessed`)

Why:
- Provide a lightweight executable regression check for the molecule scientist-header invariants after the w106 structural split.

Determinism/Replay note:
- Tooling only; no DI compute/output/hash changes.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/molecule_header_regression.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w106
What changed:
- Extracted molecule scientist-header view-model builders into new module `psi/services/molecule_header.py` (progress ladder, drift/risk summary, confidence builders, header assembly).
- Updated `psi/services/molecules.py` to act as a thin coordinator and re-export/import the moved helper functions to preserve existing signatures and smoke imports.

Why:
- Reduce change risk in `molecules.py` by isolating the deterministic molecule-header logic without altering behavior.

Determinism/Replay note:
- Structural split only; header outputs are intended to remain identical (with the `w105` moderate->medium fix already in place).
- Replay regression is the proof target for no DI output/hash drift.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/services/molecule_header.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w105
What changed:
- Fixed molecule header risk severity counting to normalize `moderate` -> `medium` before bucket aggregation in `_build_molecule_header_model`.

Why:
- Prevent undercounting medium-severity risk flags in the scientist header confidence summary and avoid scalar rule misfires.

Determinism/Replay note:
- UI/view-model-only severity counting fix; no DI snapshot output/hash logic changed.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w104
What changed:
- Hardened `psi.tools.export_outcome_dataset` hash/fingerprint field extraction with deterministic stored-field fallback precedence (inputs/output policy/provenance metadata only; no recomputation).
- Export rows now reliably fill `policy_semantics_hash`, `policy_package_hash`, and `evidence_fingerprint` from stored snapshot fields when one source path is absent.
- Extended contract smoke to lock export hash-field enrichment precedence and updated operator notes to document the deterministic fallback behavior.

Why:
- Complete v2.1 outcome dataset export enrichment while preserving read-only deterministic behavior.

Determinism/Replay note:
- Export tool remains read-only and ordered by `snapshot_id ASC`; no DI compute or hash-bearing output changes.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/export_outcome_dataset.py`
- `psi/tools/di_contract_smoke.py`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w103
What changed:
- Confirmed `psi.tools.label_outcome add` already supports explicit `--outcome-event-date` (shipped earlier) and documented the operator-facing usage/examples.
- Added deterministic contract smoke coverage for `label_outcome` outcome-event-date parsing:
  - accepts valid ISO8601 and normalizes UTC `Z`
  - rejects invalid input with a stable CLI error message

Why:
- Close the operator/docs + parser-regression gap for outcome labeling date input in the v2.1 workflow.

Determinism/Replay note:
- No DI functional changes; CLI parser/docs + smoke only.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w102
What changed:
- Audited DI runner error-output paths and confirmed shared error-output construction/parity completion is already in use.
- Extended contract smoke with multi-error-factory parity assertions (`policy_schema_mismatch` and `unsupported_template`) to lock default types/nulls and enum validity.

Why:
- Finish error-output parity hardening with stronger regression coverage while preserving replay behavior.

Determinism/Replay note:
- No DI functional changes in this patch; smoke coverage only.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w101
What changed:
- Performed a docs-first sub-assessment library audit (`docs/CODE_REVIEW_w101.md`) and confirmed reproducibility/comparability paths already use shared deterministic helpers in `psi/services/di/sub_assessments.py`.
- Added a contract smoke lock for reproducibility sub-assessment helper key-shape/order stability (`reproducibility_signal_from_soe`).

Why:
- Tighten sub-assessment library guarantees without introducing replay risk from unnecessary refactors.

Determinism/Replay note:
- No DI functional code changes in this patch.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/CODE_REVIEW_w101.md`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w100
What changed:
- Added `psi/core/di/catalogs/confidence_policy_v0_2.json` with explicit component derivation mappings (QC/Reproducibility/Comparability/Interpretability) and unchanged count-only scalar rules.
- Extended confidence policy validation/loading (`psi/core/di/catalog.py`) to validate optional `component_rules` and added `load_confidence_policy_v0_2()`.
- Updated molecule-header confidence derivation to read policy-visible component labels/order/signal mappings deterministically (behavior-preserving defaults retained).
- Extended contract smoke to validate `confidence_policy_v0_2` latest-loader selection, required component-rule keys, and absence of weighted/average catalog fields.

Why:
- Expand policy-as-data coverage for confidence component derivation while preserving non-weighted deterministic behavior.

Determinism/Replay note:
- Component derivation remains deterministic and count/categorical-only; missing evidence stays neutral via existing rules.
- Replay regression passed with no skips (UI/view-model policy mapping only; DI snapshot hashes unchanged).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalog.py`
- `psi/core/di/catalogs/confidence_policy_v0_2.json`
- `psi/services/molecules.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w99
What changed:
- Added shared deterministic heavy-compute banner text helper in `psi/services/di/util.py` and reused it in molecule header + `/di/run`.
- Moved `/di/run` heavy-compute banner outside the Scientist/Governance toggle panels so it stays visible in both modes.
- Extended contract smoke to lock shared heavy-compute banner text and deterministic DI run template panel structure.

Why:
- Keep the heavy-compute OFF/ON indicator consistently visible across scientist/governance views without affecting DI hashes.

Determinism/Replay note:
- UI/helper-only change using the existing `is_heavy_compute_enabled()` global toggle; no DI compute/output/hash changes.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/util.py`
- `psi/services/di/web.py`
- `psi/services/molecules.py`
- `psi/web/templates/di/run.html`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w98
What changed:
- Added deterministic stage-level progress advisory selection in the molecule header view-model using the first sorted blocked DI milestone.
- Rendered a stage-level `Blocked by prerequisites` notice next to the molecule progress stage title.
- Extended contract smoke to lock deterministic stage-advisory milestone selection and plain-English blocker text prefix.

Why:
- Surface prerequisite blocking directly at the progress stage level without changing DI logic or snapshot outputs.

Determinism/Replay note:
- UI/view-model interpretation only; prerequisite advisories remain explicitly sorted and DI hashes are unchanged.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w97
What changed:
- Added explicit deterministic progress hover-text builder for the molecule header (`satisfied=` / `not_yet=` milestone keys).
- Switched the progress bar tooltip/title to prefer the new policy-key explainability text.
- Extended contract smoke to lock progress hover-text ordering and policy-key presence.

Why:
- Make progress-ladder explainability explicitly policy-key-driven and stable while keeping progress logic unchanged.

Determinism/Replay note:
- UI/view-model explainability only; no DI compute/output/hash changes.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w96
What changed:
- Added deterministic drift plain-English translation helper in `psi/services/decisions.py` for DI snapshot UI rendering.
- Rendered drift translation in the DI snapshot “Run semantics” section beneath `drift_type`.
- Extended contract smoke with a deterministic drift translation fixture assertion.

Why:
- Improve scientist-first readability of drift semantics using deterministic translation (no ML / no hidden logic).

Determinism/Replay note:
- UI-only helper/rendering change; no DI compute/output/hash changes.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/decisions.py`
- `psi/web/templates/decisions/_di_snapshot.html`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w95
What changed:
- Added Scientist/Governance view toggle to `/di/run` with localStorage persistence (`psi.di.run.view_mode`), matching the molecule-page scientist-first toggle pattern.
- Kept toggle behavior UI-only (panel visibility + button state) with explicit governance note that inputs/outputs/hashes are unaffected.
- Extended contract smoke to render `/di/run` and assert localStorage toggle presence while preserving DI form fields.

Why:
- Continue the scientist-first default view rollout while keeping governance details accessible and non-obstructive.

Determinism/Replay note:
- UI-only JS/template change; no DI compute/output/hash changes.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/di/run.html`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w94
What changed:
- Updated `psi/tools/export_outcome_dataset.py` to export top-level `outcome_event_date` and deterministic `days_to_outcome` (days from snapshot `created_at`, rounded to 6 decimals).
- Refactored the exporter into deterministic row-building / JSONL-writing helpers for easier smoke verification (read-only behavior preserved).
- Added contract smoke proof that outcome dataset row generation and JSONL output are deterministic for a fixed DB.
- Updated operator notes to document the v2.1 outcome dataset additions.

Why:
- Complete the v2.1 outcome dataset block by surfacing outcome timing metadata and derived timing deltas without affecting DI hashes.

Determinism/Replay note:
- Export tool remains read-only and deterministic (explicit ordering + stable JSONL).
- DI outputs and DI snapshot hashes remain unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/export_outcome_dataset.py`
- `psi/tools/di_contract_smoke.py`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w93
What changed:
- Added additive outcome metadata field `OutcomeLabel.outcome_event_date` (nullable) to the ORM model.
- Updated `ensure_schema()` additive column evolution to add `outcome_labels.outcome_event_date` on existing DBs without destructive migration.
- Updated `psi/services/decisions.add_outcome_label()` to accept/store `outcome_event_date` metadata.
- Updated `psi/tools/label_outcome.py` to accept optional `--outcome-event-date` (ISO8601) and display the field in `list` output.
- Included `outcome_event_date` in snapshot-detail outcome label serialization (metadata only).

Why:
- Provide the additive v2.1 outcome-event timestamp metadata needed for downstream deterministic outcome-dataset exports (`days_to_outcome` in w94).

Determinism/Replay note:
- Outcome label metadata only; DI outputs and DI snapshot hashes remain unchanged.
- Additive-only schema evolution; no destructive migration.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/core/db.py`
- `psi/services/decisions.py`
- `psi/tools/label_outcome.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w92
What changed:
- Extended DI contract smoke error-output parity coverage to explicitly lock v0.3 vs v0.4 parity-extension gating behavior.
- Added assertions that common happy-path top-level parity fields remain present on parity-completed error outputs and that v0.4-only fields are emitted only for v0.4 policies.
- Included a fallback-path exercise (missing `inputs_obj.evaluator_version`) in the parity gating smoke to preserve the w75 error-parity hardening guarantee.

Why:
- Finish the remaining error-output parity hardening work as a low-risk smoke/coverage patch since the shared error-output helper/consolidation is already in place.

Determinism/Replay note:
- Test-only patch; no DI compute/schema/output/hash changes.
- Replay and hash-bearing DI outputs unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w91
What changed:
- No functional SoE consolidation changes were required.
- Added `docs/CODE_REVIEW_w91.md` documenting the SoE duplication audit and why current shared-helper coverage is already sufficient.

Why:
- Patch goal was conditional; current `psi/services/di/soe.py` already centralizes core SoE logic behind shared internal builders, so a refactor would add risk without benefit.

Determinism/Replay note:
- Docs-only patch; no DI compute/schema/output changes.
- Replay and hash-bearing DI outputs unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/CODE_REVIEW_w91.md`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w90
What changed:
- Added versioned UI-only confidence policy catalog `psi/core/di/catalogs/confidence_policy_v0_1.json`.
- Added deterministic confidence policy loaders/validation in `psi/core/di/catalog.py` (including `load_confidence_policy_latest()`).
- Wired molecule-header confidence scalar derivation to read scalar thresholds deterministically from the confidence policy catalog with safe fallback defaults.
- Extended contract smoke to validate confidence policy catalog presence, required keys, and latest-loader determinism.
- Updated operator notes to document the new confidence policy catalog.

Why:
- Make confidence scalar/component display rules policy-visible and versioned without changing DI outputs or hashes.

Determinism/Replay note:
- UI-only catalog consumption; no DI snapshot/hash-bearing output changes.
- Catalog latest selection is explicit and deterministic.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalog.py`
- `psi/core/di/catalogs/confidence_policy_v0_1.json`
- `psi/services/molecules.py`
- `psi/tools/di_contract_smoke.py`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w89
What changed:
- Extracted count-only confidence scalar derivation into `_derive_confidence_scalar_from_components` (UI-only helper).
- Marked the molecule-header confidence scalar as optional (`scalar_optional`) and surfaced `scalar_rule_id` / `scalar_counts` for transparent UI-side rule inspection.
- Kept scalar rule deterministic and non-weighted: high concern => amber, >=2 medium concerns => amber, otherwise green/unknown.
- Added contract smoke locks for scalar rule outcomes and rejection of weighting/averaging language in the confidence surface.

Why:
- Make the confidence scalar explicitly reproducible by visible component counts and easier to audit before policy-as-data grounding.

Determinism/Replay note:
- UI/view-model helper + smoke only; no DI snapshot/hash-bearing output changes.
- No weighted scoring or averaging introduced.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w88
What changed:
- Added deterministic interpretability `detail_items` (severity tier counts ordered `high -> medium -> low -> unspecified`) to the molecule-header confidence component.
- Updated molecule header confidence UI to render interpretability severity tiers distinctly as categorical chips (display-only).
- Extended contract smoke to lock deterministic interpretability tier ordering.

Why:
- Make interpretability severity tiers visible and auditable in the confidence bar without introducing any weighting or scoring changes.

Determinism/Replay note:
- UI/view-model only change; no DI snapshot/hash-bearing output changes.
- Interpretability tier ordering is explicit and smoke-locked.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w87
What changed:
- Added a component-only confidence derivation helper (`_derive_confidence_components`) for deterministic UI-side component state checks.
- Extended contract smoke to lock component derivation determinism and neutrality for missing evidence (no penalty for absent QC/repro/comparability signals).

Why:
- Make the confidence component derivation surface explicit and testable before subsequent interpretability/scalar refinements.

Determinism/Replay note:
- UI helper + smoke only; no DI compute/output/hash changes.
- Existing scalar remains unchanged in this patch.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w86
What changed:
- Added an explicit molecule-header confidence scaffold legend clarifying `Good / Concern / Not Assessed (neutral)`.
- Added contract smoke coverage that locks the no-snapshot confidence scaffold to 4 deterministic components, all `not_assessed`.

Why:
- Make the confidence bar scaffold semantics explicit to operators/users before further component derivation refinements.

Determinism/Replay note:
- UI text + smoke only; no DI output/hash changes.
- No weighting introduced; missing evidence remains neutral.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/molecules/detail.html`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w85
What changed:
- Surfaced latest DI risk items (key + severity tier) in the molecule scientist header, in addition to the existing severity counts.
- Added deterministic header risk-item ordering with explicit severity/key sort and neutral handling for unknown severities (`unspecified`).
- Extended contract smoke to lock molecule-header risk item ordering and neutrality semantics.

Why:
- Complete the next roadmap v2 step for scientist-first severity visibility without introducing scoring or affecting DI outputs.

Determinism/Replay note:
- UI/view-model only change; no DI snapshot/hash-bearing output changes.
- Header risk items use explicit deterministic ordering and neutral treatment for unknown severities.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w84
What changed:
- Added policy-as-data risk severity tiers under `template_structure.risk_flag_severity_tiers` across packaged DI policy files.
- Wired DI risk-flag enrichment to read policy/package severity tiers (with deterministic fallback behavior), preserving existing severities for current flags.
- Updated DI snapshot UI risk flag chips to display severity tiers distinctly (display-only, no weighting).
- Extended contract smoke with:
  - policy severity-tier coverage audit across packaged policies
  - deterministic policy-driven risk severity enrichment check
  - deterministic DI snapshot UI severity rendering check
- Updated operator notes to document policy-defined risk severity tiers.

Why:
- Complete the next roadmap v2.0c requirement by moving risk severity display semantics into policy-as-data and proving deterministic coverage/rendering.

Determinism/Replay note:
- Risk severity tier consumption is deterministic; enriched risk flags remain explicitly sorted.
- UI rendering change is display-only and does not affect DI snapshot hashes.
- Replay regression passed; package-level policy metadata changes may cause `policy_exact_match_not_found` skips for older snapshots because `policy_package_hash` changes while policy semantics remain unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/risk_flags.py`
- `psi/services/di/compute.py`
- `psi/web/templates/decisions/_di_snapshot.html`
- `psi/tools/di_contract_smoke.py`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`
- `psi/core/di/policies/advance_to_in_vivo_v0_1.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_2.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_3.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_4.json`
- `psi/core/di/policies/ready_for_scaleup_screen_v0_1.json`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w83
What changed:
- Added `docs/CODE_REVIEW_w83.md` as a docs-first internal checkpoint review covering patches `w75` through `w82`.
- Reviewed determinism, replay safety, policy-as-data alignment, UI-only guarantees, and hash-risk boundaries; documented findings and proof notes.
- No functional code changes were required from the review (no determinism/replay/hash-safety issues found).

Why:
- Establish a clear checkpoint record before additional roadmap work and make the audit rationale/proof easy to review.

Determinism/Replay note:
- Documentation-only patch; no DI compute/schema/output changes.
- Replay and hash-bearing DI outputs remain unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/CODE_REVIEW_w83.md`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`

## 2026-02-26 — v1.2.9w82
What changed:
- Added operator-facing roadmap v2 implementation notes in `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`.
- Documented progress-policy and template-prerequisites catalog roles (including deterministic latest loader behavior).
- Documented experiment catalog v0.2 `resolves_risk_flags` catalog-driven risk mapping, `value_functions_enforcement_reason` enum semantics, and heavy-compute OFF-by-default hash-safety guarantees.

Why:
- Provide a concise operator reference for the roadmap v2 surfaces that are now implemented across catalogs, UI governance fields, and runtime flags.

Determinism/Replay note:
- Documentation-only patch; no DI compute/schema/output changes.
- Replay and hash-bearing DI outputs remain unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`

## 2026-02-26 — v1.2.9w81
What changed:
- Added read-only deterministic outcome dataset exporter `python -m psi.tools.export_outcome_dataset` (JSONL) using existing DB fields only.
- Export rows are ordered by `snapshot_id` ascending and serialized with stable JSON key ordering for reproducibility.
- Each row includes snapshot metadata plus parsed `policy_semantics_hash`, `policy_package_hash`, `evidence_fingerprint`, `decision_state`, and aggregated outcome labels (including DI review labels when present).

Why:
- Provide deterministic groundwork for closed-loop outcome analysis without schema changes or any DB writes.

Determinism/Replay note:
- Tool is read-only (`ensure=False`) and does not mutate DB state.
- Export ordering is explicit and reproducible; no DI compute/output changes.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/export_outcome_dataset.py`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`

## 2026-02-26 — v1.2.9w80
What changed:
- Added explicit stable sorts (with comments) for molecule-header prerequisite status rows, blocked prerequisite advisory rows, and top-level prerequisite advisories.
- Extracted a small `_sorted_prerequisite_blockers_for_advisory()` helper to make the blocker ordering rule explicit and reusable.
- Added contract smoke determinism coverage that asserts prerequisite blocker ordering is stable regardless of input order.

Why:
- Prevent accidental UI/view-model ordering drift in scientist header lists and make deterministic ordering rules obvious in code.

Determinism/Replay note:
- UI/view-model sorting hardening only; no DI compute/schema/output changes.
- Replay and hash-bearing DI outputs remain unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`

## 2026-02-26 — v1.2.9w79
What changed:
- Audited the molecule-header confidence model and confirmed it already uses explicit rule-based counting only (no weighted scoring) with `not_assessed` components treated neutrally.
- Added contract smoke coverage to lock non-weighted confidence behavior, deterministic component ordering, and neutral handling of missing evidence.
- Added a smoke assertion that the visible confidence rule text explicitly states the non-weighted rule.

Why:
- Prevent regressions that could reintroduce implicit weighting or treat missing evidence as negative without an explicit deterministic rule.

Determinism/Replay note:
- Test-only enforcement of existing UI-only confidence behavior; no DI compute/schema/output changes.
- Replay and hash-bearing DI outputs remain unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`

## 2026-02-26 — v1.2.9w78
What changed:
- Added shared helper `is_heavy_compute_enabled()` in `psi/services/di/util.py` to centralize `PSI_HEAVY_COMPUTE=1` handling with a deterministic OFF-by-default behavior.
- Switched the molecule header heavy-compute banner to use the shared helper instead of reading the environment variable inline.
- Added a visible `/di/run` UI indicator (`Heavy Compute: OFF/ON`) sourced from the shared helper and explicitly stating that DI snapshot hashes are unaffected.

Why:
- Make heavy-compute status handling consistent across UI surfaces and enforce a single OFF-by-default interpretation without affecting DI hash-bearing outputs.

Determinism/Replay note:
- UI/runtime helper only; no DI snapshot schema/output changes and no hash/replay surface changes.
- Heavy-compute indicator is display-only and does not participate in DI snapshot hashing.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/util.py`
- `psi/services/molecules.py`
- `psi/services/di/web.py`
- `psi/web/templates/di/run.html`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`

## 2026-02-26 — v1.2.9w77
What changed:
- Hardened the molecule-header prerequisite advisory view-model to explicitly classify blocked prerequisite templates as `missing` vs `failed` and include latest snapshot IDs when available.
- Added explicit sorting for prerequisite template keys before advisory derivation so blocker lists render deterministically.
- Updated the molecule detail template wording to show a plain-English `Blocked by prerequisites` message for structurally impossible progress claims.

Why:
- Prevent the UI from implying an impossible progress state without a deterministic, user-visible explanation of which prerequisite templates are blocking the claim.

Determinism/Replay note:
- UI/view-model only change; no DI compute or snapshot schema/output changes.
- Advisory blocker ordering is explicit and stable (sorted prerequisite template keys).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`

## 2026-02-26 — v1.2.9w76
What changed:
- Added deterministic `load_template_prerequisites_latest()` catalog loader that selects the highest `template_prerequisites_vX_Y.json` version by parsed version tuple (stable tie-break by filename).
- Switched molecule header prerequisite loading to use the latest template-prerequisites catalog (current behavior unchanged because only `v0_1` exists).
- Expanded contract smoke coverage to audit progress-policy DI milestone template coverage against the prerequisites catalog, validate latest-loader determinism, and optionally validate `v0_2` loading if a `template_prerequisites_v0_2.json` file is present.

Why:
- Make template prerequisite policy-as-data expansion future-proof and ensure the molecule header cannot silently reference DI milestone templates missing from the catalog.

Determinism/Replay note:
- Catalog loading and milestone coverage checks use explicit deterministic ordering.
- No DI schema/output changes and no replay/hash-bearing compute changes.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalog.py`
- `psi/services/molecules.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`

## 2026-02-26 — v1.2.9w75
What changed:
- Hardened DI error-output parity completion to deterministically fall back to the error output engine evaluator version when `inputs_obj.evaluator_version` is absent, preserving governance/run-semantics reason generation.
- Tightened DI contract smoke parity coverage to select a representative parity-gated DI snapshot (`error_output_parity_v2_0a`) instead of any DI snapshot.
- Extended the parity smoke assertion to require `value_functions_enforcement_reason` in both representative success and synthesized error outputs when the value-functions extension gate is active.

Why:
- Ensure the w75 parity check exercises the intended new-snapshot gated path and validates governance/run-semantics parity consistently across success vs error outputs.

Determinism/Replay note:
- Error parity completion remains additive and extension-gated for new snapshots only (`error_output_parity_v2_0a`), preserving historical replay surfaces.
- No schema changes, no ranking/scoring changes, and no non-deterministic behavior introduced.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/runner.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`

## 2026-02-26 — v1.2.9w74
What changed:
- Extracted deterministic material readiness and mechanism readiness rationale helpers into shared sub-assessment utilities.
- Updated the advance-to-in-vivo template to call the new helpers without changing rationale text.
- Extended contract smoke coverage with minimal deterministic checks for the new helpers.

Why:
- Refactor for reuse across upcoming templates while preserving existing gate rationale behavior.

Determinism/Replay note:
- Refactor-only patch: no intended behavior or schema changes.
- Replay regression remains the proof target for unchanged hash-bearing outputs.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/sub_assessments.py`
- `psi/services/di/templates/advance_to_in_vivo.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w59
What changed:
- Expanded the existing additive `ensure_schema()` DI snapshot metadata backfill so it sets `decision_snapshots.engine_key='di'` for legacy DI rows where `engine_key` is `NULL` or empty and `schema_version LIKE 'di.%'`.
- Kept DI snapshot detection logic unchanged; the backfill makes `engine_key` authoritative for historical DI rows during schema-ensure paths.
- Documented the backfill in `MIGRATIONS.md` (idempotent, conservative, and not run in read-only replay flows that skip `ensure_schema()`).

Why it changed:
- Eliminate fallback heuristic DI snapshot detection in practice by backfilling missing `engine_key` values on historical DI snapshots.

Determinism/contract impact:
- No DI compute/ranking logic changes.
- Additive, idempotent metadata backfill only; no destructive schema changes.
- Read-only replay remains unchanged because replay flows can skip `ensure_schema()`.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w60
What changed:
- `/di/run` now supports true molecule-scope DI execution end-to-end from the web form (`scope_type=molecule` + `molecule_id`) while preserving batch-scope behavior.
- DI run form includes a scope selector (`batch`/`molecule`) with deterministic server-rendered option lists and minimal inline JS to toggle the active selector input.
- DI run context queries use explicit deterministic ordering tie-breaks for selector lists: `created_at DESC, id DESC` for both batches and molecules.
- POST handler now accepts optional `template_id`, `route`, and `study_intent` fields (if present) and stores them in `DIInput.context` without changing DI engine decision logic.

Why it changed:
- Close the remaining audit gap by enabling molecule-scope DI runs from `/di/run` rather than only batch-scope POST execution.

Determinism/contract impact:
- No DI engine compute/ranking logic changes.
- UI selection ordering is deterministic and stable.
- Replay surfaces are unchanged.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w61
What changed:
- Added additive DI output field `value_functions_enforced` for new snapshots via an explicit output-extension flag in DI inputs, keeping historical replay surfaces unchanged.
- DI snapshot UI now shows a concise **Run semantics** section (`qc_mode`, `as_of_ts`, stable-rendered `context`, `drift_type`, `state_transition`, `value_functions_enforced`).
- Extended deterministic NBE suggestions so catalog experiment suggestions can also be triggered by specific risk flags (in addition to blockers), with stable ordering and risk-flag suggestion display in the snapshot UI.

Why it changed:
- Make value-function enforcement and run semantics explicit/auditable, and broaden deterministic experiment suggestion triggers without introducing scoring.

Determinism/contract impact:
- No heuristic ranking or weighted scoring added.
- New `value_functions_enforced` field is replay-safe by explicit new-snapshot emission gating.
- NBE ordering remains deterministic (`time_tier`, `cost_tier`, `experiment_key`).

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w62
What changed:
- Added standalone deterministic fixture regression tool: `python -m psi.tools.di_fixture_regression`.
- Tool runs small DB-write-free fixture cases that validate stable ordering for gates/blockers/risk-flags/NBE suggestions and checks the `w61` `value_functions_enforced` field on DI error-path outputs.

Why it changed:
- Provide a lightweight deterministic regression harness for DI governance surfaces without introducing a heavy test framework.

Determinism/contract impact:
- Read-only/pure fixture checks only; no DI runtime behavior changes.
- No schema changes or replay surface changes.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
- `python -m psi.tools.di_fixture_regression`
## 2026-02-25 — v1.2.9w63
What changed:
- Removed truly unused local helpers from `psi/services/di/templates/advance_to_in_vivo.py` (no behavior change).
- Added clarifying comments in `psi/services/di/runner.py` documenting the intentional two-pass supersession sequence and why it preserves the single-active-snapshot invariant without changing semantics.

Why it changed:
- Governance-safe hygiene cleanup to reduce maintenance drift and make supersession behavior easier to audit.

Determinism/contract impact:
- No DI output semantics changes.
- No schema changes and no replay surface changes.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
- `python -m psi.tools.di_fixture_regression`
## 2026-02-25 — v2.0a
What changed:
- v2.0a D1 (infrastructure): refactored `psi/services/di/soe.py` to remove duplication across `build_soe_v0_2` / `build_soe_v0_3` and their molecule-scope variants using shared internal deterministic helpers (no output schema change).
- v2.0a D2 (infrastructure): consolidated DI error-output parity completion in a shared runner helper and added a contract smoke parity guard asserting representative success/error top-level key parity.
- Added policy-visible progress ladder catalog file `psi/core/di/catalogs/progress_policy_v0_1.json` plus deterministic loader/validator in `psi/core/di/catalog.py`.
- Added contract smoke validation for the progress policy catalog loader.

Why it changed:
- Establish v2.0a infrastructure groundwork from `docs/DI_MISSION_AND_ROADMAP_v2.md` while preserving deterministic replay and policy-as-data governance.

Determinism/contract impact:
- No UI/web changes in v2.0a.
- No DB schema changes.
- Replay regression remains stable; new error-output parity fields are extension-gated for new snapshots only.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w65
Naming note:
- Prior tag `v2.0a` corresponds to the w64-equivalent infrastructure-first work (SoE refactor + error parity + progress policy catalog). Human-facing patch tracking resumes at `w65+`.

What changed:
- Added a scientist-first molecule header scaffold (view-only) on molecule detail pages with a Scientist/Governance toggle (default Scientist; localStorage persisted in browser).
- Added deterministic progress bar rendering derived from `progress_policy_v0_1.json`, molecule measurement-key presence, and latest DI snapshot states (read-only view-model only).
- Added deterministic plain-English drift summary text for the latest DI snapshot drift context and a heavy-compute banner from `PSI_HEAVY_COMPUTE` (default OFF).

Why it changed:
- Begin Roadmap v2.0b scientist UX foundation without changing DI snapshot contents or hashes.

Determinism/contract impact:
- No DI snapshot compute changes and no hash-bearing DI output changes.
- View-model logic is read-only and deterministic (sorted milestones, stable snapshot ordering).

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w66
Naming note:
- Prior tag `v2.0a` corresponds to the w64-equivalent infrastructure-first work (SoE refactor + error parity + progress policy catalog). Human-facing patch tracking resumes at `w65+`.

What changed:
- Added a policy-visible template prerequisites catalog (`template_prerequisites_v0_1.json`) with deterministic loader/validator.
- Added molecule-header prerequisite advisory logic so UI progress interpretation does not claim later DI milestones when prerequisite template outcomes are missing/failed.
- Added risk severity tier scaffolding in molecule governance view (`high|medium|low|unspecified`) derived read-only from existing DI risk flags.

Why it changed:
- Implement Roadmap v2.0c structural coherence in the scientist/governance UI layer without changing DI snapshot hashes or replay behavior.

Determinism/contract impact:
- UI-only/view-model derivations are deterministic and advisory; no DI compute contract or snapshot schema changes.
- Historical policy artifacts remain unchanged; prerequisite semantics are stored in a new versioned catalog file.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w67
Naming note:
- Prior tag `v2.0a` corresponds to the w64-equivalent infrastructure-first work (SoE refactor + error parity + progress policy catalog). Human-facing patch tracking resumes at `w65+`.

What changed:
- Added a deterministic molecule-page confidence model (UI-only, render-time) with components for QC Quality, Reproducibility, Comparability, and Interpretability.
- Added a confidence bar UI in the scientist header plus visible rule text in governance view.
- Confidence summary state is derived by explicit counting rules only (no weighted scoring; missing components remain `Not Assessed`).

Why it changed:
- Implement Roadmap v2.0d confidence-bar rendering without changing DI snapshot hashes or DI engine behavior.

Determinism/contract impact:
- All confidence logic is read-only view-model derivation from existing snapshot outputs/risk flags and deterministic rules.
- No DI compute changes, no schema changes, and no replay-surface changes.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w69
What changed:
- Added `experiment_catalog_v0_2.json` (additive catalog version) with optional `resolves_risk_flags` support on experiment entries.
- Added deterministic experiment catalog validation/loader helpers, latest-version selection, and a pure risk-flag index builder (`risk_flag -> experiment_keys`).
- Added contract smoke checks for v0.2 catalog loading, latest-loader selection, and deterministic risk-flag mapping index generation.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalog.py`
- `psi/core/di/catalogs/experiment_catalog_v0_2.json`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- No DI compute/NBE behavior changes in this patch; changes are catalog/loader infrastructure only.
- Replay surfaces and snapshot hashes remain unchanged; replay regression gate verifies this.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w70
What changed:
- Updated NBE experiment suggestion planning to derive risk-flag-triggered suggestions exclusively from experiment catalog data (`resolves_risk_flags`) via the catalog mapping builder.
- Added experiment catalog v0.2 support in NBE catalog resolution, with deterministic latest-catalog fallback for forward-compatible experiment catalog refs.
- Added contract smoke assertions that NBE no longer uses a hardcoded risk->experiment map and that risk-flag suggestions remain deterministic.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/nbe.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Ordering remains deterministic (sorted risk flags, tier/cost/key sorting for experiments).
- Historical replay remains stable because v0.1 experiment catalogs simply provide empty `resolves_risk_flags`, so no extra risk-driven suggestions are invented for old snapshots.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w71
What changed:
- Added deterministic `value_functions_enforcement_reason` enum support (`active | policy_flag_off | evaluator_version_mismatch | not_applicable`) via a shared helper.
- Wired `value_functions_enforcement_reason` into DI success outputs and error outputs under the existing output-extension gating used for `value_functions_enforced`.
- Extended contract smoke to validate helper enum behavior and assert field presence in representative success/error outputs for new snapshots.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/util.py`
- `psi/services/di/compute.py`
- `psi/services/di/runner.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Field emission is extension-gated for new snapshots only (same extension gate as `value_functions_enforced`), preserving historical replay surfaces.
- No policy/schema changes and no weighted or heuristic logic introduced.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w72
What changed:
- Surfaced `value_functions_enforcement_reason` in the DI snapshot “Run semantics” governance section with a short deterministic explanation for each allowed enum value.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/decisions/_di_snapshot.html`

Determinism/Replay note:
- UI-only template rendering change; no DI compute/output changes and no snapshot hash impact.
- Replay stability remains enforced by the replay regression gate.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w73
What changed:
- Extracted reusable deterministic sub-assessment helpers for comparability QC coherence summary and reproducibility-from-SoE evidence summary.
- Updated DI eval shortlisting/tie-break derivation to call the extracted helpers without changing output shape.
- Extended contract smoke shared-helper coverage to include deterministic checks for the new helpers.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/sub_assessments.py`
- `psi/services/di/eval.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Refactor-only patch: no behavior or schema changes intended.
- Replay regression gate is the proof target for unchanged hash-bearing DI outputs.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-26 — v1.3.0a1
What changed:
- V3 additive governance foundation: added `portfolios`, `program_membership`, and `portfolio_membership` tables with explicit `sort_index` ordering.
- Added minimal deterministic portfolio CRUD services/routes/templates and portfolio detail membership management surface.
- Extended existing Program detail page with a V3 governance membership table (molecule memberships) and minimal add/sort/remove controls.
- Ordering is explicit and stable everywhere memberships are listed: `(sort_index, id)`.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/core/db.py`
- `psi/services/programs.py`
- `psi/services/portfolios.py`
- `psi/web/app.py`
- `psi/web/routers/programs.py`
- `psi/web/routers/portfolios.py`
- `psi/web/templates/base.html`
- `psi/web/templates/programs/detail.html`
- `psi/web/templates/portfolios/list.html`
- `psi/web/templates/portfolios/form.html`
- `psi/web/templates/portfolios/detail.html`

Determinism/Replay note:
- Additive schema + UI/service surfaces only; no DI engine or snapshot semantics changes.
- Membership ordering is explicit (`sort_index`, then row id), and DI replay outputs remain the proof target via strict gates.
## 2026-02-26 — v1.3.0a2
What changed:
- Added additive provenance tables: `actors` and `attribution_events` (single-machine actor model, deterministic local-first attribution).
- Added `psi/services/attribution.py` helper to record attribution events without DI coupling.
- Wired provenance recording for Program/Portfolio create/update and program/portfolio membership add/update/remove operations.
- Attribution remains governance-only metadata and is not used by DI computations.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/core/db.py`
- `psi/services/attribution.py`
- `psi/services/programs.py`
- `psi/services/portfolios.py`

Determinism/Replay note:
- Additive governance metadata only; no DI output/snapshot semantics changes.
- Replay remains strict and is the acceptance proof.
## 2026-02-26 — v1.3.0a3
What changed:
- Added additive `program_rollups` governance table for deterministic persisted program rollup artifacts.
- Implemented `psi/services/program_rollups.py` with explicit `as_of` rollup builder/persistence helper using deterministic molecule enumeration and latest DI snapshot selection as-of.
- Rollup payload captures included snapshot IDs and observed policy versions/package hashes without introducing new scoring.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/core/db.py`
- `psi/services/program_rollups.py`

Determinism/Replay note:
- Rollups are governance artifacts derived from existing snapshots with explicit `as_of`; DI engine and snapshot semantics remain unchanged.
## 2026-02-26 — v1.3.0a4
What changed:
- Added additive `comparability_assessments` governance table (categorical-only statuses with cited keys/snapshots and policy pins).
- Added `psi/services/comparability.py` scaffold service with deterministic sorting/deduping of cited measurement keys and snapshot IDs.
- Added `psi/core/di/catalogs/comparability_policy_v0_1.json` policy-as-data scaffold with categorical status registry and placeholder rule registry.
- Extended DI contract smoke to validate comparability policy scaffold schema and deterministic cited-item ordering behavior.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/core/db.py`
- `psi/services/comparability.py`
- `psi/core/di/catalogs/comparability_policy_v0_1.json`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Categorical-only comparability scaffolding; no DI scoring or snapshot semantics changes.
## 2026-02-26 — v1.3.0a5
What changed:
- Added policy-defined deterministic ranking surface scaffold (`ranking_policy_v0_1.json`) with explicit `enabled=false` default and deterministic tie-break keys.
- Added `psi/services/v3_ranking.py` to build an explainable ranking surface only when policy enables it; disabled path returns reason trail metadata without ranking.
- Extended DI contract smoke to validate the ranking policy scaffold and deterministic disabled-by-default surface behavior.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/ranking_policy_v0_1.json`
- `psi/services/v3_ranking.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Ranking surface is V3 governance scaffolding, disabled by default, and does not alter existing DI shortlisting/ranking outputs.
## 2026-02-26 — v1.3.0a6
What changed:
- Added additive `report_runs` storage table for deterministic, policy-pinned report artifacts.
- Implemented `psi/services/report_engine.py` skeleton with exactly four report types, explicit `as_of`, policy pins, snapshot coverage, fixed-section payload schemas, and deterministic validators.
- Extended DI contract smoke to lock fixed-schema deterministic payload generation for all four report types.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/core/db.py`
- `psi/services/report_engine.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Report engine is a V3 governance storage/validation scaffold only; no DI computation or snapshot semantics changes.
## 2026-02-26 — v1.3.0a7
What changed:
- Implemented deterministic Molecule Report v0 generator in `psi/services/report_engine.py` using existing molecule DI snapshot outputs only (no interpretive prose, no new scoring).
- Populates fixed Molecule Report sections (identity/context, stage, confidence, mechanism, risk, gaps, drift/history, reproducibility appendix) from latest DI snapshot as-of or deterministic placeholders.
- Extended DI contract smoke with an in-memory fixture proving fixed structure and snapshot citation behavior for the molecule report generator.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Report generation reads existing snapshots only and stores deterministic report artifacts; DI engine/snapshot semantics unchanged.
## 2026-02-26 — v1.3.0a8
What changed:
- Implemented deterministic Program Report v0 generator in `psi/services/report_engine.py` with fixed sections and explicit metadata/snapshot coverage.
- Program Report reuses `a3` program rollup for molecule overview/stage surfaces and emits deterministic “not_assessed” comparability placeholders when no program comparability assessments exist.
- Extended DI contract smoke with an in-memory fixture proving rollup-backed Program Report structure, deterministic molecule ordering, and comparability placeholder behavior.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Program Report v0 is read-only over existing snapshots/rollups and stores deterministic artifacts; DI outputs remain unchanged.
## 2026-02-26 — v1.3.0a9
What changed:
- Implemented Molecule Comparative Report v0 (2–5 molecules) in `psi/services/report_engine.py` with deterministic molecule ordering and fixed report structure.
- Added comparability citations when available, otherwise deterministic `not_assessed` placeholders.
- Integrated V3 ranking surface only through the policy-defined scaffold (disabled by default); surfaced as deterministic metadata in the report.
- Extended DI contract smoke with an in-memory fixture proving deterministic row ordering and disabled ranking surface behavior.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Comparative report generation is read-only and policy-surfaced; no DI engine behavior changes.
## 2026-02-26 — v1.3.0a10
What changed:
- Implemented Program Comparative Report v0 (2–5 programs) in `psi/services/report_engine.py` with deterministic ordering and fixed charter-aligned section structure.
- Added ranking surface integration via the policy-defined scaffold (disabled by default) and policy-derived-only resource implications placeholder surface.
- Extended DI contract smoke with an in-memory fixture proving deterministic program ordering and resource placeholder invariants.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Comparative report generation is deterministic and read-only over existing rollup/snapshot surfaces; DI outputs unchanged.
## 2026-02-26 — v1.3.0a11
What changed:
- Added minimal deterministic V3 report UI surfaces: `/reports`, `/reports/new`, `/reports/{id}` to request and view report runs without narrative summarization.
- Added `psi/services/reports_v3.py` form/request plumbing and read-only report detail context assembly.
- Added report templates that render metadata, policy pins, snapshot coverage, and structured sections verbatim.
- Extended DI contract smoke with a deterministic template render check for the report detail surface.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/reports_v3.py`
- `psi/web/app.py`
- `psi/web/routers/reports.py`
- `psi/web/templates/base.html`
- `psi/web/templates/reports/list.html`
- `psi/web/templates/reports/new.html`
- `psi/web/templates/reports/detail.html`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- UI/report request surfaces are deterministic wrappers over persisted report artifacts and generators; no DI snapshot semantics changes.
## 2026-02-26 — v1.3.0a12
What changed:
- Added minimal deterministic lineage dashboards/services for Program and Portfolio lineage (`psi/services/lineage.py` + `/lineage/...` routes/templates).
- Lineage surfaces explicitly separate evidence changes (snapshot coverage deltas), policy changes (policy pin deltas), and governance changes (attribution events).
- Added DI contract smoke coverage for deterministic lineage service categorization output on an in-memory fixture.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/lineage.py`
- `psi/web/app.py`
- `psi/web/routers/lineage.py`
- `psi/web/templates/base.html`
- `psi/web/templates/lineage/program_detail.html`
- `psi/web/templates/lineage/portfolio_detail.html`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Lineage dashboards are read-only governance surfaces over existing DB artifacts and attribution metadata; no DI semantics changes.
## 2026-02-26 — v1.3.0a13
What changed:
- Added `template_catalog_v0_1.json` scaffold for template ladder expansion governance (explicit current version + immutable version list per template).
- Added contract smoke checks for template catalog schema, deterministic ordering, and immutability guardrails against actual policy files.
- No changes to existing template semantics or DI policy resolution.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/template_catalog_v0_1.json`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Template catalog is governance metadata only; replay semantics are unchanged and remain enforced by replay regression.
## 2026-02-26 — v1.3.0a14
What changed:
- Added additive `policy_upgrade_sessions` governance table and `psi/services/policy_upgrade.py` scaffold for deterministic policy upgrade sessions.
- Sessions record old/new policy pins, deterministic delta placeholder surfaces (ranking/comparability/report sections), and an explicit persisted operator acknowledgment flag.
- Extended DI contract smoke with in-memory coverage proving deterministic delta payloads and explicit ack persistence semantics.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/core/db.py`
- `psi/services/policy_upgrade.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Upgrade-session scaffolding is governance-only and does not alter active policy selection or DI snapshot semantics.
## 2026-02-26 — v1.3.0a15
What changed:
- Expanded V3 contract coverage in `di_contract_smoke` for comparability categorical-only enforcement and attribution non-interference on report payload generation.
- Added pytest coverage for deterministic fixed-schema report engine payload generation across all 4 V3 report types (`tests/test_v3_report_engine_contracts.py`).
- Updated `docs/DI_MISSION_AND_ROADMAP_V3.md` implementation-status note to reflect the actual V3 scaffolds/surfaces shipped through `a15`, including placeholder/non-assessed policy-scaffolded surfaces.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_v3_report_engine_contracts.py`
- `docs/DI_MISSION_AND_ROADMAP_V3.md`

Determinism/Replay note:
- Contract/docs closeout only; no DI semantics or snapshot semantics changes.
## 2026-02-26 — v1.3.0a16
Intent:
- Canonicalize comparability entity pairs deterministically and add write-time governance guardrails for duplicate/conflicting pair+rule+as_of submissions.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/comparability.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Pair ordering is canonicalized lexicographically by `(entity_type, entity_id)` before persistence, so `(A,B)` and `(B,A)` resolve identically.
- Cited keys/snapshot ids are stored as stable/sorted JSON arrays.
- Duplicate/conflict handling emits deterministic error codes:
  - `comparability_duplicate_same_pair_rule_asof`
  - `comparability_conflict_same_pair_rule_asof`

Schema changes:
- None.

Gates:
- PASS

## 2026-03-07 — v1.3.0c31
Intent:
- Introduce a minimal persisted operational `ExperimentTask` entity as the foundation for board-to-execution workflows.

## 2026-03-07 — v1.3.0c33
Intent:
- Add lightweight server-rendered task routes for create/update operations.

## 2026-03-07 — v1.3.0c34
Intent:
- Harden experiment task transitions and deterministic open-task ordering.

## 2026-03-07 — v1.3.0c35
Intent:
- Wire experiment tasks into Development Board cards as command-center chips.

## 2026-03-07 — v1.3.0c36
Intent:
- Add compact “Why here?” explanations to board cards from InsightEngine-derived context.

## 2026-03-07 — v1.3.0c37
Intent:
- Make board recommendation actions task-first with optional immediate data-entry handoff.

## 2026-03-07 — v1.3.0c38
Intent:
- Polish board cards into clearer operational action stacks.

## 2026-03-07 — v1.3.0c39
Intent:
- Extend `/data/new` with experiment-task handoff context.

## 2026-03-07 — v1.3.0c40
Intent:
- Complete and link experiment tasks on successful DataRecord creation from task-linked flows.

## 2026-03-07 — v1.3.0c41
Intent:
- Add builder exploration operational tasks without coupling builder provenance/state.

## 2026-03-07 — v1.3.0c42
Intent:
- Add molecule/program cross-surface operational task visibility.

## 2026-03-07 — v1.3.0c43
Intent:
- Add Development Board operational execution filters.

## 2026-03-07 — v1.3.0c44
Intent:
- Add top-of-board in-progress rollup panel for daily execution visibility.

## 2026-03-07 — v1.3.0c45
Intent:
- Regression hardening + task model boundary documentation.

## 2026-03-07 — v1.3.0c46
Intent:
- Introduce Portfolio Intelligence read-model service foundation.

## 2026-03-07 — v1.3.0c47
Intent:
- Add program-level portfolio rollup builder.

## 2026-03-07 — v1.3.0c48
Intent:
- Add deterministic ordering for portfolio program summaries.

## 2026-03-07 — v1.3.0c49
Intent:
- Add Portfolio Intelligence router surface at `/portfolio`.

## 2026-03-07 — v1.3.0c50
Intent:
- Add Portfolio Intelligence overview template.

## 2026-03-07 — v1.3.0c51
Intent:
- Add Portfolio entry in main navigation.

## 2026-03-07 — v1.3.0c52
Intent:
- Add portfolio-level program readiness scoring heuristic.

## 2026-03-07 — v1.3.0c53
Intent:
- Add portfolio program heatmap indicators.

## 2026-03-07 — v1.3.0c54
Intent:
- Add global task dashboard metrics for portfolio leadership view.

## 2026-03-07 — v1.3.0c55
Intent:
- Add molecule leaderboard for closest-to-readiness portfolio view.

## 2026-03-07 — v1.3.0c56
Intent:
- Add portfolio evidence-gap report from InsightEngine-derived missing metrics.

## 2026-03-07 — v1.3.0c57
Intent:
- Add portfolio program bottleneck detection badges.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/portfolio.py`
- `psi/web/templates/portfolio/overview.html`
- `tests/test_portfolio_service.py`
- `tests/test_portfolio_surface.py`

Behavior:
- Added program bottleneck badges for:
  - concentrated missing metric (>50% molecules share same missing metric)
  - overdue task burden over threshold
- Displayed badges in portfolio program table.
- Added service/template tests.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/portfolio.py`
- `psi/web/routers/portfolio.py`
- `psi/web/templates/portfolio/overview.html`
- `tests/test_portfolio_service.py`
- `tests/test_portfolio_surface.py`

Behavior:
- Added `build_evidence_gap_report()` aggregating recurring missing metrics across molecules.
- Added “Evidence Gap Report” section to `/portfolio`.
- Added service/template tests for gap counting/rendering.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/portfolio.py`
- `psi/web/routers/portfolio.py`
- `psi/web/templates/portfolio/overview.html`
- `tests/test_portfolio_service.py`
- `tests/test_portfolio_surface.py`

Behavior:
- Added `build_molecule_leaderboard()` ranking molecules by:
  - insight readiness status
  - completed evidence row count
  - missing metrics burden
- Added leaderboard section to portfolio page.
- Added service/template tests.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/portfolio.py`
- `psi/web/templates/portfolio/overview.html`
- `tests/test_portfolio_service.py`
- `tests/test_portfolio_surface.py`

Behavior:
- Portfolio summary now includes:
  - `tasks_in_progress`
  - `tasks_overdue`
  - `tasks_blocked`
  - `tasks_unassigned`
- Portfolio page global task section now displays these derived metrics.
- Added service/template tests.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/portfolio.py`
- `psi/web/templates/portfolio/overview.html`
- `tests/test_portfolio_service.py`
- `tests/test_portfolio_surface.py`

Behavior:
- Added heat classification/emoji on program rows:
  - 🟢 progressing
  - 🟡 evidence gaps
  - 🔴 blocked
- Heat derived from existing readiness/task rollup fields.
- Added service/template tests.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/portfolio.py`
- `tests/test_portfolio_service.py`

Behavior:
- Readiness score now combines:
  - ready molecules
  - failed molecules
  - missing-data molecules
  - open/blocked/overdue task burden
- Heuristic is portfolio-layer read-model only (no DI mutation).
- Added regression test proving backlog penalties reduce score.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/base.html`
- `tests/test_base_navigation.py`

Behavior:
- Added top-nav link to `/portfolio` while preserving existing `/portfolios`.
- Added navigation regression test.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/portfolio/overview.html`
- `tests/test_portfolio_surface.py`

Behavior:
- Added `/portfolio` page template with:
  - Portfolio Summary
  - Program Table
  - Global Task Status
- Added template rendering tests.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/portfolio.py`
- `psi/web/app.py`
- `tests/test_portfolio_router.py`

Behavior:
- Added `GET /portfolio` route returning:
  - portfolio summary
  - program portfolio summaries
- Wired portfolio router into app.
- Added route/context tests.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/portfolio.py`
- `tests/test_portfolio_service.py`

Behavior:
- Added `build_portfolio_program_summaries()` with deterministic ordering by:
  1. readiness score (desc)
  2. open task burden (asc)
  3. molecule count (asc)
  4. program_id (asc)
- Added deterministic ordering regression test.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/portfolio.py`
- `tests/test_portfolio_service.py`

Behavior:
- Added `build_program_portfolio_summary(program_id)` with:
  - `molecules_ready`
  - `molecules_failed`
  - `molecules_missing_data`
  - `open_tasks`
  - `overdue_tasks`
  - `blocked_tasks`
- Metrics derived from existing board read-model + task table; no DI state mutation.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/portfolio.py`
- `tests/test_portfolio_service.py`

Behavior:
- Added `build_portfolio_summary()` returning:
  - `program_count`
  - `molecule_count`
  - `task_count`
  - `overdue_tasks`
  - `blocked_tasks`
  - `ready_molecules`
  - `missing_data_molecules`
- Summary is derived from existing entities and board insight groupings (read-model only).

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_experiment_task_regression_boundaries.py`
- `docs/COMMAND_CENTER_TASK_MODEL.md`

Behavior:
- Added regression tests covering:
  - task lifecycle and determinism with board present
  - task → DataRecord linkage behavior
  - no DI snapshot payload mutation from task operations
  - no fake evidence record creation via task linkage
- Added docs defining command-center boundaries and non-goals:
  - no DI semantic coupling
  - no snapshot/report coupling for task state
  - no evidence-object overloading

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/dev_board.py`
- `psi/web/templates/programs/board.html`
- `tests/test_dev_board.py`
- `tests/test_program_board_surface.py`

Behavior:
- Board payload now includes `execution_rollup`:
  - `in_progress_this_week`
  - `overdue`
  - `blocked`
  - `unassigned`
- Added “Execution Panel” at top of board for quick operational triage.
- Added service/template tests for rollup derivation/rendering.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/dev_board.py`
- `psi/web/routers/programs.py`
- `psi/web/templates/programs/board.html`
- `tests/test_program_board_filters.py`
- `tests/test_program_board_surface.py`

Behavior:
- Added board filters for:
  - owner
  - urgency
  - due soon / overdue
  - task status (`planned`, `in_progress`, `blocked`, `open`)
- Preserved existing group/search filters and made query-preserving links/forms.
- Card payload now includes top-task owner/status/urgency/due metadata for deterministic filtering.
- Added route/template tests validating filter behavior.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/services/programs.py`
- `psi/web/templates/molecules/detail.html`
- `psi/web/templates/programs/detail.html`
- `tests/test_molecule_task_visibility.py`
- `tests/test_molecule_lineage_surface.py`
- `tests/test_program_review_queue.py`

Behavior:
- Molecule detail now surfaces open operational tasks with quick status actions.
- Program detail now includes compact “Open Operational Tasks” summary table.
- Visibility remains additive/read-only with task updates routed through existing task endpoints.
- Added service/template tests for molecule/program task visibility.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/builder.py`
- `psi/web/templates/programs/board.html`
- `tests/test_builder_router.py`
- `tests/test_program_board_surface.py`

Behavior:
- Added route `POST /builder/exploration-task` to create lightweight engineering exploration tasks with:
  - `source_kind=builder_exploration`
  - builder-target hint in `suggested_assay` (`builder:point-mutation`, etc.)
- Route redirects into builder/sequence surfaces with `task_id` context.
- Board CTA now supports “Create exploration task + variant” from molecule cards.
- Added route/template tests for exploration-task creation and wiring.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/data_records.py`
- `psi/web/templates/data/form.html`
- `tests/test_data_task_handoff.py`

Behavior:
- Data form now carries hidden `task_id` through submit.
- `POST /data/new` now handles `task_id` by:
  - linking `linked_data_record_id` to created DataRecord
  - transitioning task status through lifecycle to `done` (respecting allowed transitions)
- Keeps Evidence/DataRecord semantics unchanged:
  - DataRecord remains evidence object
  - ExperimentTask is operational record with pointer to evidence
- Added test coverage for link+complete behavior.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/data_records.py`
- `psi/web/templates/data/form.html`
- `tests/test_data_task_handoff.py`

Behavior:
- `/data/new` now accepts `task_id`.
- When `task_id` is present and valid, form prefill derives from task context (program/molecule/method/title defaults).
- New Data form renders a compact “Task Context” panel showing linked task details.
- No evidence rows are auto-created during handoff (prefill only).
- Added route-level handoff test coverage.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/dev_board.py`
- `psi/web/templates/programs/board.html`
- `tests/test_dev_board.py`
- `tests/test_program_board_surface.py`

Behavior:
- Added deterministic `top_next_action` per card:
  - continue top task when open task exists
  - else add missing measurement
  - else create suggested-experiment task
  - else review molecule detail
- Surface now explicitly shows:
  - why-here narrative
  - top next action
  - trend/warnings/blocker/task chips
- Added tests for card action derivation/rendering.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/programs.py`
- `psi/web/templates/programs/board.html`
- `tests/test_experiment_task_routes.py`
- `tests/test_program_board_surface.py`

Behavior:
- Replaced direct “Run suggested experiment” links with:
  - `Create task`
  - `Create task + start data entry`
- Added route `POST /programs/{program_id}/tasks/create-and-start-data`:
  - creates a tracked task from board recommendation
  - redirects to `/data/new` with task/program/molecule context in query params
- Updated card click JS guard to avoid intercepting form/button interactions.
- Added route/template tests for payload/redirect correctness.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/dev_board.py`
- `psi/web/templates/programs/board.html`
- `tests/test_dev_board.py`
- `tests/test_program_board_surface.py`

Behavior:
- Board cards now include `why_here` narrative computed from existing bundle/grouping context:
  - failed criteria explanation
  - missing data explanation
  - no-snapshot explanation
- Template renders `Why here:` on each card with no ad hoc DI recomputation.
- Added tests for rendered explanation text and deterministic missing/no-snapshot messaging.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/dev_board.py`
- `psi/web/templates/programs/board.html`
- `tests/test_dev_board.py`
- `tests/test_program_board_surface.py`

Behavior:
- Board card payload now includes:
  - `open_task_count`
  - `in_progress_task_count`
  - `top_next_task_label`
- Board template now renders task chips on each molecule card.
- Added service/template tests covering task-aware board rendering.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/experiment_tasks.py`
- `tests/test_experiment_tasks.py`

Behavior:
- Enforced lifecycle transitions:
  - `planned -> in_progress`
  - `planned -> blocked`
  - `in_progress -> done`
  - `in_progress -> blocked`
  - `blocked -> in_progress`
  - `done` remains terminal
- Open-task ordering for list/top-next now uses deterministic key order:
  - urgency
  - due_date
  - created_at
  - id
- Added transition-graph tests and updated ordering expectations.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/experiment_tasks.py`
- `psi/web/routers/programs.py`
- `tests/test_experiment_task_routes.py`

Behavior:
- Added POST routes for:
  - task create
  - status update
  - mark in progress / blocked / done
  - owner update
  - due date update
  - urgency update
  - notes update
- Added service setters for urgency and notes to keep router logic thin/deterministic.
- Added route-level tests for registration and end-to-end create/update behavior.

Gates:
- PASS

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/core/db.py`
- `tests/test_experiment_task_model.py`

Behavior:
- Added additive ORM entity `program_experiment_tasks` with explicit separation from:
  - DI snapshots (`decision_snapshots`)
  - evidence records (`data_records`)
  - builder lineage/provenance entities
- Added nullable linkage fields:
  - `source_snapshot_id` (read-only decision context pointer)
  - `linked_data_record_id` (evidence linkage pointer)
- Added deterministic query indexes for program/molecule/status retrieval.
- Added schema/model regression tests covering table shape, index presence, and linkage behavior.

Schema changes:
- New table: `program_experiment_tasks`.
- Additive indexes:
  - `ix_experiment_tasks_program_status`
  - `ix_experiment_tasks_molecule_status`
  - `ix_experiment_tasks_program_molecule`
  - `ix_experiment_tasks_source_snapshot_id`
  - `ix_experiment_tasks_linked_data_record_id`

Gates:
- PASS

## 2026-03-07 — v1.3.0c32
Intent:
- Add a lightweight deterministic `ExperimentTask` service layer for operational work management.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/experiment_tasks.py`
- `tests/test_experiment_tasks.py`

Behavior:
- Added task service operations:
  - `create_experiment_task`
  - `list_tasks_for_program`
  - `list_tasks_for_molecule`
  - `update_task_status`
  - `assign_task_owner`
  - `set_task_due_date`
  - `link_task_to_data_record`
  - `top_open_task_for_molecule`
- Enforced deterministic list ordering across status/urgency/due date/created_at/id.
- Enforced one-way completion behavior (`done` is terminal).
- Kept boundaries clean:
  - no DI writes
  - no fake DataRecord creation
  - task-to-DataRecord linkage only to existing evidence rows

Gates:
- PASS

## 2026-03-07 — v1.3.0c30
Intent:
- Development Board performance pass for larger program sizes.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/dev_board.py`
- `tests/test_dev_board.py`

Behavior:
- Replaced per-molecule trend queries with one bulk trend query per program.
- Board now computes per-card trend signals from preloaded per-program metric series.
- Added regression coverage confirming trend signal derivation (`improving`) from bulk path.

Gates:
- PASS

## 2026-03-07 — v1.3.0c29
Intent:
- Add Development Board top summary panel.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/programs/board.html`
- `tests/test_program_board_surface.py`

Behavior:
- Added Program Summary panel with group counts:
  - Ready
  - Failed
  - Missing data
  - Not evaluated
- Added template assertions for summary panel/count rendering.

Gates:
- PASS

## 2026-03-07 — v1.3.0c28
Intent:
- Add Development Board search by molecule ID.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/programs.py`
- `psi/web/templates/programs/board.html`
- `tests/test_program_board_surface.py`

Behavior:
- Added `q` query parameter to board route and deterministic server-side filtering by `primary_id`.
- Added search form to board UI and kept filter links query-preserving.
- Added template assertions for search controls.

Gates:
- PASS

## 2026-03-07 — v1.3.0c27
Intent:
- Add Development Board status filters.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/programs.py`
- `psi/web/templates/programs/board.html`
- `tests/test_program_board_surface.py`

Behavior:
- Added query-param filters (`all|ready|failed|missing`) to board route.
- Added filter controls to board UI.
- Filtered server-side board group rendering deterministically.

Gates:
- PASS

## 2026-03-07 — v1.3.0c26
Intent:
- Add card-level warning flags on Development Board.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/dev_board.py`
- `psi/web/templates/programs/board.html`
- `tests/test_dev_board.py`
- `tests/test_program_board_surface.py`

Behavior:
- Board cards now derive warnings from insight/trend signals:
  - `confirmation recommended`
  - `conflicting evidence`
  - `instability risk`
- Warning chips are rendered per card in deterministic order.
- Added test assertions for warning fields and warning chip rendering.

Gates:
- PASS

## 2026-03-07 — v1.3.0c25
Intent:
- Add builder shortcuts on Development Board cards.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/programs/board.html`
- `tests/test_program_board_surface.py`

Behavior:
- Added `Create variant` shortcut to Builder point-mutation flow with parent preselection.
- Added `Open sequence editor` shortcut to molecule detail editor anchor.
- Added template assertions for both shortcut links.

Gates:
- PASS

## 2026-03-07 — v1.3.0c24
Intent:
- Add card-level experiment shortcuts on Development Board.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/programs/board.html`
- `tests/test_program_board_surface.py`

Behavior:
- Added `Add missing measurement` and `Run suggested experiment` shortcut buttons per card.
- Shortcuts prefill `/data/new` with `program_id`, `molecule_id`, and metric-based method/title hints.
- Added template assertions for shortcut render and route payload fields.

Gates:
- PASS

## 2026-03-07 — v1.3.0c23
Intent:
- Add card-level navigation on Development Board molecule cards.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/programs/board.html`
- `tests/test_program_board_surface.py`

Behavior:
- Board cards now expose `data-card-link` and click-through behavior to molecule detail.
- Link clicks inside cards remain native and are not overridden.
- Added template assertion for card-link attribute.

Gates:
- PASS

## 2026-03-07 — v1.3.0c22
Intent:
- Add deterministic trend indicators to Development Board cards.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/dev_board.py`
- `psi/web/templates/programs/board.html`
- `tests/test_dev_board.py`
- `tests/test_program_board_surface.py`

Behavior:
- Board service now derives per-card trend signal (`improving|declining|stable`) from trend-service output.
- Board cards now display trend chips (`▲ improving`, `▼ declining`, `■ stable`).
- Added test coverage for trend-signal presence in service and UI render.

Gates:
- PASS

## 2026-03-07 — v1.3.0c21
Intent:
- Implement Molecule Development Board card layout details.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/programs/board.html`
- `tests/test_program_board_surface.py`

Behavior:
- Board cards now show molecule identity, interpreted status, and top blocking reason text.
- Kept deterministic card ordering and link behavior.
- Added template assertion for rendered status text.

Gates:
- PASS

## 2026-03-07 — v1.3.0c20
Intent:
- Add navigation path from program detail to Development Board.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/programs/detail.html`
- `tests/test_program_review_queue.py`

Behavior:
- Added `View Development Board` button linking to `/programs/{id}/board` in Program Drill-down controls.
- Added template regression assertions for board navigation link.

Gates:
- PASS

## 2026-03-07 — v1.3.0c19
Intent:
- Build Development Board UI scaffold sections for scientist operations.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/programs/board.html`
- `tests/test_program_board_surface.py`

Behavior:
- Board sections now render as explicit section blocks with stable IDs and per-group counts.
- Added deterministic card placeholder row style for upcoming card enrichments.
- Added template coverage for section IDs/count rendering.

Gates:
- PASS

## 2026-03-07 — v1.3.0c18
Intent:
- Add lightweight per-program Development Board caching with explicit invalidation.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/dev_board.py`
- `psi/services/data_records.py`
- `psi/services/decisions.py`
- `psi/services/di/runner.py`
- `tests/test_dev_board.py`

Behavior:
- Added in-process program board cache and `invalidate_program_board_cache()` helper.
- Invalidation now fires when data records are created/updated and when snapshots are created via legacy and DI paths.
- Added cache behavior test covering cache hit and invalidation refresh.

Gates:
- PASS

## 2026-03-07 — v1.3.0c17
Intent:
- Add Development Board route surface under programs.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/programs.py`
- `psi/web/templates/programs/board.html`
- `tests/test_program_board_route.py`

Behavior:
- Added `GET /programs/{program_id}/board` rendering a dedicated development-board page.
- Added initial board template with READY/FAILED/MISSING/NOT EVALUATED sections.
- Added route test verifying board page renders expected sections.

Gates:
- PASS

## 2026-03-07 — v1.3.0c16
Intent:
- Introduce Molecule Development Board service model and deterministic grouping logic.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/dev_board.py`
- `tests/test_dev_board.py`

Behavior:
- Added `build_development_board(program_id)` that groups molecule cards into `ready`, `failed`, `missing_data`, and `not_evaluated` from latest DI snapshot interpretation.
- Added deterministic sort/order for board cards and group output.
- Added service test covering grouping behavior.

Gates:
- PASS

## 2026-03-07 — v1.3.0c15
Intent:
- Add bulk-import UI and two-step validate/confirm flow.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/data_records.py`
- `psi/web/templates/data/list.html`
- `psi/web/templates/data/bulk_import.html`
- `tests/test_bulk_import_template.py`

Behavior:
- Added `/data/bulk-import` page with paste, validation, error preview, and explicit confirm import step.
- Confirm import creates data records through existing `create_data_record()` path.
- Added data list navigation link to bulk import.
- Added template regression tests for bulk-import route surface and form actions.

Gates:
- PASS

## 2026-03-07 — v1.3.0c14
Intent:
- Add deterministic bulk-import validation service (no writes until confirmation).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/bulk_import.py`
- `tests/test_bulk_import.py`

Behavior:
- Added parser for pasted bulk-import tables with strict header contract.
- Added row validator resolving molecule/batch references and assay defaults per metric key.
- Validation output is deterministic and separates valid rows from error rows.

Gates:
- PASS

## 2026-03-07 — v1.3.0c13
Intent:
- Add trend-signal interpretation using Insight Engine surfaces.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/insight_engine.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`
- `tests/test_insight_engine.py`
- `tests/test_molecule_lineage_surface.py`

Behavior:
- Added `summarize_trend_signals()` for deterministic improving/declining/stable classification.
- Molecule detail now renders trend insight chips above chart cards.
- Added service and template regression coverage for trend signals.

Gates:
- PASS

## 2026-03-07 — v1.3.0c12
Intent:
- Add molecule trend chart surface from deterministic trend aggregation.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`
- `tests/test_molecule_lineage_surface.py`

Behavior:
- Molecule detail now includes `molecule_trends` context from `build_molecule_trends()`.
- Added scientist-facing “Trend Signals” panel with lightweight deterministic SVG sparklines via vanilla JS.
- Added template regression assertions for trend panel rendering.

Gates:
- PASS

## 2026-03-07 — v1.3.0c11
Intent:
- Add deterministic trend aggregation service for key scientist metrics.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/trends.py`
- `tests/test_trends.py`

Behavior:
- Added `build_molecule_trends()` for deterministic per-molecule time-series over `monomer_pct`, `kd_nM`, and `value_eu_ml`.
- Added aggregation test covering stable output shape and ordering.

Gates:
- PASS

## 2026-03-07 — v1.3.0c10
Intent:
- Harden decision-to-experiment bridge actions for scope-safe routing.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/decisions/_di_snapshot.html`
- `tests/test_decision_insight_summary.py`

Behavior:
- Experiment bridge buttons now render only when both `program_id` and `molecule_id` exist on snapshot scope.
- Added explicit fallback guidance text when scope IDs are unavailable.
- Added template regression coverage for the scope-ID requirement path.

Gates:
- PASS

## 2026-03-07 — v1.3.0c9
Intent:
- Enrich evidence-breakdown payload detail for decision interpretation surfaces.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/insight_engine.py`
- `tests/test_insight_engine.py`

Behavior:
- Missing-evidence entries now retain deterministic detail fields (`classification`, `required_threshold`, `batch`, `observed_value`) for richer decision breakdown rendering.
- Added regression assertion for missing-evidence classification field.

Gates:
- PASS

## 2026-03-07 — v1.3.0c8
Intent:
- Promote Insight Engine narrative to decision-page header surface.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/decisions/detail.html`
- `psi/web/templates/decisions/_di_snapshot.html`
- `tests/test_decision_insight_summary.py`

Behavior:
- Decision detail header now includes DI decision-summary text when InsightBundle is available.
- Added deterministic evidence breakdown and experiment-bridge sections in DI snapshot rendering.
- Added template regression coverage for evidence breakdown and bridge links.

Gates:
- PASS

## 2026-03-07 — v1.3.0c7
Intent:
- Fulfill scientist/governance mode split for molecule interpretation surfaces.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`
- `psi/web/static/style.css`
- `tests/test_molecule_lineage_surface.py`

Behavior:
- Added governance payload model for molecule insight surfaces (policy refs, snapshot hash, gate statuses).
- Added governance-only “Insight Governance Detail” panel and scientist-only Next Steps panel.
- Molecule view-mode toggle now drives both header and panel visibility.

Gates:
- PASS

## 2026-03-07 — v1.3.0c6
Intent:
- Expand molecule Next Steps with explicit blocking evidence details.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/molecules/detail.html`
- `tests/test_molecule_lineage_surface.py`

Behavior:
- Added blocking evidence detail table with metric, observed value, required threshold, and batch.
- Added regression assertions for blocking detail render.

Gates:
- PASS

## 2026-03-07 — v1.3.0c5
Intent:
- Add molecule-level scientist-facing Next Steps panel from the Insight Engine.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`
- `tests/test_molecule_lineage_surface.py`

Behavior:
- Molecule detail context now builds a deterministic `molecule_insight_bundle` from the latest DI snapshot output.
- Molecule detail template now renders “What This Molecule Needs Next” with status, blocking issues, missing evidence, and suggested experiments.
- Added template regression assertions for panel render.

Gates:
- PASS

## 2026-03-07 — v1.3.0b76
Intent:
- Improve CDR graft preview to show explicit before/after reconstruction details.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/builder.py`
- `psi/web/templates/builder/cdr_builder.html`
- `tests/test_builder_cdr_template.py`

Behavior:
- CDR graft drafts now emit HC/LC preview rows with inserted CDR labels.
- Added explicit warning banner: “Sequence reconstructed from CDRs using scaffold”.
- CDR builder preview now renders before/after panel with inserted CDR context.
- Added template test coverage for reconstruction preview surfaces.

Gates:
- PASS

## 2026-03-07 — v1.3.0b75
Intent:
- Add dedicated CDR-only builder UI flow with draft preview.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/builder.py`
- `psi/web/templates/builder/index.html`
- `psi/web/templates/builder/cdr_builder.html`
- `tests/test_builder_router.py`
- `tests/test_builder_cdr_template.py`

Behavior:
- Added `/builder/cdr-builder` and `/builder/cdr-builder/draft` routes.
- Added CDR builder page with CDR inputs, framework settings, and deterministic draft preview rendering.
- Linked CDR builder from builder landing page.
- Added focused route/template coverage.

Gates:
- PASS

## 2026-03-07 — v1.3.0b74
Intent:
- Add scaffold framework engine foundations for CDR graft builder mode.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/builder.py`
- `psi/services/builder_ops.py`
- `tests/test_builder_scaffold.py`

Behavior:
- Added framework scaffold presets and `apply_cdr_graft()` pure operation.
- Added numbering/light-chain validation (`kabat`, `chothia`, `imgt`; `kappa`/`lambda`).
- Wired `cdr_graft` mode in draft builder with deterministic operation payload and preview support.
- Added scaffold operation and draft validation tests.

Gates:
- PASS

## 2026-03-07 — v1.3.0b73
Intent:
- Add deterministic KIH operations for builder drafts.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/builder.py`
- `psi/services/builder_ops.py`
- `psi/services/builder_validation.py`
- `tests/test_builder_kih_ops.py`
- `tests/test_builder_modes.py`

Behavior:
- Added pure KIH operations: `apply_kih_knob`, `apply_kih_hole`, `remove_kih`.
- Added `kih_toggle` draft handling with explicit action validation and HC1 requirement checks.
- Added preview row output for KIH draft mutations and focused KIH operation tests.

Gates:
- PASS

## 2026-03-07 — v1.3.0b72
Intent:
- Add deterministic Fc swap operation support to builder draft construction.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/builder.py`
- `psi/services/builder_ops.py`
- `psi/services/builder_validation.py`
- `tests/test_builder_fc_swap.py`

Behavior:
- Added Fc presets (`human_igg1`, `mouse_igg2a`, `fab_no_fc`) and pure `apply_fc_swap()` op.
- Added Fc swap validation requiring heavy-chain context (`HC1`).
- `fc_swap` draft mode now applies preset at draft-build time with preview row summary.
- Added focused Fc swap unit and draft tests.

Gates:
- PASS

## 2026-03-07 — v1.3.0b71
Intent:
- Expand builder mode contracts to include future engineering modes.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/builder.py`
- `tests/test_builder_modes.py`

Behavior:
- Builder now recognizes `cdr_graft`, `fc_swap`, and `kih_toggle` in `MoleculeBuildSpec.mode`.
- Added deterministic mode recognition test coverage for expanded modes.
- No UI behavior change yet for new modes.

Gates:
- PASS

## 2026-03-07 — v1.3.0b70
Intent:
- Polish builder parent-selection UX with recent selections, clear/switch controls, and selected-parent summary.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/builder/clone.html`
- `psi/web/templates/builder/point_mutation.html`
- `tests/test_builder_router_parent_selector.py`

Behavior:
- Added selected parent summary card on clone and point-mutation forms.
- Added “Clear selection” control to reset current program/molecule selection.
- Added recent parent memory (localStorage, deterministic capped list of 5) and display.
- Kept preview-before-save flow unchanged.

Gates:
- PASS

## 2026-03-07 — v1.3.0b69
Intent:
- Add global builder molecule search autocomplete endpoint and UI hooks.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/builder.py`
- `psi/web/templates/builder/clone.html`
- `psi/web/templates/builder/point_mutation.html`
- `tests/test_builder_router.py`
- `tests/test_builder_search.py`

Behavior:
- Added `/builder/search_molecules?q=` endpoint returning deterministic JSON suggestions (`id`, `primary_id`, `title`, `program_name`), limited to 10.
- Added search inputs and lightweight autocomplete result rendering in clone and point-mutation pages.
- Added tests for route presence and bounded search output contract.

Gates:
- PASS

## 2026-03-07 — v1.3.0b68
Intent:
- Redesign builder parent selection with deterministic Program → Molecule cascading selectors.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/builder.py`
- `psi/web/templates/builder/clone.html`
- `psi/web/templates/builder/point_mutation.html`
- `tests/test_builder_router_parent_selector.py`

Behavior:
- Builder clone and point-mutation forms now provide a program dropdown and a molecule dropdown filtered by selected program.
- Added deterministic parent-selection payloads (`parent_programs`, `parent_molecules_by_program`) and client-side cascade rendering.
- Added focused template tests for cascade selector presence.

Gates:
- PASS

## 2026-03-07 — v1.3.0b67
Intent:
- Finalize builder phase-1 docs and regression hardening for non-interference guarantees.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/README.md`
- `docs/BUILDER_PHASE1_v1.3.0b67.md`
- `tests/test_builder_service.py`

Behavior:
- Added builder phase-1 documentation defining scope, safety invariants, determinism rules, and next safe steps.
- Added regression assertion that builder creation does not create DI snapshots or program memberships.
- Kept builder subsystem outside Programs while preserving existing molecule/program/DI flows.

Gates:
- PASS

## 2026-03-07 — v1.3.0b66
Intent:
- Improve builder preview UX and strengthen invalid-draft safety messaging.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/builder.py`
- `psi/web/templates/builder/point_mutation.html`
- `tests/test_builder_service.py`
- `tests/test_builder_router.py`

Behavior:
- Added `preview_rows` to mutation drafts for explicit before/after mutation summaries.
- Point mutation preview now renders clear validation errors, warnings, and before/after mutation table.
- Save action remains gated behind valid draft path; invalid drafts continue to block creation.
- Added tests for preview row generation and template rendering of before/after mutation summary.

Gates:
- PASS

## 2026-03-07 — v1.3.0b65
Intent:
- Persist additive builder derivation provenance for parent→child molecule creation.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/services/builder.py`
- `tests/test_builder_service.py`

Behavior:
- Added additive `molecule_derivations` table model for parent/child provenance.
- Builder create now records deterministic derivation rows with `derivation_type`, summary, and canonical `edit_payload_json`.
- Added tests asserting provenance persistence for clone and point-mutation flows.

Gates:
- PASS

## 2026-03-07 — v1.3.0b64
Intent:
- Implement full point-mutation builder flow (draft + validation + create).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/builder.py`
- `psi/web/routers/builder.py`
- `psi/web/templates/builder/point_mutation.html`
- `tests/test_builder_service.py`
- `tests/test_builder_router.py`

Behavior:
- `build_molecule_draft(...)` now supports `point_mutation` mode with deterministic operation parsing and WT residue validation.
- Added point mutation draft/build endpoint (`POST /builder/point-mutation/draft`) and create endpoint (`POST /builder/point-mutation/create`).
- Point mutation UI now provides preview-before-save and displays validation errors without partial writes.
- Added service and router tests for successful mutation flow and invalid WT mismatch handling.

Gates:
- PASS

## 2026-03-07 — v1.3.0b63
Intent:
- Add deterministic point-mutation parsing and pure mutation ops for builder workflows.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/builder_ops.py`
- `psi/services/builder_validation.py`
- `tests/test_builder_point_mutation_ops.py`

Behavior:
- Added mutation token parser supporting deterministic multi-token input (`S32A N54Q`, comma/space/semicolon separators).
- Added pure mutation application with WT residue checks, range checks, and explicit error reporting.
- Added validation helpers for target component existence and non-empty mutation sets.
- Added unit tests for parse, duplicate-position errors, deterministic apply, and mismatch handling.

Gates:
- PASS

## 2026-03-07 — v1.3.0b62
Intent:
- Implement clone molecule builder flow with deterministic preview-before-save behavior.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/builder.py`
- `psi/web/routers/builder.py`
- `psi/web/templates/builder/clone.html`
- `tests/test_builder_service.py`
- `tests/test_builder_router.py`

Behavior:
- Added clone draft build endpoint (`POST /builder/clone/draft`) and explicit create endpoint (`POST /builder/clone/create`).
- Builder clone UI now collects inputs, renders draft validation/errors, previews component sequences, and enables confirm-save only from draft.
- `create_molecule_from_draft(...)` now persists a new molecule from draft components deterministically without mutating parent.
- Added regression tests for clone flow routes/template and parent-unchanged child creation.

Gates:
- PASS

## 2026-03-07 — v1.3.0b61
Intent:
- Add standalone Builder router and landing surface outside Programs.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/app.py`
- `psi/web/routers/builder.py`
- `psi/web/templates/base.html`
- `psi/web/templates/builder/index.html`
- `psi/web/templates/builder/clone.html`
- `psi/web/templates/builder/point_mutation.html`
- `tests/test_builder_router.py`

Behavior:
- Added top-level `/builder` route with standalone landing page and deterministic molecule list.
- Added scaffold routes `/builder/clone` and `/builder/point-mutation` for builder workflows.
- Added Builder top-nav entry, keeping builder concerns separate from Programs.
- Added focused router/template tests.

Gates:
- PASS

## 2026-03-07 — v1.3.0b60
Intent:
- Introduce standalone Molecule Builder service foundation with explicit draft/build and create boundaries.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/builder.py`
- `psi/services/builder_ops.py`
- `psi/services/builder_validation.py`
- `tests/test_builder_service.py`

Behavior:
- Added typed builder contracts: `MoleculeBuildSpec`, `MoleculeDraft`, `MoleculeCreateMeta`.
- Added `build_molecule_draft(...)` for deterministic, read-only draft construction.
- Added `create_molecule_from_draft(...)` for explicit persistence of a new molecule only.
- Added service tests for read-only draft behavior, parent immutability, and no-write on invalid drafts.

Gates:
- PASS

## 2026-03-07 — v1.3.0b59
Intent:
- Hotfix program detail runtime SQL to match live `data_measurements` schema and prevent `/programs/{id}` OperationalError.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/programs.py`
- `tests/test_program_review_queue.py`

Behavior:
- Replaced program evidence query fallback `COALESCE(dm.metric_key, dm.name)` with canonical `dm.metric_key` only.
- Added a regression test asserting the active program evidence SQL does not reference `dm.name`.

Gates:
- PASS

## 2026-03-07 — v1.3.0b58
Intent:
- Finalize Program-centric PSI phase 1 with status documentation and regression hardening checks.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/DI_V3_STATUS_v1.3.0b58.md`
- `docs/README.md`
- `tests/test_program_review_queue.py`

Behavior:
- Added a formal V3 status checkpoint document covering delivered program-centric surfaces, guardrails, and remaining gaps.
- Added a regression test that enforces governance panel default-hidden behavior in program detail.
- Updated docs index to include the new V3 status checkpoint.

Gates:
- PASS

## 2026-03-07 — v1.3.0b57
Intent:
- Enforce scientist-vs-governance separation on the program dashboard by hiding DI governance analytics behind an explicit toggle.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/programs/detail.html`
- `tests/test_program_review_queue.py`

Behavior:
- Program detail now renders DI governance analytics inside a default-hidden panel with `aria-hidden="true"`.
- Added deterministic governance toggle state persistence via `localStorage` key `psi_program_detail_mode`.
- Scientist-first surfaces remain visible by default; governance details remain accessible on demand.

Gates:
- PASS

## 2026-03-03 — v1.3.0b27
Intent:
- Final verification checkpoint for b16-b27 chain with deterministic gate confirmation and overlay-safe packaging consistency.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`

Behavior:
- No runtime logic changes in this patch.
- Finalized chain version marker and recorded gate verification status.

Gates:
- PASS

## 2026-03-03 — v1.3.0b26
Intent:
- Clean up redundant report CSS hooks and keep report table alignment rules consolidated.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/static/style.css`

Behavior:
- Removed redundant `.fact-sheet-matrix` text-alignment hook now superseded by report-scoped table-header alignment rules.
- No non-report page behavior changes.
- No payload or service changes.

Gates:
- PASS

## 2026-03-03 — v1.3.0b25
Intent:
- Tighten report detail header layout and molecule-specific header wording using template/CSS-only adjustments.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`
- `psi/web/static/style.css`

Behavior:
- Added dedicated report header layout class to remove inline spacing behavior and keep consistent header alignment.
- Header label now uses `Subject` for molecule reports and `Subjects` for other report types.
- Kept molecule-specific hiding of snapshot coverage unchanged.
- No payload or routing behavior changes.

Gates:
- PASS

## 2026-03-03 — v1.3.0b24
Intent:
- Add minimal docs index links for V3 roadmap/status navigation.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/README.md`

Behavior:
- Added `docs/README.md` with links to V3 mission charter and the new V3 status checkpoint doc.
- Documentation-only patch; no runtime code changes.

Gates:
- PASS

## 2026-03-03 — v1.3.0b23
Intent:
- Add V3 roadmap checkpoint status document comparing charter requirements to implemented code surfaces.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/DI_V3_STATUS_v1.3.0b23.md`

Behavior:
- Added a documentation-only status checkpoint grounded in `docs/DI_MISSION_AND_ROADMAP_V3.md` and current code modules.
- Included implemented vs partial areas, risks, and next recommended patch themes.
- No runtime behavior, DI semantics, or schema changes.

Gates:
- PASS

## 2026-03-03 — v1.3.0b22
Intent:
- Add strict payload-only enforcement tests for report rendering paths (molecule + comparative surface).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_report_payload_only_rendering.py`

Behavior:
- Added a molecule board payload-only render test that validates output without any DB access.
- Added a comparative identity summary payload-only test using a NoQuery session guard to ensure no view-time query path is needed for molecule-comparative identity rendering.
- No runtime report generation or routing behavior changed.

Gates:
- PASS

## 2026-03-03 — v1.3.0b21
Intent:
- Strengthen reproducibility appendix schema contract tests across all V3 report types.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_v3_report_contracts.py`

Behavior:
- Added an explicit contract test asserting `reproducibility_appendix` required base keys for molecule, program, molecule comparative, and program comparative reports.
- Added molecule-specific assertions for deterministic `measurement_keys` ordering and `governance_red_flags` list presence.
- No runtime report generation behavior changed.

Gates:
- PASS

## 2026-03-03 — v1.3.0b20
Intent:
- Harden report-engine deterministic serialization/fingerprint invariants with targeted tests.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_v3_report_engine_contracts.py`

Behavior:
- Added a deterministic fingerprint test proving equivalent payload dict key ordering yields identical canonical JSON and fingerprint.
- Added a deterministic fingerprint test for molecule payloads with reproducibility appendix present and measurement key citations.
- No report engine runtime behavior changed.

Gates:
- PASS

## 2026-03-03 — v1.3.0b19
Intent:
- Polish board narrative panel microcopy and measurement-key presentation (template-only).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/_board_narrative.html`

Behavior:
- Renamed headings for readability: Executive Snapshot, Evidence Status, Recommended Next Steps.
- Narrative “What this means” heading updated to “Interpretation”.
- Measurement key chips now render deterministically sorted and humanized.
- Empty-state phrasing updated to clearer scientist-facing language.
- No payload generation changes.

Gates:
- PASS

## 2026-03-03 — v1.3.0b18
Intent:
- Improve artifacts board readability with deterministic grouping and compact link UX (payload-only rendering).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/reports_v3.py`
- `psi/web/templates/reports/board_molecule_v3.html`

Behavior:
- Artifacts are deterministically sorted for display (artifact type + stable secondary keys) in board display shaping.
- Molecule board artifacts section now renders grouped sub-tables by artifact type.
- Added a small UI-only “Copy all artifact links” button using existing rendered links; no server/DB dependency.
- No report payload schema changes and no view-time DB query changes.

Gates:
- PASS

## 2026-03-03 — v1.3.0b17
Intent:
- Polish molecule board readability (header/summary microcopy and empty states) without changing report semantics.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/reports_v3.py`
- `psi/web/templates/reports/board_molecule_v3.html`
- `tests/test_board_molecule_sections_rendering.py`

Behavior:
- Molecule board header renamed to **Molecule Overview** and default labels now use `Not available` phrasing.
- Report summary and table empty states are clearer and scientist-friendly (e.g., “No artifacts linked yet.”).
- Display fallback for missing program identity in molecule board builder normalized to `Not available`.
- No payload changes; no view-time query changes.

Gates:
- PASS

## 2026-03-03 — v1.3.0b16
Intent:
- Apply global report table-header alignment polish so report/lineage table headings are left-aligned consistently.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/static/style.css`
- `psi/web/templates/reports/list.html`
- `psi/web/templates/reports/new.html`
- `psi/web/templates/lineage/program_detail.html`
- `psi/web/templates/lineage/portfolio_detail.html`

Behavior:
- Added report-scoped CSS that left-aligns `<th>` across report detail, report board templates, upgrade/ladder board panels, and lineage packets.
- Added minimal wrapper classes (`report-page`, `lineage-packet`) to allow scoped styling without affecting unrelated pages.
- No payload generation changes.

Gates:
- PASS

## 2026-03-03 — v1.3.0b15
Intent:
- Add explicit deterministic ranking tie-break contract fields and tie-break explanation schema metadata without changing ranking behavior.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/ranking_policy_v0_2.json`
- `psi/services/v3_ranking.py`

Behavior:
- Ranking policy v0.2 now explicitly carries `method.tie_break_contract.tie_break_keys` and `explanation_schema_version`.
- `load_ranking_policy_v0_2()` now normalizes tie-break contract defaults deterministically and strips any unexpected `weights` key from method payload.
- `build_ranking_surface()` tie-break explanations now include `schema_version` while preserving existing deterministic `keys` and `key_values`.

Guardrails:
- No DB migrations.
- No DI semantic changes.
- No ranking algorithm changes beyond deterministic contract metadata hardening.

Gates:
- PASS

## 2026-03-03 — v1.3.0b14
Intent:
- Fix codex/repo divergence after b13 by shipping an atomic overlay that includes the previously omitted report engine + aligned tests.

Root cause:
- Prior b13 overlay did not include `psi/services/report_engine.py` and several related test files, leaving repo runtime/tests on stale molecule report contract behavior.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `psi/services/reports_v3.py`
- `tests/test_di_run_verify_and_report_pins.py`
- `tests/test_scientific_summary_report.py`
- `tests/test_v3_attribution_isolation.py`
- `tests/test_v3_board_report_determinism.py`
- `tests/test_v3_molecule_report_schema.py`
- `tests/test_v3_ranking_tiebreak.py`
- `tests/test_v3_report_contracts.py`
- `tests/test_v3_report_engine_contracts.py`
- `tests/test_v3_narrative_measurement_wiring.py`
- `tests/test_molecule_report_evidence_only.py`
- `tests/test_board_molecule_sections_rendering.py`
- `tests/test_ui_label_humanization.py`
- `psi/tools/di_contract_smoke.py`
- `psi/web/templates/reports/board_molecule_v3.html`

Behavior:
- Molecule reports remain evidence-only (no DI sections reintroduced).
- Molecule payload contract includes deterministic `reproducibility_appendix` scaffolding required by report engine/smoke checks.
- Report display and tests are aligned to evidence-only molecule semantics and payload-driven rendering.
- Overlay packaged atomically to avoid code/test skew between codex and runtime repo.

Guardrails:
- No DB migrations.
- No DI semantic, snapshot contract, or fingerprinting changes.
- No view-time report recompute introduced.

Gates:
- PASS

## 2026-03-03 — v1.3.0b13
Intent:
- Align molecule report contracts/tests with evidence-only payload semantics while preserving required `reproducibility_appendix` contract keys for engine/smoke compatibility.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`
- `psi/web/templates/reports/board_molecule_v3.html`
- `tests/test_board_molecule_sections_rendering.py`
- `tests/test_molecule_report_evidence_only.py`
- `tests/test_ui_label_humanization.py`
- `tests/test_v3_narrative_measurement_wiring.py`
- `tests/test_v3_report_contracts.py`
- `tests/test_v3_report_engine_contracts.py`

Behavior:
- Molecule report section contract now consistently expects:
  - `identity_context`
  - `fact_sheet`
  - `artifacts`
  - `reproducibility_appendix`
- Molecule `reproducibility_appendix` is evidence-only and deterministic; tests now validate `measurement_keys` from fact-sheet measurement coverage.
- Board molecule template now binds summary fields from `report_summary` with backward-compatible fallback.
- Smoke contract check now enforces `reproducibility_appendix` base keys for all report skeletons, including molecule reports.
- Evidence-only tests updated to assert no DI sections while still requiring deterministic reproducibility appendix presence.

Guardrails:
- No DB schema changes.
- No DI semantic, snapshot contract, hashing/fingerprint, or replay behavior changes.

Gates:
- PASS

## 2026-03-03 — v1.3.0b12
Intent:
- Add payload-persisted molecule report artifacts surface and render it payload-only in board view.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `psi/services/reports_v3.py`
- `psi/services/report_artifacts.py`
- `psi/web/templates/reports/board_molecule_v3.html`
- `tests/test_molecule_report_artifacts.py`
- `tests/test_molecule_report_evidence_only.py`
- `tests/test_board_molecule_sections_rendering.py`
- `tests/test_v3_report_contracts.py`

Behavior:
- Added `sections.artifacts` to molecule report payload at write-time:
  - schema: `{"schema_version":"v1","as_of":...,"items":[...]}`
  - each item includes deterministic type, batch, record, timestamp, label, and internal links.
- Added deterministic artifact assembler:
  - `assemble_molecule_report_artifacts(db, molecule_id, as_of)`
  - type ordering: `SEC`, `SDS_PAGE`, `ENDOTOXIN`, `OTHER`
  - stable item ordering with explicit tie-breaks.
- Molecule board now renders an “Artifacts” section from payload only (no view-time DB recompute).

Tests:
- Added:
  - `test_molecule_report_persists_artifacts_section`
  - `test_artifacts_ordering_deterministic`
  - `test_artifacts_render_no_db_query_at_view_time`
  - `test_artifacts_links_are_internal_and_stable`

Guardrails:
- No DI dependence for artifact rendering.
- No schema migration, replay, hash/fingerprint, or policy semantic changes.

Gates:
- PASS

## 2026-03-03 — v1.3.0b11
Intent:
- Convert molecule reports to evidence-only payload/UI and fix Experimental Results header alignment.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `psi/services/reports_v3.py`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/reports/board_molecule_v3.html`
- `psi/web/static/style.css`
- `tests/test_board_molecule_sections_rendering.py`
- `tests/test_molecule_report_evidence_only.py`
- `tests/test_v3_report_contracts.py`
- `tests/test_v3_report_engine_contracts.py`
- `tests/test_v3_narrative_measurement_wiring.py`
- `tests/test_v3_molecule_report_schema.py`
- `tests/test_v3_board_report_determinism.py`
- `tests/test_di_run_verify_and_report_pins.py`

Behavior:
- Molecule report generation now persists evidence-only sections:
  - `identity_context`
  - `fact_sheet`
- Molecule report payload no longer persists DI-derived sections (readiness/gates/comparability/risk/reproducibility appendices).
- Molecule board template now renders evidence-only sections and uses “Report Summary” wording.
- Removed molecule snapshot coverage display in report detail executive header.
- Experimental Results matrix now has a stable left-alignment hook (`.fact-sheet-matrix`) for header/body alignment.
- Added evidence-only regression tests:
  - `test_molecule_report_evidence_only_has_no_di_sections`
  - `test_molecule_report_renders_without_snapshots`
  - `test_molecule_report_board_template_no_di_strings`
  - `test_experimental_results_header_alignment_hook_present`

Guardrails:
- Payload-rendering remains view-time DB independent for report content.
- No DI route/helper removal, schema migration, replay, hash/fingerprint, or policy semantic changes.

Gates:
- PASS

## 2026-03-03 — v1.3.0b10
Intent:
- Harden run-governance coherence checks and pin-warning coverage without changing replay defaults.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/run_manifest.py`
- `tests/test_di_run_verify_and_report_pins.py`

Behavior:
- Added `verify_di_run(di_run_id)` to validate run-subject coherence deterministically:
  - contiguous `subject_index` from 0
  - each subject has a linked snapshot
  - snapshot scope and decision key match each subject/run
- Added tests for:
  - verify happy path
  - detection of missing snapshot link
  - `missing_policy_pins_or_hashes` warning emitted only when pins/hashes are actually absent

Guardrails:
- Replay regression defaults unchanged.
- No DI semantic, snapshot contract, hash/fingerprint, or schema migration changes.

Gates:
- PASS

## 2026-03-03 — v1.3.0b9
Intent:
- Persist best-batch/per-batch gate summaries into molecule report payload at write-time and render gate sections from payload only.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `psi/services/reports_v3.py`
- `tests/test_v3_board_report_determinism.py`

Behavior:
- Added deterministic write-time gate extraction for molecule reports:
  - best-batch gate matrix
  - per-batch gate snapshot summary
  - snapshot selection trace
- Persisted gate data under `sections.fact_sheet.gates_v1` in report payload.
- Updated molecule board display shaping to read gate rows from persisted payload (`gates_v1`) instead of placeholder empties.
- Extended no-view-query determinism tests to assert gate rendering remains payload-driven.

Guardrails:
- Payload additive-only (`fact_sheet.gates_v1`).
- No DI semantic, snapshot contract, hash/fingerprint, or replay behavior changes.

Gates:
- PASS

## 2026-03-03 — v1.3.0b8
Intent:
- Add deterministic multi-subject DI orchestration that persists run manifests and links per-subject snapshots.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/runner.py`
- `tests/test_di_multi_subject_runner.py`

Behavior:
- Added `run_di_multi_subject(...)` to orchestrate one run across ordered subjects:
  - subject index `0`: molecule scope
  - subject indices `1..N`: batch scopes ordered by `created_at DESC, id DESC`
- Added deterministic run-id construction and manifest creation via `di_runs`/`di_run_subjects`.
- Linked generated snapshot ids back onto `di_run_subjects.decision_snapshot_id` in deterministic subject order.
- Added tests for deterministic subject ordering and snapshot-link persistence.

Guardrails:
- No change to existing `run_di(...)` single-subject semantics.
- No snapshot contract, policy semantics, hash/fingerprint, or replay behavior changes.

Gates:
- PASS

## 2026-03-03 — v1.3.0b7
Intent:
- Introduce additive DI run coverage tables (`di_runs`, `di_run_subjects`) and deterministic run-manifest helpers.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/services/di/run_manifest.py`
- `tests/test_di_run_manifest_tables.py`

Behavior:
- Added `DIRun` and `DIRunSubject` SQLAlchemy models with deterministic indexing and uniqueness constraints.
- Added `create_di_run_manifest`, `list_run_subjects`, and `lookup_run_by_run_id` helpers for deterministic run manifest persistence and lookup.
- Added tests covering minimal roundtrip insert, stable subject ordering, and unique `(di_run_id, subject_index)` enforcement.

Guardrails:
- Additive schema only; no destructive changes.
- No DI semantic, snapshot contract, policy, hash/fingerprint, or replay behavior changes.

Gates:
- PASS

## 2026-03-03 — v1.3.0b6
Intent:
- Remove Technical View tab buttons from board-facing UI while keeping technical sections/routes available.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/reports/board_upgrade_delta_v3.html`
- `psi/web/templates/reports/board_template_ladder_v3.html`
- `psi/web/templates/lineage/program_detail.html`
- `psi/web/templates/lineage/portfolio_detail.html`
- `tests/test_report_detail_board_template_selection.py`

Behavior:
- Removed “Technical View” tab buttons from report detail, upgrade delta, template ladder, and lineage board pages.
- Kept technical panels intact and accessible in rendered views; only tab controls were removed.
- Simplified tab scripts to avoid runtime errors after button removal.
- Added a template regression test asserting “Technical View” label is absent from the report detail tab controls.

Guardrails:
- UI-only/template changes.
- No DI semantic, snapshot-contract, hash/fingerprint, policy, or replay behavior changes.

Gates:
- PASS
## 2026-03-02 — v1.3.0a48
Summary:
- Hard-deprecate V3 shortlisting policy usage by quarantining legacy shortlisting catalog as non-executable metadata and removing executable `ranking_weights` content.
- Ensure V3 report policy pins surface shortlisting as deprecated/non-executable (`allow_shortlisting=false`) for board-safe surfaces.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/shortlisting_policy_v0_1.json`
- `psi/services/reports_v3.py`
- `psi/tools/di_contract_smoke.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`21 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a49
Summary:
- Add deterministic governance tests that forbid weighted-heuristic tokens in specific DI runtime modules and the shortlisting legacy catalog.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_v3_no_weighted_heuristics.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`22 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a50
Summary:
- Define canonical V3 Molecule Report schema builder with fixed section ordering (`I..VIII`), deterministic JSON serialization, and governance fingerprinting that explicitly excludes report timestamp.
- Wire molecule report fields to real molecule/snapshot/readiness/evidence/policy data where available.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_board_reports.py`
- `tests/test_v3_molecule_report_schema.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`23 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a51
Summary:
- Add canonical V3 Comparison Report schema builder with fixed `I..VIII` section ordering, metric-row/table format, stable molecule column sorting by `molecule_id`, and comparability citation/status surfaces.
- Keep comparison contract non-scored and non-weighted.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_board_reports.py`
- `tests/test_v3_comparison_report_schema.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`24 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a52
Summary:
- Add board-readable Jinja templates for canonical V3 molecule/comparison reports and a deterministic renderer that consumes report JSON without mutating canonical payloads.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_board_reports.py`
- `psi/web/templates/reports/board_molecule_v3.html`
- `psi/web/templates/reports/board_comparison_v3.html`
- `tests/test_v3_board_report_rendering.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`25 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a53
Summary:
- Add determinism tests for canonical V3 molecule/comparison reports:
  - timestamp exclusion from fingerprint
  - stable section/column ordering
  - byte-stable canonical JSON basis comparisons
  - stable non-scientific float formatting in canonical serialization

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_board_reports.py`
- `tests/test_v3_board_report_determinism.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`26 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a54
Summary:
- Add deterministic rule-based executive summary bullet generator for strengths/risks/decision status/required actions.
- Wire molecule and comparison report section VIII to generated bullet surfaces.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_board_reports.py`
- `tests/test_v3_executive_summary_bullets.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`27 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a55
Summary:
- Add deterministic Upgrade Delta Report skeleton under policy upgrade artifacts:
  - `header`
  - `executive_summary_bullets`
  - `change_table`
  - `appendix`
- Add board-readable HTML rendering template for upgrade delta report.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `psi/web/templates/reports/board_upgrade_delta_v3.html`
- `psi/tools/di_contract_smoke.py`
- `tests/test_policy_upgrade_diff_artifact.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`28 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a56
Summary:
- Populate deterministic `ranking_delta` section in upgrade delta appendix:
  - enabled flag changes
  - tie-break contract changes
  - criteria registry ID diffs (added/removed/unchanged)
- Keep ranking deltas ID-only with no weight/scoring fields.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `tests/test_policy_upgrade_diff_artifact.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`28 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a57
Summary:
- Populate deterministic `comparability_delta` in upgrade delta appendix:
  - rule registry ID diffs
  - allowed status diffs
  - gating behavior ID change status
- Keep citations/deltas as IDs/keys (no prose scoring surfaces).

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `tests/test_policy_upgrade_diff_artifact.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`28 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a58
Summary:
- Populate deterministic `template_catalog_delta` appendix section for upgrade deltas:
  - template key diffs
  - current version changes
  - immutable version set changes
  - prerequisite catalog ID changes

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `tests/test_policy_upgrade_diff_artifact.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`28 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a59
Summary:
- Enforce explicit operator acknowledgment for semantic upgrade deltas:
  - add deterministic `action_required` warning surfaces with board-visible `Action Required` label
  - add semantic-action guard (`policy_upgrade_action_required`) before report generation when unacknowledged semantic upgrades affect current pins

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `psi/services/reports_v3.py`
- `tests/test_policy_upgrade_diff_artifact.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`29 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a60
Summary:
- Formalize deterministic Template Ladder board packet/report:
  - stage list table
  - current stage
  - missing prerequisites
  - derived next actions
- Add board-readable ladder report template renderer and determinism tests.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/template_ladder_report.py`
- `psi/web/templates/reports/board_template_ladder_v3.html`
- `tests/test_template_ladder_report.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`30 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a61
Summary:
- Add fixed-schema lineage board packet surfaces for program and portfolio lineage with deterministic ordering.
- Add lineage board packet determinism tests analogous to report determinism coverage.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/lineage.py`
- `tests/test_lineage_board_packet.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`31 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a47
Summary:
- Remove numeric weight tables from executable shortlisting ranking logic, replacing weighted score math with deterministic lexicographic tie-break ordering only.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/shortlisting.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS
## 2026-03-02 — v1.3.0a46
Intent:
- Document V3 hardening contracts and changelog alignment for a32-a46.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/V3_HARDENING_CONTRACT_NOTES_a32_a46.md`

Determinism notes:
- Added operator-facing contract doc covering:
  - canonical serialization rules
  - ranking tie-break contract
  - comparability citation requirements
  - policy-upgrade diff artifact format
- Document is aligned to implemented code paths and tests from a32-a46.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a45
Intent:
- Surface deterministic measurement-key and evidence-snapshot citations in report detail UI for comparability/rollup context.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/reports_v3.py`
- `psi/web/templates/reports/detail.html`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Added deterministic citation extraction in report detail:
  - `measurement_key_citations` (sorted)
  - `evidence_snapshot_refs` (sorted)
- Extraction uses only stored report payload structures and snapshot coverage.
- UI now shows policy, rule, measurement, and evidence citation summaries in fixed positions.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a44
Intent:
- Improve scientist-facing report clarity by surfacing policy pin versions/hashes and involved rule IDs prominently in report detail UI.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/reports_v3.py`
- `psi/web/templates/reports/detail.html`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Added deterministic `policy_pin_summary` and sorted `rule_ids` extraction in report detail service.
- UI render is strictly data-driven from stored report payload and pins; no new inference logic.
- Smoke template check now locks the presence of policy/rule summary surfaces.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a43
Intent:
- Add deterministic optional `report_fingerprint` computed from canonical report payload body.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `tests/test_v3_report_contracts.py`

Determinism notes:
- Added canonical SHA-256 report fingerprint generation from canonical serialized payload basis (excluding fingerprint field itself).
- Fingerprint is persisted in payload metadata only; no DI snapshot hash semantics changed.
- Added contract checks for fingerprint stability across repeated generation.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a42
Intent:
- Add explicit attribution-isolation contracts ensuring actor/attribution metadata never influences deterministic report/ranking/rollup outputs.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_v3_attribution_isolation.py`

Determinism notes:
- Added pytest contracts showing that adding attribution events does not alter:
  - program rollup outputs
  - generated program report payloads
  - ranking surfaces
- Confirms attribution remains governance metadata only, not part of deterministic computed surfaces.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a41
Intent:
- Expand replay regression harness coverage to include deterministic program rollup surface checks.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_replay_regression.py`

Determinism notes:
- Replay harness now tracks program IDs in the tested snapshot slice and verifies `build_program_rollup()` is deterministic (double-run equality at fixed `as_of`).
- Rollup nondeterminism is governance-fatal and now contributes to replay failure output.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a40
Intent:
- Add upgrade-session verification routine requiring deterministic snapshot-set and input-link presence.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_policy_upgrade_diff_artifact.py`

Determinism notes:
- Policy diff artifact now carries:
  - `snapshot_ids`
  - `deterministic_inputs`
- Added `verify_policy_upgrade_session()` with deterministic failure modes:
  - `policy_upgrade_session_missing_snapshot_set`
  - `policy_upgrade_session_missing_deterministic_inputs`
- Smoke and unit tests now validate verification success/failure paths deterministically.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a39
Intent:
- Add deterministic policy diff artifact generation for upgrade sessions with canonical hash metadata.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_policy_upgrade_diff_artifact.py`

Determinism notes:
- Added `build_policy_diff_artifact()` with stable structured payload:
  - old/new policy pins
  - old/new package and semantics hashes
  - sorted changed keys
  - deterministic nested delta surface
- `PolicyUpgradeSession.delta_payload_json` now stores this canonical diff artifact.
- Added deterministic artifact tests and updated smoke checks for new shape.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a38
Intent:
- Formalize deterministic comparability category resolution order, including explicit partial-data fallback behavior.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/comparability.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Added `resolve_comparability_category()` with explicit policy-order precedence and stable candidate normalization.
- Added conservative deterministic fallback for partial/missing data (`not_comparable` when configured).
- `get_effective_comparability()` now returns deterministic `category_resolution` metadata.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a37
Intent:
- Enforce governance-grade comparability citations (measurement keys + snapshot IDs) and fail deterministically when absent.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/comparability.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Comparability creation now requires non-empty citations:
  - `cited_measurement_keys`
  - `cited_snapshot_ids`
- Added deterministic validation errors:
  - `comparability_missing_measurement_citations`
  - `comparability_missing_snapshot_citations`
- Updated smoke fixtures and added explicit missing-citation failure assertions.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a36
Intent:
- Normalize and strengthen deterministic ranking explanation trace surfaces.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_ranking.py`
- `tests/test_v3_ranking_tiebreak.py`

Determinism notes:
- `reason_trail` entries now include explicit `policy_rule_id`, `criterion_id`, `outcome`, `applied`.
- `tie_break_explanation` now includes deterministic `key_values` for configured tie-break keys.
- Added top-level `explanation_trace_version` for stable trace contract evolution.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a35
Intent:
- Formalize ranking tie-break contract in policy v0.2 and enforce deterministic tie resolution path in ranking service.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/ranking_policy_v0_2.json`
- `psi/services/v3_ranking.py`
- `tests/test_v3_ranking_tiebreak.py`

Determinism notes:
- Ranking tie-break now derives directly from ordered `method.tie_break_keys` in policy.
- Added explicit `tie_break_contract` policy stanza (`deterministic_only=true`, `weights_allowed=false`).
- Added tie-scenario tests that lock deterministic ranking order and explanation keys.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a34
Intent:
- Add V3 report contract tests for all four report types plus canonical serialization stability checks.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_v3_report_contracts.py`

Determinism notes:
- Added contract checks for required section keys across:
  - molecule report
  - program report
  - molecule comparative report
  - program comparative report
- Added repeat-generation canonical serialization lock for identical fixture inputs.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a33
Intent:
- Formalize deterministic ordering contracts for comparative report entity rows.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `tests/test_v3_report_engine_contracts.py`

Determinism notes:
- Added explicit comparative ordering helpers:
  - molecule rows: `(primary_id, molecule_id, title)`
  - program rows: `(program_id)`
- Comparative report generators now call these helpers directly.
- Added unit contracts asserting stable ordering regardless of input order.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a32
Intent:
- Introduce canonical report serialization utilities for deterministic JSON string/bytes emission.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `tests/test_v3_report_engine_contracts.py`
- `pytest.ini`

Determinism notes:
- Added canonical report serialization helpers with stable dict-key ordering, explicit UTF-8 byte encoding, tuple/set normalization, and stable float formatting.
- Persisted `ReportRun` JSON fields now use canonical report serialization.
- Added byte-for-byte deterministic serialization tests.
- Added deterministic pytest discovery scoping to `tests/` to prevent artifact tree collection drift.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a31
Intent:
- Add deterministic governance red-flag surfaces to report reproducibility appendices.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Red flags are emitted as a stable, sorted list (`flag_code` ordered) inside existing `reproducibility_appendix` sections.
- Flags cover:
  - missing policy pins/hashes
  - comparability ambiguity (duplicate pair/rule candidates)
  - unacknowledged policy upgrade affecting current pins
  - ranking disabled/policy incomplete on comparative reports
- No report top-level schema keys changed.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a30
Intent:
- Add deterministic, catalog-driven Next-Best-Experiments suggestions into existing V3 report sections.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/v3_experiment_suggestions_v0_1.json`
- `psi/services/report_engine.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Suggestions are sourced from versioned catalog rules with explicit `priority_order` and deterministic sort `(priority, suggestion_key, label)`.
- Suggestions include categorical priority (`high|medium|low`) and explicit reason trails only; no numeric scoring.
- Program/molecule report schemas are unchanged; suggestions are injected within existing section keys.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a29
Intent:
- Add V3 catalog immutability contract tests and additive version-surface checks.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_v3_catalog_immutability.py`

Determinism notes:
- Locked immutable byte-level hashes for foundational V3 catalogs:
  - `template_catalog_v0_1.json`
  - `ranking_policy_v0_1.json`
  - `comparability_policy_v0_1.json`
- Added deterministic additive-version checks for ranking/comparability/template catalog file surfaces.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a28
Intent:
- Tighten lineage query scope for report and membership attribution retrieval while preserving deterministic ordering.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/lineage.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Program lineage now scopes report-run retrieval to `program_report` rows with exact serialized subject IDs.
- Program/portfolio membership attribution queries now scope to the relevant membership IDs only.
- Added smoke coverage to assert unrelated membership attribution events are excluded deterministically.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a27
Intent:
- Expand program rollup citation linkage with deterministic template/policy/snapshot coverage references.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/program_rollups.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Rollups now emit sorted citation arrays for `template_keys` and `decision_keys` in addition to snapshot/policy citations.
- Added stable `snapshot_coverage_summary` with deterministic counts.
- Contract smoke locks the citation key surface order.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a26
Intent:
- Introduce policy-driven categorical program posture derivation for rollups (no scoring) with deterministic citations.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/program_rollups.py`
- `psi/core/di/catalogs/program_posture_policy_v0_1.json`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Program posture is derived by fixed categorical rules from deterministic stage counts and molecule totals.
- Added structured rollup citations with stable key ordering (`snapshot_ids`, policy refs, molecule ids).
- Program posture policy catalog is versioned JSON and validated by contract smoke.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a25
Intent:
- Add deterministic warning surfaces for unacknowledged policy upgrades in report and lineage views.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `psi/services/reports_v3.py`
- `psi/services/lineage.py`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/lineage/program_detail.html`
- `psi/web/templates/lineage/portfolio_detail.html`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Added `get_unacknowledged_upgrade_warnings()` with explicit ordering `(created_at DESC, id DESC)` and stable warning payload keys.
- Report detail and lineage contexts now expose deterministic governance warnings without changing report/DI semantics.
- Contract smoke validates warning presence for unacknowledged sessions and absence after explicit acknowledgement.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a24
Intent:
- Replace policy-upgrade placeholder deltas with deterministic changed-key classification and categorical impact flags.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Policy upgrade delta payload now emits stable top-level keys:
  - `changed_policy_keys`
  - `classification`
  - `downstream_impact_flags`
- Classification and impact flags are computed from explicit sorted changed-key sets; no probabilistic or weighted logic.
- Contract smoke locks stable key ordering and expected categorical flags.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a23
Intent:
- Stabilize attribution metadata JSON serialization and expand attribution coverage for key V3 governance actions.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/attribution.py`
- `psi/services/comparability.py`
- `psi/services/policy_upgrade.py`
- `psi/services/report_engine.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Attribution metadata now normalizes recursively with sorted dict keys and ISO-8601 datetime/date conversion before serialization.
- New attribution events are emitted for `report_run.create`, `policy_upgrade.session.create`, `policy_upgrade.session.acknowledge`, and `comparability.assessment.create`.
- Event payload structures are stable-key dictionaries without time-based nondeterministic fields beyond explicit timestamps.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a17
Intent:
- Make comparability policy JSON authoritative for statuses/rules and scope applicability; remove hardcoded status semantics from Python.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/core/db.py`
- `psi/services/comparability.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Comparability validation now loads a cached deterministic policy object from `comparability_policy_v0_1.json`.
- `rule_id` and `status` are validated from policy data, and scope applicability uses deterministic canonical pair type ordering.
- Policy load failures and validation failures return explicit deterministic error codes.

Schema changes:
- Additive field: `comparability_assessments.policy_semantics_hash`.

Gates:
- PASS
## 2026-03-02 — v1.3.0a18
Intent:
- Add deterministic “effective comparability” resolution and governance warning surfaces over historical assessments without deleting history.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/comparability.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Effective comparability selection uses explicit `(as_of DESC, id DESC)` ordering on canonical pair and optional `rule_id`.
- History summary is deterministic (status-count map sorted by status key).
- Governance warnings are deterministic objects and ordered by stable warning key derivation.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a19
Intent:
- Introduce `ranking_policy_v0_2` with explicit lexicographic ladder semantics (policy-defined, non-weighted) while keeping ranking disabled by default.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/ranking_policy_v0_2.json`
- `psi/services/v3_ranking.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Ranking method now reads policy-defined `criteria_order`, `outcome_precedence`, and tie-break keys.
- Enabled ranking path is lexicographic only; no hit-count heuristic and no numeric weights.
- If policy is enabled but incomplete, surface returns deterministic `policy_incomplete` with empty ranking entities.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a20
Intent:
- Harden ranking surface explainability and contract visibility (policy hashes, criterion-ordered reason trails, stable tie-break explanation), fully policy-driven.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_ranking.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Ranking output now includes deterministic policy hashes and tie-break explanation fields.
- Per-entity reason trails are emitted in policy criteria order.
- Contract checks assert no weight fields in ranking output and policy-order alignment.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a21
Intent:
- Remove hardcoded report policy pins and derive deterministic pin bundles from V3 catalogs.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/reports_v3.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_v3_report_engine_contracts.py`

Determinism notes:
- Added deterministic `get_v3_report_policy_pins(report_type)` to derive template/comparability/ranking versions and hashes from catalog files.
- Pin objects are stable-key bundles and are now used by report generation form path.
- Contract and pytest tests lock pin bundle stability for report types.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a22
Intent:
- Deepen report reproducibility appendix content under existing schema keys with deterministic governance metadata.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_v3_report_engine_contracts.py`

Determinism notes:
- Reproducibility appendix now always includes stable keys:
  - `policy_pins`
  - `catalog_versions`
  - `cited_snapshot_ids`
  - `inputs_summary`
- Keys are present across all 4 report types without changing top-level report schema keys.

Schema changes:
- None.

Gates:
- PASS

## 2026-03-03 — v1.3.0a127
Intent:
- Prevent canonical DB pollution from DI smoke tooling by defaulting contract smoke to an isolated scratch copy.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_di_contract_smoke_scratch_mode.py`

Behavior:
- `python -m psi.tools.di_contract_smoke` now defaults to scratch mode.
- New CLI options:
  - `--use-live-db` (run directly on source DB)
  - `--db-path` (explicit source DB)
  - `--scratch-dir` (override scratch location)
  - `--keep-scratch` (preserve scratch DB file)
- Tool logs now emit deterministic runtime routing details: `live_db`, `scratch_db`, `use_live_db`.
- Scratch file reuses stable name `di_contract_smoke.sqlite` and is deleted unless `--keep-scratch`.

Notes:
- No DB schema changes.
- No DI semantic, replay, snapshot, or hashing behavior changes.
- Optional read-only clutter visibility tool available at `python -m psi.tools.smoke_clutter_report`.

Gates:
- PASS

## 2026-03-03 — v1.3.0a128
Intent:
- Fix di_contract_smoke determinism harness drift by guaranteeing run1/run2 start from identical seeded DB state.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_di_contract_smoke_scratch_mode.py`

Behavior:
- Added deterministic two-run scratch harness (`base -> run1/run2`) with stable file names:
  - `di_contract_smoke_base.sqlite`
  - `di_contract_smoke_run1.sqlite`
  - `di_contract_smoke_run2.sqlite`
- Batch-scope smoke determinism now seeds the base copy once, then fans out run1/run2 from that seeded base.
- This prevents run-local timestamp drift (e.g., `created_at` in evidence refs) from causing false non-determinism failures.
- Tool now logs per-run DB paths and base-copy usage during determinism checks.

Guardrails:
- No DB schema changes.
- No DI semantic, snapshot-contract, hash/fingerprint, or replay behavior changes.

Gates:
- PASS

## 2026-03-03 — v1.3.0a129
Intent:
- Fix `di_contract_smoke` determinism drift caused by volatile tool-seeded timestamps (`created_at`/derived recency) across run1 vs run2.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_di_contract_smoke_scratch_mode.py`

Behavior:
- Added fixed seed timestamp constant for smoke-tool generated fixture rows.
- Added harness helper to pin `data_records` and `data_measurements` timestamps for seeded records.
- Made smoke seed helpers idempotent for run-pair comparisons so run1/run2 do not add fresh timestamped fixture rows.
- Added failure diagnostics classifier for first differences, including timestamp-drift classification and path/value snippets.
- Preserved a128 base/run copy strategy and current CLI contract.

Guardrails:
- Tools-only harness fix.
- No DB schema, DI semantics, snapshot contract, hash/fingerprint, or replay behavior changes.

Gates:
- PASS

## 2026-03-03 — v1.3.0b28
Intent:
- Add deterministic, stage-sequenced metric ordering contract for molecule fact sheets.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/fact_sheet.py`

Behavior:
- Introduced canonical metric stage order list and index map in `fact_sheet.py`.
- Replaced simple `required + alpha(observed)` ordering with deterministic ordering:
  - preserve `required_metric_keys` priority only when snapshot gate requirements are present
  - then canonical stage-sequenced metrics
  - then remaining observed metrics alphabetically.
- Preserved existing payload shape and deterministic batch/measurement selection rules.

Gates:
- PASS

## 2026-03-03 — v1.3.0b29
Intent:
- Add deterministic fact-sheet unit fallback chain for numeric cell display.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/fact_sheet.py`
- `tests/test_v3_molecule_report_schema.py`

Behavior:
- `_display_value` now uses fallback order for numeric cells:
  1. measurement unit
  2. metric catalog unit
  3. deterministic suffix-map fallback
  4. blank
- Added deterministic suffix fallback map in `fact_sheet.py`.
- Added unit fallback test for unknown metric suffix `_pct`.

Gates:
- PASS

## 2026-03-03 — v1.3.0b30
Intent:
- Harden scientist-facing metric metadata via curated deterministic catalog overrides.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/metric_catalog.py`
- `tests/test_metric_catalog.py`

Behavior:
- Added explicit curated fallback entries (labels/domains/units/sort_order) for selected expression, assay, endotoxin, PK/PD, and in vivo metrics.
- Existing catalog-backed entries remain unchanged.
- Unknown keys still use deterministic humanized fallback.

Gates:
- PASS

## 2026-03-03 — v1.3.0b31
Intent:
- Make progress milestone rendering use an explicit deterministic stage order (including late endotoxin placement).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecule_header.py`
- `tests/test_molecule_header_model.py`
- `tests/fixtures/molecule_header_model_lock_v1.json`

Behavior:
- Replaced early milestone key iteration from plain sorted keys to explicit ordered sequence with deterministic sorted fallback for unknown keys.
- Kept milestone semantics unchanged.
- Added progress milestone ordering test and updated lock fixture accordingly.

Gates:
- PASS

## 2026-03-03 — v1.3.0b32
Intent:
- Align progress policy catalog milestone key order with explicit stage sequence (ordering-only).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/progress_policy_v0_2.json`

Behavior:
- Reordered `early_milestones` keys to match stage display sequence:
  `expression_present`, `basic_qc_present`, `purification_present`, `functional_assay_present`, `endotoxin_present`, `pk_screen_present`.
- No metric requirements or policy semantics changed.

Gates:
- PASS

## 2026-03-03 — v1.3.0b33
Intent:
- Hide Technical Audit section from scientist-facing report detail UI (template-only change).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`

Behavior:
- Removed technical audit panel include from report detail page.
- Left backend report detail context generation unchanged to preserve governance/debug surfaces.

Gates:
- PASS

## 2026-03-03 — v1.3.0b34
Intent:
- Add/align deterministic tests for metric ordering, unit fallback, milestone order, and technical-audit hide behavior.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/_technical_audit.html`
- `tests/test_molecule_report_evidence_only.py`

Behavior:
- Updated hidden technical panel heading label to non-scientist-facing wording.
- Added report-detail rendering test asserting `"Technical Audit"` is not shown in scientist view while structured payload block remains rendered for contracts.
- b28-b33 tests already added for fact-sheet ordering, unit fallback, and milestone sequence remain in place.

Gates:
- PASS

## 2026-03-03 — v1.3.0b35
Intent:
- Keep governance/technical payload panel hidden by default on scientist-facing report detail view.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`
- `tests/test_molecule_report_evidence_only.py`

Behavior:
- Removed JavaScript that forced report technical panel visibility in normal mode.
- Board panel remains visible by default.
- Added regression assertions that report detail keeps technical panel hidden (`aria-hidden="true"`) and no longer contains script-based unhide behavior.

Gates:
- PASS

## 2026-03-03 — v1.3.0b36
Intent:
- Add explicit governance-mode toggle on report detail while keeping scientist mode default.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`
- `tests/test_molecule_report_evidence_only.py`

Behavior:
- Added `Governance` toggle button in non-PDF report detail header.
- Added localStorage-backed mode switch (`psi.view.report_detail_mode`) to show/hide technical panel intentionally.
- Scientist mode remains default and technical panel stays hidden unless toggled.
- Added PDF-mode test assertion that governance toggle is not rendered in export mode.

Gates:
- PASS

## 2026-03-03 — v1.3.0b37
Intent:
- Make technical audit markup explicitly governance-only and keep it out of PDF render path.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/reports/_technical_audit.html`
- `tests/test_molecule_report_evidence_only.py`

Behavior:
- Added governance root marker (`data-report-panel=\"governance\"`) and muted banner in technical audit partial.
- Report detail now omits technical panel include entirely in PDF mode.
- Added assertions that governance panel markup appears in non-PDF render and is absent in PDF render.

Gates:
- PASS

## 2026-03-03 — v1.3.0b38
Intent:
- Align comparative ranking policy execution with pinned policy version to remove governance drift.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `tests/test_v3_report_contracts.py`

Behavior:
- Comparative report generation now uses `load_ranking_policy_latest()` instead of `v0.1` hard-loading.
- Reproducibility appendix `catalog_versions.ranking_policy` now reflects the effective ranking policy version used for ranking surface generation.
- Added regression test asserting comparative ranking surface policy version and appendix version match pinned ranking policy version.

Gates:
- PASS

## 2026-03-03 — v1.3.0b39
Intent:
- Strengthen comparative ranking determinism transparency while keeping scientist surface unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/_technical_audit.html`
- `tests/test_v3_report_contracts.py`

Behavior:
- Added governance-only technical audit block showing comparative ranking tie-break contract (`tie_break_keys`, policy version, deterministic note).
- Added deterministic comparative ranking test verifying identical entity ordering across reversed subject input and tie-break explanation keys.

Gates:
- PASS

## 2026-03-03 — v1.3.0b40
Intent:
- Align CI workflow gates with required PSI V3 verification commands.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `.github/workflows/ci.yml`

Behavior:
- Added `python -m psi.tools.db_schema_sanity` step in CI after DI contract smoke.
- Added `python -m psi.tools.di_replay_regression --limit 5` step in CI after schema sanity.
- Preserved existing compile/pytest/di_contract_smoke sequence.

Gates:
- PASS

## 2026-03-03 — v1.3.0b41
Intent:
- Add read-time canonical metric key normalization scaffold for deterministic alias handling.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/metric_catalog.py`
- `psi/services/fact_sheet.py`
- `tests/test_metric_catalog.py`
- `tests/test_v3_molecule_report_schema.py`

Behavior:
- Added `normalize_metric_key()` and deterministic alias map in metric catalog layer.
- Fact sheet assembly now normalizes measurement and required metric keys before grouping/ordering, collapsing aliases into canonical rows.
- Added unit tests for alias normalization and report-schema test ensuring alias/canonical duplicates render as a single canonical metric row.

Gates:
- PASS

## 2026-03-03 — v1.3.0b42
Intent:
- Harden metric group taxonomy and deterministic group ordering to reduce `Other` dominance in report surfaces.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/metric_catalog.py`
- `psi/services/fact_sheet.py`
- `tests/test_metric_catalog.py`

Behavior:
- Expanded curated metric metadata with stronger domain/group assignments (Expression, Purity/SEC, Binding, Functional, Endotoxin, PK, In Vivo).
- Added deterministic group-order contract helper (`metric_group_sort_key`) and applied it to fact-sheet batch coverage summaries.
- Added tests for group mapping and stable group sort order.

Gates:
- PASS

## 2026-03-03 — v1.3.0b43
Intent:
- Harden unit metadata and display behavior for canonical metric rendering with conservative handling of variable-unit metrics.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/data/metric_catalog_v1.json`
- `psi/services/metric_catalog.py`
- `tests/test_metric_catalog.py`
- `tests/test_v3_molecule_report_schema.py`

Behavior:
- Updated metric catalog entry for `ec50` to avoid implied canonical unit when measurement unit is missing.
- Kept canonical units for deterministic metrics (e.g., `kd_nM` remains `nM`).
- Added tests ensuring variable-unit metrics remain unit-conservative and fact-sheet display does not invent a unit for `ec50` when source measurement has no unit.

Gates:
- PASS

## 2026-03-03 — v1.3.0b44
Intent:
- Preserve raw measurement-key citation traceability while deduplicating scientist-facing metric display to canonical keys.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/reports_v3.py`
- `psi/web/templates/reports/_technical_audit.html`
- `tests/test_v3_reports_ui_identity.py`

Behavior:
- Report detail context now includes:
  - `measurement_key_citations` (raw keys),
  - `measurement_key_citations_display` (canonical deduped keys),
  - `measurement_key_citation_map` (raw→canonical rows).
- Technical audit panel now renders canonical citation display and raw-to-canonical mapping for governance tracing.
- Added test verifying deterministic citation mapping for alias keys.

Gates:
- PASS

## 2026-03-03 — v1.3.0b45
Intent:
- Add governance guardrails against weighted heuristics in ranking/comparative Python paths and update V3 status documentation.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_no_weighted_heuristics.py`
- `docs/DI_V3_STATUS_v1.3.0b23.md`

Behavior:
- Added deterministic static audit test that checks ranking/comparative functions for banned weighted-heuristic inline patterns.
- Added b45 addendum to V3 status doc describing the new guard scope and intent.

Gates:
- PASS

## 2026-03-03 — v1.3.0b46
Intent:
- Contain legacy YAML rules execution under an explicit compatibility module with governance-only messaging.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/legacy_yaml_compat.py`
- `psi/services/decisions.py`
- `psi/services/evidence.py`
- `psi/web/routers/data_records.py`
- `psi/web/templates/reports/_technical_audit.html`
- `tests/test_legacy_yaml_compat.py`

Behavior:
- Added `psi/services/legacy_yaml_compat.py` wrappers for legacy YAML rule load/run calls.
- Updated legacy YAML call sites to use compatibility wrappers (containment approach; no DI snapshot semantic changes).
- Added governance-panel note clarifying legacy YAML path non-interference with DI snapshot semantics.
- Added startup compatibility test and legacy wrapper round-trip test.

Gates:
- PASS

## 2026-03-07 — v1.3.0b47
Intent:
- Add a minimal additive program-level molecule role/state foundation for program-centric workflows.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/services/programs.py`
- `psi/web/routers/programs.py`
- `psi/web/templates/programs/detail.html`
- `tests/test_program_molecule_status.py`
- `tests/test_program_review_queue.py`

Behavior:
- Added `ProgramMoleculeStatus` table model (`program_id`, `molecule_id`, `role`, `rationale`, timestamps) with deterministic unique key.
- Added deterministic service helpers to list/upsert program molecule role state.
- Added role update route `POST /programs/{program_id}/molecules/{molecule_id}/role`.
- Program dashboard now displays and edits role/rationale in membership rows.

Gates:
- PASS

## 2026-03-07 — v1.3.0b48
Intent:
- Establish a scientist-first program dashboard scaffold on `/programs/{id}` with deterministic summary bars and counts.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/programs.py`
- `psi/web/templates/programs/detail.html`
- `tests/test_program_review_queue.py`

Behavior:
- Added deterministic `program_dashboard` summary block in program detail service.
- Added Program Header cards for molecule count, active contenders, posture, pending entries, and candidate role counts.
- Added display-only progress/confidence bars derived from existing rollup state counts.

Gates:
- PASS

## 2026-03-07 — v1.3.0b49
Intent:
- Add a deterministic Candidate Set surface (lead/backup/active/watchlist/deprioritized/archived) to the program dashboard.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/programs.py`
- `psi/web/templates/programs/detail.html`
- `tests/test_program_review_queue.py`

Behavior:
- Added `candidate_set` grouping in program detail service based on per-program role state and membership order.
- Added Candidate Set cards to `/programs/{id}` with role-grouped molecule lists and rationale display.

Gates:
- PASS

## 2026-03-07 — v1.3.0b50
Intent:
- Add a deterministic Molecule Status Board on the program dashboard.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/programs.py`
- `psi/web/templates/programs/detail.html`
- `tests/test_program_review_queue.py`

Behavior:
- Program detail now computes `program_molecule_status_board` rows from latest per-molecule snapshot outputs plus role state.
- Added Molecule Status Board UI with molecule, role, readiness, key blocker, and last evidence update.

Gates:
- PASS

## 2026-03-07 — v1.3.0b51
Intent:
- Add a deterministic program evidence summary by evidence category / metric group.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/programs.py`
- `psi/web/templates/programs/detail.html`
- `tests/test_program_review_queue.py`

Behavior:
- Program detail now computes `program_evidence_summary` from program data measurements using metric-group normalization.
- Added Program Evidence Summary table to `/programs/{id}` with stable group ordering and coverage counts.

Gates:
- PASS

## 2026-03-07 — v1.3.0b52
Intent:
- Add a deterministic Program Evidence Map matrix (molecules × evidence categories).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/programs.py`
- `psi/web/templates/programs/detail.html`
- `tests/test_program_review_queue.py`

Behavior:
- Added `program_evidence_matrix` to program detail context.
- Added Program Evidence Map table with stable group ordering and explicit present/missing markers.

Gates:
- PASS

## 2026-03-07 — v1.3.0b53
Intent:
- Refine program progress/confidence bars with explicit deterministic basis labeling.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/programs.py`
- `psi/web/templates/programs/detail.html`
- `tests/test_program_review_queue.py`

Behavior:
- Added program-level `progress_label` / `confidence_label` and explicit display-only basis strings.
- Program dashboard now explains how progress/confidence percentages are derived from existing deterministic state counts.

Gates:
- PASS

## 2026-03-07 — v1.3.0b54
Intent:
- Add program-aware suggested next experiments to the program dashboard.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/programs.py`
- `psi/web/templates/programs/detail.html`
- `tests/test_program_review_queue.py`

Behavior:
- Program detail now emits deterministic `program_suggested_experiments` prioritized for lead/backup/active candidates.
- Suggestions are derived from existing missing metric / failing gate / pending queue signals (display-only, non-semantic).

Gates:
- PASS

## 2026-03-07 — v1.3.0b55
Intent:
- Redesign program report board template into a scientist-facing program review briefing.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/board_program_v3.html`
- `tests/test_board_program_posture_rendering.py`

Behavior:
- Program board now renders structured sections: Executive Summary, Program Context, Candidate Set, Evidence Overview, Program Risks, Recommended Next Experiments, Decision Framing, and Evidence Appendix.
- Governance detail remains secondary via existing technical panel path.

Gates:
- PASS

## 2026-03-07 — v1.3.0b56
Intent:
- Improve program navigation/drill-down from program dashboard to molecule/evidence/report surfaces.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/programs/detail.html`
- `tests/test_program_review_queue.py`

Behavior:
- Added Program Drill-down quick links for molecules, data records, evidence, decisions, and one-click program report generation.
- Navigation remains deterministic and route-only (no semantic changes).

Gates:
- PASS

## 2026-03-07 — v1.3.0b77
Intent:
- Add a deterministic molecule lineage panel to molecule detail (parent + children) using builder provenance.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`
- `tests/test_molecule_lineage_surface.py`

Behavior:
- `get_molecule_detail()` now emits `lineage_parent` and `lineage_children` from `molecule_derivations` with deterministic ordering.
- Molecule detail page now renders a dedicated Lineage card with parent and child molecule links plus derivation type/summary.

Gates:
- PASS

## 2026-03-07 — v1.3.0b78
Intent:
- Improve builder preview/validation ergonomics with deterministic diff visibility while preserving strict preview-before-save behavior.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/builder.py`
- `psi/web/templates/builder/point_mutation.html`
- `psi/web/templates/builder/cdr_builder.html`
- `tests/test_builder_service.py`
- `tests/test_builder_scaffold.py`
- `tests/test_builder_cdr_template.py`
- `tests/test_builder_router.py`

Behavior:
- Drafts now include explicit `assumptions` and `changed_residues` surfaces derived deterministically from before/after sequences.
- Point mutation and CDR builder previews now render warnings, assumptions, sequence diff view, and changed-residue tables.
- Invalid drafts remain non-creatable; added coverage ensures create actions are hidden when draft errors exist.

Gates:
- PASS

## 2026-03-07 — v1.3.0b79
Intent:
- Document Builder Phase 2 and harden regression coverage for builder non-interference guarantees.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/BUILDER_PHASE2_v1.3.0b79.md`
- `docs/README.md`
- `tests/test_builder_non_interference.py`

Behavior:
- Added Builder Phase 2 architecture/safety documentation and indexed it from docs.
- Added regression test proving builder create has no side effects on programs, DI snapshots, report runs, or batches.

Gates:
- PASS

## 2026-03-07 — v1.3.0b80
Intent:
- Add additive Variant Set persistence foundation for Builder Phase 3.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/services/builder.py`
- `tests/test_builder_variant_set_models.py`

Behavior:
- Added additive tables/models: `builder_variant_sets` and `builder_variant_set_members`.
- Added deterministic persistence helpers in builder service for variant set row creation and ordered member insertion.
- Added tests covering table persistence and deterministic membership ordering.

Gates:
- PASS

## 2026-03-07 — v1.3.0b81
Intent:
- Add Variant Set Builder service API boundary with deterministic draft/create flow.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/builder.py`
- `tests/test_builder_variant_set_service.py`

Behavior:
- Added API types: `VariantSetBuildSpec`, `VariantSetDraft`, `VariantSetCreateMeta`, `VariantSetCreateResult`.
- Added `build_variant_set_draft()` and `create_variant_set_from_draft()` with deterministic member ordering and naming.
- Added service tests for deterministic draft ordering and persisted set/member creation.

Gates:
- PASS

## 2026-03-07 — v1.3.0b82
Intent:
- Add standalone Variant Set Builder route and landing page scaffold.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/builder.py`
- `psi/web/templates/builder/index.html`
- `psi/web/templates/builder/variant_set.html`
- `tests/test_builder_variant_set_router.py`

Behavior:
- Added `/builder/variant-set` and `/builder/variant-set/draft` routes.
- Added Variant Set Builder entry point on builder index and initial family-type selection UI.
- Added route/template coverage tests for variant set builder surface.

Gates:
- PASS

## 2026-03-07 — v1.3.0b83
Intent:
- Implement mutation panel variant-family generation with deterministic preview naming/order.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/builder_ops.py`
- `psi/web/routers/builder.py`
- `psi/web/templates/builder/variant_set.html`
- `tests/test_builder_variant_set_router.py`
- `tests/test_builder_variant_set_mutation_panel.py`

Behavior:
- Added deterministic mutation-panel member generator supporting singles, pair combinations, and explicit combos.
- Variant Set draft route now builds mutation-panel members from user inputs and renders ordered draft preview rows.
- Added tests validating member generation and deterministic naming (e.g., `M_104_N4Q_G3L`).

Gates:
- PASS

## 2026-03-07 — v1.3.0b84
Intent:
- Add Fc/format panel variant-family generation.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/builder_ops.py`
- `psi/web/routers/builder.py`
- `psi/web/templates/builder/variant_set.html`
- `tests/test_builder_variant_set_fc_panel.py`

Behavior:
- Added deterministic Fc panel member generator for `human_igg1`, `mouse_igg2a`, `fab_no_fc`.
- Variant set draft route now supports `fc_panel` with configurable presets input.
- Added tests for deterministic preset ordering and valid fc_panel variant draft generation.

Gates:
- PASS

## 2026-03-07 — v1.3.0b85
Intent:
- Add KIH panel variant-family generation.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/builder_ops.py`
- `psi/web/routers/builder.py`
- `psi/web/templates/builder/variant_set.html`
- `tests/test_builder_variant_set_kih_panel.py`

Behavior:
- Added deterministic KIH panel member generator (`off`, `on_knob`, `on_hole`) mapped to existing KIH actions.
- Variant set draft route now supports `kih_panel` from explicit KIH presets input.
- Added tests for default KIH panel members and valid KIH panel variant draft generation.

Gates:
- PASS

## 2026-03-07 — v1.3.0b86
Intent:
- Add scaffold comparison family generation for shared CDR inputs across multiple frameworks.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/builder_ops.py`
- `psi/web/routers/builder.py`
- `psi/web/templates/builder/variant_set.html`
- `tests/test_builder_variant_set_scaffold_panel.py`

Behavior:
- Added scaffold panel member generator producing deterministic `cdr_graft` members from selected scaffold presets.
- Added additional framework preset and scaffold-family inputs on variant set page (scaffolds, chain type, numbering, CDR inputs).
- Scaffold panel drafts now produce reconstructed-from-CDR member summaries and deterministic ordering.

Gates:
- PASS

## 2026-03-07 — v1.3.0b87
Intent:
- Add variant family draft review + save-all confirmation surface.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/builder.py`
- `psi/web/templates/builder/variant_set.html`
- `tests/test_builder_variant_set_router.py`

Behavior:
- Added `/builder/variant-set/create` save endpoint that rebuilds draft deterministically and refuses invalid families.
- Variant set preview now acts as campaign review surface with save-all confirmation when draft is valid.
- Template tests now assert save action is hidden for invalid drafts.

Gates:
- PASS

## 2026-03-07 — v1.3.0b88
Intent:
- Add persisted variant-family review surface after save.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/builder.py`
- `psi/web/templates/builder/variant_set_detail.html`
- `tests/test_builder_variant_set_router.py`

Behavior:
- Added `/builder/variant-sets/{variant_set_id}` detail route for campaign/family review.
- Save flow now redirects to family detail page with ordered member listing and parent/derivation context.
- Added template/route tests for family detail rendering.

Gates:
- PASS

## 2026-03-07 — v1.3.0b89
Intent:
- Finalize Builder Phase 3 documentation and regression hardening.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/BUILDER_PHASE3_v1.3.0b89.md`
- `docs/README.md`
- `tests/test_builder_variant_set_regression.py`

Behavior:
- Added Builder Phase 3 documentation covering variant set architecture, controlled generation scope, and safety boundaries.
- Added regression tests for no program/DI/report/batch coupling, parent immutability, deterministic member/save ordering, and invalid-draft no-write behavior.

Gates:
- PASS

## 2026-03-07 — v1.3.0b90
Intent:
- Add deterministic region-aware sequence annotation foundation for sequence editor workflows.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/sequence_annotation.py`
- `tests/test_sequence_annotation.py`

Behavior:
- Added `annotate_sequence_for_editor()` to produce per-residue annotation payloads (component, position, AA, region, numbering label).
- Deterministic ordering by component role/id and residue position.
- Added unit tests for structure correctness and repeat-call determinism.

Gates:
- PASS

## 2026-03-07 — v1.3.0b91
Intent:
- Add reusable sequence editor render partial and wire annotation context into molecule detail.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/_sequence_editor.html`
- `psi/web/templates/molecules/detail.html`
- `tests/test_sequence_editor_template.py`

Behavior:
- Molecule detail now includes `sequence_editor_annotations` generated deterministically from components/domains/numbering maps.
- Added `_sequence_editor.html` partial with per-residue interactive spans and stable data attributes.
- Added template test validating interactive residue render attributes.

Gates:
- PASS

## 2026-03-07 — v1.3.0b92
Intent:
- Add residue hover metadata tooltip behavior for sequence editor.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/static/sequence_editor.js`
- `psi/web/templates/molecules/_sequence_editor.html`
- `psi/web/templates/molecules/detail.html`
- `tests/test_molecule_lineage_surface.py`

Behavior:
- Added hover tooltip for `.seq-residue` elements showing component, residue position, region, and numbering label.
- Wired sequence editor JS into molecule detail page scripts block.
- Added render assertion coverage for tooltip container and script include.

Gates:
- PASS

## 2026-03-07 — v1.3.0b93
Intent:
- Add click-to-mutate interaction and local mutation queue UI.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/static/sequence_editor.js`
- `psi/web/templates/molecules/_sequence_editor.html`
- `tests/test_sequence_editor_template.py`

Behavior:
- Added mutation queue panel with remove and clear-all actions.
- Clicking residues now prompts for target AA and queues deterministic mutation entries keyed by component/position.
- Queue list is always rendered in deterministic order.

Gates:
- PASS

## 2026-03-07 — v1.3.0b94
Intent:
- Add direct mutation notation parsing + WT validation foundation and unify with queue representation.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/sequence_editor.py`
- `psi/web/static/sequence_editor.js`
- `psi/web/templates/molecules/_sequence_editor.html`
- `tests/test_sequence_editor_service.py`
- `tests/test_sequence_editor_template.py`

Behavior:
- Added backend parser/normalizer (`parse_mutation_notation`, `normalize_mutation_queue`) with WT mismatch validation.
- Added direct notation input UI and apply action that feeds the same local queue shape as click edits.
- Added deterministic service tests for parsing/sorting/WT mismatch handling.

Gates:
- PASS

## 2026-03-07 — v1.3.0b95
Intent:
- Add deterministic sequence preview/diff panel for queued mutations.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/sequence_editor.py`
- `psi/web/static/sequence_editor.js`
- `psi/web/templates/molecules/_sequence_editor.html`
- `tests/test_sequence_editor_service.py`
- `tests/test_sequence_editor_template.py`

Behavior:
- Added `build_sequence_preview()` service to derive edited sequence, changed positions, and validation errors without mutating stored molecules.
- Sequence editor UI now renders live original/edited preview and changed-position summary from queue state.
- Added service and template tests for preview/diff surfaces.

Gates:
- PASS

## 2026-03-07 — v1.3.0b96
Intent:
- Integrate sequence editor queue with Builder single-variant draft flow.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/static/sequence_editor.js`
- `psi/web/templates/molecules/_sequence_editor.html`
- `tests/test_sequence_editor_template.py`

Behavior:
- Added sequence-editor handoff form posting to `/builder/point-mutation/draft` with queued mutation tokens.
- JS now synchronizes deterministic queue state into hidden Builder form fields and enforces single-component handoff.
- Added template assertion coverage for Builder handoff controls.

Gates:
- PASS

## 2026-03-07 — v1.3.0b97
Intent:
- Integrate sequence editor queue with Variant Set Builder seeding flow.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/static/sequence_editor.js`
- `psi/web/templates/molecules/_sequence_editor.html`
- `tests/test_sequence_editor_template.py`

Behavior:
- Added sequence-editor handoff form posting to `/builder/variant-set/draft` with deterministic `mutation_panel` inputs.
- JS now synchronizes queue tokens into variant-set fields and optionally emits an explicit full-combination token group.
- Added template assertions for variant-set handoff controls.

Gates:
- PASS

## 2026-03-07 — v1.3.0b98
Intent:
- Add sequence editor phase documentation and safety-focused regression hardening.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/SEQUENCE_EDITOR_PHASE1_v1.3.0b98.md`
- `tests/test_sequence_editor_regression.py`

Behavior:
- Added Phase 1 sequence editor architecture/safety documentation.
- Added deterministic regression tests for queue ordering and pure non-mutating preview behavior.
- Added static coupling guard test ensuring sequence editor modules remain outside Program/DI/Report paths.

Gates:
- PASS

## 2026-03-07 — v1.3.0b99
Intent:
- Harden sequence-editor handoff state so builder actions cannot carry stale queue payloads.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/static/sequence_editor.js`
- `psi/web/templates/molecules/_sequence_editor.html`
- `tests/test_sequence_editor_template.py`

Behavior:
- Fixed queue rendering flow so handoff synchronization always runs, including empty-queue state.
- Empty or mixed-component queue now deterministically clears/disabled handoff payloads and buttons.
- Added inline handoff hints to explain why actions are disabled and when they are ready.

Gates:
- PASS

## 2026-03-07 — v1.3.0b100
Intent:
- Make sequence-editor direct-entry and preview behavior explicitly component-aware.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/static/sequence_editor.js`
- `psi/web/templates/molecules/_sequence_editor.html`
- `tests/test_sequence_editor_regression.py`
- `tests/test_sequence_editor_template.py`

Behavior:
- Added explicit target component selector in the sequence editor control panel.
- Direct notation parsing and assignment now target the selected component instead of implicit first component.
- Preview/diff now renders for the selected component deterministically.

Gates:
- PASS

## 2026-03-07 — v1.3.0b101
Intent:
- Strengthen scientist-facing bridge from sequence edits into Builder draft workflows.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/builder.py`
- `psi/web/static/sequence_editor.js`
- `psi/web/templates/builder/point_mutation.html`
- `psi/web/templates/molecules/_sequence_editor.html`
- `tests/test_builder_router.py`
- `tests/test_sequence_editor_template.py`

Behavior:
- Promoted Builder draft handoff to clear primary CTA and clarified sequence-editor guidance text.
- Added queue context payload fields (source molecule, component, mutation count, tokens) to Builder handoff.
- Builder point-mutation draft page now displays sequence-editor handoff context when present.

Gates:
- PASS

## 2026-03-07 — v1.3.0b102
Intent:
- Align sequence-editor handoff validation with backend mutation normalization semantics.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/builder.py`
- `psi/web/static/sequence_editor.js`
- `psi/web/templates/builder/point_mutation.html`
- `psi/web/templates/builder/variant_set.html`
- `psi/web/templates/molecules/_sequence_editor.html`
- `tests/test_builder_router.py`
- `tests/test_builder_variant_set_router.py`
- `tests/test_sequence_editor_template.py`

Behavior:
- Added server-side mutation normalization helper at builder handoff boundary using `sequence_editor.normalize_mutation_queue`.
- Point-mutation and mutation-panel draft flows now canonicalize incoming mutation tokens per component when context is available.
- Added UI notes surfaces for normalization errors/warnings in builder draft templates.

Gates:
- PASS

## 2026-03-07 — v1.3.0b103
Intent:
- Add end-to-end handoff tests and phase documentation for actionable sequence-editor workflows.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/SEQUENCE_EDITOR_WORKFLOW_v1.3.0b103.md`
- `tests/test_sequence_editor_handoff_routes.py`
- `tests/test_sequence_editor_regression.py`

Behavior:
- Added route-level tests validating sequence-editor payload handoff into builder point-mutation and variant-set draft routes.
- Added regression assertions for disabled-state payload clearing hooks in sequence-editor JS.
- Added workflow documentation defining supported sequence-editor-to-builder behaviors.

Gates:
- PASS

## 2026-03-07 — v1.3.0c1
Intent:
- Add Scientist Interpretation Layer foundation with deterministic insight bundle generation.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/insight_engine.py`
- `tests/test_insight_engine.py`

Behavior:
- Added `build_insight_bundle(snapshot, ...)` as the single deterministic DI interpretation entrypoint.
- Bundle now includes molecule status, blocking issues, missing/failing evidence, and recommended experiments.
- Added unit tests for nested snapshot handling and deterministic missing/failing extraction.

Gates:
- PASS

## 2026-03-07 — v1.3.0c2
Intent:
- Extend Insight Engine with deterministic evidence classification surfaces.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/insight_engine.py`
- `tests/test_insight_engine.py`

Behavior:
- Added strongest supporting/blocking evidence ranking surfaces from gate outcomes and used evidence.
- Added deterministic missing-evidence ranking and bundle-level decision summary generation.
- Added coverage tests for supporting/blocking evidence ordering.

Gates:
- PASS

## 2026-03-07 — v1.3.0c3
Intent:
- Add policy expectation extraction for scientist-facing interpretation surfaces.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/insight_engine.py`
- `tests/test_insight_engine.py`

Behavior:
- Added `extract_policy_expectations(policy)` to emit simplified threshold/requirement expectations.
- Expectation text now uses metric catalog labels/units for scientist readability.
- Added deterministic expectation extraction tests.

Gates:
- PASS

## 2026-03-07 — v1.3.0c4
Intent:
- Wire Insight Engine narrative into DI decision detail surfaces.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/decisions.py`
- `psi/web/templates/decisions/_di_snapshot.html`
- `tests/test_decision_insight_summary.py`

Behavior:
- DI decision detail context now includes `di_insight_bundle` from the Insight Engine.
- Added top-level “Decision Summary” narrative block to DI snapshot template.
- Added service test confirming DI snapshot detail includes deterministic narrative text.

Gates:
- PASS
## 2026-03-07 — v1.3.0c58
Intent:
- Add portfolio timeline activity chart surface derived from tasks and evidence timestamps.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/portfolio.py`
- `psi/web/routers/portfolio.py`
- `psi/web/templates/portfolio/overview.html`
- `tests/test_portfolio_router.py`
- `tests/test_portfolio_service.py`
- `tests/test_portfolio_surface.py`

Behavior:
- Added deterministic weekly timeline rollup for tasks completed, tasks created, and evidence records created.
- Wired timeline data into portfolio overview context and rendered a dedicated Portfolio Timeline section.
- Added service/router/template tests covering timeline aggregation and rendering.

Gates:
- PASS
## 2026-03-07 — v1.3.0c59
Intent:
- Add portfolio CSV export for leadership reporting surfaces.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/portfolio.py`
- `psi/web/routers/portfolio.py`
- `tests/test_portfolio_router.py`
- `tests/test_portfolio_service.py`

Behavior:
- Added deterministic export rows builder from program portfolio summaries.
- Added `/portfolio/export` endpoint returning CSV with program status, task counts, and molecule readiness metrics.
- Added router/service tests for CSV shape and deterministic row ordering.

Gates:
- PASS
## 2026-03-07 — v1.3.0c60
Intent:
- Add portfolio regression hardening coverage and layer documentation.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/PORTFOLIO_INTELLIGENCE_LAYER.md`
- `tests/test_portfolio_regression.py`

Behavior:
- Added regression tests for deterministic portfolio summary output, DI snapshot read-only guarantees, board behavior invariance, and task/data-record linkage integrity.
- Added portfolio layer documentation defining architecture boundaries, read-model inputs, service surfaces, and regression guarantees.

Gates:
- PASS
## 2026-03-07 — v1.3.0c61
Intent:
- Add Scientific Trajectory Engine core simulation entrypoint.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/trajectory.py`
- `tests/test_trajectory_service.py`

Behavior:
- Added deterministic `simulate_experiment_outcome(...)` trajectory projection using latest DI read-model context.
- Trajectory output includes predicted gate deltas, readiness shift projection, impacted metrics, confidence level, and explanation.
- Added tests for output shape and deterministic no-snapshot behavior.

Gates:
- PASS
## 2026-03-07 — v1.3.0c62
Intent:
- Add deterministic metric impact modeling for trajectory simulations.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/trajectory.py`
- `tests/test_trajectory_service.py`

Behavior:
- Added `predict_metric_delta(metric_key, experiment_type)` mapping common experiment categories to impacted metrics.
- Simulation output now derives `impacted_metrics` from deterministic metric-delta modeling.
- Added mapping tests for KD, SEC/purity, internalization, and fallback paths.

Gates:
- PASS
## 2026-03-07 — v1.3.0c63
Intent:
- Add deterministic gate-transition prediction for trajectory projections.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/trajectory.py`
- `tests/test_trajectory_service.py`

Behavior:
- Added `predict_gate_transitions(metric_changes, gate_context=...)` to simulate gate-before/gate-after deltas without snapshot mutation.
- `simulate_experiment_outcome(...)` now uses gate-transition prediction service logic.
- Added deterministic tests for predicted gate delta ordering and status transitions.

Gates:
- PASS
## 2026-03-07 — v1.3.0c64
Intent:
- Add readiness projection logic for trajectory outcomes.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/trajectory.py`
- `tests/test_trajectory_service.py`

Behavior:
- Added `predict_readiness_shift(gate_changes, metric_changes, readiness_before=...)`.
- Simulation now uses explicit readiness-shift projection output (`readiness_before`, `readiness_after`).
- Added tests verifying readiness transitions to ready when projected gate improvements occur.

Gates:
- PASS
## 2026-03-07 — v1.3.0c65
Intent:
- Add numeric trajectory confidence scoring.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/trajectory.py`
- `tests/test_trajectory_service.py`

Behavior:
- Added `score_trajectory_confidence(...)` with deterministic 0–1 scoring based on metric importance, assumptions, and historical stability.
- Simulation output now includes `confidence_score` and bucketed `confidence_level`.
- Added tests for score range, determinism, and assumptions penalty impact.

Gates:
- PASS
## 2026-03-07 — v1.3.0c66
Intent:
- Integrate trajectory candidate generation with InsightEngine recommendations.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/trajectory.py`
- `tests/test_trajectory_service.py`

Behavior:
- Added `generate_trajectory_candidates(molecule_id)` deriving candidates from InsightEngine `recommended_experiments`.
- Candidate payload now includes expected readiness gain, metric coverage improvement, gate impact, and simulation confidence.
- Added tests validating deterministic candidate generation and expected fields.

Gates:
- PASS
## 2026-03-07 — v1.3.0c67
Intent:
- Add deterministic trajectory candidate ranking.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/trajectory.py`
- `tests/test_trajectory_service.py`

Behavior:
- Added `rank_trajectory_candidates(...)` with deterministic sort by expected readiness gain, confidence, effort estimate, coverage, and metric key.
- Added lightweight effort estimation based on assay type.
- Added tests verifying ranking order and effort influence.

Gates:
- PASS
## 2026-03-07 — v1.3.0c68
Intent:
- Add molecule-level Scientific Trajectory panel.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`
- `tests/test_molecule_lineage_surface.py`

Behavior:
- Molecule detail context now includes ranked `trajectory_candidates` derived from trajectory service.
- Added a new “Scientific Trajectory” panel on molecule detail rendering top projected experiments and expected readiness impact.
- Added service/template tests for trajectory panel context and rendering.

Gates:
- PASS
## 2026-03-07 — v1.3.0c69
Intent:
- Add trajectory hints to development board cards.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/dev_board.py`
- `psi/web/templates/programs/board.html`
- `tests/test_dev_board.py`

Behavior:
- Development board now derives `trajectory_next_experiment` per molecule from ranked trajectory candidates.
- Board cards render a compact “Trajectory hint” line when a top projection exists.
- Added board service test coverage for trajectory hint presence and expected metric linkage.

Gates:
- PASS
## 2026-03-07 — v1.3.0c70
Intent:
- Add program-level trajectory aggregation.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/trajectory.py`
- `tests/test_trajectory_service.py`

Behavior:
- Added `build_program_trajectory(program_id)` to aggregate top projected experiments across molecules in a program.
- Program-level trajectory ordering is deterministic by readiness gain, confidence, effort, molecule, and metric key.
- Added tests validating cross-molecule aggregation behavior.

Gates:
- PASS
## 2026-03-07 — v1.3.0c71
Intent:
- Add portfolio-level trajectory insight aggregation.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/trajectory.py`
- `psi/web/routers/portfolio.py`
- `psi/web/templates/portfolio/overview.html`
- `tests/test_portfolio_router.py`
- `tests/test_portfolio_surface.py`
- `tests/test_trajectory_service.py`

Behavior:
- Added `build_portfolio_trajectory()` to identify globally high-impact projected experiments across programs.
- Portfolio overview now renders a “Portfolio Trajectory Insights” section.
- Added service/router/template tests for portfolio trajectory context and rendering.

Gates:
- PASS
## 2026-03-07 — v1.3.0c72
Intent:
- Add multi-experiment trajectory simulation.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/trajectory.py`
- `tests/test_trajectory_service.py`

Behavior:
- Added `simulate_experiment_set(molecule_id, experiments[])` returning cumulative readiness projection, impacted metrics, and impacted gates.
- Multi-experiment simulation composes deterministic per-experiment read-model projections without mutating DI/task/evidence state.
- Added tests for cumulative set simulation outputs.

Gates:
- PASS
## 2026-03-07 — v1.3.0c73
Intent:
- Add branching trajectory-tree modeling with deterministic ordering.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/trajectory.py`
- `tests/test_trajectory_service.py`

Behavior:
- Added `build_trajectory_tree(...)` producing deterministic trajectory nodes rooted at current state with branching projected experiment outcomes.
- Tree generation is bounded (`max_depth`, `branch_limit`) and read-model only.
- Added tests for deterministic tree output and node structure.

Gates:
- PASS
## 2026-03-07 — v1.3.0c74
Intent:
- Add molecule-page trajectory visualization surface.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`
- `tests/test_molecule_lineage_surface.py`

Behavior:
- Molecule detail context now includes a derived `trajectory_tree` structure.
- Added “Trajectory Graph” section rendering current state to projected states.
- Added service/template tests for trajectory graph context and rendering.

Gates:
- PASS
## 2026-03-07 — v1.3.0c75
Intent:
- Add trajectory regression hardening and documentation.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/SCIENTIFIC_TRAJECTORY_ENGINE.md`
- `tests/test_trajectory_regression.py`

Behavior:
- Added regression tests ensuring trajectory simulation does not mutate DI snapshots, DataRecord state, or ExperimentTask state.
- Added board-invariance regression coverage for trajectory reads.
- Added Scientific Trajectory Engine documentation defining boundaries, service surfaces, UI surfaces, and determinism guarantees.

Gates:
- PASS
## 2026-03-07 — v1.3.0c76
Intent:
- Add ScientificClaim persistence foundation with additive schema support.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/core/db.py`
- `tests/test_scientific_claim_model.py`

Behavior:
- Added `ScientificClaim` core model and additive link models for evidence/decision/task relationships.
- Extended schema ensure/index setup for deterministic claim query patterns.
- Added model/schema tests validating table shape and additive lifecycle/link behavior.

Gates:
- PASS
## 2026-03-07 — v1.3.0c77
Intent:
- Add Scientific Claims service layer with deterministic lifecycle/query operations.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/claims.py`
- `tests/test_claims_service.py`

Behavior:
- Added claim service operations: create/get/list/update/archive/top helpers.
- Added deterministic molecule/program claim ordering by status, confidence, updated_at, id.
- Added service tests covering creation, ordering, lifecycle transitions, and retrieval APIs.

Gates:
- PASS
## 2026-03-07 — v1.3.0c78
Intent:
- Harden scientific-claim lifecycle transitions and deterministic ordering semantics.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/claims.py`
- `tests/test_claims_service.py`

Behavior:
- Added explicit transition helper `can_transition_claim_status(...)` and enforced one-way transition rules.
- Archived status remains terminal unless explicitly changed in service policy.
- Added transition-matrix tests covering allowed/blocked lifecycle paths.

Gates:
- PASS
## 2026-03-07 — v1.3.0c79
Intent:
- Add disciplined claim-type templates and statement helpers.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/claims.py`
- `tests/test_claims_service.py`

Behavior:
- Added canonical claim-type template map to constrain statement semantics.
- Added helper `claim_type_template(...)` and strengthened statement formatting for typed claims.
- Added tests ensuring claim type normalization/template behavior remains deterministic.

Gates:
- PASS
## 2026-03-07 — v1.3.0c80
Intent:
- Add claim-to-evidence linkage semantics.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/claims.py`
- `tests/test_claim_evidence_links.py`

Behavior:
- Added deterministic claim evidence linking/unlinking/listing surfaces with direction support (`supporting|contradicting|contextual`).
- Added dedicated evidence-link tests validating add/list/remove behavior.

Gates:
- PASS
## 2026-03-07 — v1.3.0c81
Intent:
- Add claim-to-decision linkage semantics.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/claims.py`
- `tests/test_claim_decision_links.py`

Behavior:
- Added deterministic claim/decision association helpers and list surfaces.
- Added dedicated tests validating link-only behavior with no DecisionSnapshot payload mutation.

Gates:
- PASS
## 2026-03-07 — v1.3.0c82
Intent:
- Add claim-to-task linkage semantics.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/claims.py`
- `tests/test_claim_task_links.py`

Behavior:
- Added deterministic claim/task association helpers and listing support.
- Added dedicated tests validating link behavior and task-state non-mutation guarantees.

Gates:
- PASS
## 2026-03-07 — v1.3.0c83
Intent:
- Add deterministic claim synthesis summaries.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/claims.py`
- `tests/test_claim_synthesis.py`

Behavior:
- Added deterministic synthesis helpers: support summary, conflict summary, maturity summary.
- Maturity surfaces now include support/conflict counts, linked decision count, and linked task open/done counts.
- Added dedicated synthesis tests for summary correctness.

Gates:
- PASS
## 2026-03-07 — v1.3.0c84
Intent:
- Add molecule-level scientific claims panel.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`
- `tests/test_molecule_claim_surface.py`

Behavior:
- Molecule detail context now includes top active claims with deterministic support/conflict/maturity summaries.
- Added “Scientific Claims” panel to molecule detail showing status, confidence, support/conflict, and linked next-task hint.
- Added molecule-claim surface tests for context and rendering.

Gates:
- PASS
## 2026-03-07 — v1.3.0c85
Intent:
- Add scientific claim detail route and page.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/app.py`
- `psi/web/routers/claims.py`
- `psi/web/templates/claims/detail.html`
- `tests/test_claim_router.py`
- `tests/test_claim_surface.py`

Behavior:
- Added server-rendered claim detail route `/claims/{claim_id}`.
- Added claim detail surface with claim statement, type/status/confidence, evidence/decision/task links, and maturity summary.
- Added route/template tests for detail rendering and context.

Gates:
- PASS
## 2026-03-07 — v1.3.0c86
Intent:
- Add task and trajectory context to claim surfaces.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/claims.py`
- `psi/web/templates/claims/detail.html`
- `tests/test_claim_router.py`
- `tests/test_claim_surface.py`

Behavior:
- Claim detail context now includes linked open tasks and claim-relevant trajectory candidates.
- Added claim-type metric hints to select relevant trajectory rows deterministically.
- Claim detail page now renders open-task context and trajectory context sections.

Gates:
- PASS
## 2026-03-07 — v1.3.0c87
Intent:
- Add program-level scientific claim summary surfaces.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/programs.py`
- `psi/web/templates/programs/detail.html`
- `tests/test_program_claim_summary.py`

Behavior:
- Program detail context now includes deterministic claim summary counts and preview rows.
- Program page now renders claim status buckets and top active claim rows.
- Added tests validating program claim rollup context behavior.

Gates:
- PASS
## 2026-03-07 — v1.3.0c88
Intent:
- Add portfolio-level claim insight rollups.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/portfolio.py`
- `psi/web/routers/portfolio.py`
- `psi/web/templates/portfolio/overview.html`
- `tests/test_portfolio_router.py`
- `tests/test_portfolio_service.py`
- `tests/test_portfolio_surface.py`

Behavior:
- Added deterministic `build_portfolio_claim_summary(...)` rollups for most-supported, most-at-risk, evidence-starved, and highest-task-burden claims.
- Portfolio overview now renders claim insight sections.
- Added router/service/template tests for claim summary context and rendering.

Gates:
- PASS
## 2026-03-07 — v1.3.0c89
Intent:
- Add Scientific Claims regression boundary coverage.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_claim_regression_boundaries.py`

Behavior:
- Added explicit regression tests ensuring claim reads do not mutate DI snapshots, task states, or create evidence rows.
- Added deterministic ordering/summary regression checks for claims service outputs.

Gates:
- PASS
## 2026-03-07 — v1.3.0c90
Intent:
- Add Scientific Claims layer documentation and final coherence polish.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/SCIENTIFIC_CLAIMS_LAYER.md`
- `psi/services/claims.py`
- `psi/web/routers/claims.py`
- `psi/web/templates/base.html`
- `psi/web/templates/claims/list.html`
- `tests/test_base_navigation.py`
- `tests/test_claim_router.py`
- `tests/test_claim_surface.py`

Behavior:
- Added claims index route `/claims` and list template for scientist-facing discoverability.
- Added navigation entry for Claims.
- Added documentation covering claim/hypothesis semantics, link boundaries, architecture constraints, and extension points.

Gates:
- PASS

## 2026-03-07 — v1.3.0c91
Intent:
- Add ScientificPlan/ScientificPlanStep additive model and schema foundation.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/core/db.py`
- `tests/test_scientific_plan_model.py`

Behavior:
- Added persisted planning entities `ScientificPlan` and `ScientificPlanStep` with deterministic indexes and ORM relationships.
- Extended `ensure_schema` with additive table/column coverage and plan indexes.
- Added model/schema tests validating lifecycle and additive behavior.

Gates:
- PASS

## 2026-03-07 — v1.3.0c92
Intent:
- Add deterministic ScientificPlan service layer and step operations.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/plans.py`
- `tests/test_plans_service.py`

Behavior:
- Added plan CRUD/list/top helpers for molecule/claim/program scopes.
- Added step operations for add/list/status update with stable ordering and timestamps.
- Added service tests for lifecycle, ordering behavior, and step operations.

Gates:
- PASS

## 2026-03-07 — v1.3.0c93
Intent:
- Harden ScientificPlan and ScientificPlanStep status transitions and ordering semantics.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/plans.py`
- `tests/test_plans_service.py`

Behavior:
- Added explicit plan and step transition matrices and transition validators.
- Enforced one-way lifecycle transitions and terminal states for plans/steps.
- Added deterministic step ordering by status then step_order/id with transition tests.

Gates:
- PASS

## 2026-03-07 — v1.3.0c94
Intent:
- Add disciplined plan_type/step_kind helpers and rationale rendering for ScientificPlan.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/plans.py`
- `tests/test_plans_service.py`

Behavior:
- Added enumerated plan types and step kinds with normalization helpers.
- Added deterministic plan-type rationale templates and formatting fallback helper.
- Added tests covering type discipline and rendering helper behavior.

Gates:
- PASS

## 2026-03-07 — v1.3.0c95
Intent:
- Add deterministic ScientificPlan generation core for molecule and claim scopes.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/plans.py`
- `tests/test_plan_generation.py`

Behavior:
- Added `generate_plan_for_molecule(...)` and `generate_plan_for_claim(...)` using insight, trajectory, claim support, and open-task context.
- Added deterministic step synthesis with ordered proposed steps and expected gain fields.
- Added generation tests for deterministic reuse and claim-linked de-risking plan creation.

Gates:
- PASS

## 2026-03-07 — v1.3.0c96
Intent:
- Add explicit molecule readiness plan generation refinement.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/plans.py`
- `tests/test_plan_generation.py`

Behavior:
- Added `generate_readiness_plan_for_molecule(...)` with deterministic step ranking: missing gating evidence, highest-impact trajectory, then confirmatory follow-up.
- Updated molecule plan generation to delegate to readiness-focused builder.
- Added tests covering prioritized missing metrics and confirmatory step inclusion.

Gates:
- PASS

## 2026-03-07 — v1.3.0c97
Intent:
- Add explicit claim de-risking plan generation behavior with contradiction-aware follow-up.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/plans.py`
- `tests/test_plan_generation.py`

Behavior:
- Added `generate_claim_derisking_plan_for_claim(...)` and routed `generate_plan_for_claim(...)` through it.
- Added deterministic contradiction-aware confirmatory step insertion for claims with contradicting evidence links.
- Extended tests to validate claim-test plus confirmatory step composition.

Gates:
- PASS

## 2026-03-07 — v1.3.0c98
Intent:
- Add deterministic plan scoring and ranking helpers for planning-layer prioritization.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/plans.py`
- `tests/test_plan_ranking.py`

Behavior:
- Added effort estimation and weighted plan scoring from readiness/claim/evidence gains with effort and step-count penalties.
- Added `rank_plans(...)` and wired top-plan helpers to ranking output.
- Added tests for deterministic plan scoring/ranking and top-plan consistency.

Gates:
- PASS

## 2026-03-07 — v1.3.0c99
Intent:
- Add molecule recommended planning surface.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`
- `tests/test_molecule_plan_surface.py`

Behavior:
- Added molecule-level recommended plan context in molecule detail service with top plan summaries and step previews.
- Added a compact "Recommended Plans" panel to molecule detail template.
- Added molecule planning surface tests for context and rendering.

Gates:
- PASS

## 2026-03-07 — v1.3.0c100
Intent:
- Add claim-facing planning panel with recommended de-risking plans.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/claims.py`
- `psi/web/templates/claims/detail.html`
- `tests/test_claim_router.py`
- `tests/test_claim_surface.py`
- `tests/test_claim_plan_surface.py`

Behavior:
- Extended claim detail service context with recommended claim plans and step previews.
- Added "Recommended Claim Plans" section to claim detail template with expected gains.
- Added/updated tests for claim plan context and rendering.

Gates:
- PASS

## 2026-03-07 — v1.3.0c101
Intent:
- Add server-rendered plan detail route and template.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/app.py`
- `psi/web/routers/plans.py`
- `psi/web/templates/plans/detail.html`
- `tests/test_plan_router.py`
- `tests/test_plan_surface.py`

Behavior:
- Added `/plans/{plan_id}` route backed by plan detail service context.
- Added plan detail template with scope links, expected gains, ordered steps, and task instantiation status.
- Registered plans router in app and added route/template tests.

Gates:
- PASS

## 2026-03-07 — v1.3.0c102
Intent:
- Add explicit plan step/full-plan task instantiation bridge.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/plans.py`
- `psi/web/routers/plans.py`
- `psi/web/templates/plans/detail.html`
- `tests/test_plan_router.py`
- `tests/test_plan_task_instantiation.py`

Behavior:
- Added `create_task_from_plan_step(...)` and `create_tasks_from_plan(...)` to instantiate proposed plan steps into ExperimentTasks by explicit action only.
- Linked created tasks back to plan steps and marked step status as `task_created`.
- Added POST routes and UI actions for explicit step/plan instantiation plus tests.

Gates:
- PASS

## 2026-03-07 — v1.3.0c103
Intent:
- Add program and portfolio planning rollups.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/programs.py`
- `psi/services/portfolio.py`
- `psi/web/routers/portfolio.py`
- `psi/web/templates/programs/detail.html`
- `psi/web/templates/portfolio/overview.html`
- `tests/test_program_claim_summary.py`
- `tests/test_program_plan_summary.py`
- `tests/test_portfolio_router.py`
- `tests/test_portfolio_service.py`
- `tests/test_portfolio_surface.py`

Behavior:
- Added program-level plan summary/preview in program detail context and template.
- Added portfolio-level plan insights and summary counters (most actionable, accepted, awaiting instantiation, bottleneck-targeting).
- Extended router/template/service tests for program and portfolio planning rollups.

Gates:
- PASS

## 2026-03-07 — v1.3.0c104
Intent:
- Add explicit planning-layer regression boundary coverage.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_plan_regression_boundaries.py`

Behavior:
- Added regression tests ensuring plan generation does not mutate DI snapshot payloads, task status truth, claim truth, or create fake evidence.
- Added deterministic ordering/summary regression checks for plan ranking/detail outputs.

Gates:
- PASS

## 2026-03-07 — v1.3.0c105
Intent:
- Add Trajectory-to-Planning documentation and final scientist-facing polish.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/TRAJECTORY_TO_PLANNING_LAYER.md`
- `psi/services/plans.py`
- `psi/web/routers/plans.py`
- `psi/web/templates/base.html`
- `psi/web/templates/plans/list.html`
- `tests/test_base_navigation.py`
- `tests/test_plan_router.py`
- `tests/test_plan_surface.py`

Behavior:
- Added planning layer documentation with boundaries, determinism, generated-vs-instantiated semantics, and extension points.
- Added `/plans` list route/template and navigation entry for discoverability.
- Added tests for plans list/nav rendering and route registration.

Gates:
- PASS
