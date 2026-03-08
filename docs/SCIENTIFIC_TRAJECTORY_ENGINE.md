# Scientific Trajectory Engine

Version: v1.3.0c75

## Goal

The Scientific Trajectory Engine provides deterministic projections for "what happens if this experiment succeeds" without mutating operational or evidence state.

Projection chain:

experiment -> metric improvement -> gate transition -> readiness shift -> program/portfolio impact

## Architectural Boundaries

Trajectory projections are strictly read-model computations.

Must not:
- mutate `DecisionSnapshot` rows or payloads
- create hypothetical `DataRecord` entries
- mutate `ExperimentTask` lifecycle state

May read:
- `Program`
- `Molecule`
- `DecisionSnapshot`
- `ExperimentTask`
- InsightEngine outputs (`build_insight_bundle`)
- policy-derived expectations already present in snapshot outputs

## Service Surface

File: `psi/services/trajectory.py`

Core functions:
- `simulate_experiment_outcome(...)`
- `predict_metric_delta(...)`
- `predict_gate_transitions(...)`
- `predict_readiness_shift(...)`
- `score_trajectory_confidence(...)`
- `generate_trajectory_candidates(...)`
- `rank_trajectory_candidates(...)`
- `build_program_trajectory(...)`
- `build_portfolio_trajectory(...)`
- `simulate_experiment_set(...)`
- `build_trajectory_tree(...)`

## UI Surfaces

- Molecule detail: Scientific Trajectory panel and Trajectory Graph.
- Development board cards: trajectory hint for top projected experiment.
- Portfolio overview: Portfolio Trajectory Insights.

## Determinism and Regression Guarantees

Regression tests assert:
- repeated trajectory calls produce deterministic outputs
- DI snapshot payloads are unchanged after trajectory reads
- task status/linkage are unchanged after trajectory reads
- board output remains stable after trajectory reads
- replay/contract gates remain unchanged
