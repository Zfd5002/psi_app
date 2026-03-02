# PSI V3 Hardening Contract Notes (v1.3.0a32-v1.3.0a46)

## Canonical Serialization Contract
- Report payload persistence uses canonical JSON serialization (`psi/services/report_engine.py`):
  - sorted object keys
  - deterministic handling for tuple/set containers
  - UTF-8 byte serialization helper
  - stable float formatting
- Optional `report_fingerprint` is computed from canonical payload basis (excluding fingerprint field itself).
- Fingerprint is report metadata only; DI snapshot hash surfaces are unchanged.

## Ranking Tie-Break Contract
- Ranking policy `ranking_policy_v0_2.json` remains non-weighted and deterministic.
- Tie-break behavior is policy-defined via ordered `method.tie_break_keys`.
- Explanation traces include deterministic per-criterion records and tie-break key-value surfaces.
- No adaptive scoring or hidden ranking logic is allowed.

## Comparability Citation Requirements
- Comparability writes require both:
  - `cited_measurement_keys`
  - `cited_snapshot_ids`
- Missing citations are deterministic validation failures:
  - `comparability_missing_measurement_citations`
  - `comparability_missing_snapshot_citations`
- Category resolution is deterministic and policy-ordered, with conservative fallback for missing/partial data.

## Upgrade Diff Artifact Format
- Policy upgrade sessions store a structured deterministic diff artifact:
  - old/new policy pins
  - old/new package hash
  - old/new semantics hash
  - sorted changed keys
  - nested classification + downstream impact flags
  - snapshot set and deterministic input linkage metadata
- Verification routine enforces required linkage presence before session is considered valid.

## Changelog Scope (a32-a46)
- a32: canonical report serialization + pytest discovery scoping
- a33: comparative ordering contracts
- a34: report contract tests across 4 report types
- a35: ranking tie-break formalization and tests
- a36: ranking explanation trace normalization
- a37: comparability citation enforcement
- a38: comparability category resolution deterministic contract
- a39: deterministic policy diff artifact
- a40: upgrade session verification routine
- a41: replay harness rollup-surface determinism checks
- a42: attribution isolation contract tests
- a43: report fingerprint stabilization
- a44: policy/rule prominence in report UI
- a45: measurement/evidence citation surfacing in report UI
- a46: this contract note document + PATCH_NOTES consolidation
