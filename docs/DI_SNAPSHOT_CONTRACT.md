# DI Snapshot Contract (v0.2)

This document defines the **Decision Intelligence (DI)** snapshot contract used by PSI.

This contract is **additive-only**: newer PSI versions may add fields, but must not remove
or rename existing fields without an explicit, versioned migration plan.

**Goals:**
- Deterministic and reproducible decision artifacts
- Explainable outputs (what triggered, what failed, what evidence was used/ignored, and why)
- Policy as data (versioned, hashable, exportable)
- Local-first, overlay-safe evolution

**Non-goals (v0.2):**
- No weighted scoring system
- No probabilistic/ML behavior
- No automatic mutation of measurements/QC
- No opaque ranking; controlled shortlisting is allowed only when policy-enabled and fully deterministic

---

## 1. Where snapshots live

All decision outputs are stored in the existing `decision_snapshots` table.

DI snapshots are **distinguished** from legacy rule-engine snapshots via:
- `decision_snapshots.engine_key == "di"` (preferred)
- `decision_snapshots.schema_version` starts with `"di."` (preferred)
- Fallback: `outputs_json` contains `decision_state` + `gates` (best-effort compatibility)

DI snapshots MUST remain readable even if some discriminator fields are missing (older rows).

### 1.1 Snapshot lineage metadata (additive)

Decision snapshots carry lifecycle metadata to support lineage traversal:
- `is_superseded` (0/1; NULL allowed for legacy rows)
- `superseded_by_snapshot_id` (nullable int)
- `superseded_at` (nullable timestamp)

Latest snapshot queries should treat `superseded_by_snapshot_id IS NULL` as the active row.

---

## 2. Determinism invariant

**Same PSI DB state + same DI policy (canonical JSON + hashes) + same selection rules + same `as_of_ts` + same `qc_mode` ⇒ identical DI outputs.**

Note: each run creates a new DB row with a new snapshot id; the **row id is not part of determinism**.

Guardrail tooling:
- `python -m psi.tools.di_contract_smoke` (ephemeral DB; runs DI twice; asserts deterministic payload)

---

## 3. Required DI inputs_json fields

For DI snapshots, `decision_snapshots.inputs_json` MUST include:

### 3.1 Core DI inputs
- `decision_key` (string)
- `scope_type` (string; v0.1 supports `"batch"` and `"molecule"`)
- `scope_id` (int; batch id)
- `as_of_ts` (string or null; ISO8601 text)
- `qc_mode` (string; `none|model_safe|strict`)
- `context` (object; store-only in v0.1)

### 3.2 Snapshot identifiers
- `engine_key` = `"di"`
- `engine_id` (string)
- `schema_version` = `"di.snapshot.v0_1"`
- `selector_version` (string)
- `evaluator_version` (string)
- `selection_semantics_version` (string; currently `di.selection.v0_1`)

### 3.3 Policy packaging (dual-hash; v1.2.9d+)

Policy package schema (stored indirectly via hashes + embedded canonical body):
- `policy_id`
- `policy_version`
- `policy_name`
- `policy_schema_version` (policy package schema version string; e.g. `di.policy_package.v0_1`)
- `policy_semantics_hash` (sha256 hex of canonical `policy_body` JSON; evaluation semantics)
- `policy_package_hash` (sha256 hex of canonical full policy package JSON; artifact integrity)

Back-compat fields (kept):
- `policy_hash` (alias of `policy_semantics_hash`)
- `policy_source` (filename or label)
- `policy_json_canonical` (canonical JSON string of `policy_body`, stable serialization)

### 3.4 Experiment catalog reference (v1.2.9d+)
- `catalog_id`
- `catalog_version`
- `catalog_hash` (sha256 hex of canonical catalog JSON)

Optional debugging-only metadata may be present (e.g. machine-local `policy_path`).

---

## 4. Required DI outputs_json fields

`decision_snapshots.outputs_json` MUST be a JSON object containing the keys below.

### 4.1 Top-level required keys
- `decision_state` (string; `ready|not_ready|cannot_assess`)
- `policy` (object; display fields + dual hashes)
- `engine` (object; engine identifiers)
- `provenance` (object; selection/evaluation inputs and fingerprints)
- `state_of_evidence` (object; descriptive evidence reporting)
- `gates` (list; templated gate results)
- `blockers` (list; templated blockers)
- `risk_flags` (list; templated risk flags)
- `drift_type` (string enum; `NO_CHANGE|EVIDENCE_ONLY|POLICY_ONLY|BOTH|INCOMPARABLE`)
- `state_transition` (object; additive; present when a prior active snapshot exists)

### 4.2 Engine metadata
`engine` MUST include:
- `engine_id` (string)
- `schema_version` (string; `di.snapshot.v0_1`)
- `selector_version` (string)
- `evaluator_version` (string)

Additive fields may be present, including:
- `code_version` (string; PSI code version from `psi/version.py`)
- `evaluation_version` (string; alias of `evaluator_version` for readability)

### 4.6 Evidence identifier surface (additive)

If present:
- `measurement_ids_used` MUST be a list of unique integers sorted ascending.

### 4.5 Experiment suggestions (v1.2.9v37; additive)

If present, the DI output MAY include catalog-driven experiment suggestions:

- `experiment_suggestions` (dict): mapping of `blocker_key` → `[experiment_key, ...]`
- `recommended_experiments` (list): flattened list of objects with catalog fields

Determinism:
- `experiment_suggestions` preserves blocker order from the DI output.
- Experiments are sorted by `(time_tier, cost_tier, experiment_key)` using a fixed tier order.
- Suggestions are catalog/policy-driven only (no optimization, no scoring, no weights).
- `recommended_experiments` is de-duplicated by `experiment_key` and globally ordered by `(time_tier, cost_tier, experiment_key)`.
- `recommended_experiments[].triggered_by_blockers` is a sorted list of blocker keys.
- `recommended_experiments[].metric_keys`, `resolves`, `outputs`, and `prerequisites` are sorted lexicographically.

### 4.7 Ranking (v1.2.9w35; additive)

If present, the DI output MAY include a deterministic `ranking` object:

- `ranking.scope_type` (string; `batch` or `molecule`)
- `ranking.candidates` (list; ordered best → worst deterministically)
- `ranking.winner_candidate_id` (int or null)
- `ranking.ranking_rule_version` (string; explicit)

Each candidate entry MUST include:

- `candidate_type` (string; currently `batch`)
- `candidate_id` (int)
- `score` (number; deterministic)
- `tie_breaker` (object; includes `created_at` and `id`)
- `factors` (list; deterministic structured factors)

Factor semantics:
- `weight` is a positive magnitude.
- `direction` controls sign in scoring (`pro` adds, `con` subtracts).

### 4.8 Outcome labels (metadata; additive)

Outcome labels are stored in the `outcome_labels` table and attached to a `DecisionSnapshot`
via `OutcomeLabel.snapshot_id`. They are metadata only and do not affect deterministic DI outputs.

DI review labels (optional):
- `di_review_verdict` (string; one of the configured verdict keys)
- `di_review_rationale` (string; free-text rationale)

### 4.3 Provenance integrity (v1.2.9k+; additive)

If present, `outputs_json.provenance.integrity` MUST be a dict containing:

- `snapshot_content_hash` (sha256 hex)
- `evidence_fingerprint` (sha256 hex)

#### 4.3.1 evidence_fingerprint definition

The `evidence_fingerprint` MUST represent **selected evidence only**.

For each `metric_key` in sorted order, include the tuple:

- `metric_key`
- `measurement_id`
- `qc_status`
- `unit`
- `comparator`

Hash:

```
evidence_fingerprint = sha256(stable_json(sorted_metric_tuples))
```

Where `stable_json` is PSI's deterministic JSON serializer (sorted keys, compact separators).

#### 4.3.2 snapshot_content_hash definition

The `snapshot_content_hash` MUST be computed over an authoritative, portable payload:

```json
{
  "inputs": inputs_json minus machine-local debug fields (e.g., policy_path),
  "outputs": outputs_json with provenance.integrity removed,
  "evidence_ids": evidence_ids_json
}
```

Hash:

```
snapshot_content_hash = sha256(stable_json(authoritative_snapshot_payload))
```

Notes:
- `policy_path` is explicitly machine-local and MUST NOT contribute to integrity hashes.
- `provenance.integrity` is excluded from the hash to avoid self-reference.
- `outputs.engine.code_version` is metadata and MUST NOT contribute to `snapshot_content_hash` (it may change across releases).
- Snapshot row metadata (id, created_at, etc.) is not part of the authoritative payload.

### 4.3.3 drift_type derivation (v1.2.9w23; additive)

`drift_type` is a deterministic enum derived from:
- current `policy.policy_semantics_hash`
- current `provenance.integrity.evidence_fingerprint`
- current comparability status (`comparability.is_comparable` when present; otherwise confidence_degradation/high-severity flags)
- prior snapshot hashes embedded in `inputs_json.drift_context`

Rules:
- If not comparable → `INCOMPARABLE`
- Else if evidence unchanged and policy unchanged → `NO_CHANGE`
- Else if evidence changed and policy unchanged → `EVIDENCE_ONLY`
- Else if policy changed and evidence unchanged → `POLICY_ONLY`
- Else → `BOTH`

### 4.3.4 state_transition derivation (v1.2.9w24; additive)

If a prior *active* snapshot exists for the same scope, outputs include:

- `state_transition.from_state` (string)
- `state_transition.to_state` (string)
- `state_transition.trigger` (enum: `NONE|EVIDENCE|POLICY|BOTH|INCOMPARABLE`)

Derivation:
- If `drift_type == INCOMPARABLE` → `trigger = INCOMPARABLE`
- Else if `from_state == to_state` → `trigger = NONE`
- Else map `drift_type`:
  - `EVIDENCE_ONLY` → `EVIDENCE`
  - `POLICY_ONLY` → `POLICY`
  - `BOTH` → `BOTH`

If no prior active snapshot exists, `state_transition` may be omitted.

### 4.4 State of Evidence (SoE)

`state_of_evidence` MUST preserve the legacy (v0.1) keys:
- `used` (object mapping metric_key → EvidenceRef)
- `ignored_evidence` (list of IgnoredEvidence)
- `warnings` (list)

Determinism:
- `ignored_evidence` must be ordered by `(metric_key ASC, measurement_id ASC)`.
- `warnings` preserves emission order from selection/enrichment (deterministic for a fixed DB state).

#### SoE v0.2 (v1.2.9f+)
`state_of_evidence.soe_v0_2` MUST exist and be a dict containing:
- `requirements`
- `metric_status`
- `gate_coverage`
- `summary`
- `qc_summary`
- `recency`
- `coverage`

Determinism:
- metric keys must be emitted in lexicographic order
- gate keys must be emitted in lexicographic order

#### SoE v0.3 (v1.2.9i+; additive)
If present, `state_of_evidence.soe_v0_3` MUST be:

```yaml
schema_version: "0.3"
evidence_summary:
  - metric_key
    total_count
    usable_count
    ignored_count
    latest_timestamp
    methods_present[]
    units_present[]
    ignore_reasons_breakdown[]
```

Rules:
- Deterministic ordering by `metric_key` ascending
- `methods_present`, `units_present`, and `ignore_reasons_breakdown` must be sorted lexicographically
- `latest_timestamp` is an ISO8601 string (UTC-naive text) derived from evidence timestamps (produced_at preferred, else created_at)

---

## 5. Readiness + reporting-normalized outputs (additive)

The DI output may include derived-only reporting objects.

### 5.1 Readiness (v1.2.9g+)
If present, `readiness` MUST be a dict.

Existing readiness keys (v1.2.9g):
- `state`
- `blockers` (list; deterministically sorted)
- `coverage`
- `qc_confidence`
- `comparability`

#### Normalized readiness shape (v1.2.9i+; additive)
If present, readiness SHOULD also include:
- `decision_context` (string)
- `readiness_level` (string; normalized alias derived from readiness state)
- `blocking_gates` (list; must exist, even if empty)
- `blocking_reasons` (list; must exist, even if empty)
- `assumptions` (list; must exist, even if empty)
- `required_next_steps` (list; must exist, even if empty)

### 5.2 Gate outcomes + coverage fingerprint (v1.2.9g+)
If present:
- `gate_outcomes` must be a dict keyed by gate_key (keys sorted lexicographically)
- `coverage_fingerprint` must be a sha256 hex string over stable JSON of reporting-only signals

Determinism:
- `gates` list preserves deterministic gate evaluation order (template gate key order).
- `blockers` list preserves deterministic evaluation order (gate order, then per-gate blocker emission order).
- `risk_flags` list preserves deterministic evaluation order (pre-gate flags, then per-gate flags in gate order).

### 5.3 Evidence comparability diagnostics (v1.2.9j+; additive)

If present, `comparability` MUST be a dict and MUST always include:

```yaml
comparability:
  is_comparable: true
  reason: "ok"
  policy_semantics_hash_changed: false
  evidence_fingerprint_changed: false
  metric_level: []
  qc_coherence: []
  summary:
    total_flags: 0
    high_severity_count: 0
```

Severity enum (stable): `low|moderate|high`.

#### 5.3.1 Metric-level comparability flags

Each entry in `comparability.metric_level` MUST include:

- `metric_key` (string)
- `issue` (string; currently one of `mixed_method|unit_inconsistent`)
- `severity` (string; `low|moderate|high`)

Issue-specific keys:
- For `mixed_method`: `methods_detected[]` (sorted lexicographically)
- For `unit_inconsistent`: `units_detected[]` (sorted lexicographically)

Determinism:
- `comparability.metric_level` must be sorted by `(metric_key ASC, issue ASC)`.

#### 5.3.2 QC coherence flags

Each entry in `comparability.qc_coherence` MUST include:

- `metric_key` (string)
- `issue` (string; currently `qc_inconsistent`)
- `states_detected[]` (sorted lexicographically)
- `severity` (string; `low|moderate|high`)

Determinism:
- `comparability.qc_coherence` must be sorted by `(metric_key ASC, issue ASC)`.

---

## 6. Verification report (read-only; additive)

`psi.services.di.verify.verify_snapshot` returns a verification report. It is not
stored in `decision_snapshots.outputs_json`.

### 6.1 diff_summary (v1.2.9w26; additive)

When a prior snapshot exists for the same scope and `comparability.is_comparable`
is true, the verification report MAY include:

```yaml
diff_summary:
  prev_snapshot_id: 123
  changed_fields: ["decision_state", "gate_outcomes.G1_material_readiness.status"]
  changed_counts:
    total_fields_changed: 1
    coverage_fields_changed: 0
    risk_fields_changed: 0
    gate_fields_changed: 1
    comparability_fields_changed: 0
    readiness_fields_changed: 0
    blocker_fields_changed: 0
    state_fields_changed: 0
  notes: []
```

Notes:
- `changed_fields` are stable, contract-level field paths.
- Hashes are excluded from the diff surface.

---

## 7. Shortlisting (v1.2.9w12; additive)

If policy enables shortlisting, outputs may include:

```yaml
shortlisting:
  enabled: true
  refused: false
  refusal_reason: ""
  refusal_reasons: []
  tie_break_hierarchy: ["readiness_completeness", "qc_coherence", "purity_aggregation", "reproducibility", "functional_potency"]
  ranked_candidates:
    - candidate_id: "batch:123"
      scope_type: "batch"
      scope_id: 123
      decision_state: "ready"
      readiness_completeness: 1.0
      qc_coherence:
        high_severity_count: 0
        total_flags: 0
      purity_aggregation:
        monomer_pct: { evaluated_status: "PASS", interpretation_gap: false }
        hmw_pct: { evaluated_status: "PASS", interpretation_gap: false }
        lmw_pct: { evaluated_status: "PASS", interpretation_gap: false }
      reproducibility:
        status: "not_available"
      functional_potency:
        context_valid: true
        metrics:
          percent_killing: { evaluated_status: "PASS", interpretation_gap: false }
          ec50: { evaluated_status: "PASS", interpretation_gap: false }
          pass_fail: { evaluated_status: "PASS", interpretation_gap: false }
      tie_breaks:
        - { key: "readiness_completeness", value: 1.0 }
        - { key: "qc_coherence", value: { high_severity_count: 0, total_flags: 0 } }
        - { key: "purity_aggregation", value: { ... } }
        - { key: "reproducibility", value: "not_available" }
        - { key: "functional_potency", value: { ... } }
      tie_break_explanations:
        - { key: "readiness_completeness", summary: "...", details: { ... } }
        - { key: "qc_coherence", summary: "...", details: { ... } }
        - { key: "purity_aggregation", summary: "...", details: { ... } }
        - { key: "reproducibility", summary: "...", details: { ... } }
        - { key: "functional_potency", summary: "...", details: { ... } }
```

Determinism:
- `tie_break_hierarchy` order is fixed by policy/implementation.
- `tie_breaks` and `tie_break_explanations` must follow `tie_break_hierarchy` order.
- `ranked_candidates` list is deterministic; in v0.5 it contains a single candidate for the current scope.
- `refusal_reasons` are emitted in deterministic check order:
  `blockers_present`, `hard_gates_not_passed`, `readiness_state_below_threshold`, `coverage_below_threshold`.

#### 5.3.3 Summary

- `summary.total_flags = len(metric_level) + len(qc_coherence)`
- `summary.high_severity_count` counts flags where `severity == "high"`

Rules:
- `comparability` is additive-only and must be emitted even if both arrays are empty.

### 5.4 Confidence degradation (v1.2.9j+; additive)

If present, `confidence_degradation` MUST be a dict and MUST include:

```yaml
confidence_degradation:
  triggered: true|false
  reasons: []
```

Rules:
- `triggered` MUST be `true` iff one or more **high-severity** comparability flags exist.
- `reasons` MUST be a list of structured objects (no free-text reasons), each containing:
  - `kind` (string; issue key)
  - `metric_key` (string)
  - `severity` (string)
- `reasons` MUST be deterministically sorted by `(kind ASC, metric_key ASC, severity ASC)`.

Integration expectation:
- These signals are governance diagnostics only: they must not change gate evaluation pass/fail.

---

## 6. Suggestions (v1.2.9i+; additive)

If present, `suggestions` MUST be a list of objects.

Each suggestion must contain:
- `suggestion_id` (string)
- `type` (string)
- `rationale` (string)
- `action_spec` (object) containing:
  - `metric_key` (string)
  - `preferred_method` (string or null)
  - `required_unit` (string or null)

Rules:
- Suggestions are **policy-derived only** (gate failures, missing evidence, unit/method incompatibility)
- No scoring, no ranking weights
- Deterministic ordering (by `suggestion_id`)

---

## 7. Backward compatibility expectations

- Older consumers must continue to work if new additive fields appear.
- New consumers must tolerate missing additive fields when reading older snapshots.
- No destructive DB changes are allowed as part of this contract.
