# DI Roadmap v2 Implementation Notes (Operator)

## Scope

This note summarizes the current PSI DI roadmap v2 implementation surfaces that operators are expected to rely on:

- Progress policy catalog and template prerequisites catalog (policy-as-data for molecule header progress/advisories)
- Experiment catalog v0.2 `resolves_risk_flags` usage (catalog-driven risk mapping)
- `value_functions_enforcement_reason` semantics (governance/run-semantics field)
- Heavy compute OFF-by-default guarantee and hash-safety boundary

## Implementation Status (Shipped Through `v1.2.9w114` + `v1.2.9x08`)

Completed (operator-relevant):

- Scientist-first molecule header surfaces:
  - deterministic progress ladder + hover explainability
  - prerequisite advisory (`Blocked by prerequisites`)
  - risk flags with policy severity tiers
  - confidence component rendering + optional non-weighted scalar
  - heavy compute OFF/ON indicator (UI-only)
- Scientist/Governance toggle (UI-only) on `/di/run` with localStorage persistence
- DI snapshot UI risk severity rendering + drift plain-English translation (deterministic, UI-only)
- Policy-as-data risk severity tiers (copied into `policy_body` and preferred there; template-structure fallback retained)
- Confidence policy catalog support (`confidence_policy_v0_1`, `confidence_policy_v0_2`)
- Outcome labeling additive metadata:
  - `OutcomeLabel.outcome_event_date`
  - deterministic outcome dataset export includes `outcome_event_date` + `days_to_outcome`
  - export enrichment reads stored snapshot hashes/fingerprints only (no recomputation)
- Structural hardening (output-preserving):
  - molecule header split (`psi/services/molecule_header.py`)
  - molecule sequence/composition helper split (`psi/services/molecule_sequences.py`)
  - viewer helper split (`psi/services/molecule_viewer.py`)
  - SoE builder consolidation / DI runner integrity helper deduplication

Additional optional deterministic tooling shipped:

- `psi.tools.molecule_header_regression`
- `psi.tools.molecule_viewer_regression`
- `psi.tools.pytest_smoke`
- `psi.tools.code_size_report`

Remaining roadmap areas (high-level, unchanged intent):

- Continue policy-as-data expansion where any UI derivation still relies on code defaults
- Additional deterministic regression fixtures/locks for UI assembly hot-spots
- CI wiring to run the canonical gate suite as a single command (tool may exist; adoption is separate)

## Progress Policy + Template Prerequisites Catalogs

### Progress policy (current)

- File: `psi/core/di/catalogs/progress_policy_v0_1.json`
- Loader: `psi.core.di.catalog.load_progress_policy_v0_1()`
- Purpose:
  - Defines `early_milestones` (measurement-presence milestones)
  - Defines `di_milestones` (milestone key -> DI template key)

### Template prerequisites policy (current)

- File: `psi/core/di/catalogs/template_prerequisites_v0_1.json`
- Loaders:
  - `load_template_prerequisites_v0_1()`
  - `load_template_prerequisites_latest()` (deterministic highest-version selection)
- Purpose:
  - Defines prerequisite template relationships used by the molecule header UI advisory layer
  - Prevents UI progress claims when a milestone template is `ready` but prerequisite templates are missing/failed

### Operator expectations

- These catalogs are policy-as-data inputs for UI progress/advisory behavior.
- Molecule header advisory logic is UI-only and does not modify DI snapshots.
- Contract smoke validates that progress-policy DI milestone template keys are covered by the template prerequisites catalog.

## Experiment Catalog v0.2 Risk Mapping (`resolves_risk_flags`)

### Catalog field

- File: `psi/core/di/catalogs/experiment_catalog_v0_2.json`
- Field: `experiments[].resolves_risk_flags` (list of risk flag keys)

### Semantics

- Risk-to-experiment suggestions are catalog-driven.
- `resolves_risk_flags` is normalized and sorted by the catalog loader/validator.
- Missing `resolves_risk_flags` values are treated as an empty list (backward-compatible with older catalog versions).

### Operational implication

- To change which experiments are suggested for risk flags, update the experiment catalog data.
- Avoid embedding risk-flag-to-experiment mappings in Python logic.

## Risk Flag Severity Tiers (Policy-as-Data, UI Display)

### Policy metadata field

- Preferred location: `policy_body.risk_flag_severity_tiers` in packaged DI policy files
- Backward-compatible fallback: `template_structure.risk_flag_severity_tiers`
- Shape: object mapping `risk_flag_key -> severity_tier`
- Current allowed tiers:
  - `high`
  - `medium`
  - `low`
  - (`moderate` accepted for backward compatibility in validators/runtime normalization)

### Semantics

- Severity tiers are policy/package metadata used for deterministic risk-flag enrichment and UI display.
- This is display semantics only (not weighted scoring and not adaptive logic).
- Unknown/unmapped risk flags fall back to `unspecified` (neutral / not assessed), not `low`.

### Vocabulary compatibility + deprecation horizon

- Forward vocabulary for new policy authoring is `high | medium | low`.
- Legacy vocabulary `moderate` is accepted only for backward-compatible runtime normalization and validator acceptance.
- Runtime normalization currently maps `moderate -> medium` deterministically before UI/confidence interpretation.
- Planned deprecation horizon:
  - Keep the compatibility shim while legacy snapshot replay support requires exact historical package/hash resolvability.
  - Re-evaluate removal only after a deliberate governance decision that archived legacy snapshot replay can be retired (not scheduled in the current v2 chain).

### Operator expectations

- Severity tier changes should be made in policy files (policy-as-data), not by editing Python severity mappings.
- DI snapshot UI may render severity badges/text distinctly, but this does not change DI snapshot hashing rules.

## Confidence Policy Catalog (UI-Only Transparency)

### Catalog

- File: `psi/core/di/catalogs/confidence_policy_v0_1.json`
- Loaders:
  - `load_confidence_policy_v0_1()`
  - `load_confidence_policy_latest()` (deterministic highest-version selection)

### Current scope

- `component_order` (UI transparency; deterministic display order target)
- `scalar_rules` for the molecule-header optional confidence scalar, including:
  - `high_concern_escalates_to`
  - `medium_concerns_amber_min`
  - `unknown_when_assessed_count_is_zero`

### Important boundary

- This catalog drives UI-only confidence display logic.
- It must not alter DI snapshot outputs or snapshot hash computation.

## Outcome Dataset v2.1 Additions

### Outcome label metadata (additive)

- `OutcomeLabel.outcome_event_date` (nullable datetime) is additive metadata for post-hoc outcome timing.
- This field is outcome-label metadata only and does not affect DI outputs or DI snapshot hashes.

### Outcome labeling CLI (`psi.tools.label_outcome`)

- `add` supports `--outcome-event-date` (ISO8601 date or timestamp).
- Accepted examples:
  - `2026-02-26`
  - `2026-02-26T12:00:00Z`
- Invalid formats fail with a deterministic CLI error message.

Example:

```bash
python -m psi.tools.label_outcome add \
  --snapshot-id 123 \
  --name efficacy_outcome \
  --text responder \
  --outcome-event-date 2026-02-26T12:00:00Z
```

### Deterministic export (`psi.tools.export_outcome_dataset`)

Exporter now includes:

- `outcome_event_date` (latest non-null event date across a snapshot's outcome labels, if present)
- `days_to_outcome` = `outcome_event_date - snapshot.created_at` (days, rounded to 6 decimals; omitted/null when unavailable)
- `policy_semantics_hash`, `policy_package_hash`, `evidence_fingerprint` enriched from stored snapshot fields only (inputs/output policy/provenance metadata; no recomputation)

Determinism guarantees:

- Rows ordered by `snapshot_id` ascending
- Outcome labels ordered by `(snapshot_id, created_at, id)`
- Hash/fingerprint fields are read from stored snapshot JSON via deterministic fallback precedence
- JSONL serialized with stable key ordering

## `value_functions_enforcement_reason` Semantics

### Field

- Output field: `value_functions_enforcement_reason`
- Emitted on gated DI outputs (success and parity-completed error outputs) for new snapshots

### Allowed values

- `active`
- `policy_flag_off`
- `evaluator_version_mismatch`
- `not_applicable`

### Meaning (deterministic)

- `active`: template enforcement flag is on and evaluator version matches the expected template evaluator version
- `policy_flag_off`: template is applicable but value-function enforcement is disabled by template policy flag
- `evaluator_version_mismatch`: template expects enforcement, but the actual evaluator version does not match
- `not_applicable`: template lookup/applicability is unavailable or version inputs are incomplete

### Replay safety

- Emission is extension-gated for new snapshots.
- Historical replay remains stable because legacy snapshots do not carry the new output-extension flags.

## Heavy Compute OFF-by-Default Guarantee

### Global toggle

- Environment variable: `PSI_HEAVY_COMPUTE`
- Shared helper: `psi.services.di.util.is_heavy_compute_enabled()`
- Effective behavior:
  - `PSI_HEAVY_COMPUTE=1` => ON
  - anything else / unset => OFF (default)

### UI visibility

- Molecule header shows a heavy-compute status banner
- `/di/run` page shows `Heavy Compute: OFF/ON`

### Hash-safety boundary

- Heavy compute status indicators are UI/runtime convenience only.
- Heavy compute toggle must not affect DI snapshot hash-bearing outputs (`inputs_obj`, `outputs_obj`, integrity hashes).
- Current UI copy explicitly states this hash-safety guarantee.

## Legacy YAML Engine Deprecation Scope (Scoping Note)

- PSI still contains legacy YAML-driven decision-engine/registry surfaces (for example `psi/core/decision_engine.py` and YAML-backed registry compatibility paths).
- Roadmap v2 DI hardening patches in this chain do not change those legacy YAML runtime paths.
- Deprecation boundary (current plan):
  - Keep legacy YAML engine support intact for non-DI compatibility paths.
  - Continue migrating DI/governance-critical logic to deterministic Python + versioned JSON policy/catalog data.
  - Any future YAML deprecation/removal must be a separate explicitly approved migration with replay/compatibility impact analysis.
