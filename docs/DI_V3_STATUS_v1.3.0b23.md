# DI V3 Status Checkpoint (v1.3.0b23)

Source charter: `docs/DI_MISSION_AND_ROADMAP_V3.md` (Status LOCKED, V3 line `1.3.0 -> 1.3.9z###`).

## Implemented vs Charter

### Implemented (code-verified)
- Deterministic report engine with fixed report types is present in `psi/services/report_engine.py`.
- Policy-driven ranking surface (disabled by default) is implemented in `psi/services/v3_ranking.py` with catalog-backed policy loading from `psi/core/di/catalogs/ranking_policy_v0_2.json`.
- Comparability governance objects/loaders are present in `psi/services/comparability.py`.
- Report UI surfaces exist for all major V3 board pages under `psi/web/templates/reports/` and are routed through `psi/web/routers/reports.py` + `psi/services/reports_v3.py`.
- Determinism gate tools are active: `psi/tools/di_contract_smoke.py` and `psi/tools/di_replay_regression.py`.
- Molecule report path is currently evidence-only by design (fact sheet + artifacts + reproducibility scaffold), matching current policy/UI decisions.

### Partial / In-progress
- Charter language for snapshot-cited report behavior is satisfied for comparative/program paths, but molecule board intentionally omits DI sections and DI citations in board UI.
- Template ladder / upgrade delta / lineage pages are present, but readability and section consistency are still incremental across patches.
- Roadmap-level “portfolio operating system” behaviors are present as scaffolds with some placeholder/not-assessed surfaces.

### Remaining backlog (actionable)
- Continue tightening payload-only rendering guarantees across all board templates (not only molecule).
- Expand strict schema contract tests for board-facing fields that are now intentionally molecule evidence-only.
- Keep report microcopy and table layout harmonized across report, lineage, and export=pdf paths.
- Maintain one-source-of-truth policy pin/version display consistency in all board and technical surfaces.

## Risk / Unknowns
- Drift risk: tests and runtime can diverge when overlays omit report-engine or contract-test files.
- UI drift risk: board templates can regress to mixed labels/empty-state language without centralized conventions.
- Determinism risk: future additions to report payloads must preserve explicit ordering and canonical serialization assumptions.

## Next 3 Recommended Patch Themes
1. **Payload-only enforcement expansion**
   - Add no-query guards for additional report types and board partials.
2. **Board presentation consistency pass**
   - Normalize headings/empty states/chip rendering across report templates and lineage packets.
3. **Policy pin/citation coherence checks**
   - Add cross-surface tests to ensure policy versions/hashes and citation fields remain internally consistent.

## Notes
- This checkpoint is documentation-only and does not alter DI semantics, schema, or replay behavior.

## b45 Addendum (No-Weighted-Heuristics Guard)
- Added focused static guard test at `tests/test_no_weighted_heuristics.py`.
- Scope is intentionally narrow to ranking/comparative generation functions:
  - `psi/services/v3_ranking.py::build_ranking_surface`
  - `psi/services/report_engine.py::generate_molecule_comparative_report_v0`
  - `psi/services/report_engine.py::generate_program_comparative_report_v0`
- The guard fails if banned weighted-heuristic markers appear inline in those paths, preserving policy-as-data governance constraints.
