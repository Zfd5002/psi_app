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
* No new DB tables
* No mutation of QC/source data
