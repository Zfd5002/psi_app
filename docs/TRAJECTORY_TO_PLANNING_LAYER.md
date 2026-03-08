# Trajectory-to-Planning Layer

## Purpose
The Trajectory-to-Planning layer converts deterministic read-model context into structured work plans.

Inputs:
- trajectory candidates
- scientific claims and claim maturity
- missing evidence from insight outputs
- open execution context from experiment tasks

Outputs:
- `ScientificPlan` (proposed bundle of work)
- `ScientificPlanStep` (ordered proposed steps)

## What A Plan Is
A plan is a scientist-facing, deterministic proposal for next work.
It is not evidence and not a DI decision artifact.

A plan stores:
- scope (`molecule | claim | program`)
- plan type
- status lifecycle (`draft | recommended | accepted | archived | superseded`)
- expected gain estimates
- rationale

A step stores:
- execution order
- metric/assay context
- step kind (`experiment | builder_exploration | confirmatory | claim_test`)
- status (`proposed | task_created | done | skipped`)
- optional link to an instantiated `ExperimentTask`

## Generated vs User-Instantiated
Generated:
- recommendations and expected gain estimates
- proposed ordered steps
- ranking/scores used for display and prioritization

User-instantiated:
- task creation from a plan or plan step
- explicit operational execution through ExperimentTask surfaces

The system does **not** auto-complete tasks, auto-create evidence, or auto-update claim truth as a side effect of plan generation.

## Relationship To Other PSI Layers
- DI snapshots: read-only inputs only
- Evidence/DataRecord: remains source of empirical truth
- Claims: semantic assertions; plans may target claim de-risking but do not mutate claim truth
- ExperimentTask: operational execution record; created only by explicit instantiation actions
- Trajectory: projected impact model feeding plan recommendation

## Architectural Boundaries
This layer must not:
- modify DI semantics
- change DI snapshot hashing
- write plan state into DecisionSnapshot payloads
- create fake evidence rows
- auto-complete ExperimentTasks
- mutate claim status/confidence during generation

## Determinism Rules
- Stable ordering for plan and step lists
- Deterministic generation from explicit read-model inputs
- Deterministic ranking from expected gains and effort/step penalties
- No LLM/free-text generation in core planning summaries

## Extension Points
Future additive extensions may include:
- richer effort models by assay class
- explicit resource/batch constraints
- multi-plan comparative bundles by molecule cohort
- scenario-level planning against portfolio bottlenecks

These should remain read-model driven and preserve DI/evidence/claim boundaries.
