# PSI Tutorial 1 Audit & Specification (v1.3.0d107)

## 1. Executive Summary
- Overall tutorial viability: **High**, but the current draft is not yet trustworthy as a beginner walkthrough without targeted updates.
- Biggest mismatches with current PSI:
  - Phase 4 is stale. It assumes no DI evaluation before manual DI run, but `/data/new` now auto-refreshes current assessment after save.
  - Tutorial still uses older “Data Record / Results” wording in several places; the UI now emphasizes **Experiment Result** language.
  - Final-state expectations over-promise: with the current dataset and current DI policy gates, “A3 fully ready” is not guaranteed.
- Biggest beginner-UX risks:
  - Molecule structured-sequence entry path appears inconsistent in code (form field names vs router extraction names), creating risk for Builder-dependent steps.
  - Navigation between Program Workspace, Program Workflow, Board, and supporting registries remains non-obvious without explicit guidance.
  - Reports and some advanced DI/gov surfaces still expose technical tokens that need explicit tutorial translation.

## 2. Phase-by-Phase Validation of Existing Tutorial

| Tutorial Phase | Status | What is still correct | What must change | Beginner-risk notes |
|---|---|---|---|---|
| Phase 1 — Create Program | VALID BUT NEEDS UI/LANGUAGE UPDATES | `/programs/new` exists; save redirects to Program Workspace `/programs/{id}`. | Keep user-facing wording tied to “Program Workspace.” | Low risk. |
| Phase 2 — Create Initial Molecules | PARTIALLY BROKEN / NEEDS REWORK | Molecule create surface exists (`/molecules/new`), IgG mode exists, structured fields are visible in template. | Re-validate structured sequence persistence. Template uses `HC1/LC1` field names while router component extractor reads lowercase keys (`hc1/lc1`). | High risk: Builder may fail if parent has no structured components. |
| Phase 3 — Enter Initial Characterization Data | VALID BUT NEEDS UI/LANGUAGE UPDATES | Batch creation, result capture, schema-driven fields all exist; baseline order is executable. | Replace “Results → New Data Record” wording with “Experiment Results → Add Experiment Result.” | Medium risk: users can get lost if workflow return path is not explicit. |
| Phase 4 — Baseline Board Checkpoint | PARTIALLY BROKEN / NEEDS REWORK | Board route `/programs/{id}/board` is correct. | Must reflect DI-driven board semantics in d107: baseline molecules are not necessarily “Not Evaluated” after result entry because auto-refresh runs on save. Also board label is “Assessment Pending,” not “Not Evaluated.” | High risk: current instructions teach wrong interpretation. |
| Phase 5 — Builder Variants | VALID BUT NEEDS UI/LANGUAGE UPDATES | Builder point-mutation flow exists (`/builder/point-mutation`) and supports draft→create flow. | Confirm parent molecule has structured components before this phase. Keep exact button labels: “Build draft,” then “Create molecule from draft.” | Medium-high risk if Phase 2 structured entry failed. |
| Phase 6 — Improved In Vitro Results | VALID BUT NEEDS UI/LANGUAGE UPDATES | All listed assay families are schema-supported. | Use Experiment Result terminology consistently; clarify that improvement in raw data does not always equal DI-ready status. | Medium risk due expected-outcome assumptions. |
| Phase 7 — PK Data | VALID AS WRITTEN | `PK_PD/NONCOMPARTMENTAL` exists with matching fields (cmax, auc, half-life, units fields). | Keep explicit units fields (`cmax_units`, `auc_units`). | Low-medium risk. |
| Phase 8 — Biodistribution Data | VALID BUT NEEDS UI/LANGUAGE UPDATES | Biodistribution can be represented through `PK_PD` with `matrix=tissue` + PD marker/effect text. | Keep explicit note that this is a proxy path, not a dedicated biodistribution schema. | Medium risk if users expect a first-class “biodistribution” type. |
| Phase 9 — In Vivo Efficacy Data | VALID AS WRITTEN | `IN_VIVO_EFFICACY/NOD` form path and fields exist. | Keep field names aligned with schema (`primary_outcome_value`, `primary_outcome_units`, etc.). | Low risk. |
| Phase 10 — Evidence and Claims | VALID BUT NEEDS UI/LANGUAGE UPDATES | Evidence, claims, plans surfaces exist. Evidence can be created from existing results and requires citations. | Frame as optional interpretation/governance layer in core path. | Medium risk: users may think this is computationally required for DI. |
| Phase 11 — Reports | VALID BUT NEEDS UI/LANGUAGE UPDATES | Program, molecule, and molecule comparative reports are supported. | Use exact UI labels: “Generate Report” and technical report type tokens (`program_report`, etc.). | Medium risk: report-type labels are technical. |
| Phase 12 — Final Decision Flow | PARTIALLY BROKEN / NEEDS REWORK | `/di/run` and decision detail/history surfaces are valid. | Primary flow now defaults to canonical progression. Advanced decision/package selectors are in “Advanced governance options.” Button is “Run Development Assessment,” not “Run DI.” | High risk: current text overstates deterministic final outcome with this dataset. |

## 3. Synthetic Dataset Compatibility Report

### Sequences
- Existing tutorial sequence set is generally reusable.
- **Critical compatibility risk:** molecule form/router mismatch for structured inputs.
  - Template fields: `name="HC1"`, `"LC1"`, `"HC2"`, `"LC2"` in [`/home/zach/psi_codex/psi/web/templates/molecules/form.html`].
  - Router extractor reads lowercase keys `hc1/lc1/hc2/lc2` in [`/home/zach/psi_codex/psi/web/routers/molecules.py`].
  - Service requires HC1/LC1 only when `components` are passed; otherwise creation falls back to legacy/unstructured path in [`/home/zach/psi_codex/psi/services/molecules.py`].
- Practical implication: tutorial sequence steps need explicit validation instructions and fallback guidance, or this can break Builder continuity.

### Builder Mutations
- Point mutation flow and syntax are supported (`component`, `mutations`, `Build draft` → `Create molecule from draft`) via [`/home/zach/psi_codex/psi/web/templates/builder/point_mutation.html`] and builder services.
- Builder requires parent structured components; otherwise draft errors (“Parent molecule has no structured components to derive from.”) from [`/home/zach/psi_codex/psi/services/builder.py`].

### Batches
- Batch creation flow and molecule linkage are stable (`/batches/new`, batch auto IDs) in [`/home/zach/psi_codex/psi/web/templates/batches/form.html`].

### Result-entry schemas and field compatibility
- Tutorial assay families map to current registry:
  - `EXPRESSION/TRANSIENT_HEK`
  - `SEC/SEC`
  - `ENDOTOXIN/LAL`
  - `BINDING/SPR`
  - `CELL_ASSAY/KILLING`
  - `PK_PD/NONCOMPARTMENTAL`
  - `IN_VIVO_EFFICACY/NOD`
- Source: [`/home/zach/psi_codex/psi/core/registry.py`].

### Field names and units/validation risks
- Scientific notation values are accepted by measurement extraction regex (`8.2e4`, `1.1e-2`) in [`/home/zach/psi_codex/psi/services/measurements.py`].
- Batch requirement is enforced server-side for batch-scoped data types in [`/home/zach/psi_codex/psi/services/data_records.py`].
- **Load-bearing DI compatibility risk:** policy gates require some canonical metric keys that current tutorial often provides only via non-canonical fields.
  - Policy requires `lmw_pct` but tutorial uses mainly `lmw_percent`.
  - Policy conditionally requires internalization/surface-expression when `kd_nM` exists.
  - Source: [`/home/zach/psi_codex/psi/core/di/policies/advance_to_in_vivo_v0_5.json`].

### Redundant or unsupported records
- Tutorial includes both canonical and legacy binding/endotoxin keys; this is acceptable and can be useful for compatibility.
- Some values may be computationally redundant for DI but still valid for report/evidence narrative.

### DI/report/evidence/claim/plan compatibility with same dataset
- DI auto-refresh runs after create/edit experiment result saves via [`/home/zach/psi_codex/psi/web/routers/data_records.py`].
- Reports are compatible with this dataset if subject IDs are selected correctly.
- Evidence/claims/plans are supported but not required for DI computation.

## 4. Current UI Language / Label Corrections

Use these exact labels in tutorial text (current d107 UI):
- Top nav `Experiment Results` (not “Results”).
- Data capture page title: `Capture Experiment Result`.
- Save button: `Save Experiment Result`.
- Secondary save button: `Save and add another result`.
- Program workflow page: `{Program Name} Program Workflow`.
- Workflow CTA: `Add Experiment Result`.
- Board CTA: `Open Board`.
- Board pending column label: `ASSESSMENT PENDING`.
- Board summary label: `Assessment pending`.
- DI run page title: `Run Development Assessment`.
- DI run submit button: `Run Development Assessment`.
- Manual legacy decisions page title: `Legacy YAML Assessment (Advanced)`.
- Reports page primary CTA: `Generate Report`.
- Report run page title: `Generate Report` and report type tokens are still technical (`program_report`, `molecule_report`, `molecule_comparative_report`).

Primary source templates:
- [`/home/zach/psi_codex/psi/web/templates/base.html`]
- [`/home/zach/psi_codex/psi/web/templates/data/form.html`]
- [`/home/zach/psi_codex/psi/web/templates/programs/workflow.html`]
- [`/home/zach/psi_codex/psi/web/templates/programs/board.html`]
- [`/home/zach/psi_codex/psi/web/templates/di/run.html`]
- [`/home/zach/psi_codex/psi/web/templates/reports/list.html`]

## 5. Beginner Navigation Model

### Recommended home base
- Primary home base: **Program Workflow** (`/programs/{program_id}/workflow`).
- Reason: it centralizes ready/in-progress/blocked/awaiting-data queues and result-capture entry links.

### Safest page-to-page workflow
1. `Programs` → open `Tutorial 1` Program Workspace.
2. Click `Open Program Workflow`.
3. Use `Add Experiment Result` or `Start result capture` links from workflow.
4. After save, use `Continue in Program Workflow` from result detail.
5. Use `Open Board` for posture checks.
6. Use `Back to Program` for strategy-level actions (new molecule/report drill-down).

### Places tutorial should add extra explanation/screenshots
- First transition from Program Workspace to Program Workflow.
- Difference between Program Workspace and Development Board.
- Data form scope selectors (Program/Molecule/Batch coupling).
- Report generation selector UX (technical report type tokens).
- DI run page: scientist default vs advanced governance details.
- Molecule structured sequence entry and verification of saved structured components.

### Places that should be explicitly marked optional
- Evidence creation.
- Claim creation.
- Plan creation.
- Legacy YAML decisions path (`/decisions/new`).

## 6. PSI Feature Coverage Map

### Covered well by current tutorial concept
- Programs and Program Workspace.
- Molecule creation.
- Batch creation and batch-linked capture.
- Experiment Result capture (`/data/new`) and review (`/data/{id}`).
- Program Workflow execution loop.
- Program Development Board review.
- Reports: program, molecule, comparative.
- DI run (`/di/run`) and decision detail/history basics.

### Partially covered
- Builder continuity from structured parent sequence to child variants (due structured-input persistence risk).
- Evidence/claim/plan framing as optional interpretation layers.
- Current assessment semantics after each save (tutorial currently under-emphasizes this d107 behavior).

### Missing or under-covered
- QC actions on extracted measurements (approve/reject per result detail).
- Decision history compare/verify/export flows.
- Program narrative and governance lineage surfaces.
- Portfolio Intelligence and cross-program prioritization surfaces.
- Files/attachments flow for experiment artifacts.

### Should remain optional for Tutorial 1
- Legacy YAML decision run path.
- Deep governance verification/compare/export.
- Portfolio-level operations.
- Advanced plan lifecycle transitions beyond a simple demonstration.

## 7. Expected Tutorial Outcomes

### Expected state progression (code-aligned)
- After baseline result capture in Phase 3:
  - A/B/C should appear on board, but not necessarily in “Assessment Pending,” because save triggers DI refresh.
  - Board grouping reflects latest snapshot-derived status (`Ready`, `Failed Criteria`, `Missing Data`, `Assessment Pending`).
- After child variant result capture (Phases 6–9):
  - A1/A2/A3 should receive refreshed current assessments after each relevant save.
  - A3 should look strongest comparatively, but may still be blocked or missing specific gate requirements.

### Expected DI behavior
- Auto-refresh on create/edit experiment result is expected and tested.
  - Source: [`/home/zach/psi_codex/tests/test_data_auto_assessment_refresh.py`].
- Board status is snapshot-based and updates with latest active snapshot.
  - Source: [`/home/zach/psi_codex/psi/services/dev_board.py`].

### Reports
- Program/molecule/comparative report generation should succeed with valid subject selections.
- Comparative reports require 2–5 selected subjects.
  - Source: [`/home/zach/psi_codex/psi/services/reports_v3.py`].

### Evidence/claim/plan flows
- Evidence creation requires at least one cited data record.
  - Source: [`/home/zach/psi_codex/psi/services/evidence.py`].
- Claims/plans are operationally available and can be exercised, but are not DI prerequisites.

### Final posture realism with current dataset
- Current tutorial likely **over-promises deterministic “advance A3” readiness**.
- Reasons:
  - Gate dependency on internalization/surface-expression when `kd_nM` is present.
  - Potential canonical-key mismatch risk (e.g., `lmw_pct` expectations).
- Recommended final tutorial language should be: strongest candidate posture with explicit review of remaining blockers, unless dataset is adjusted to satisfy all required gates.

## 8. Information Required to Write the Final Tutorial

### Required confirmed facts
- Exact current labels and CTA text on all core pages (Program Workspace, Workflow, Board, Experiment Result, DI run, Reports).
- Exact schema keys/methods for all assay families in the fixed dataset.
- Exact board semantics post-d107 (auto-assessment refresh + snapshot grouping).
- Exact DI run primary flow semantics (canonical chain default, advanced options collapsed).
- Exact evidence citation constraints by evidence type.

### Optional but helpful confirmations
- One runtime spot-check that structured HC/LC sequence entry persists into `MoleculeComponent` rows for tutorial-created molecules.
- One runtime spot-check of final A3 board/assessment state using the fixed dataset.
- One runtime spot-check that tutorial report sequence generates all three reports without manual-ID fallback.

### Unresolved ambiguities
- Structured-sequence form field name mismatch risk may invalidate builder steps if not mitigated.
- The fixed dataset may not satisfy all canonical progression gates for a fully “ready” endpoint.
- Report type labels remain technical and can confuse first-time users unless tutorial explicitly translates them.

## 9. Recommended Tutorial Structure

1. Orientation and navigation map (home base = Program Workflow).
2. Program creation.
3. Molecule creation with explicit structured-sequence validation checkpoint.
4. Batch creation for baseline molecules.
5. Baseline experiment-result capture (ordered sequence, workflow-return loop).
6. Board/workflow checkpoint framed as **current assessment state review**, not “DI not run yet.”
7. Builder variant generation from validated parent.
8. Child batch creation.
9. Improved in vitro capture.
10. PK capture.
11. Biodistribution proxy capture (`PK_PD` tissue context).
12. In vivo efficacy capture.
13. Optional interpretation layer: evidence, claims, plan.
14. Report checkpoint (program, molecule, comparative).
15. Final DI review via `/di/run` canonical flow.
16. Final conclusion framed as strongest-candidate recommendation with explicit gate/blocker readout.

## 10. Follow-On Patch Opportunities

Tutorial-enabling UX fixes discovered during this audit (not broad redesign):
- Molecule structured input reliability: align form field names and router extractor keys so HC/LC structured entries persist deterministically.
- Board local-nav wording consistency: update any residual “Not Evaluated” descriptor labels to “Assessment Pending.”
- Report-type UX polish: add human-readable labels next to technical report type tokens on `/reports/new`.
- Program-scoped prefill consistency: ensure links like `/molecules/new?program_id=...` visibly preselect program context.
- Final-state transparency: expose gate-level missing requirements more directly on post-save/result surfaces so tutorials can cite them without deep decision-page navigation.

---

### Key code locations used in this audit
- Tutorial baseline: `/home/zach/psi_codex/TUTORIAL_1_FINAL_REVISED_vNEXT.md`
- Version and patch context: `/home/zach/psi_codex/psi/version.py`, `/home/zach/psi_codex/PATCH_NOTES.md`
- Core routes/templates:
  - `/home/zach/psi_codex/psi/web/templates/base.html`
  - `/home/zach/psi_codex/psi/web/templates/programs/detail.html`
  - `/home/zach/psi_codex/psi/web/templates/programs/workflow.html`
  - `/home/zach/psi_codex/psi/web/templates/programs/board.html`
  - `/home/zach/psi_codex/psi/web/templates/data/form.html`
  - `/home/zach/psi_codex/psi/web/templates/data/detail.html`
  - `/home/zach/psi_codex/psi/web/templates/molecules/form.html`
  - `/home/zach/psi_codex/psi/web/templates/molecules/detail.html`
  - `/home/zach/psi_codex/psi/web/templates/batches/form.html`
  - `/home/zach/psi_codex/psi/web/templates/batches/detail.html`
  - `/home/zach/psi_codex/psi/web/templates/builder/index.html`
  - `/home/zach/psi_codex/psi/web/templates/builder/point_mutation.html`
  - `/home/zach/psi_codex/psi/web/templates/evidence/form.html`
  - `/home/zach/psi_codex/psi/web/templates/claims/new.html`
  - `/home/zach/psi_codex/psi/web/templates/plans/new.html`
  - `/home/zach/psi_codex/psi/web/templates/reports/list.html`
  - `/home/zach/psi_codex/psi/web/templates/reports/new.html`
  - `/home/zach/psi_codex/psi/web/templates/di/run.html`
  - `/home/zach/psi_codex/psi/web/templates/decisions/list.html`
  - `/home/zach/psi_codex/psi/web/templates/decisions/new.html`
- Services/logic:
  - `/home/zach/psi_codex/psi/core/registry.py`
  - `/home/zach/psi_codex/psi/services/data_records.py`
  - `/home/zach/psi_codex/psi/services/measurements.py`
  - `/home/zach/psi_codex/psi/services/current_assessment.py`
  - `/home/zach/psi_codex/psi/services/development_progression.py`
  - `/home/zach/psi_codex/psi/services/dev_board.py`
  - `/home/zach/psi_codex/psi/services/workflow_center.py`
  - `/home/zach/psi_codex/psi/services/evidence.py`
  - `/home/zach/psi_codex/psi/services/reports_v3.py`
  - `/home/zach/psi_codex/psi/core/di/policies/advance_to_in_vivo_v0_5.json`
- Routers:
  - `/home/zach/psi_codex/psi/web/routers/programs.py`
  - `/home/zach/psi_codex/psi/web/routers/molecules.py`
  - `/home/zach/psi_codex/psi/web/routers/batches.py`
  - `/home/zach/psi_codex/psi/web/routers/builder.py`
  - `/home/zach/psi_codex/psi/web/routers/data_records.py`
  - `/home/zach/psi_codex/psi/web/routers/evidence.py`
  - `/home/zach/psi_codex/psi/web/routers/claims.py`
  - `/home/zach/psi_codex/psi/web/routers/plans.py`
  - `/home/zach/psi_codex/psi/web/routers/reports.py`
  - `/home/zach/psi_codex/psi/web/routers/di.py`
  - `/home/zach/psi_codex/psi/web/routers/decisions.py`
- Tests:
  - `/home/zach/psi_codex/tests/test_data_auto_assessment_refresh.py`
  - `/home/zach/psi_codex/tests/test_program_board_surface.py`
  - `/home/zach/psi_codex/tests/test_di_run_surface.py`
  - `/home/zach/psi_codex/tests/test_program_scoped_registry_filters.py`
  - `/home/zach/psi_codex/tests/test_data_form_selector_metadata.py`
