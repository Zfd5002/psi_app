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
- No candidate ranking/shortlisting
- No weighted scoring system
- No probabilistic/ML behavior
- No automatic mutation of measurements/QC

---

## 1. Where snapshots live

All decision outputs are stored in the existing `decision_snapshots` table.

DI snapshots are **distinguished** from legacy rule-engine snapshots via:
- `decision_snapshots.engine_key == "di"` (preferred)
- `decision_snapshots.schema_version` starts with `"di."` (preferred)
- Fallback: `outputs_json` contains `decision_state` + `gates` (best-effort compatibility)

DI snapshots MUST remain readable even if some discriminator fields are missing (older rows).

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
- `scope_type` (string; v0.1 supports `"batch"`)
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

### 4.2 Engine metadata
`engine` MUST include:
- `engine_id` (string)
- `schema_version` (string; `di.snapshot.v0_1`)
- `selector_version` (string)
- `evaluator_version` (string)

Additive fields may be present, including:
- `code_version` (string; PSI code version from `psi/version.py`)
- `evaluation_version` (string; alias of `evaluator_version` for readability)

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

### 4.4 State of Evidence (SoE)

`state_of_evidence` MUST preserve the legacy (v0.1) keys:
- `used` (object mapping metric_key → EvidenceRef)
- `ignored_evidence` (list of IgnoredEvidence)
- `warnings` (list)

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

### 5.3 Evidence comparability diagnostics (v1.2.9j+; additive)

If present, `comparability` MUST be a dict and MUST always include:

```yaml
comparability:
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
