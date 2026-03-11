from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from psi.core.fasta import to_fasta, sha256_text
from psi.core.models import (
    BuilderVariantSet,
    BuilderVariantSetMember,
    Molecule,
    MoleculeComponent,
    MoleculeDerivation,
)
from psi.core.utils import now_utc
from psi.services import molecules as molecule_svc
from psi.services.molecule_sequences import get_or_create_chain
from psi.services.builder_ops import (
    apply_cdr_graft,
    apply_fc_swap,
    apply_kih_hole,
    apply_kih_knob,
    apply_point_mutations,
    clone_components,
    remove_kih,
    parse_point_mutation_tokens,
)
from psi.services.builder_validation import (
    validate_heavy_chain_for_fc_swap,
    validate_heavy_chain_for_kih,
    is_valid,
    validate_parent_exists,
    validate_point_mutations_not_empty,
    validate_primary_id,
    validate_target_component_exists,
)
from psi.services.sequence_diff import build_diff_rows


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
    assumptions: list[str] = field(default_factory=list)
    preview_rows: list[dict[str, str]] = field(default_factory=list)
    changed_residues: list[dict[str, str]] = field(default_factory=list)
    is_valid: bool = False
    inherited_program_id: int | None = None


@dataclass(frozen=True)
class VariantSetBuildSpec:
    family_type: str
    parent_molecule_id: int
    set_name: str
    naming_base: str
    rationale: str = ""
    members: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class VariantSetDraftMember:
    sort_index: int
    member_label: str
    member_summary: str
    molecule_spec: MoleculeBuildSpec
    molecule_draft: MoleculeDraft


@dataclass
class VariantSetDraft:
    family_type: str
    parent_molecule_id: int
    set_name: str
    naming_base: str
    rationale: str
    members: list[VariantSetDraftMember] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    is_valid: bool = False


@dataclass(frozen=True)
class VariantSetCreateMeta:
    actor: str = "builder"
    note: str = ""


@dataclass
class VariantSetCreateResult:
    variant_set_id: int
    molecule_ids: list[int]


def _compute_changed_residues(*, component: str, before: str, after: str) -> list[dict[str, str]]:
    if before == after:
        return []
    out: list[dict[str, str]] = []
    max_len = max(len(before), len(after))
    for idx in range(max_len):
        old = before[idx] if idx < len(before) else "-"
        new = after[idx] if idx < len(after) else "-"
        if old == new:
            continue
        out.append(
            {
                "component": str(component),
                "position": str(idx + 1),
                "from": str(old),
                "to": str(new),
            }
        )
    return out


def _attach_preview_diff_rows(preview_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in list(preview_rows or []):
        item = dict(row or {})
        before = str(item.get("before") or "")
        after = str(item.get("after") or "")
        item["diff_rows"] = build_diff_rows(original=before, edited=after)
        out.append(item)
    return out


def _slug_token(value: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip()).strip("_")
    return s or "variant"


def _build_member_primary_id(*, naming_base: str, member_label: str, fallback_index: int) -> str:
    base = _slug_token(naming_base)
    label = _slug_token(member_label)
    if label == "variant":
        label = f"v{int(fallback_index)}"
    return f"{base}_{label}"


def _resolve_family_root_molecule(db: Session, *, molecule: Molecule) -> Molecule:
    """Return the top-most parent in derivation lineage (best-effort, cycle-safe)."""
    cur = molecule
    seen: set[int] = set()
    while cur is not None and int(cur.id) not in seen:
        seen.add(int(cur.id))
        edge = (
            db.query(MoleculeDerivation)
            .filter(MoleculeDerivation.child_molecule_id == int(cur.id))
            .order_by(MoleculeDerivation.id.asc())
            .first()
        )
        if edge is None:
            return cur
        parent = db.get(Molecule, int(edge.parent_molecule_id))
        if parent is None:
            return cur
        cur = parent
    return molecule


def _primary_series_prefix(primary_id: str) -> str:
    """Derive a flat family-series prefix from a primary ID.

    Examples:
    - TUT1-A    -> TUT1-A
    - TUT1-A001 -> TUT1-A
    - TUT1-A-12 -> TUT1-A
    """
    pid = str(primary_id or "").strip()
    if not pid:
        return ""
    m = re.match(r"^(.*?)(?:[-_]?(\d+))$", pid)
    if not m:
        return pid
    prefix = str(m.group(1) or "").rstrip("-_")
    return prefix or pid


def suggest_new_primary_id_for_parent(
    db: Session,
    *,
    parent_molecule_id: int,
) -> dict[str, Any]:
    """Suggest next flat family-series primary ID for a selected parent.

    Returns payload suitable for Builder parent-context API.
    """
    parent = db.get(Molecule, int(parent_molecule_id))
    if parent is None:
        raise KeyError("Parent molecule not found")

    root = _resolve_family_root_molecule(db, molecule=parent)
    root_primary_id = str(root.primary_id or "").strip()
    prefix = _primary_series_prefix(root_primary_id or str(parent.primary_id or ""))
    if not prefix:
        prefix = str(parent.primary_id or "").strip()

    prog_id = int(parent.program_id)
    prog_rows = (
        db.query(Molecule.primary_id)
        .filter(Molecule.program_id == int(prog_id))
        .all()
    )
    pat = re.compile(rf"^{re.escape(prefix)}(?:[-_]?(\d+))$")
    max_n = 0
    max_width = 3
    for (pid_raw,) in prog_rows:
        pid = str(pid_raw or "").strip()
        mm = pat.match(pid)
        if not mm:
            continue
        digits = str(mm.group(1) or "")
        if not digits:
            continue
        try:
            n = int(digits)
        except Exception:
            continue
        max_n = max(max_n, n)
        max_width = max(max_width, len(digits))

    next_n = int(max_n) + 1
    suggested = f"{prefix}{next_n:0{max_width}d}"
    return {
        "parent_molecule_id": int(parent.id),
        "parent_primary_id": str(parent.primary_id or ""),
        "program_id": int(parent.program_id),
        "series_prefix": str(prefix),
        "lineage_root_molecule_id": int(root.id),
        "lineage_root_primary_id": str(root.primary_id or ""),
        "suggested_new_primary_id": str(suggested),
    }


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
    supported_modes = {"clone", "point_mutation", "cdr_graft", "fc_swap", "kih_toggle"}
    parent = db.get(Molecule, int(spec.parent_molecule_id))
    errors: list[str] = []
    errors.extend(validate_parent_exists(parent is not None))
    errors.extend(validate_primary_id(spec.new_primary_id))
    if mode not in supported_modes:
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

    derivation_type = mode
    summary = f"{derivation_type} from {parent_primary_id or 'unknown'}"
    operations_payload = list(spec.operations or [])
    warnings: list[str] = []
    assumptions: list[str] = []
    preview_rows: list[dict[str, str]] = []
    changed_residues: list[dict[str, str]] = []
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
                changed_residues.extend(
                    _compute_changed_residues(component=component, before=before_seq, after=mutated_seq)
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
    elif mode == "fc_swap" and parent is not None:
        op = operations_payload[0] if operations_payload else {}
        preset = str((op.get("preset") if isinstance(op, dict) else "") or "").strip().lower()
        errors.extend(validate_heavy_chain_for_fc_swap(available_components=parent_components.keys()))
        next_components, fc_errors = apply_fc_swap(components=parent_components, preset=preset)
        errors.extend(fc_errors)
        if not fc_errors:
            parent_components = next_components
            summary = f"fc swap ({preset}) from {parent_primary_id or 'unknown'}"
            before_hc = str(_load_parent_components(db, parent_molecule_id=int(parent.id)).get("HC1") or "")
            preview_rows.append(
                {
                    "component": "HC1",
                    "before": before_hc,
                    "after": str(parent_components.get("HC1") or ""),
                    "mutations": f"fc_preset={preset}",
                }
            )
            changed_residues.extend(
                _compute_changed_residues(
                    component="HC1",
                    before=before_hc,
                    after=str(parent_components.get("HC1") or ""),
                )
            )
        operations_payload = [{"type": "fc_swap", "preset": preset}]
    elif mode == "kih_toggle" and parent is not None:
        op = operations_payload[0] if operations_payload else {}
        action = str((op.get("action") if isinstance(op, dict) else "") or "").strip().lower()
        errors.extend(validate_heavy_chain_for_kih(available_components=parent_components.keys()))
        before_hc = str(parent_components.get("HC1") or "")
        after_hc = before_hc
        kih_errors: list[str] = []
        if action == "apply_knob":
            after_hc, kih_errors = apply_kih_knob(sequence=before_hc)
        elif action == "apply_hole":
            after_hc, kih_errors = apply_kih_hole(sequence=before_hc)
        elif action == "remove":
            after_hc, kih_errors = remove_kih(sequence=before_hc)
        else:
            errors.append("Unsupported KIH action.")
        errors.extend(kih_errors)
        if not kih_errors and before_hc:
            parent_components["HC1"] = after_hc
            summary = f"kih toggle ({action}) from {parent_primary_id or 'unknown'}"
            preview_rows.append(
                {
                    "component": "HC1",
                    "before": before_hc,
                    "after": after_hc,
                    "mutations": f"kih_action={action}",
                }
            )
            changed_residues.extend(
                _compute_changed_residues(component="HC1", before=before_hc, after=after_hc)
            )
        operations_payload = [{"type": "kih_toggle", "action": action}]
    elif mode == "cdr_graft":
        op = operations_payload[0] if operations_payload else {}
        framework_preset = str((op.get("framework_preset") if isinstance(op, dict) else "") or "human_vh3_vk1").strip().lower()
        light_chain_type = str((op.get("light_chain_type") if isinstance(op, dict) else "") or "kappa").strip().lower()
        numbering_scheme = str((op.get("numbering_scheme") if isinstance(op, dict) else "") or "kabat").strip().lower()
        def _opval(key: str) -> str:
            if isinstance(op, dict):
                return str(op.get(key) or "").strip()
            return ""
        cdrs = {
            "HCDR1": _opval("HCDR1"),
            "HCDR2": _opval("HCDR2"),
            "HCDR3": _opval("HCDR3"),
            "LCDR1": _opval("LCDR1"),
            "LCDR2": _opval("LCDR2"),
            "LCDR3": _opval("LCDR3"),
        }
        graft_components, graft_errors = apply_cdr_graft(
            framework_preset=framework_preset,
            light_chain_type=light_chain_type,
            numbering_scheme=numbering_scheme,
            cdrs=cdrs,
        )
        errors.extend(graft_errors)
        if not graft_errors:
            before_hc = str(parent_components.get("HC1") or "")
            before_lc = str(parent_components.get("LC1") or "")
            parent_components = graft_components
            summary = f"cdr graft ({framework_preset}/{light_chain_type}/{numbering_scheme})"
            warnings.append("Sequence reconstructed from CDRs using scaffold assumptions.")
            assumptions.append(f"framework_preset={framework_preset}")
            assumptions.append(f"light_chain_type={light_chain_type}")
            assumptions.append(f"numbering_scheme={numbering_scheme}")
            preview_rows.append(
                {
                    "component": "HC1",
                    "before": before_hc or "(template unavailable)",
                    "after": str(parent_components.get("HC1") or ""),
                    "mutations": "HCDR1,HCDR2,HCDR3",
                }
            )
            preview_rows.append(
                {
                    "component": "LC1",
                    "before": before_lc or "(template unavailable)",
                    "after": str(parent_components.get("LC1") or ""),
                    "mutations": "LCDR1,LCDR2,LCDR3",
                }
            )
            changed_residues.extend(
                _compute_changed_residues(
                    component="HC1",
                    before=before_hc or "",
                    after=str(parent_components.get("HC1") or ""),
                )
            )
            changed_residues.extend(
                _compute_changed_residues(
                    component="LC1",
                    before=before_lc or "",
                    after=str(parent_components.get("LC1") or ""),
                )
            )
        operations_payload = [
            {
                "type": "cdr_graft",
                "framework_preset": framework_preset,
                "light_chain_type": light_chain_type,
                "numbering_scheme": numbering_scheme,
                **cdrs,
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
        assumptions=assumptions,
        preview_rows=_attach_preview_diff_rows(preview_rows),
        changed_residues=changed_residues,
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


def create_variant_set_record(
    db: Session,
    *,
    name: str,
    builder_mode: str,
    summary: str = "",
    rationale: str = "",
    spec_json: str = "{}",
) -> BuilderVariantSet:
    row = BuilderVariantSet(
        name=str(name or "").strip(),
        builder_mode=str(builder_mode or "").strip(),
        summary=str(summary or "").strip() or None,
        rationale=str(rationale or "").strip() or None,
        spec_json=str(spec_json or "{}"),
        created_at=now_utc(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def add_variant_set_members(
    db: Session,
    *,
    variant_set_id: int,
    members: list[dict[str, Any]],
) -> list[BuilderVariantSetMember]:
    rows: list[BuilderVariantSetMember] = []
    ordered = sorted(
        [m for m in (members or []) if isinstance(m, dict)],
        key=lambda m: (int(m.get("sort_index") or 0), int(m.get("molecule_id") or 0), str(m.get("member_label") or "")),
    )
    for m in ordered:
        row = BuilderVariantSetMember(
            variant_set_id=int(variant_set_id),
            molecule_id=int(m.get("molecule_id") or 0),
            sort_index=int(m.get("sort_index") or 0),
            member_label=str(m.get("member_label") or ""),
            member_summary=str(m.get("member_summary") or "") or None,
            created_at=now_utc(),
        )
        db.add(row)
        rows.append(row)
    db.commit()
    return (
        db.query(BuilderVariantSetMember)
        .filter(BuilderVariantSetMember.variant_set_id == int(variant_set_id))
        .order_by(BuilderVariantSetMember.sort_index.asc(), BuilderVariantSetMember.id.asc())
        .all()
    )


def build_variant_set_draft(db: Session, spec: VariantSetBuildSpec) -> VariantSetDraft:
    parent = db.get(Molecule, int(spec.parent_molecule_id))
    errors: list[str] = []
    errors.extend(validate_parent_exists(parent is not None))
    if not str(spec.set_name or "").strip():
        errors.append("Variant set name is required.")
    if not str(spec.naming_base or "").strip():
        errors.append("Naming base is required.")
    supported_family_types = {"mutation_panel", "fc_panel", "kih_panel", "scaffold_panel"}
    family_type = str(spec.family_type or "").strip().lower()
    if family_type not in supported_family_types:
        errors.append("Unsupported variant family type.")

    rows = sorted(
        [m for m in (spec.members or []) if isinstance(m, dict)],
        key=lambda m: (int(m.get("sort_index") or 0), str(m.get("member_label") or ""), str(m.get("new_primary_id") or "")),
    )
    members: list[VariantSetDraftMember] = []
    warnings: list[str] = []
    for idx, row in enumerate(rows, start=1):
        member_label = str(row.get("member_label") or f"variant_{idx}").strip()
        mode = str(row.get("mode") or "").strip().lower() or "clone"
        new_primary_id = str(row.get("new_primary_id") or "").strip() or _build_member_primary_id(
            naming_base=str(spec.naming_base or ""),
            member_label=member_label,
            fallback_index=idx,
        )
        new_title = str(row.get("new_title") or "").strip() or f"{str(spec.set_name or '').strip()} — {member_label}"
        member_rationale = str(row.get("rationale") or "").strip() or str(spec.rationale or "").strip()
        operations = row.get("operations") if isinstance(row.get("operations"), list) else []
        molecule_spec = MoleculeBuildSpec(
            mode=mode,
            parent_molecule_id=int(spec.parent_molecule_id),
            new_primary_id=new_primary_id,
            new_title=new_title,
            rationale=member_rationale,
            operations=operations,
        )
        molecule_draft = build_molecule_draft(db, molecule_spec)
        member_summary = str(row.get("member_summary") or "").strip() or str(molecule_draft.derivation_summary or "")
        if molecule_draft.errors:
            errors.extend([f"{member_label}: {e}" for e in molecule_draft.errors])
        if molecule_draft.warnings:
            warnings.extend([f"{member_label}: {w}" for w in molecule_draft.warnings])
        members.append(
            VariantSetDraftMember(
                sort_index=int(row.get("sort_index") or idx),
                member_label=member_label,
                member_summary=member_summary,
                molecule_spec=molecule_spec,
                molecule_draft=molecule_draft,
            )
        )

    if not members:
        errors.append("At least one variant member is required.")

    draft = VariantSetDraft(
        family_type=family_type,
        parent_molecule_id=int(spec.parent_molecule_id),
        set_name=str(spec.set_name or "").strip(),
        naming_base=str(spec.naming_base or "").strip(),
        rationale=str(spec.rationale or "").strip(),
        members=members,
        errors=[e for e in errors if str(e or "").strip()],
        warnings=[w for w in warnings if str(w or "").strip()],
    )
    draft.is_valid = bool(not draft.errors and all(bool(m.molecule_draft.is_valid) for m in draft.members))
    return draft


def create_variant_set_from_draft(
    db: Session,
    draft: VariantSetDraft,
    meta: VariantSetCreateMeta,
) -> VariantSetCreateResult:
    if not bool(draft.is_valid):
        raise ValueError("Cannot create variant set from invalid draft.")
    del meta
    created_molecule_ids: list[int] = []
    for member in sorted(draft.members, key=lambda m: (int(m.sort_index), str(m.member_label))):
        created = create_molecule_from_draft(
            db,
            member.molecule_draft,
            MoleculeCreateMeta(actor="builder_variant_set"),
        )
        created_molecule_ids.append(int(created.id))

    payload = {
        "family_type": draft.family_type,
        "parent_molecule_id": int(draft.parent_molecule_id),
        "set_name": draft.set_name,
        "naming_base": draft.naming_base,
        "rationale": draft.rationale,
        "members": [
            {
                "sort_index": int(m.sort_index),
                "member_label": str(m.member_label),
                "member_summary": str(m.member_summary),
                "mode": str(m.molecule_spec.mode),
                "new_primary_id": str(m.molecule_spec.new_primary_id),
            }
            for m in sorted(draft.members, key=lambda x: (int(x.sort_index), str(x.member_label)))
        ],
    }
    row = create_variant_set_record(
        db,
        name=str(draft.set_name),
        builder_mode=str(draft.family_type),
        summary=f"{len(created_molecule_ids)} variants",
        rationale=str(draft.rationale),
        spec_json=json.dumps(payload, sort_keys=True, separators=(",", ":")),
    )
    members_payload = []
    ordered_members = sorted(draft.members, key=lambda x: (int(x.sort_index), str(x.member_label)))
    for idx, member in enumerate(ordered_members):
        members_payload.append(
            {
                "sort_index": int(member.sort_index),
                "molecule_id": int(created_molecule_ids[idx]),
                "member_label": str(member.member_label),
                "member_summary": str(member.member_summary),
            }
        )
    add_variant_set_members(db, variant_set_id=int(row.id), members=members_payload)
    return VariantSetCreateResult(variant_set_id=int(row.id), molecule_ids=created_molecule_ids)
