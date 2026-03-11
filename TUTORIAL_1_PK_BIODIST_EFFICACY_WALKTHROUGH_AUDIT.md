# TUTORIAL_1_PK_BIODIST_EFFICACY_WALKTHROUGH_AUDIT

## 1. Executive Summary
PSI can support a tutorial-ready walkthrough for **PK** and **efficacy** data entry today, but with important caveats around metric-key conventions and evidence linkage. **Biodistribution** is not modeled as a first-class assay family; it is only supportable through generic/semi-structured paths (primarily PK/PD with `matrix=tissue` and free-text/aux fields).  

For tutorial authors, the strongest code-aligned path is:
`Program workflow/board/molecule → task-linked /data/new → /data/{id} review → /evidence/new (cite records) → claim/plan linkage → reports/DI surfaces`.

Key constraints to document in the tutorial:
- PK, biodistribution, and efficacy are mostly handled through generic `DataRecord` + measurement extraction.
- Efficacy has explicit schema support (`IN_VIVO_EFFICACY`), PK has explicit schema support (`PK_PD`), biodistribution does not.
- Evidence citation rules explicitly map `InVivo_Efficacy` evidence to `IN_VIVO_EFFICACY` records; there is no equivalent explicit PK evidence-type mapping in registry evidence-source rules.
- Units are partly explicit (schema fields like `*_units`) and partly implicit via extracted measurements; omission can make downstream report interpretation ambiguous.

## 2. Audit Question and Scope
**Question audited:** Can PSI, as currently implemented, support PK, biodistribution, and efficacy data entry and walkthrough-style user guidance in a tutorial-ready, code-aligned way?

Scope reviewed:
- Data/measurement model and form pipeline
- Task/handoff routes into data capture
- Downstream usage in molecule/workflow/evidence/claims/plans/reports/DI surfaces
- Unit entry/storage/display behavior
- Tests validating the intended UI flows

## 3. Codebase Support for PK, Biodistribution, and Efficacy

### 3.1 Data model architecture (explicit vs generic)
- `psi/core/models.py`: `DataRecord` is a generic record object (`domain`, `data_type`, `method`, `params_json`, `results_json`).
- `psi/core/db.py` + `psi/core/measurement_schema.py`: extracted measurement rows live in `data_measurements` with `metric_key`, `value_num/value_text`, `unit`.
- `psi/services/data_records.py`: ingestion persists record JSON then triggers measurement extraction.
- `psi/services/measurements.py`: extraction is generic over JSON keys, not assay-family-specific.

### 3.2 Explicit schema support in registry
- `psi/core/registry.py` includes explicit data types:
  - `PK_PD`
  - `IN_VIVO_EFFICACY`
- `PK_PD` has structured fields for common PK concepts (example keys: `cmax`, `cmax_units`, `auc`, `auc_units`, `half_life_h`, `matrix`, etc.).
- `IN_VIVO_EFFICACY` has structured fields for in vivo outcomes (example keys: `primary_outcome_value`, `primary_outcome_units`, `effect_size`, `hazard_ratio`, `p_value`, `survival_median_days`, `notes_interpretation`, `conclusion`).

### 3.3 Biodistribution support status
- No distinct `BIODISTRIBUTION` data type/method family was found in registry data schemas.
- Closest modeled path is implicit/semi-structured representation via `PK_PD` with matrix/context fields (e.g., `matrix=tissue`) and additional textual/result fields.
- Verdict for biodistribution modeling: **implicit support through generic primitives; no explicit first-class assay family**.

### 3.4 Evidence-source compatibility constraints
- `psi/core/registry.py` `EVIDENCE_TO_DATA_SOURCES` maps evidence types to allowable data sources.
- `InVivo_Efficacy` evidence is explicitly mapped to `IN_VIVO_EFFICACY` methods.
- No explicit evidence source mapping found for `PK_PD` as a dedicated evidence type in this ruleset.
- Tutorial implication: efficacy-to-evidence chain is direct; PK may need contextual handling (or evidence typing choices) instead of a clean explicit PK evidence lane.

### 3.5 Humanization/display clues
- `tests/test_ui_label_humanization.py` confirms token humanization like `IN_VIVO_EFFICACY/NOD` and `PK_PD/NONCOMP`.
- This supports user-facing readability of these assay families in tables/queues, but does not create first-class biodistribution semantics.

## 4. Exact User Entry Paths for Each Data Family

### Shared entry surfaces
Primary entry routes/pages in current UI:
- `GET /data/new` (`psi/web/routers/data_records.py`, template `psi/web/templates/data/form.html`)
- Common upstream launch points:
  - Program workflow awaiting-data row: `psi/web/templates/partials/programs/workflow_awaiting_data_rows.html`
  - Program board missing-measurement actions: `psi/web/templates/programs/board.html`
  - Molecule execution section capture link: `psi/web/templates/molecules/partials/workflow_loop.html`

The data form is schema-driven by `psi/web/static/data_form.js`, using `/api/registry`.

---

### 4.1 PK entry path (tutorial-friendly)
**Best entry path for tutorial:**
1. Go to program workflow page: `GET /programs/{program_id}/workflow`.
2. In “Awaiting Data Entry”, click **Start result capture** (task-linked `/data/new?...&task_id=...&source=workflow&return_to=...`).
3. On `/data/new`:
   - Select/confirm `domain=BIO` equivalent via form domain selector.
   - Set `data_type=PK_PD`.
   - Choose method (`NONCOMPARTMENTAL` or `COMPARTMENTAL`, registry-normalized names).
   - Fill structured PK params/results fields rendered by `data_form.js`.
   - Enter unit fields where provided (`cmax_units`, `auc_units`, etc.).
4. Submit to `POST /data/new`.
5. Review at `GET /data/{record_id}`.

**Alternative entry path:** direct from molecule detail capture link (`/molecules/{id}` → “Capture Experiment Result”), then set PK fields manually.

---

### 4.2 Biodistribution entry path (code-aligned implicit pattern)
Because there is no explicit biodistribution data type:

**Practical tutorial path:**
1. Start from the same workflow or molecule capture route into `/data/new`.
2. Use `data_type=PK_PD` (or generic type if needed), choose method that best matches intended run.
3. Encode biodistribution context in available schema fields (notably matrix/context fields like `matrix=tissue`, plus structured/free-text fields).
4. Submit and review on `/data/{record_id}`.

**Tutorial caveat to state explicitly:** this is a **proxy representation** using generic PK/PD infrastructure, not a dedicated biodistribution assay object.

---

### 4.3 Efficacy entry path (explicit)
**Best entry path for tutorial:**
1. Go via task-linked capture from workflow (`/programs/{id}/workflow`) if task exists; otherwise use molecule capture link.
2. On `/data/new` choose:
   - `data_type=IN_VIVO_EFFICACY`
   - method `NOD` or `OTHER_MOUSE`
3. Fill structured efficacy fields (`primary_outcome_value`, `primary_outcome_units`, effect and interpretation fields).
4. Submit via `POST /data/new`.
5. Review at `/data/{record_id}`.

This path is explicit and cleanly supported by current schemas.

## 5. Exact Downstream Usage Paths for Each Data Family

### 5.1 Data detail and interpretation handoff
- `GET /data/{record_id}` (`psi/web/templates/data/detail.html`):
  - Shows record metadata, JSON payloads, extracted measurements, QC actions.
  - Provides **Create or Link Evidence** actions (`/evidence/new?...&return_to=/data/{id}`).

### 5.2 Evidence creation and linkage
- `GET/POST /evidence/new` (`psi/web/routers/evidence.py`, `psi/web/templates/evidence/form.html`):
  - User selects evidence type and cites DataRecords.
  - Allowed citation choices are constrained by registry mapping (`/api/evidence_allowed_sources`).
- `GET /evidence/{id}` shows cited records and context.

**Data-family behavior:**
- Efficacy: directly aligned through `InVivo_Efficacy` evidence mapping.
- PK: visible as data/results but not mapped as a dedicated evidence-source family in current registry rules.
- Biodistribution (PK proxy): same limitation as PK; may be visible but less directly typed for evidence semantics.

### 5.3 Molecule/program/workflow surfaces
- Molecule detail (`/molecules/{id}`): shows capture context, execution links, batch/evidence-data sections; non-special assay families often appear in generic lists/tables.
- Program workflow (`/programs/{id}/workflow`):
  - Awaiting data entry bucket
  - Recent learning/results sections
  - Interpretation queue with evidence creation actions
- Program board (`/programs/{id}/board`): missing-measurement and task/data actions.

### 5.4 Claims/plans/reports/decision usage
- Claim detail (`/claims/{id}`), Plan detail (`/plans/{id}`): consume evidence/task context and recent-learning cues.
- Reports (`/reports/new`, `/reports/{id}`): include metric/fact-sheet content derived from measurements and related objects.
- DI/decisions:
  - `/di/run`, `/decisions/new`
  - Policies reference specific metric keys (e.g., `cmax_ug_ml`, `half_life_days` in advance-to-in-vivo policies/catalogs), so PK key naming alignment matters.

### 5.5 Directness classification
- **Directly visible:** Data detail, workflow recent-learning/queues, evidence detail citations.
- **Indirectly used:** reports/fact sheets and DI readiness signals via metric aggregation.
- **Not strongly surfaced as dedicated family:** biodistribution as a first-class object/lane.

## 6. Units Handling for These Data Types

### 6.1 Where units are entered
- Data form schema fields (via registry + `data_form.js`) expose explicit unit fields for many PK/efficacy values (e.g., `*_units`, plus field-level unit hints like `h`).
- Units can also be embedded in result values in limited cases; extractor has minimal inference (`%` suffix handling).

### 6.2 Where units are stored
- In record JSON (`results_json` / `params_json`) as entered fields.
- In `data_measurements.unit` when extractor populates measurement rows.

### 6.3 Where units are displayed
- Data detail measurement table and JSON sections.
- Report fact sheet/matrix surfaces (`psi/services/fact_sheet.py`, report templates) via:
  1. measurement unit
  2. metric catalog default unit
  3. fallback formatting

### 6.4 Family-specific implications
- PK: strongly unit-sensitive; omission or inconsistent key/unit conventions reduces downstream interpretability.
- Biodistribution proxy: requires explicit unit/context fields to avoid ambiguity (especially tissue concentration-style values).
- Efficacy: primary outcome units should be filled for narrative/report clarity.

### 6.5 Key mismatch risk to highlight in tutorial
- DI and metric catalog favor PK keys like `cmax_ug_ml`, `half_life_days`.
- PK form schemas include keys such as `cmax`, `half_life_h`.
- Tutorial should call out which keys/units are being used and why, otherwise DI/report expectations may not align.

## 7. Tutorial Walkthrough Readiness

### 7.1 PK walkthrough readiness
- **Usable:** Yes, via task-linked `/data/new` and explicit `PK_PD` schema.
- **Needs explicit tutorial guidance:** metric-key naming and unit consistency; evidence linkage expectations.

### 7.2 Biodistribution walkthrough readiness
- **Usable:** Mostly, through PK/generic representation.
- **Limitation:** no first-class biodistribution type; tutorial must explicitly explain proxy encoding pattern.

### 7.3 Efficacy walkthrough readiness
- **Usable:** Yes, strongest of the three due to explicit `IN_VIVO_EFFICACY` schema and evidence-source mapping.

### 7.4 Non-obvious steps tutorial must explain
- Start from workflow/task when possible to preserve context (`task_id`, `return_to`, capture notices).
- In evidence form, record citation selection is user action (not fully automatic from data detail intent).
- Some downstream surfaces summarize generically rather than assay-family-specific panels.

## 8. Minimal vs Best-Practice Tutorial Entry Patterns

### 8.1 PK
- **Minimal:** direct `/data/new` → choose `PK_PD` → save record.
- **Best-practice:** create/use workflow task → task-linked `/data/new` → fill structured PK + units → review `/data/{id}` → create evidence where appropriate → return to workflow/claim/plan context.

### 8.2 Biodistribution
- **Minimal:** direct `/data/new` as generic/PK record with free text.
- **Best-practice:** task-linked `/data/new` using `PK_PD` with tissue matrix/context + explicit units + interpretation text → review detail → link evidence/claims with explicit note that assay is biodistribution proxy.

### 8.3 Efficacy
- **Minimal:** direct `/data/new` with `IN_VIVO_EFFICACY` and save.
- **Best-practice:** workflow task handoff → `IN_VIVO_EFFICACY` (`NOD`/`OTHER_MOUSE`) with explicit outcome units + interpretation fields → data detail QC/review → evidence creation (`InVivo_Efficacy`) → claim/plan update context.

## 9. UI Surfaces the Tutorial Must Explicitly Describe

### Core capture surfaces
- `GET /programs/{program_id}/workflow` (`psi/web/templates/programs/workflow.html` + partial rows)
- `GET /programs/{program_id}/board` (`psi/web/templates/programs/board.html`)
- `GET /molecules/{molecule_id}` (`psi/web/templates/molecules/detail.html`)
- `GET/POST /data/new` (`psi/web/templates/data/form.html` + `psi/web/static/data_form.js`)
- `GET /data/{record_id}` (`psi/web/templates/data/detail.html`)

### Evidence/interpretation surfaces
- `GET/POST /evidence/new`, `GET /evidence/{id}` (`psi/web/templates/evidence/form.html`, `evidence/detail.html`)
- `GET /claims/{claim_id}` (`psi/web/templates/claims/detail.html`)
- `GET /plans/{plan_id}` (`psi/web/templates/plans/detail.html`)

### Reporting/decision surfaces
- `GET /reports/new`, `GET /reports/{report_run_id}` (`psi/web/routers/reports.py`, report templates)
- `GET/POST /di/run` (`psi/web/routers/di.py`)
- `GET/POST /decisions/new` (`psi/web/routers/decisions.py`)

### Handoff/context plumbing tutorial should name
- `psi/web/handoff_context.py`
- hidden form fields and query params: `task_id`, `return_to`, `source`, `captured`, `updated`, `from_task`, `next`
- capture notice partial: `psi/web/templates/partials/capture_notice.html`

## 10. Final Verdict

1. **Can PSI currently support PK entry in a tutorial-friendly way?**  
**Mostly.** `PK_PD` structured entry is present and walkthrough-able, but tutorial must handle unit/key conventions carefully and cannot assume clean dedicated PK evidence typing.

2. **Can PSI currently support biodistribution entry in a tutorial-friendly way?**  
**Mostly.** It is supportable through generic/semi-structured PK/PD paths (often matrix=tissue), but not as an explicit first-class biodistribution assay family.

3. **Can PSI currently support efficacy entry in a tutorial-friendly way?**  
**Yes.** `IN_VIVO_EFFICACY` has explicit schema support and direct evidence-source mapping, making it the cleanest of the three.

4. **Can PSI currently support a descriptive walkthrough that explains exactly where the user goes to perform these actions?**  
**Yes.** Routes/templates/handoff flows are explicit enough to produce literal “go here, click this, fill these fields” instructions.

5. **What exact pages/routes/forms should the tutorial explicitly mention?**  
At minimum: `/programs/{id}/workflow`, `/programs/{id}/board`, `/molecules/{id}`, `/data/new`, `/data/{id}`, `/evidence/new`, `/evidence/{id}`, `/claims/{id}`, `/plans/{id}`, `/reports/new`, `/reports/{id}`, `/di/run`, `/decisions/new`, plus task/handoff parameters (`task_id`, `return_to`, `source`, `from_task`).

## 11. Appendix: Key code locations examined
- Models/data plumbing:
  - `psi/core/models.py`
  - `psi/core/db.py`
  - `psi/core/measurement_schema.py`
  - `psi/services/data_records.py`
  - `psi/services/measurements.py`
- Registry/schemas/evidence-source rules:
  - `psi/core/registry.py`
  - `psi_rules/psirules-0.1.0.yml`
- Routers:
  - `psi/web/routers/data_records.py`
  - `psi/web/routers/evidence.py`
  - `psi/web/routers/programs.py`
  - `psi/web/routers/molecules.py`
  - `psi/web/routers/reports.py`
  - `psi/web/routers/di.py`
  - `psi/web/routers/decisions.py`
  - `psi/web/routers/search.py`
- Templates/static:
  - `psi/web/templates/data/form.html`
  - `psi/web/templates/data/detail.html`
  - `psi/web/templates/evidence/form.html`
  - `psi/web/templates/evidence/detail.html`
  - `psi/web/templates/programs/workflow.html`
  - `psi/web/templates/partials/programs/workflow_awaiting_data_rows.html`
  - `psi/web/templates/partials/programs/workflow_interpretation_row.html`
  - `psi/web/templates/programs/board.html`
  - `psi/web/templates/molecules/detail.html`
  - `psi/web/templates/molecules/partials/workflow_loop.html`
  - `psi/web/templates/partials/capture_notice.html`
  - `psi/web/static/data_form.js`
- Reporting/metrics/decision relevance:
  - `psi/services/fact_sheet.py`
  - `psi/services/metric_catalog.py`
  - `psi/services/report_engine.py`
  - `psi/core/di/policies/advance_to_in_vivo_v0_5.json`
  - `psi/core/di/catalogs/experiment_catalog_v0_2.json`
- Tests consulted for behavior intent:
  - `tests/test_data_surface_context.py`
  - `tests/test_data_task_handoff.py`
  - `tests/test_data_handoff_redirects.py`
  - `tests/test_workflow_data_handoff_links.py`
  - `tests/test_evidence_form_return_path.py`
  - `tests/test_ingestion_static_js.py`
  - `tests/test_metric_catalog.py`
  - `tests/test_ui_label_humanization.py`
  - `tests/test_program_workflow_recent_learning.py`
  - `tests/test_v3_molecule_report_schema.py`
