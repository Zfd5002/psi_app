# Molecule Builder Phase 3 (v1.3.0b89)

## What Phase 3 Adds
- Variant Set Builder as a standalone engineering campaign surface.
- Family-level draft and create APIs:
  - `build_variant_set_draft(...)`
  - `create_variant_set_from_draft(...)`
- Additive persistence for campaign identity and ordered members:
  - `builder_variant_sets`
  - `builder_variant_set_members`
- Family review page after save:
  - `/builder/variant-sets/{variant_set_id}`

## Supported Family Types (Controlled)
- `mutation_panel`
- `fc_panel`
- `kih_panel`
- `scaffold_panel`

Generation is intentionally controlled and deterministic, not unconstrained combinatorics.

## Safety and Isolation
- Builder remains outside Programs.
- Builder does not execute DI, create decision snapshots, create reports, or create batches.
- Builder creates only new molecules plus builder provenance/campaign rows.
- Parent molecules are never mutated.

## Provenance Model
- Molecule-level provenance remains in `molecule_derivations`.
- Family/campaign provenance is additive:
  - set-level metadata (`name`, `builder_mode`, `rationale`, `spec_json`)
  - ordered member linkage (`sort_index`, `member_label`, `member_summary`, `molecule_id`)

## Observed vs Constructed
- Clone / point mutation / Fc / KIH derive from observed parent components.
- Scaffold panel uses reconstructed sequences from CDR + scaffold assumptions and labels them accordingly.

## Determinism Rules
- All member generation order is explicit and stable.
- Save order follows deterministic member ordering.
- Variant set membership persistence uses explicit `sort_index` ordering.
