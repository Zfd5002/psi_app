# PSI App UX Audit + Patch Plan

## 1. Executive Summary
This read-only audit confirms all five user-reported app UX issues are real in current code, with two high-impact workflow problems: (1) data-entry selector coupling is missing, and (2) Program Workspace drill-down links pass `program_id` query params that several destination routes currently ignore. Navigation between molecule/batch/program is partially present but inconsistently surfaced.

## 2. Confirmed App-Level UX Issues
1. Missing obvious molecule -> program action
- Confirmed in [`psi/web/templates/molecules/detail.html`](/home/zach/psi_codex/psi/web/templates/molecules/detail.html): primary/secondary actions include batch, DI, edit, legacy decision, but no explicit “Open Program Workspace” action.
- `surface.local_nav` for molecule also has no program link in [`psi/web/ui_surfaces.py`](/home/zach/psi_codex/psi/web/ui_surfaces.py).

2. Molecule / batch / program navigation is not obvious
- Molecule page has many links but no direct program CTA; batch detail has molecule link but no direct program link (see [`psi/web/templates/batches/detail.html`](/home/zach/psi_codex/psi/web/templates/batches/detail.html)).
- Navigation is possible indirectly, but pathing is non-obvious.

3. `/data/new` selector dependencies/autofill are not implemented
- Form renders full global lists for Program/Molecule/Batch from `get_form_context` (all rows) in [`psi/services/data_records.py`](/home/zach/psi_codex/psi/services/data_records.py) and [`psi/web/templates/partials/data/form_core_fields.html`](/home/zach/psi_codex/psi/web/templates/partials/data/form_core_fields.html).
- `data_form.js` handles domain/data_type/method schema rendering and batch-required hint, but does not filter molecule options by program, batches by molecule, or perform cross-autofill program<->molecule<->batch.
- Batch-first launch `/data/new?batch_id=...` preselects batch only; it does not auto-fill molecule/program unless passed separately.

4. Adding second/third data record is clunky
- New record save redirects to `/data/{id}` (detail) by design in [`psi/web/routers/data_records.py`](/home/zach/psi_codex/psi/web/routers/data_records.py).
- Form actions only expose `Save` + `Cancel`; no “Save and add another” in [`psi/web/templates/partials/data/form_actions.html`](/home/zach/psi_codex/psi/web/templates/partials/data/form_actions.html).
- Data detail has workflow/evidence actions but no direct “new sibling data record with preserved context”.

5. Program Workspace drill-down links can land on global registries
- Program detail links include `?program_id=...` for molecules/data/evidence/decisions in [`psi/web/templates/programs/detail.html`](/home/zach/psi_codex/psi/web/templates/programs/detail.html).
- But list routes/services currently ignore those query params:
  - `/molecules` route uses `svc.list_molecules(db)` (global) in [`psi/web/routers/molecules.py`](/home/zach/psi_codex/psi/web/routers/molecules.py)
  - `/data` route uses `svc.list_data_records(db)` (global) in [`psi/web/routers/data_records.py`](/home/zach/psi_codex/psi/web/routers/data_records.py)
  - `/evidence` route uses `svc.list_evidence(db)` (global) in [`psi/web/routers/evidence.py`](/home/zach/psi_codex/psi/web/routers/evidence.py)
  - `/decisions` route uses `svc.list_decision_snapshots(db)` (global) in [`psi/web/routers/decisions.py`](/home/zach/psi_codex/psi/web/routers/decisions.py)

## 3. Existing Partial Support Already in Code
- Strong prefill/handoff plumbing exists for data capture:
  - `program_id/molecule_id/batch_id/task_id/return_to` accepted by `/data/new`.
  - task-linked context is applied in `new_data(...)`.
  - return-path and capture notices are normalized via [`psi/web/handoff_context.py`](/home/zach/psi_codex/psi/web/handoff_context.py).
- Data form already gives early batch requirement hints (`batchRequirementHint`) and enforces `batchSel.required` by data type in [`psi/web/static/data_form.js`](/home/zach/psi_codex/psi/web/static/data_form.js).
- Molecule “experimental” section already provides fast, fully-prefilled “Add data” links per batch.
- Program drill-down intent is already present in template links; the mismatch is primarily destination-route filtering.

## 4. Recommended Priority Order
1. Data-entry selector dependency/autofill behavior (`/data/new`)
- Highest day-to-day workflow friction; directly affects core Task -> Data -> Evidence loop and increases entry error risk.

2. Program drill-down route filtering mismatch
- High trust and orientation impact; users expect program-scoped views but get global registries.

3. Add explicit molecule/batch -> program navigation affordances
- High confusion reducer with low implementation risk.

4. Streamline repeated data entry (2nd/3rd records)
- Important productivity improvement after core context correctness is fixed.

## 5. Smallest Safe Patch Directions
1. Molecule -> Program button
- Add one explicit “Open Program Workspace” action on molecule detail (header action or local subnav item) using existing `molecule.program_id`.

2. Molecule/batch/program navigability
- Add direct program link on batch detail header and keep molecule link; avoid structural rework.

3. Data-entry selector dependencies/autofill
- Add lightweight client-side selector coupling in existing `data_form.js` using already-rendered program/molecule/batch option data: filter molecules by selected program, filter batches by selected molecule, and auto-sync related selectors when one is chosen.

4. Batch launch prefill behavior
- When `/data/new` is opened with `batch_id`, resolve molecule/program from batch server-side and prefill those fields unless explicitly provided.

5. Program drill-down scope correctness
- Make list routes honor optional `program_id` filter (and reflect it in list context/header), reusing existing query-param links from Program Workspace.

6. Repeated data-entry flow
- Add one additional action path (“save + new with same context” or a context-preserving “new record” CTA on data detail) while preserving existing save/redirect behavior.

## 6. Recommended Next Move
Start with a single focused app patch covering two high-impact items together: (a) `/data/new` selector coupling/autofill, and (b) program-scoped registry filtering for drill-down destinations. Then apply the low-risk navigation CTA additions (molecule/batch -> program) and repeated-entry quality-of-life action.
