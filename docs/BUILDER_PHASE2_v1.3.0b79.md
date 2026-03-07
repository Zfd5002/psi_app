# Molecule Builder Phase 2 (v1.3.0b79)

## Scope
- Keeps Builder as a standalone engineering workspace outside Programs.
- Extends builder operations to include scaffold-driven CDR grafting, Fc swap, and KIH toggle.
- Strengthens deterministic preview-first UX with explicit warnings, assumptions, and changed-residue diffs.

## Architecture
- Core boundary remains:
  - `build_molecule_draft(spec) -> MoleculeDraft` (read/transform/validate only)
  - `create_molecule_from_draft(draft, meta) -> Molecule` (explicit write step)
- Builder service modules:
  - `psi/services/builder.py`
  - `psi/services/builder_ops.py`
  - `psi/services/builder_validation.py`
- Builder web surface:
  - `psi/web/routers/builder.py`
  - `psi/web/templates/builder/*`

## Observed vs Constructed Sequences
- Clone and point-mutation flows start from observed parent molecule components.
- CDR builder constructs sequences from scaffold presets and CDR inputs.
- Constructed outputs are explicitly labeled as scaffold-assumption driven.

## Safety Rules
- Builder reads molecules and writes only new molecules plus derivation provenance.
- Builder never mutates parent molecules.
- Builder never assigns program memberships.
- Builder never creates DI snapshots.
- Builder never creates reports.
- Builder never creates batches/evidence.

## Determinism Notes
- Input parsing and mutation application are deterministic.
- Preview rows and changed-residue rows are deterministic.
- Draft validity blocks save path deterministically (`is_valid=False` cannot be persisted).

## Regression Guardrails
- Non-interference test coverage enforces no side effects on:
  - program memberships
  - DI snapshots
  - report runs
  - batches
