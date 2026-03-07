# Molecule Builder Phase 1 — v1.3.0b67

## Scope
Builder is a standalone engineering workspace outside Programs.

Implemented in `b60`-`b67`:
- deterministic two-step boundary:
  - `build_molecule_draft(spec) -> MoleculeDraft`
  - `create_molecule_from_draft(draft, meta) -> Molecule`
- clone flow (preview-first)
- point mutation flow (preview-first, WT validation)
- additive derivation provenance persistence
- builder router and templates (`/builder`, `/builder/clone`, `/builder/point-mutation`)

## Safety invariants
- Draft build is read-only.
- Invalid drafts do not write partial molecules.
- Create step inserts only a new molecule + component rows + optional derivation provenance.
- Builder does not trigger DI execution, decisions, reports, or program membership mutation.
- Parent molecule rows and components remain unchanged.

## Determinism notes
- deterministic component ordering in drafts and previews
- deterministic mutation parsing and application order
- canonical JSON for provenance payload (`sort_keys=True`, compact separators)

## Known limitations (intentional in phase 1)
- Clone mode persists with `composition_sha256=None` to avoid composition uniqueness collisions for engineering copies.
- Builder currently reuses parent program context because `molecules.program_id` is required by current schema.
- No CDR graft/Fc swap/KIH/humanization ops yet (reserved for future phases).

## Next safe steps
1. Add builder-specific molecule list/filter view for provenance lineage browsing.
2. Add optional explicit “engineering workspace program” isolation mode if schema policy allows.
3. Add richer mutation UX (per-component dropdown constrained to available roles).
4. Add optional validation helpers for amino-acid alphabets and disallowed residues by format.
