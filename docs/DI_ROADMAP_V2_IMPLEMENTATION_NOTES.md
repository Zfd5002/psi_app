# DI Roadmap v2 Implementation Notes (Operator)

## Scope

This note summarizes the current PSI DI roadmap v2 implementation surfaces that operators are expected to rely on:

- Progress policy catalog and template prerequisites catalog (policy-as-data for molecule header progress/advisories)
- Experiment catalog v0.2 `resolves_risk_flags` usage (catalog-driven risk mapping)
- `value_functions_enforcement_reason` semantics (governance/run-semantics field)
- Heavy compute OFF-by-default guarantee and hash-safety boundary

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

- Location: `template_structure.risk_flag_severity_tiers` in packaged DI policy files
- Shape: object mapping `risk_flag_key -> severity_tier`
- Current allowed tiers:
  - `high`
  - `moderate`
  - `low`

### Semantics

- Severity tiers are policy/package metadata used for deterministic risk-flag enrichment and UI display.
- This is display semantics only (not weighted scoring and not adaptive logic).
- Unknown risk flags fall back to conservative deterministic defaults in code (backward compatibility).

### Operator expectations

- Severity tier changes should be made in policy files (policy-as-data), not by editing Python severity mappings.
- DI snapshot UI may render severity badges/text distinctly, but this does not change DI snapshot hashing rules.

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
