from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from psi.core.antibody_domains import extract_variable_span_anarci
from psi.core.biochem import liability_sites
from psi.core.fasta import normalize_aa_sequence
from psi.core.models import DomainInstance, Molecule, MoleculeComponent, SequenceEntity
from psi.core.utils import now_utc
from psi.services.domain_artifacts import (
    ensure_domain_artifact_running,
    set_artifact_failure,
    set_artifact_success,
)
from psi.services.sequences import get_or_create_sequence_entity


DEFAULT_TOOL_NAME = "abnumber"


def _settings_hash(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(blob.encode("utf-8")).hexdigest()


def ensure_sequence_entity(db: Session, seq_norm: str) -> SequenceEntity:
    ent = get_or_create_sequence_entity(db, seq_norm)
    if not ent:
        raise ValueError("Empty sequence")
    return ent


def ensure_component_sequence_entity(db: Session, c: MoleculeComponent) -> None:
    if c.sequence_entity_id:
        return
    ent = get_or_create_sequence_entity(db, c.fasta)
    if not ent:
        return
    c.sequence_entity_id = ent.id
    c.updated_at = now_utc()
    db.add(c)
    db.commit()


def ensure_liability_sites_artifact(
    db: Session,
    *,
    sequence_id: int,
    tool_name: str,
    tool_version: str,
    settings_hash: str,
) -> None:
    """Ensure liability sites artifact exists (cheap, safe to call repeatedly)."""
    settings = {"settings_hash": settings_hash}
    art, created = ensure_domain_artifact_running(
        db,
        sequence_id=sequence_id,
        artifact_type="liability_sites",
        domain_type=None,
        tool_name=tool_name,
        tool_version=tool_version,
        settings=settings,
    )
    if not created:
        return
    try:
        seq = db.get(SequenceEntity, sequence_id)
        if not seq:
            set_artifact_failure(db, art, "Sequence entity not found")
            return
        result = {"sites": liability_sites(seq.sequence_norm)}
        set_artifact_success(db, art, result)
    except Exception as e:
        set_artifact_failure(db, art, str(e))


def _upsert_domain_instance(
    db: Session,
    *,
    molecule_id: int,
    component_id: int,
    domain_type: str,
    start_idx: int,
    end_idx: int,
    domain_sequence_id: Optional[int],
    source: str,
    method: str,
    tool_name: Optional[str],
    tool_version: Optional[str],
    settings_hash: Optional[str],
    status: str,
    warnings: list[str] | None,
    error: str | None,
) -> DomainInstance:
    existing = db.execute(
        select(DomainInstance)
        .where(DomainInstance.molecule_id == molecule_id)
        .where(DomainInstance.component_id == component_id)
        .where(DomainInstance.domain_type == domain_type)
        .order_by(DomainInstance.updated_at.desc())
    ).scalar_one_or_none()

    if existing and (existing.source or "").lower() == "user" and source == "auto":
        return existing

    if existing:
        existing.start_idx = int(start_idx)
        existing.end_idx = int(end_idx)
        existing.domain_sequence_id = domain_sequence_id
        existing.source = source
        existing.method = method
        existing.tool_name = tool_name
        existing.tool_version = tool_version
        existing.settings_hash = settings_hash
        existing.status = status
        existing.warnings_json = json.dumps(warnings or [], ensure_ascii=False)
        existing.error = error
        existing.updated_at = now_utc()
        db.add(existing)
        db.commit()
        return existing

    inst = DomainInstance(
        molecule_id=molecule_id,
        component_id=component_id,
        domain_type=domain_type,
        start_idx=int(start_idx),
        end_idx=int(end_idx),
        domain_sequence_id=domain_sequence_id,
        source=source,
        method=method,
        tool_name=tool_name,
        tool_version=tool_version,
        settings_hash=settings_hash,
        status=status,
        warnings_json=json.dumps(warnings or [], ensure_ascii=False),
        error=error,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst


def extract_domains_for_molecule(db: Session, molecule_id: int) -> None:
    m = db.get(Molecule, molecule_id)
    if not m:
        return
    fmt = (m.molecule_format or "").strip()
    comps = db.execute(select(MoleculeComponent).where(MoleculeComponent.molecule_id == molecule_id)).scalars().all()
    by_role = {c.role: c for c in comps}

    for c in comps:
        ensure_component_sequence_entity(db, c)

    settings = {"purpose": "domain_extraction", "format": fmt, "policy": "vnext"}
    settings_hash = _settings_hash(settings)
    tool_version = "unknown"
    try:
        import abnumber  # type: ignore

        tool_version = getattr(abnumber, "__version__", "unknown")
    except Exception:
        tool_version = "unavailable"

    def _record_failure(component: MoleculeComponent, domain_type: str, msg: str) -> None:
        _upsert_domain_instance(
            db,
            molecule_id=molecule_id,
            component_id=component.id,
            domain_type=domain_type,
            start_idx=0,
            end_idx=0,
            domain_sequence_id=None,
            source="auto",
            method="abnumber",
            tool_name=DEFAULT_TOOL_NAME,
            tool_version=tool_version,
            settings_hash=settings_hash,
            status="failure",
            warnings=[],
            error=msg,
        )

    if fmt == "scFv":
        for role, dtype in (("VH", "VH"), ("VL", "VL")):
            c = by_role.get(role)
            if not c or not c.fasta:
                continue
            seq = normalize_aa_sequence(c.fasta)
            if not seq:
                continue
            ent = get_or_create_sequence_entity(db, seq)
            _upsert_domain_instance(
                db,
                molecule_id=molecule_id,
                component_id=c.id,
                domain_type=dtype,
                start_idx=0,
                end_idx=len(seq),
                domain_sequence_id=ent.id if ent else None,
                source="auto",
                method="explicit_component",
                tool_name=None,
                tool_version=None,
                settings_hash=settings_hash,
                status="success",
                warnings=[],
                error=None,
            )
        return

    if fmt != "IgG":
        return

    for role, want in (("HC1", "VH"), ("HC2", "VH"), ("LC1", "VL"), ("LC2", "VL")):
        c = by_role.get(role)
        if not c or not c.fasta:
            continue
        seq = normalize_aa_sequence(c.fasta)
        if not seq:
            continue
        try:
            span = extract_variable_span_anarci(seq)
            start = int(span.start)
            end = int(span.end_excl)
        except Exception as e:
            _record_failure(c, want, f"ANARCI extraction failed: {e}")
            continue
        if end <= start or end > len(seq):
            _record_failure(c, want, f"Invalid variable span start={start} end={end} len={len(seq)}")
            continue
        dom_seq = seq[start:end]
        ent = get_or_create_sequence_entity(db, dom_seq)
        _upsert_domain_instance(
            db,
            molecule_id=molecule_id,
            component_id=c.id,
            domain_type=want,
            start_idx=start,
            end_idx=end,
            domain_sequence_id=ent.id if ent else None,
            source="auto",
            method="anarci_domain_detection",
            tool_name="anarci",
            tool_version="vendored",
            settings_hash=settings_hash,
            status="success",
            warnings=[],
            error=None,
        )



def upsert_user_domain_instance(
    db: Session,
    *,
    molecule_id: int,
    component_id: int,
    domain_type: str,
    start_idx: int,
    end_idx: int,
) -> DomainInstance:
    c = db.get(MoleculeComponent, component_id)
    if not c:
        raise KeyError("Component not found")
    seq = normalize_aa_sequence(c.fasta)
    if start_idx < 0 or end_idx <= start_idx or end_idx > len(seq):
        raise ValueError("Invalid span")
    dom_seq = seq[start_idx:end_idx]
    ent = get_or_create_sequence_entity(db, dom_seq)
    return _upsert_domain_instance(
        db,
        molecule_id=molecule_id,
        component_id=component_id,
        domain_type=domain_type,
        start_idx=start_idx,
        end_idx=end_idx,
        domain_sequence_id=ent.id if ent else None,
        source="user",
        method="manual_span",
        tool_name=None,
        tool_version=None,
        settings_hash=None,
        status="success",
        warnings=[],
        error=None,
    )
