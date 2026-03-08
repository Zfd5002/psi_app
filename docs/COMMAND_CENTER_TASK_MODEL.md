# PSI Command-Center Task Model

## Purpose

The Development Board is a scientist-facing command surface. `ExperimentTask` provides the minimal persisted operational bridge from board insight to execution without changing DI or evidence semantics.

## Entity Boundary

`ExperimentTask` (`program_experiment_tasks`) is operational state only.

It is intentionally separate from:

- DI decision artifacts (`decision_snapshots`, including `outputs_json`)
- Evidence objects (`data_records`, `evidence`)
- Builder lineage/provenance objects (`molecule_derivations`, variant-set entities)
- Process-local board cache

## Lifecycle

Supported statuses:

- `planned`
- `in_progress`
- `blocked`
- `done`

Allowed transitions:

- `planned -> in_progress`
- `planned -> blocked`
- `in_progress -> done`
- `in_progress -> blocked`
- `blocked -> in_progress`

`done` is terminal.

## Evidence Linkage

When data entry is initiated from a task-linked flow:

1. `/data/new` accepts `task_id` and pre-fills context.
2. No evidence row is created until form submit.
3. On successful DataRecord creation:
   - `ExperimentTask.linked_data_record_id` is set
   - task is completed (`done`) via lifecycle-safe transitions.

## Board Determinism

Open-task ordering is deterministic:

1. urgency
2. due date
3. created_at
4. id

Board group logic remains InsightEngine-driven; task overlays are additive.

## Non-Goals

- No task state inside snapshot payloads
- No fake DataRecord creation
- No repurposing of ProgramMoleculeStatus into task storage
- No heavy workflow/ACL machinery
