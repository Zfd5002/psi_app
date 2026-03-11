# PSI Workflow Simplification Audit (Read-Only)

## 1. Executive Summary

PSI’s current scientist workflow is operationally rich but layered: `DataRecord -> extracted measurements -> (optional) Evidence -> (optional) Claim/Plan -> DecisionSnapshot-driven surfaces`.

High-confidence findings from code:
- **DI does not require Evidence or Claims to compute** in the canonical path. DI reads extracted measurement rows (`data_measurements`) selected by metric/QC/as-of rules, then writes immutable `DecisionSnapshot`s.
- **Data capture is load-bearing**: creating/updating a data record extracts measurements and then auto-refreshes molecule assessment synchronously.
- **Evidence/Claim layers are largely interpretive/governance and workflow-bridging**, not hard computational prerequisites for DI.
- **Usability burden comes mostly from manual translation across layers** (result entry, then evidence narrative, then claim narrative), while DI computation itself is measurement-centric.

Biggest usability risks:
- Repeated manual restatement of scientific meaning across DataRecord/Evidence/Claim layers.
- Scientist-facing workflow encourages full loop completion, but minimal DI unlock path is shorter than the visible conceptual chain.

Biggest structural insight:
- PSI has a dual nature: a measurement-driven deterministic DI engine plus governance/interpretation layers. The engine can run with a narrower input set than the full scientist workflow model suggests.

---

## 2. Audit 1 — Real Workflow Trace

### Step-by-step workflow (actual code path)

### Step 0: Establish scope (Program/Molecule/Batch)
Scientist action
-> Create Program / Molecule / Batch
-> UI routes: `/programs/new`, `/molecules/new`, `/batches/new`
-> Backend: program/molecule/batch routers/services
-> DB entities: `programs`, `molecules`, `batches`
-> Downstream effects: scope available for data capture and DI lineage resolution
-> DI effect: none yet

### Step 1: Capture experiment result (primary load-bearing step)
Scientist action
-> Submit Data Record form
-> UI page/route: `GET /data/new` -> `POST /data/new` (`psi/web/routers/data_records.py:183-388`)
-> Backend functions:
- `create_data()` router (`psi/web/routers/data_records.py:285-388`)
- `create_data_record()` service (`psi/services/data_records.py:127-217`)
- `extract_measurements()` (`psi/services/measurements.py:80-119`)
- `upsert_measurements()` (`psi/services/measurements.py:292+`)
-> DB entities written:
- `data_records`
- `data_measurements` (derived rows)
- `audit_events`
-> Downstream effects:
- board cache invalidated (`psi/services/data_records.py:215`)
- optional task linkage/status updates when `task_id` present (`psi/web/routers/data_records.py:330-345`)
-> DI effect:
- auto refresh is called in same request (`refresh_current_assessment_for_molecule`, `psi/web/routers/data_records.py:347-360`)
- DI run writes new immutable `decision_snapshots` via `run_di` (`psi/services/di/runner.py:690-803`)

### Step 2: Measurement selection and policy evaluation
Scientist action
-> none (automatic after save)
-> Backend:
- DI selector: `select_batch_measurements()` (`psi/services/di/selectors.py:53-260`)
- DI compute: `compute_di_output()` + template eval (`psi/services/di/runner.py:833+`, `psi/services/di/compute.py`)
-> DB entities read:
- `data_measurements` joined with `data_records`
- `measurement_qc` where present
-> DB entities written:
- `decision_snapshots` (new active snapshot supersedes prior active snapshot for same scope)
-> DI effect:
- current molecule/program board posture updated from latest snapshot

### Step 3: Review current assessment
Scientist action
-> Open Data detail, Molecule detail, Program board/workflow
-> UI routes:
- `/data/{id}` (`psi/web/routers/data_records.py:391-417`)
- `/molecules/{id}` (molecule detail templates consume DI bundle/progression)
- `/programs/{id}/board` (`psi/web/routers/programs.py:114-167`)
-> Backend:
- board model from latest snapshot per molecule (`psi/services/dev_board.py:286-371`)
-> DB entities read:
- `decision_snapshots` + molecules/tasks
-> DI effect:
- grouped status shown as ready/failed/missing_data/not_evaluated

### Step 4 (optional): Create Evidence
Scientist action
-> Create evidence citing one or more data records
-> UI route: `/evidence/new`
-> Backend: `create_evidence()` (`psi/services/evidence.py:46-122`)
-> DB entities written:
- `evidence`
- `evidence_citations`
- `audit_events`
-> Downstream effects:
- interpretation linkage and traceability; pending interpretation queue clears when records are cited (`psi/services/workflow_center.py:53-64`)
-> DI effect:
- **none directly in canonical DI compute path**

### Step 5 (optional): Create Claim/Plan/Task links
Scientist action
-> Create claim and optionally link records/decisions/tasks; create plans
-> UI routes: `/claims/new`, `/plans/new`
-> Backend: `create_claim()` etc. (`psi/services/claims.py:105+`)
-> DB entities written:
- `scientific_claims`
- link tables (`scientific_claim_*_links`)
- `scientific_plans`, `scientific_plan_steps`
-> DI effect:
- **no direct requirement for DI calculation**

### Step 6 (optional/manual): Explicit DI run (advanced/governance path)
Scientist action
-> Run `/di/run` or legacy `/decisions/new`
-> UI routes:
- canonical DI form `/di/run` (`psi/web/routers/di.py`)
- legacy YAML path `/decisions/new` (`psi/web/routers/decisions.py:23-54`)
-> Backend:
- canonical path calls `run_di` directly
- legacy path `run_and_snapshot()` reads Evidence-centric inputs (`psi/services/decisions.py:312+`)
-> DI effect:
- additional snapshots; governance/audit history preserved

### Mandatory vs optional for DI output
Mandatory (canonical current-assessment path):
- Program/Molecule/Batch lineage
- DataRecord with parsable results -> extracted measurement rows
- DI policy metric keys/thresholds satisfied or missing/failing
- snapshot write path

Optional for canonical DI computation:
- Evidence creation
- Claim creation
- Plan creation
- manual DI execution via `/di/run`

### Where DI refresh is automatic
- `POST /data/new` and `POST /data/{id}/edit` call `refresh_current_assessment_for_molecule(...)` after successful record save (`psi/web/routers/data_records.py:347-360`, `501-514`).

### Observed workflow friction points
1. **Translation repetition**: scientist enters results in DataRecord, then often restates meaning in Evidence summary/details, then again in Claim statement.
2. **Conceptual mismatch**: UI loop emphasizes `Evidence -> Claim -> Plan -> Task`, while DI compute is measurement-first.
3. **Dual DI paths**: canonical `/di/run` vs legacy `/decisions/new` can blur “what feeds DI” for users.
4. **Structured form burden**: DataRecord form requires scope + schema-based params/results JSON assembly, then later interpretation layers are separate forms.

---

## 3. Audit 2 — Entity Duplication Analysis

### Program
- Purpose in theory: top-level portfolio/workflow scope.
- What it stores: identity, narrative context, aggregation anchors.
- Where used: all major surfaces; board/workflow/report scoping.
- Duplicates: minimal.
- Necessity: **necessary**.

### Molecule
- Purpose: scientific subject scope.
- Stores: identity/modality/target context, relationships to batches/program.
- Used: molecule workspace, board, DI scope.
- Duplicates: some status echoes across board/current assessment widgets.
- Necessity: **necessary**.

### Batch
- Purpose: experiment/manufacturing lot context and temporal granularity.
- Stores: batch identity and links to molecule.
- Used: data capture scope and DI selector lineage.
- Duplicates: some scope info repeated in data/evidence rows.
- Necessity: **necessary** (especially for many experimental data types).

### DataRecord
- Purpose in theory: canonical experiment/result record.
- Stores in practice: scope + typed schema + params/results JSON, plus derived fields (`raw_inputs_json`, `derived_outputs_json`, `primary_result_text`).
- Created at: `/data/new`.
- Consumed by: measurement extraction, evidence citation, workflow recency views.
- Duplicates:
- JSON values are re-materialized in `data_measurements` rows.
- `raw_inputs_json`/`derived_outputs_json` mirror params/results.
- Necessity: **necessary**, but contains internal duplication for compatibility/provenance.

### DataMeasurement (`data_measurements`)
- Purpose in theory: normalized metric layer for DI selection.
- Stores: metric key, numeric/text/bool value, unit/comparator, QC flags, provenance.
- Created by: automatic extraction from DataRecord results.
- Consumed by: DI selectors/evaluation, trending, QC review.
- Duplicates: repeats DataRecord result content in normalized form.
- Necessity: **necessary and load-bearing for DI**.

### Evidence + EvidenceCitation
- Purpose in theory: scientist interpretation object linking claim-support narrative to cited data.
- Stores: summary/details/strength/type + citations to DataRecords.
- Created at: `/evidence/new`.
- Consumed by: evidence pages, workflow “pending interpretation”, claim context, some report/readout narratives.
- Duplicates:
- often semantically duplicates result interpretation already inferable from measurements + DI blockers.
- Necessity for DI compute: **mostly optional/derivative** in canonical path; **governance/interpretation-useful**.

### ScientificClaim (+ links)
- Purpose in theory: explicit hypothesis/interpretation lifecycle and trace links.
- Stores: statement/status/confidence/rationale plus links to data/decisions/tasks.
- Created at: `/claims/new`.
- Consumed by: molecule/program interpretation surfaces and plan generation context.
- Duplicates:
- overlaps with evidence narrative and DI conclusions (e.g., “affinity is sufficient”).
- Necessity for DI compute: **optional/interpretive**, not required.

### ScientificPlan (+ steps)
- Purpose: execution planning and task generation.
- Stores: expected gains and ordered steps.
- Consumed by: execution/workflow orchestration.
- Duplicates: can repeat recommendations already present in DI suggested experiments and workflow suggestions.
- Necessity for DI compute: **optional for compute, useful for operations**.

### DecisionSnapshot / DIRun / DIRunSubject
- Purpose: immutable governed DI output with replay/audit provenance.
- Stores: frozen inputs/outputs/evidence ids, supersession chain.
- Created by: auto-refresh or manual DI runs.
- Consumed by: board grouping, decision detail/history/verify/export, reports.
- Duplicates: historical rows intentionally duplicate successive assessments for audit.
- Necessity: **essential governance layer**.

### Top areas of semantic duplication
1. **Binding strength narrative** repeated across:
- DataRecord results (e.g., `kd_nM`)
- Evidence summary (“supports strong binding”)
- Claim statement
- DI readiness/blocker narrative
2. **Next-step recommendations** appear in:
- DI recommended experiments
- workflow task suggestions
- plan steps
3. **Status language** appears in multiple abstractions:
- DI gate statuses
- board card status
- claim status
- task status

### Top areas of structural duplication
1. DataRecord JSON values and normalized measurement rows both store core metric facts.
2. Evidence and Claim layers can restate interpretation over the same cited records without additional computational input.
3. Legacy DI path (`/decisions/new`) still computes from Evidence-centric inputs, while canonical DI path computes from measurements.

---

## 4. Audit 3 — DI Dependency Analysis

### What DI actually reads (canonical path)
From `run_di` and `compute_di_output`:
- DI input envelope: decision key, scope type/id, qc mode, as-of timestamp (`psi/core/di/schema.py:7-15`).
- Measurement evidence selected from `data_measurements` joined to `data_records` (`psi/services/di/selectors.py:76-87`).
- Selection attributes: metric key normalization, unit/comparator/value fields, QC status/policy, primary/newest tie-breaks, as-of filtering, ignore flags (`psi/services/di/selectors.py:107-260`).
- Policy package thresholds/required metrics and alias maps (`psi/core/di/policies/advance_to_in_vivo_v0_5.json:79-292`).

### Whether DI reads Evidence objects
- **Canonical DI (`/di/run`, auto-refresh): No direct reads of `evidence`/`evidence_citations` tables in runner/selectors/compute path.**
- “Evidence” in DI internals is `EvidenceRef` from measurement selection, not the `Evidence` ORM entity (`psi/core/di/schema.py:21-39`).

### Whether DI reads Claims/Interpretations
- **No direct claim dependency** in canonical compute path.
- Claims are linked to decisions/tasks/data for scientist interpretation lifecycle (`psi/services/claims.py`).

### Whether DI reads summarized/derived structures
- Yes: selectors produce `used_by_metric`, `ignored`, `warnings`; compute derives gates/readiness/shortlisting/risk flags from that set.
- Snapshot output is then post-processed into insight/progression summaries for UI (`psi/services/insight_engine.py`, `psi/services/development_progression.py`).

### Minimal DI input model (code-backed)
For canonical DI to function, minimum required inputs are:
1. Valid DI policy package + decision key.
2. Scope lineage (molecule or batch linked to program).
3. At least some extracted measurement rows (`data_measurements`) associated with scoped records.
4. Metric keys that align with policy gate requirements (otherwise DI returns missing-data/blocker states, but still runs).
5. QC/as-of metadata handling as configured.

Equivalent practical chain in current code:
`DataRecord results -> extracted measurements -> DI selector/evaluator -> DecisionSnapshot`

Not required for canonical DI computation:
- manual Evidence creation
- Claim creation
- Plan creation

### DI dependencies by layer
- Programs/Molecules/Batches: **essential** (scope lineage)
- DataRecords: **essential upstream carrier**
- DataMeasurements: **essential direct input**
- MeasurementQC: **conditionally essential** (when QC modes enforce filtering)
- Evidence/EvidenceCitation: **optional for compute; important for interpretation/governance workflow**
- Claims/Plans: **optional for compute; important for human reasoning/coordination**
- DecisionSnapshot: **essential output/governance artifact**

---

## 5. High-Confidence Conclusions

1. PSI’s canonical DI engine is **measurement-driven**, not Evidence/Claim-driven.
2. Scientist can unlock DI assessment immediately after structured data capture because auto-refresh runs on data create/update.
3. Evidence and Claims add value for interpretation, traceability, and team communication, but are not hard prerequisites for DI computation.
4. Usability burden is concentrated in **manual semantic translation across layers** rather than in DI computation requirements.
5. Governance-critical design (immutable snapshots, supersession, replay/verify) is intact and clearly load-bearing.

---

## 6. Open Questions / Areas Requiring Deeper Audit

1. Legacy vs canonical DI usage split:
- `/di/run` (measurement-centric) and `/decisions/new` (legacy Evidence-centric YAML path) coexist; operational prevalence is unclear.
2. Report dependency depth:
- Some reports consume snapshot outputs heavily; additional audit needed to quantify where Evidence/Claim objects are mandatory vs decorative.
3. Policy coverage expectations:
- Need a policy-by-policy map of required metric keys vs common data-entry schemas to quantify unavoidable scientist input burden.
4. QC operational burden:
- How often strict/model-safe QC modes materially change gate outcomes in real usage is not evident from static code.

---

## 7. Suggested Follow-On Audit Directions

1. **Canonical-vs-legacy decision path usage audit**:
- quantify how often `/decisions/new` vs `/di/run` is used and where each is linked from scientist surfaces.
2. **Interpretation-layer necessity audit**:
- trace where Evidence and Claims alter downstream actions/reports versus where they only restate DI-observable facts.
3. **Metric-entry burden audit**:
- map policy-required metrics to data-form schemas/methods to identify minimum assay-entry set for each progression gate.
4. **Workflow-loop efficiency audit**:
- measure click/entry count for “data captured -> DI updated -> next action available” with and without evidence/claim creation.
5. **Governance-value vs UX-cost audit**:
- isolate which audit/provenance artifacts are truly required in routine scientist flow versus governance-only review flow.

---

### Key code locations used (primary)
- Models: `psi/core/models.py`
- Data capture router: `psi/web/routers/data_records.py`
- Data record service: `psi/services/data_records.py`
- Measurement extraction/upsert: `psi/services/measurements.py`
- Auto current assessment: `psi/services/current_assessment.py`
- DI runner/selectors/compute/schema:
  - `psi/services/di/runner.py`
  - `psi/services/di/selectors.py`
  - `psi/services/di/compute.py`
  - `psi/core/di/schema.py`
- Canonical progression presenter: `psi/services/development_progression.py`
- Board aggregation: `psi/services/dev_board.py`
- Workflow center: `psi/services/workflow_center.py`
- Evidence service: `psi/services/evidence.py`
- Claims service: `psi/services/claims.py`
- DI web/run surfaces:
  - `psi/services/di/web.py`
  - `psi/web/routers/di.py`
  - `psi/web/templates/di/run.html`
- Legacy decisions path:
  - `psi/web/routers/decisions.py`
  - `psi/services/decisions.py`
- Policy package example: `psi/core/di/policies/advance_to_in_vivo_v0_5.json`
- Representative tests:
  - `tests/test_data_auto_assessment_refresh.py`
  - `tests/test_current_assessment_service.py`
  - `tests/test_dev_board.py`
