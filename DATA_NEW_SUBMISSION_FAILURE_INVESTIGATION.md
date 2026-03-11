# DATA_NEW_SUBMISSION_FAILURE_INVESTIGATION

## 1. Executive Summary
The observed `POST /data/new` failure is most likely caused by a blank hidden form field `task_id=""`, not by scientific notation values like `8.2e4`.

`/data/new` declares `task_id` as `Optional[int] = Form(None)`. In FastAPI/Pydantic form parsing, an empty string for an integer-typed field triggers an `int_parsing` error before route logic executes. The data form template always includes a hidden `task_id` input, and in non-task-linked/manual entry mode it is rendered as an empty string. That matches the exact error payload.

Scientific notation in result fields is likely acceptable in PSI’s downstream result/measurement handling and is not the direct cause of this specific error.

## 2. The Error Observed
Exact error:

```json
{"detail":[{"type":"int_parsing","loc":["body","task_id"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":""}]}
```

This indicates request-body parsing failed on `task_id` before handler business logic.

## 3. Was Scientific Notation the Likely Cause?
Short answer: no for this exact failure.

Code-grounded evidence:
- The error location is `loc: ["body", "task_id"]`, not any result field (`ka`, `kon`, etc.).
- The route signature parses `task_id` as integer-form input at request-binding time.
- PSI measurement parsing accepts scientific notation via regex and float conversion:
  - `psi/services/measurements.py` `_NUM_RE` includes `[eE][+-]?\d+`.
  - `_parse_numericish()` then calls `float(s)`, which accepts `8.2e4` and `1.1e-2`.

So `8.2e4` is not the most likely cause of the observed `task_id` parse error.

## 4. How /data/new Handles task_id
### Route declaration
In `psi/web/routers/data_records.py`:
- `GET /data/new` accepts query `task_id: Optional[int] = None`.
- `POST /data/new` declares `task_id: Optional[int] = Form(None)`.

### Template behavior
In `psi/web/templates/data/form.html`, the form always includes:

```html
<input type="hidden" name="task_id" value="{{ prefill.task_id ... else '' }}" />
```

When not entering from task context, this renders `value=""`.

### Why task_id is parsed at all
Because the hidden input is always present in the posted form body, FastAPI attempts to bind it to `Optional[int]`. Empty-string input is still an input value, and integer parsing fails.

## 5. Most Likely Failure Mechanism
1. User opens `/data/new` manually (no task context).
2. `GET /data/new` builds `prefill.task_id = None`.
3. Template renders hidden `task_id` with empty string.
4. On Save, browser submits `task_id=`.
5. FastAPI/Pydantic form binding attempts integer parse for `task_id`.
6. Parse fails with `int_parsing` on `""`.
7. Request fails before data-record creation/validation logic runs.

This is fully consistent with the observed error.

## 6. Whether the Failure Occurs Before Binding-Field Validation
Yes.

The error occurs during request parsing/binding (framework layer), before execution reaches:
- `create_data(...)` body logic,
- `svc.create_data_record(...)`,
- any registry normalization/validation,
- any binding result/measurement handling.

So the binding assay fields were not yet evaluated in this failed submission.

## 7. Follow-On Risks in the Submitted Binding Inputs
After `task_id` parsing is avoided, the provided binding payload is largely code-aligned.

### Field-name alignment (BINDING/SPR)
From `psi/core/registry.py`, `BINDING -> SPR` supports:
- Parameters: `analyte_name`, `analyte_type`, `ligand_or_capture`, `buffer`, `assay_temperature_c`, `replicates_n`, `chip_or_sensor`, `capture_strategy`, `reference_subtraction`, `notes`.
- Results: `kd`, `ka`, `kdiss`, `fit_model`, `chi2`, `rmax`, `binding_confirmed`, `conclusion`, plus legacy `kd_nM`, `kon`, `koff`.

The submitted field set matches these keys.

### Value compatibility checks
- `fit_model=1to1` is valid (allowed options include `1to1`).
- `binding_confirmed=yes` is valid (options `no/yes`).
- `conclusion=borderline` is valid (options `pass/borderline/fail`).
- Scientific notation values (`8.2e4`, `1.1e-2`) are compatible with float parsing in PSI measurement extraction.

### Potential secondary caveat (not this error)
If required batch scoping is not satisfied, `create_data_record` can raise `batch_id is required for this data type`. For `BINDING`, batch is expected. That would be a later service-level validation error, not the current `task_id` parse failure.

## 8. What This Means for Future Tutorial / UI Guidance
For current behavior, manual `/data/new` entry can fail if form submits `task_id=""` as posted body data. Task-linked flows (workflow links with `task_id=<int>`) avoid this specific parse issue because `task_id` is a valid integer.

Tutorial guidance implications (without prescribing code changes):
- Distinguish manual result entry vs task-linked result entry.
- In troubleshooting text, prioritize `task_id` parse errors as form-context issues, not assay numeric-format issues.
- If users see `loc: ["body", "task_id"]`, they should treat it as request-binding context failure before assay validation.

## 9. Appendix: Key code locations examined
- `psi/web/routers/data_records.py`
  - `GET /data/new` (`task_id: Optional[int]`)
  - `POST /data/new` (`task_id: Optional[int] = Form(None)`)
- `psi/web/templates/data/form.html`
  - hidden `task_id` input rendered with empty string when no task context
- `psi/web/templates/partials/data/form_core_fields.html`
  - core Data Record fields and required form structure
- `psi/web/templates/partials/programs/workflow_awaiting_data_rows.html`
  - task-linked capture URL includes `task_id={{ t.id }}`
- `psi/web/handoff_context.py`
  - handoff parsing semantics and task context normalization
- `psi/core/registry.py`
  - canonical `BINDING/SPR` schema fields and allowed options
  - other data-type method schemas used by form rendering
- `psi/web/static/data_form.js`
  - dynamic schema-driven params/results rendering
- `psi/services/data_records.py`
  - service-level validation and create path (reached only after successful form binding)
- `psi/services/measurements.py`
  - scientific notation acceptance in numeric parsing (`_NUM_RE`, `float()` path)

---

## Final Verdict
A. **Was `8.2e4` the most likely cause of this exact error?**
- **No**

B. **What was the most likely direct cause of the error?**
- The form submitted a hidden `task_id` as an empty string, and FastAPI failed to parse that empty value as an integer before running route logic.

C. **Would the same submission likely fail even if `8.2e4` were replaced with `82000`?**
- **Yes**
