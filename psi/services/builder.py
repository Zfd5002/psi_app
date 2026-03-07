from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from psi.core.fasta import to_fasta, sha256_text
from psi.core.models import Molecule, MoleculeComponent, MoleculeDerivation
from psi.core.utils import now_utc
from psi.services import molecules as molecule_svc
from psi.services.molecule_sequences import get_or_create_chain
from psi.services.builder_ops import (
    apply_point_mutations,
    clone_components,
    parse_point_mutation_tokens,
)
from psi.services.builder_validation import (
    is_valid,
    validate_parent_exists,
    validate_point_mutations_not_empty,
    validate_primary_id,
    validate_target_component_exists,
)


@dataclass(frozen=True)
class MoleculeBuildSpec:
    mode: str
    parent_molecule_id: int
    new_primary_id: str
    new_title: str = ""
    rationale: str = ""
    operations: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class MoleculeCreateMeta:
    actor: str = "builder"
    note: str = ""


@dataclass
class MoleculeDraft:
    mode: str
    parent_molecule_id: int
    new_primary_id: str
    new_title: str
    parent_primary_id: str
    components: dict[str, str]
    derivation_type: str
    derivation_summary: str
    provenance_payload: dict[str, Any]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    preview_rows: list[dict[str, str]] = field(default_factory=list)
    is_valid: bool = False
    inherited_program_id: int | None = None


def _load_parent_components(db: Session, *, parent_molecule_id: int) -> dict[str, str]:
    rows = (
        db.query(MoleculeComponent)
        .filter(MoleculeComponent.molecule_id == int(parent_molecule_id))
        .order_by(MoleculeComponent.role.asc(), MoleculeComponent.id.asc())
        .all()
    )
    return {str(r.role): str(r.fasta or "") for r in rows if str(r.fasta or "").strip()}


def build_molecule_draft(db: Session, spec: MoleculeBuildSpec) -> MoleculeDraft:
    mode = str(spec.mode or "").strip().lower()
    parent = db.get(Molecule, int(spec.parent_molecule_id))
    errors: list[str] = []
    errors.extend(validate_parent_exists(parent is not None))
    errors.extend(validate_primary_id(spec.new_primary_id))
    if mode not in {"clone", "point_mutation"}:
        errors.append("Unsupported builder mode.")

    parent_components: dict[str, str] = {}
    parent_primary_id = ""
    inherited_program_id: int | None = None
    if parent is not None:
        parent_primary_id = str(parent.primary_id or "")
        inherited_program_id = int(parent.program_id)
        parent_components = clone_components(parent_components=_load_parent_components(db, parent_molecule_id=int(parent.id)))
        if not parent_components:
            errors.append("Parent molecule has no structured components to derive from.")

    derivation_type = "clone" if mode == "clone" else mode
    summary = f"{derivation_type} from {parent_primary_id or 'unknown'}"
    operations_payload = list(spec.operations or [])
    warnings: list[str] = []
    preview_rows: list[dict[str, str]] = []
    if mode == "point_mutation" and parent is not None:
        op = operations_payload[0] if operations_payload else {}
        component = str((op.get("component") if isinstance(op, dict) else "") or "").strip()
        mutation_text = str((op.get("mutations") if isinstance(op, dict) else "") or "").strip()
        before_seq = str(parent_components.get(component) or "")
        errors.extend(validate_target_component_exists(component_name=component, available_components=parent_components.keys()))
        muts, parse_errors = parse_point_mutation_tokens(mutation_text)
        errors.extend(parse_errors)
        errors.extend(validate_point_mutations_not_empty(muts))
        if not parse_errors and component in parent_components and muts:
            mutated_seq, apply_errors = apply_point_mutations(sequence=parent_components.get(component, ""), mutations=muts)
            errors.extend(apply_errors)
            if not apply_errors:
                parent_components[component] = mutated_seq
                summary = f"point mutation on {component} from {parent_primary_id or 'unknown'}"
                preview_rows.append(
                    {
                        "component": component,
                        "before": before_seq,
                        "after": mutated_seq,
                        "mutations": mutation_text,
                    }
                )
            else:
                warnings.append("Draft preview unchanged due to mutation validation errors.")
        operations_payload = [
            {
                "type": "point_mutation",
                "component": component,
                "mutations": mutation_text,
            }
        ]

    draft = MoleculeDraft(
        mode=mode,
        parent_molecule_id=int(spec.parent_molecule_id),
        new_primary_id=str(spec.new_primary_id or "").strip(),
        new_title=str(spec.new_title or "").strip(),
        parent_primary_id=parent_primary_id,
        components=parent_components,
        derivation_type=derivation_type,
        derivation_summary=summary,
        provenance_payload={
            "parent_molecule_id": int(spec.parent_molecule_id),
            "derivation_type": derivation_type,
            "operations": operations_payload,
            "rationale": str(spec.rationale or "").strip(),
        },
        errors=[e for e in errors if str(e or "").strip()],
        warnings=warnings,
        preview_rows=preview_rows,
        inherited_program_id=inherited_program_id,
    )
    draft.is_valid = is_valid(draft.errors)
    return draft


def create_molecule_from_draft(db: Session, draft: MoleculeDraft, meta: MoleculeCreateMeta) -> Molecule:
    del meta  # reserved for attribution/provenance persistence in follow-up patches.
    if not bool(draft.is_valid):
        raise ValueError("Cannot create molecule from invalid draft.")
    if draft.inherited_program_id is None:
        raise ValueError("Draft missing inherited program context.")
    role_order = sorted(str(k) for k in draft.components.keys())
    role_to_seq = {str(r): str(draft.components.get(r) or "").strip() for r in role_order}
    if not role_to_seq:
        raise ValueError("Draft has no components to persist.")

    chains_by_role: dict[str, str | None] = {}
    ents_by_role = {}
    for role, seq in role_to_seq.items():
        ent = get_or_create_chain(db, seq)
        ents_by_role[role] = ent
        chains_by_role[role] = getattr(ent, "chain_id", None)

    composition_hash = molecule_svc.composition_sha256(chains_by_role)
    persisted_comp_hash = None if str(draft.mode or "").strip().lower() == "clone" else composition_hash
    try:
        m = Molecule(
            program_id=int(draft.inherited_program_id),
            primary_id=str(draft.new_primary_id),
            title=(str(draft.new_title or "").strip() or None),
            description=str(draft.derivation_summary),
            description_user=str(draft.derivation_summary),
            molecule_format="IgG",
            heavy_compute_enabled=0,
            composition_sha256=persisted_comp_hash,
            sequences=to_fasta([(r, role_to_seq[r]) for r in role_order]).strip() or None,
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        db.add(m)
        db.flush()
        for role in role_order:
            seq = role_to_seq[role]
            ent = ents_by_role[role]
            db.add(
                MoleculeComponent(
                    molecule_id=int(m.id),
                    role=role,
                    fasta=seq,
                    sha256=sha256_text(seq),
                    sequence_entity_id=int(ent.id) if ent is not None else None,
                    created_at=now_utc(),
                    updated_at=now_utc(),
                )
            )
        db.add(
            MoleculeDerivation(
                parent_molecule_id=int(draft.parent_molecule_id),
                child_molecule_id=int(m.id),
                derivation_type=str(draft.derivation_type or "unknown"),
                summary=str(draft.derivation_summary or ""),
                edit_payload_json=json.dumps(draft.provenance_payload or {}, sort_keys=True, separators=(",", ":")),
                created_at=now_utc(),
            )
        )
        db.commit()
        db.refresh(m)
        return m
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Unable to create molecule from draft.") from exc
