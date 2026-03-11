# TUTORIAL_1_REPORTS_UNITS_COMPANY_AUDIT

## 1. Executive Summary
The revised Tutorial 1 concept is directionally correct and much stronger than the prior version because it adds a company/board meeting checkpoint and explicit report generation.

Code-grounded findings:
- PSI has a real report-run system with four report types (`molecule_report`, `program_report`, `molecule_comparative_report`, `program_comparative_report`) and an upgrade-delta comparison surface.
- The proposed three-report checkpoint (program + single molecule + comparative molecules) is valid and directly supported by `/reports/new` and report detail templates.
- Units are present in PSI, but not universally required at validation time. They are represented at multiple layers (registry field metadata, extracted measurement unit column, and display fallbacks), with several caveats.
- To be fully code-aligned and comprehensive for report capability, the tutorial should explicitly include: report list/detail review, governance toggle in report detail, and upgrade-delta view; optionally add program-comparative report if strict completeness is desired.

High-level reassessment:
- The revised concept now supports a meaningful internal review checkpoint.
- It still leaves some implemented reporting/governance capability under-exercised unless extended.

## 2. Revised Tutorial 1 Concept Under Review
Concept audited:
1. Create `Tutorial 1` program.
2. Create `TUT1-A`, `TUT1-B`, `TUT1-C` baseline molecules.
3. Capture synthetic sequences and synthetic data.
4. Keep initial set blocked/non-advancing, with one best blocked parent.
5. Create improved child molecules via builder.
6. Progress one child furthest.
7. Insert an internal company/board meeting pause.
8. At that pause, generate:
- program report
- individual molecule report
- comparative molecules report
9. Include explicit units in experimental datasets wherever PSI supports/expects units.

## 3. Codebase Inventory of Report Capabilities

### 3.1 Report models and persisted run lifecycle
Primary model:
- [`ReportRun`](/home/zach/psi_codex/psi/core/models.py:835) in [`psi/core/models.py`](/home/zach/psi_codex/psi/core/models.py)
  - Fields: `report_type`, `subject_ids_json`, `as_of`, `policy_pins_json`, `snapshot_coverage_json`, `payload_json`, `created_at`.
  - Lifecycle is persisted run creation; detail views render from persisted payload.

Related model used by comparison reports:
- [`ComparabilityAssessment`](/home/zach/psi_codex/psi/core/models.py:810)

### 3.2 Report routers and user-facing flow
Router:
- [`psi/web/routers/reports.py`](/home/zach/psi_codex/psi/web/routers/reports.py)

User-facing flow:
- `GET /reports` -> list runs (`reports/list.html`)
- `GET /reports/new` -> generate form (`reports/new.html`)
- `POST /reports/new` -> create run and redirect to detail
- `GET /reports/{id}` -> report detail (`reports/detail.html`)
- `GET /reports/upgrade-delta?base=&cand=` -> policy/report delta view (`reports/upgrade_delta_detail.html`)

Selector APIs used by report form JS:
- `GET /reports/options/programs`
- `GET /reports/options/molecules?program_id=...`

### 3.3 Report services and types
Service orchestration:
- [`psi/services/reports_v3.py`](/home/zach/psi_codex/psi/services/reports_v3.py)
  - `generate_report_from_form(...)` validates report type and subject count constraints.
  - `get_report_run_detail(...)` enriches UI context (identity summary, citation maps, governance warnings).
  - `build_report_upgrade_delta_view(...)` computes changed/unchanged rows and policy-pin deltas.

Report engine:
- [`psi/services/report_engine.py`](/home/zach/psi_codex/psi/services/report_engine.py)
  - Supported report types:
    - `molecule_report`
    - `program_report`
    - `molecule_comparative_report`
    - `program_comparative_report`
  - Generator functions:
    - `generate_molecule_report_v0`
    - `generate_program_report_v0`
    - `generate_molecule_comparative_report_v0`
    - `generate_program_comparative_report_v0`

### 3.4 Report templates and rendered content
Templates:
- Form/list/detail:
  - [`reports/new.html`](/home/zach/psi_codex/psi/web/templates/reports/new.html)
  - [`reports/list.html`](/home/zach/psi_codex/psi/web/templates/reports/list.html)
  - [`reports/detail.html`](/home/zach/psi_codex/psi/web/templates/reports/detail.html)
- Board renderers:
  - [`reports/board_molecule_v3.html`](/home/zach/psi_codex/psi/web/templates/reports/board_molecule_v3.html)
  - [`reports/board_program_v3.html`](/home/zach/psi_codex/psi/web/templates/reports/board_program_v3.html)
  - [`reports/board_comparison_v3.html`](/home/zach/psi_codex/psi/web/templates/reports/board_comparison_v3.html)
- Upgrade delta:
  - [`reports/upgrade_delta_detail.html`](/home/zach/psi_codex/psi/web/templates/reports/upgrade_delta_detail.html)
  - [`reports/board_upgrade_delta_v3.html`](/home/zach/psi_codex/psi/web/templates/reports/board_upgrade_delta_v3.html)

Technical/gov layer in detail view:
- `reports/detail.html` includes a governance toggle (`Scientist` vs `Governance`) with localStorage mode persistence and hidden technical audit panel.

### 3.5 Operational limits and prerequisites by report type
From `generate_report_from_form(...)`:
- `molecule_report`: exactly 1 subject ID.
- `program_report`: exactly 1 subject ID.
- `molecule_comparative_report`: 2-5 subject IDs.
- `program_comparative_report`: 2-5 subject IDs.

Practical UI constraint:
- `reports/new.html` molecule selector is loaded by selected program; out-of-program molecule comparisons are easiest through Manual IDs.

### 3.6 Exists vs user-facing vs tutorial-exercisable vs importance
- `molecule_report`: exists, user-facing, tutorial-exercisable, high importance.
- `program_report`: exists, user-facing, tutorial-exercisable, high importance.
- `molecule_comparative_report`: exists, user-facing, tutorial-exercisable, high importance.
- `program_comparative_report`: exists, user-facing, tutorial-exercisable, medium/high (portfolio/leadership comparative scenario).
- `upgrade-delta`: exists, user-facing, tutorial-exercisable, medium (governance reproducibility/policy-change checkpoint).

## 4. Codebase Audit of Measurement / Units Handling

### 4.1 Where units are represented
1. **Measurement table column**
- `data_measurements.unit` exists in baseline schema:
  - [`psi/core/measurement_schema.py`](/home/zach/psi_codex/psi/core/measurement_schema.py)

2. **Extracted measurement records from results JSON**
- Extraction pipeline:
  - [`extract_measurements(...)`](/home/zach/psi_codex/psi/services/measurements.py)
- Unit derivation behavior:
  - Numeric strings with `%` suffix infer `unit='%'`.
  - Otherwise, extracted unit may be empty unless unit is embedded in value text or explicit fields are present.

3. **Registry field metadata**
- Data schema fields include `units` labels for UI display:
  - [`psi/core/registry.py`](/home/zach/psi_codex/psi/core/registry.py)
- These units are field metadata; they are not universally hard-required server-side.

4. **Report/fact-sheet rendering**
- Display path prefers measurement unit, then catalog unit fallback, then suffix fallback:
  - [`_display_value(...)` in `psi/services/fact_sheet.py`](/home/zach/psi_codex/psi/services/fact_sheet.py)

### 4.2 Where units appear in UI
- Data detail extracted measurements table has explicit unit column:
  - [`psi/web/templates/data/detail.html`](/home/zach/psi_codex/psi/web/templates/data/detail.html)
- Data form labels show units from registry schema metadata:
  - [`psi/web/static/data_form.js`](/home/zach/psi_codex/psi/web/static/data_form.js)
- Evidence forms can carry unit-containing cited data paths (indirect, via citations and optional inline data creation):
  - [`psi/web/static/evidence_form.js`](/home/zach/psi_codex/psi/web/static/evidence_form.js)
- Report molecule fact sheet displays values with units where resolved:
  - [`reports/board_molecule_v3.html`](/home/zach/psi_codex/psi/web/templates/reports/board_molecule_v3.html)

### 4.3 Unit handling constraints and caveats
- Units are **not globally required** by create/update data routes.
- Structured form fields often imply units by metric key names and field labels, but explicit unit persistence depends on results payload content and extraction behavior.
- Bulk import explicitly includes a `unit` column and validates that column presence in input header:
  - [`psi/services/bulk_import.py`](/home/zach/psi_codex/psi/services/bulk_import.py)
- Test contracts confirm nuanced behavior:
  - Unit can be shown from measurement unit and should not degrade to `n cited` in fact sheet cell display.
  - `ec50` without measurement unit should **not** imply catalog unit automatically.
  - Suffix fallback may add units for suffix-convention keys (e.g., `_pct`).
  - See [`tests/test_v3_molecule_report_schema.py`](/home/zach/psi_codex/tests/test_v3_molecule_report_schema.py).

### 4.4 Tutorial implication for units
- Treat units as a tutorial-wide discipline for realism and report readability.
- But this is a **tutorial rule**, not a strict backend validation rule for every data path.

## 5. Best Design for the Tutorial’s Company / Board Meeting Checkpoint

### 5.1 Recommended checkpoint count and placement
Best code-aligned structure is **two checkpoints**:

1. **Checkpoint A (baseline review)**
- After entering baseline A/B/C data and creating initial tasks/evidence/claims.
- Purpose: establish blocked state and choose best blocked parent.

2. **Checkpoint B (post-optimization review)**
- After child variants are created and improved data/evidence are captured.
- Purpose: select emerging lead and decide next-stage execution posture.

### 5.2 Surfaces immediately before each checkpoint
Before each meeting checkpoint, review:
- Program strategy/detail: [`/programs/{id}`]
- Development board: [`/programs/{id}/board`]
- Program workflow center: [`/programs/{id}/workflow`]
- Key molecule detail (candidate + comparator)

This aligns meeting decisions with operational state, not just static report output.

### 5.3 Report generation order (recommended)
For each checkpoint:
1. **Program report** (`program_report`) first
- Program-wide posture, candidate set, risk/blockers, next-best experiments.
2. **Single-molecule report** (`molecule_report`) second
- Fact sheet, coverage, artifacts, molecule-level evidence framing.
3. **Comparative molecules report** (`molecule_comparative_report`) third
- Relative stage/confidence/comparability across candidate molecules.

### 5.4 What these reports answer in internal review terms
- Program report: “Is this program investable for next cycle right now?”
- Molecule report: “What is true about this specific candidate and its evidence/coverage quality?”
- Comparative molecule report: “Which molecule should receive next marginal effort and budget?”

### 5.5 Additional paired surfaces for operational realism
To make the checkpoint feel like a real internal biotech review, pair reports with:
- Decision snapshots (`/decisions/*`) for governance trace and verification.
- Portfolio overview (`/portfolio`) for cross-program resource framing.
- Program narrative view (`/programs/{id}/narrative`) for leadership-readable synthesis.

## 6. Report Readiness Requirements for:

### Program report
**Minimal prerequisites (code-valid):**
- Program exists.
- At least one molecule in program.
- Report run can still be generated with sparse payload.

**Ideal prerequisites (meaningful tutorial output):**
- Multiple molecules in program with mixed stages/signals.
- DI snapshots available for stage/posture context.
- Some comparability rows and measurement key coverage.
- Active tasks/plans/claims and recent evidence for narrative usefulness.

### Individual molecule report
**Minimal prerequisites:**
- Molecule exists.
- `molecule_report` can run without rich data.

**Ideal prerequisites:**
- Batch + data records + extracted measurements.
- Unit-aware measurement values for readable fact sheet.
- At least one decision snapshot and artifacts/citations.

### Comparative molecules report
**Minimal prerequisites:**
- 2-5 molecule IDs.

**Ideal prerequisites:**
- All selected molecules have recent snapshots and data coverage.
- Distinct measurement-key presence and risk profiles.
- Comparability assessments present (otherwise surface remains partially not assessed).

## 7. Coverage Reassessment of the Revised Tutorial Concept
With report checkpoint and units added, coverage improves materially.

What is now well covered:
- Core molecule/program execution loop.
- Builder-derived progression narrative.
- Scientist interpretation via evidence/claims/plans.
- Meeting-style readout using major report types.

What remains not fully comprehensive for report capability:
- `program_comparative_report` is not in the stated checkpoint set.
- `reports/upgrade-delta` governance comparison is not explicitly included.
- Report list management/review path (`/reports`) and governance toggle in report detail are not explicitly called out.

Therefore, report capability coverage is strong but still not exhaustive.

## 8. Remaining Gaps / Blind Spots
Even after these additions, remaining under-covered areas include:
- Full decision/governance cycle depth (decision verify/history/compare/outcome labels/export).
- Report upgrade-delta (base vs candidate run comparison).
- Program-comparative reporting (if strict report-system coverage goal).
- Some QC-heavy flows (per-measurement review patterns) unless explicitly scripted.
- Portfolio/leadership narrative/export linkage at meeting time if only program-level review is performed.

## 9. Recommended Revised Tutorial Phase Outline

### Phase 1: Setup and baseline candidates
- Create program `Tutorial 1`.
- Create `TUT1-A/B/C` and baseline batches/data.
- Ensure explicit units in all synthetic assay/result entries where field semantics require or imply measurement quantities.

### Phase 2: Baseline loop closure
- Create tasks; run task statuses across workflow buckets.
- Capture data from task handoff.
- Review measurements/QC.
- Create evidence; create/transition claims and plans.

### Phase 3: Company Meeting Checkpoint A (baseline)
- Review program detail, board, workflow.
- Generate reports in order: program -> single molecule (best blocked) -> comparative molecules.
- Record decision rationale for selecting best blocked parent.

### Phase 4: Builder optimization
- Derive child molecules from selected parent via builder flows.
- Enter improved synthetic data with explicit units.
- Update evidence/claims/plans/tasks.

### Phase 5: Company Meeting Checkpoint B (post-optimization)
- Repeat report triad (program, lead-child molecule, comparative set including children).
- Optionally include report upgrade-delta for governance-style comparison.
- Select furthest-progressing child as tutorial lead.

### Phase 6: Governance and leadership closeout
- Inspect decision snapshot surfaces tied to progression claims.
- Review portfolio + program narrative surfaces.
- Export at least one narrative/report artifact for leadership-style communication.

## 10. Appendix: Key code locations examined

Reports:
- [`psi/core/models.py`](/home/zach/psi_codex/psi/core/models.py)
- [`psi/web/routers/reports.py`](/home/zach/psi_codex/psi/web/routers/reports.py)
- [`psi/services/reports_v3.py`](/home/zach/psi_codex/psi/services/reports_v3.py)
- [`psi/services/report_engine.py`](/home/zach/psi_codex/psi/services/report_engine.py)
- [`psi/services/fact_sheet.py`](/home/zach/psi_codex/psi/services/fact_sheet.py)
- [`psi/services/v3_narrative.py`](/home/zach/psi_codex/psi/services/v3_narrative.py)
- [`psi/web/templates/reports/new.html`](/home/zach/psi_codex/psi/web/templates/reports/new.html)
- [`psi/web/templates/reports/list.html`](/home/zach/psi_codex/psi/web/templates/reports/list.html)
- [`psi/web/templates/reports/detail.html`](/home/zach/psi_codex/psi/web/templates/reports/detail.html)
- [`psi/web/templates/reports/board_program_v3.html`](/home/zach/psi_codex/psi/web/templates/reports/board_program_v3.html)
- [`psi/web/templates/reports/board_molecule_v3.html`](/home/zach/psi_codex/psi/web/templates/reports/board_molecule_v3.html)
- [`psi/web/templates/reports/board_comparison_v3.html`](/home/zach/psi_codex/psi/web/templates/reports/board_comparison_v3.html)
- [`psi/web/templates/reports/upgrade_delta_detail.html`](/home/zach/psi_codex/psi/web/templates/reports/upgrade_delta_detail.html)

Data/measurements/units:
- [`psi/core/measurement_schema.py`](/home/zach/psi_codex/psi/core/measurement_schema.py)
- [`psi/core/registry.py`](/home/zach/psi_codex/psi/core/registry.py)
- [`psi/services/measurements.py`](/home/zach/psi_codex/psi/services/measurements.py)
- [`psi/services/data_records.py`](/home/zach/psi_codex/psi/services/data_records.py)
- [`psi/services/metric_catalog.py`](/home/zach/psi_codex/psi/services/metric_catalog.py)
- [`psi/services/bulk_import.py`](/home/zach/psi_codex/psi/services/bulk_import.py)
- [`psi/web/routers/data_records.py`](/home/zach/psi_codex/psi/web/routers/data_records.py)
- [`psi/web/templates/data/form.html`](/home/zach/psi_codex/psi/web/templates/data/form.html)
- [`psi/web/templates/data/detail.html`](/home/zach/psi_codex/psi/web/templates/data/detail.html)
- [`psi/web/static/data_form.js`](/home/zach/psi_codex/psi/web/static/data_form.js)
- [`psi/web/templates/data/bulk_import.html`](/home/zach/psi_codex/psi/web/templates/data/bulk_import.html)

Related meeting/context surfaces:
- [`psi/web/routers/programs.py`](/home/zach/psi_codex/psi/web/routers/programs.py)
- [`psi/web/templates/programs/detail.html`](/home/zach/psi_codex/psi/web/templates/programs/detail.html)
- [`psi/web/templates/programs/board.html`](/home/zach/psi_codex/psi/web/templates/programs/board.html)
- [`psi/web/templates/programs/workflow.html`](/home/zach/psi_codex/psi/web/templates/programs/workflow.html)
- [`psi/web/routers/portfolio.py`](/home/zach/psi_codex/psi/web/routers/portfolio.py)
- [`psi/web/templates/portfolio/overview.html`](/home/zach/psi_codex/psi/web/templates/portfolio/overview.html)

Tests:
- [`tests/test_v3_report_contracts.py`](/home/zach/psi_codex/tests/test_v3_report_contracts.py)
- [`tests/test_v3_reports_ui_identity.py`](/home/zach/psi_codex/tests/test_v3_reports_ui_identity.py)
- [`tests/test_v3_molecule_report_schema.py`](/home/zach/psi_codex/tests/test_v3_molecule_report_schema.py)
- [`tests/test_report_payload_only_rendering.py`](/home/zach/psi_codex/tests/test_report_payload_only_rendering.py)
- [`tests/test_molecule_report_artifacts.py`](/home/zach/psi_codex/tests/test_molecule_report_artifacts.py)
- [`tests/test_v3_narrative_measurement_wiring.py`](/home/zach/psi_codex/tests/test_v3_narrative_measurement_wiring.py)

---

## Final Required Verdicts

1. **Does the revised Tutorial 1 concept now include a code-aligned and meaningful company/board meeting checkpoint?**
- **Mostly**
- Reason: The added report pause is code-aligned and meaningful, but it becomes fully operationally realistic only when explicitly paired with board/workflow/detail context and at least one governance-oriented surface.

2. **Are explicit measurement units required strongly enough that they should be treated as a tutorial-wide rule?**
- **Mostly**
- Reason: Backend validation does not require units everywhere, but UI/report clarity and scientific realism are materially better with explicit units. There are known fallback/ambiguity behaviors (including `ec50` unit caveat), so a tutorial-wide unit rule is strongly advisable.

3. **Is the revised Tutorial 1 concept now comprehensive enough to exercise PSI’s implemented report capability?**
- **Mostly**
- Reason: It now covers the three most central report workflows, but not full report capability breadth (`program_comparative_report`, upgrade-delta comparison, and governance-mode review patterns) unless those are added explicitly.
