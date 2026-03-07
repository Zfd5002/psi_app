# Sequence Editor Phase 1 (v1.3.0b98)

## Scope
- Region-aware interactive sequence surface for molecule engineering workflows.
- Builder-integrated mutation queue and preview flow.
- No coupling to Programs, DI, Reports, Evidence, or Batches.

## Safety Invariants
- Existing molecules are never mutated in place by the editor.
- All edits remain local queue/preview state until explicit Builder draft/create steps.
- Sequence editor routes/forms hand off only to Builder flows.
- Deterministic ordering is enforced for queued mutations and preview changed positions.

## Data and Persistence Model
- Sequence editor itself does not persist edits.
- Persistence happens only through existing Builder safety boundary:
  - `build_molecule_draft(...)`
  - `create_molecule_from_draft(...)`
- Parent molecule remains unchanged; derived molecule creation is explicit.

## User Flow
1. View residue-aware sequence (component, position, region, numbering label).
2. Queue mutations by click and/or direct notation.
3. Review deterministic preview/diff and validation feedback.
4. Handoff queue to Builder single-variant draft or Variant Set draft.
5. Explicit save through Builder only.

## Determinism Notes
- Mutation queue normalization is sorted by `(component_role, position)`.
- Duplicate position edits are resolved deterministically.
- Preview change indices are returned in ascending numeric order.

## Non-Goals (Phase 1)
- No in-place sequence editing persistence.
- No Program assignment.
- No DI execution or policy evaluation.
- No report generation.
