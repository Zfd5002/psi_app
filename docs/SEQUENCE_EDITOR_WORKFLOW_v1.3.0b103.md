# Sequence Editor Workflow (v1.3.0b103)

## What Scientists Can Do
- Open Molecule Detail and use the region-aware sequence editor panel.
- Queue mutations by clicking residues or entering notation (`S2A N4Q`).
- Select the explicit target component for notation and preview.
- Review deterministic preview/diff before handoff.
- Launch:
  - Builder single-variant draft (`/builder/point-mutation/draft`)
  - Variant Set mutation-panel draft (`/builder/variant-set/draft`)

## Workflow Guarantees
- Existing molecules are never mutated in place.
- Queue ordering and mutation token emission are deterministic.
- Empty queue disables handoff actions and clears hidden payloads.
- Mixed-component queue disables single-variant handoff.
- Builder receives explicit context from sequence editor handoff:
  - source molecule
  - queued component
  - mutation count
  - queued mutation tokens

## Validation Alignment
- Builder handoff routes now normalize mutation tokens server-side using sequence-editor normalization semantics.
- Invalid/out-of-range/WT-mismatch notes are surfaced in draft views.

## Scope Boundary
- Sequence editor is builder-integrated only.
- No coupling to Programs, DI, Reports, Evidence, or Batches.
- Molecule creation remains draft-first then explicit create via Builder.
