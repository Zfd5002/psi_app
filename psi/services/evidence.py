from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from psi.core.audit import record_audit
from psi.core.decision_engine import load_rules
from psi.core.models import AuditEvent, Batch, DataRecord, Evidence, EvidenceCitation, Molecule, Program
from psi.core.registry import get_allowed_data_sources_for_evidence
from psi.core.utils import model_to_dict, now_utc
from psi.services.data_records import create_data_record, get_form_context


def list_evidence(db: Session) -> dict:
    ev = db.query(Evidence).order_by(Evidence.created_at.desc()).limit(200).all()
    programs = db.query(Program).order_by(Program.name.asc()).all()
    molecules = db.query(Molecule).order_by(Molecule.primary_id.asc()).all()
    batches = db.query(Batch).order_by(Batch.created_at.desc()).all()
    return {"evidence": ev, "programs": programs, "molecules": molecules, "batches": batches}


def get_evidence(db: Session, evidence_id: int) -> Evidence | None:
    return db.get(Evidence, evidence_id)


def get_evidence_detail(db: Session, evidence_id: int) -> dict:
    ev = get_evidence(db, evidence_id)
    if not ev:
        raise KeyError("Evidence not found")
    citations = db.query(EvidenceCitation).filter(EvidenceCitation.evidence_id == evidence_id).all()
    dr_ids = [c.data_record_id for c in citations]
    data_records = db.query(DataRecord).filter(DataRecord.id.in_(dr_ids)).all() if dr_ids else []
    audits = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_type == "Evidence", AuditEvent.entity_id == evidence_id)
        .order_by(AuditEvent.timestamp.desc())
        .all()
    )
    return {"ev": ev, "citations": citations, "data_records": data_records, "audits": audits}


def create_evidence(
    db: Session,
    *,
    program_id: int,
    molecule_id: Optional[int],
    batch_id: Optional[int],
    domain: str,
    evidence_type: str,
    strength: int,
    summary: str,
    details: str = "",
    citation_data_record_ids: str = "",
    # inline DataRecord
    create_datarecord_inline: Optional[str] = None,
    dr_domain: str = "",
    dr_data_type: str = "",
    dr_method: str = "",
    dr_title: str = "",
    dr_notes: str = "",
    dr_run_date: str = "",
    dr_params_json: str = "{}",
    dr_results_json: str = "{}",
    dr_uploads=None,
    storage=None,
) -> Evidence:
    cited_ids = _parse_id_list(citation_data_record_ids)

    if create_datarecord_inline:
        rec = create_data_record(
            db,
            program_id=program_id,
            molecule_id=molecule_id,
            batch_id=batch_id,
            domain=(dr_domain or domain),
            data_type=dr_data_type,
            method=dr_method,
            title=(dr_title or "Inline data record"),
            notes=dr_notes,
            run_date=dr_run_date,
            params_json=dr_params_json,
            results_json=dr_results_json,
            uploads=dr_uploads,
            storage=storage,
            reason="created inline from Evidence",
        )
        cited_ids.append(rec.id)

    if not cited_ids:
        raise ValueError("Evidence must cite at least one Data Record")

    _enforce_citation_restrictions(db, evidence_type, cited_ids)

    ev = Evidence(
        program_id=program_id,
        molecule_id=molecule_id,
        batch_id=batch_id,
        domain=domain,
        evidence_type=evidence_type,
        strength=int(strength),
        summary=summary.strip(),
        details=details.strip() or None,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)

    for rid in cited_ids:
        db.add(EvidenceCitation(evidence_id=ev.id, data_record_id=rid))
    db.commit()

    record_audit(db, entity_type="Evidence", entity_id=ev.id, action="create", before=None, after=model_to_dict(ev))
    db.commit()

    return ev


def update_evidence(
    db: Session,
    *,
    evidence_id: int,
    program_id: int,
    molecule_id: Optional[int],
    batch_id: Optional[int],
    domain: str,
    evidence_type: str,
    strength: int,
    summary: str,
    details: str = "",
    citation_data_record_ids: str = "",
    reason: str = "",
) -> Evidence:
    ev = get_evidence(db, evidence_id)
    if not ev:
        raise KeyError("Evidence not found")

    cited_ids = _parse_id_list(citation_data_record_ids)
    if not cited_ids:
        raise ValueError("Evidence must cite at least one Data Record")

    _enforce_citation_restrictions(db, evidence_type, cited_ids)

    before = model_to_dict(ev)
    ev.program_id = program_id
    ev.molecule_id = molecule_id
    ev.batch_id = batch_id
    ev.domain = domain
    ev.evidence_type = evidence_type
    ev.strength = int(strength)
    ev.summary = summary.strip()
    ev.details = details.strip() or None
    ev.updated_at = now_utc()

    db.query(EvidenceCitation).filter(EvidenceCitation.evidence_id == evidence_id).delete()
    for rid in cited_ids:
        db.add(EvidenceCitation(evidence_id=evidence_id, data_record_id=rid))

    db.add(ev)
    db.commit()

    record_audit(
        db,
        entity_type="Evidence",
        entity_id=ev.id,
        action="update",
        before=before,
        after=model_to_dict(ev),
        reason=reason or None,
    )
    db.commit()
    return ev


def get_evidence_form_context(db: Session, rules_path: str) -> dict:
    ctx = get_form_context(db)
    rules = load_rules(rules_path)
    domains = list(rules["domains"].keys())
    domain_evidence_types = {}
    for d in domains:
        et = rules["domains"][d].get("evidence_types", [])
        domain_evidence_types[d] = list(et.keys()) if isinstance(et, dict) else list(et)
    ctx.update({"domains": domains, "domain_evidence_types": domain_evidence_types, "rules_version": rules.get("version")})
    return ctx


def _parse_id_list(raw: str) -> list[int]:
    raw = (raw or "").strip()
    if not raw:
        return []
    out: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except Exception:
            continue
    return out


def _enforce_citation_restrictions(db: Session, evidence_type: str, cited_ids: list[int]) -> None:
    allowed = get_allowed_data_sources_for_evidence(evidence_type)
    if not allowed.get("allowed"):
        return

    allowed_pairs = {(d["data_type"], d["method"]) for d in allowed["allowed"]}
    for rid in cited_ids:
        dr = db.get(DataRecord, rid)
        if not dr:
            raise ValueError(f"Invalid DataRecord id {rid}")
        if (dr.data_type, dr.method) not in allowed_pairs:
            raise ValueError(f"DataRecord {rid} ({dr.data_type}/{dr.method}) cannot be cited for {evidence_type}")
