# DI V3 Status — v1.3.0b58

## Scope of this checkpoint
- Baseline preserved: deterministic DI snapshots, immutable snapshot contract, replay invariance, and policy-as-data.
- Program-centric phase 1 delivered as additive surfaces on top of existing molecule and DI infrastructure.
- Scientist-first program UX promoted; governance-heavy details remain available but are not default.

## Implemented in b47-b58
- Program molecule role/state foundation:
  - additive `program_molecule_status` model
  - deterministic role/rationale helpers and update route
- Program dashboard scaffold:
  - summary header cards, candidate-set segmentation, molecule status board
  - evidence summary + evidence matrix with deterministic ordering
  - program-level progress/confidence bars (explicitly display-only)
  - program-aware suggested next experiments (display-only deterministic heuristic)
- Program report board redesign:
  - executive-summary-forward scientist report surface
  - governance details kept secondary
- Navigation polish:
  - direct drill-down links from program to molecule/data/evidence/decisions/report generation
- Governance separation hardening:
  - DI portfolio/governance analytics in program detail are hidden by default behind explicit toggle
  - toggle state persisted with localStorage key `psi_program_detail_mode`

## Determinism and governance checks
- No DI snapshot schema changes introduced.
- No policy hash or evaluation semantics changes introduced in this chain.
- No destructive DB changes introduced.
- Report and dashboard ordering remains explicit and deterministic.
- Existing gates remained required and green across patch series:
  - `python -m compileall -q psi`
  - `pytest -q`
  - `python -m psi.tools.di_contract_smoke`
  - `python -m psi.tools.di_replay_regression --limit 5`

## Known remaining gaps
- Program-level confidence/progress remain display heuristics, not policy ratified governance semantics.
- Program report payload still depends on current report engine shape; additional consolidation may be useful before broader template expansion.
- Governance panel data density is high; future refinement should preserve access while improving scanning ergonomics.

## Recommended next steps
1. Add a dedicated program report payload schema appendix for candidate-set provenance and evidence coverage rationale.
2. Add targeted no-view-time-query tests for program report board rendering paths similar to molecule evidence-only guard tests.
3. Add deterministic contract tests for candidate-set ordering across role changes and membership sort updates.
4. Add governance-panel paging/compact views to reduce render weight on large programs while keeping full traceability available.
