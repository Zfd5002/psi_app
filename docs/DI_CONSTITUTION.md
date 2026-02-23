## DI Constitution v0.1 (PSI Decision Intelligence)

### 1. Purpose

PSI Decision Intelligence (DI) produces deterministic, explainable, policy-versioned decision artifacts from PSI measurement data.

DI:

* summarizes the State of Evidence
* evaluates gates for a specific decision template
* surfaces blockers and risk flags
* suggests experiments that address blockers (non-ordered, non-optimized mappings)

DI does NOT:

* mutate QC or source data
* assign readiness percentages or scores
* rank candidates
* hide logic in opaque weights

---

### 1.1 Scope & Canonical DI Surfaces (Constitution-Governed)

This Constitution governs the **DI engine** and the minimal set of surfaces that can affect deterministic DI execution, verification, and snapshot auditability.

**In-scope (canonical DI surfaces):**

* `psi/services/di/**` (engine execution, policy evaluation, selection semantics, SoE construction)
* DI integrity + verification surfaces (e.g. `integrity.py`, `verify.py`, and any helpers they call)
* DI CLI tools that execute, validate, or regress DI determinism (e.g. `psi/tools/di_contract_smoke.py`, `psi/tools/di_replay_regression.py`, and successors)
* DI snapshot persistence surfaces in `psi/core/models.py` / `psi/core/db.py` **only as they relate to DI snapshots** (`decision_snapshots`, DI-related provenance fields, and deterministic storage semantics)
* DI policy packages (IDs, versions, packaging hashes, and any on-disk package layout)

**Out-of-scope:**

Files outside the list above are out-of-scope **unless they route into DI engine execution or mutate DI snapshot state**. If an out-of-scope surface begins to influence DI outcomes (directly or indirectly), it must be explicitly promoted into scope via a deliberate Constitution update.



### 1.2 Legacy YAML Engine Boundary (Non-Constitution-Governed)

PSI historically included a **legacy YAML rules engine** path (e.g. `psi/services/decisions.py`). That path is **not Constitution-governed**.

**Governance boundary:**

* The DI engine (`psi/services/di/**`) is the **canonical governed engine**.
* If PSI supports multiple decision engines concurrently, **snapshots must be explicitly labeled by engine** (legacy YAML vs DI) so comparisons are not accidental.
* Any transition where the UI routes a decision workflow from legacy YAML to DI must be **explicit, versioned, and documented** (not an incidental refactor).
* This boundary remains in place until the legacy YAML engine is formally deprecated and removed under a dedicated deprecation plan.

**Target timeline (non-binding):**

PSI intends to begin deprecating the legacy YAML engine after a stable DI-only release cycle. Target: publish a formal deprecation notice in a future 2026 release window, followed by removal only after a full release cycle of transition support. This is a planning target, not a promise.

### 2. Determinism Guarantee

Same PSI DB state + same policy package + same selection semantics version + same as-of timestamp ⇒ identical DI output JSON.

Determinism enforced by:

* canonical JSON hashing
* stable list ordering
* explicit tie-break rules
* dual-hash policy packaging
* catalog hash validation

---

### 3. Policy is Data

Policy packages must include:

* policy_id
* policy_version
* policy_name
* policy_schema_version
* template_key
* decision_scope
* changelog[]
* policy_body
* experiment_catalog_ref
* template_structure

Dual hashes:

* policy_semantics_hash = sha256(policy_body canonical JSON)
* policy_package_hash = sha256(entire policy package canonical JSON)

---

### 4. Template Structure (Ontology Declaration)

Each policy must declare:

```json
{
  "template_structure": {
    "context_knobs": [],
    "gate_categories": [],
    "risk_flag_categories": [],
    "blocker_taxonomy": []
  }
}
```

For advance_to_in_vivo (v0.1):

context_knobs:

* route
* model
* study_intent

gate_categories:

* material_readiness
* purity_integrity
* endotoxin
* functional

risk_flag_categories:

* qc_uncertainty

blocker_taxonomy:

* missing_required_metric
* qc_rejected_required_metric
* unreviewed_qc_required_metric
* insufficient_functional_anchor
* conflicting_metrics
* metric_present_but_non_numeric
* interpretation_gap_internalization

---

### 5. Selection Semantics

Selection semantics version:
`di.selection.v0_1`

Tie-break precedence:

1. is_primary
2. newest produced_at
3. newest created_at
4. smallest measurement_id

Selection semantics version must be emitted in snapshots.

---

### 6. Ignored Evidence Taxonomy

Allowed reason keys:

* qc_failed
* qc_unreviewed_strict
* superseded_by_primary
* superseded_by_newer
* outlier_policy
* metric_not_applicable
* unit_inconvertible
* method_incomparable
* as_of_excluded

Ignored evidence must be ordered by:

1. metric_key
2. measurement_id

---

### 7. Blockers & Risk Flags

Blockers:

* Must use declared blocker_taxonomy
* Deterministically ordered

Risk flags:

* Structured
* Deterministic
* No scoring

---

### 8. Experiment Suggestions

Mapping:
blocker_key → [experiment_key]

Rules:

* No ranking
* No prioritization
* Lists must be de-duplicated and lexicographically sorted
* All experiment_keys must exist in referenced catalog

---

### 9. Drift Guards (v0.1)

* No readiness score/percent (descriptive coverage ratios are allowed; no scoring/ranking)
* No scoring
* No ranking
* No planner heuristics
* No new database tables for scoring, ranking, adaptive logic, learned thresholds, or probabilistic reasoning.
* Deterministic audit/provenance/labeling support tables are permitted (e.g. `OutcomeLabel`).
* No mutation of QC/source data

---

### 9.1 Patch Governance

Before producing any **DI-related patch ZIP** (including docs-only governance updates), the patch is **invalid** unless these commands pass in a clean environment:

```
python -m compileall -q psi
python -m psi.tools.di_contract_smoke
python -m psi.tools.di_replay_regression --limit 50
```

If any command fails, **do not ship the patch**.

Second-pass logic review is required if the patch touches any of the following high-risk surfaces:

* `psi/services/di/runner.py`
* `psi/services/di/verify.py`
* `psi/services/di/integrity.py`
* `psi/core/models.py`
* `psi/core/db.py`
* any code path that writes to `decision_snapshots`

The second pass must explicitly re-validate:

* determinism invariants
* snapshot immutability (no mutation of stored snapshots)
* anchored replay fidelity
* hash surface stability (especially cross-version replay noise)
