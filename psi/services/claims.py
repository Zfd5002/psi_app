from __future__ import annotations

from typing import Any

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from psi.core.models import (
    DecisionSnapshot,
    ExperimentTask,
    ScientificClaim,
    ScientificClaimDecisionLink,
    ScientificClaimEvidenceLink,
    ScientificClaimTaskLink,
)
from psi.core.utils import now_utc
from psi.services import trajectory as trajectory_svc

CLAIM_STATUSES: tuple[str, ...] = (
    "hypothesis",
    "emerging",
    "supported",
    "contradicted",
    "archived",
)
CLAIM_CONFIDENCE_LEVELS: tuple[str, ...] = ("low", "medium", "high")
CLAIM_TYPES: tuple[str, ...] = (
    "affinity",
    "internalization",
    "developability",
    "in_vivo_readiness",
    "manufacturability",
    "safety_signal",
    "mechanism",
)
CLAIM_TYPE_TEMPLATES: dict[str, str] = {
    "affinity": "Molecule exhibits target affinity consistent with progression criteria.",
    "internalization": "Molecule internalization behavior supports intended mechanism.",
    "developability": "Molecule developability profile is within acceptable bounds.",
    "in_vivo_readiness": "Molecule is suitable to advance to in vivo studies.",
    "manufacturability": "Molecule manufacturability is consistent with scale-up screening needs.",
    "safety_signal": "Molecule safety signals are within acceptable exploratory limits.",
    "mechanism": "Molecule behavior is consistent with the intended biological mechanism.",
}
CLAIM_TYPE_METRIC_HINTS: dict[str, tuple[str, ...]] = {
    "affinity": ("kd_nM",),
    "internalization": ("internalization_score",),
    "developability": ("sec_monomer_pct", "tm_c"),
    "in_vivo_readiness": ("kd_nM", "sec_monomer_pct", "internalization_score"),
    "manufacturability": ("sec_monomer_pct", "hwm_pct"),
    "safety_signal": ("cytokine_release_index",),
    "mechanism": tuple(),
}

_ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "hypothesis": {"emerging"},
    "emerging": {"supported", "contradicted"},
    "supported": {"archived"},
    "contradicted": {"archived"},
    "archived": set(),
}


def can_transition_claim_status(*, from_status: str, to_status: str) -> bool:
    cur = normalize_claim_status(from_status)
    nxt = normalize_claim_status(to_status)
    return nxt in (_ALLOWED_STATUS_TRANSITIONS.get(cur) or set())


def normalize_claim_status(value: str | None) -> str:
    v = str(value or "").strip().lower()
    return v if v in CLAIM_STATUSES else "hypothesis"


def normalize_claim_confidence(value: str | None) -> str:
    v = str(value or "").strip().lower()
    return v if v in CLAIM_CONFIDENCE_LEVELS else "low"


def normalize_claim_type(value: str | None) -> str:
    v = str(value or "").strip().lower()
    return v if v in CLAIM_TYPES else "mechanism"


def format_claim_statement(*, claim_type: str, title: str, statement: str | None = None) -> str:
    st = str(statement or "").strip()
    if st:
        return st
    t = str(title or "").strip() or "Scientific claim"
    ct = normalize_claim_type(claim_type)
    tpl = str(CLAIM_TYPE_TEMPLATES.get(ct) or "")
    return f"[{ct}] {t}. {tpl}".strip()


def claim_type_template(claim_type: str) -> str:
    return str(CLAIM_TYPE_TEMPLATES.get(normalize_claim_type(claim_type)) or CLAIM_TYPE_TEMPLATES["mechanism"])


def claim_relevant_metric_keys(claim_type: str) -> list[str]:
    ct = normalize_claim_type(claim_type)
    return sorted({str(x) for x in (CLAIM_TYPE_METRIC_HINTS.get(ct) or tuple()) if str(x).strip()})


def create_claim(
    db: Session,
    *,
    scope_type: str,
    molecule_id: int | None,
    program_id: int | None,
    title: str,
    claim_type: str,
    statement: str,
    status: str = "hypothesis",
    confidence_level: str = "low",
    rationale: str = "",
) -> ScientificClaim:
    scope = str(scope_type or "").strip().lower()
    if scope not in {"molecule", "program"}:
        raise ValueError("scope_type must be molecule or program")
    if scope == "molecule" and molecule_id is None:
        raise ValueError("molecule scope requires molecule_id")
    if program_id is None and molecule_id is None:
        raise ValueError("claim requires molecule_id and/or program_id")
    c = ScientificClaim(
        scope_type=scope,
        molecule_id=(int(molecule_id) if molecule_id is not None else None),
        program_id=(int(program_id) if program_id is not None else None),
        title=str(title or "").strip() or "Untitled claim",
        claim_type=normalize_claim_type(claim_type),
        statement=format_claim_statement(claim_type=claim_type, title=title, statement=statement),
        status=normalize_claim_status(status),
        confidence_level=normalize_claim_confidence(confidence_level),
        rationale=str(rationale or "").strip() or None,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _claim_order_query(q):
    st_rank = case(
        (ScientificClaim.status == "emerging", 0),
        (ScientificClaim.status == "hypothesis", 1),
        (ScientificClaim.status == "supported", 2),
        (ScientificClaim.status == "contradicted", 3),
        (ScientificClaim.status == "archived", 4),
        else_=5,
    )
    conf_rank = case(
        (ScientificClaim.confidence_level == "high", 0),
        (ScientificClaim.confidence_level == "medium", 1),
        (ScientificClaim.confidence_level == "low", 2),
        else_=3,
    )
    return q.order_by(st_rank.asc(), conf_rank.asc(), ScientificClaim.updated_at.desc(), ScientificClaim.id.asc())


def list_claims_for_molecule(db: Session, *, molecule_id: int, include_archived: bool = False) -> list[ScientificClaim]:
    q = db.query(ScientificClaim).filter(ScientificClaim.molecule_id == int(molecule_id))
    if not include_archived:
        q = q.filter(ScientificClaim.status != "archived")
    return _claim_order_query(q).all()


def list_claims_for_program(db: Session, *, program_id: int, include_archived: bool = False) -> list[ScientificClaim]:
    q = db.query(ScientificClaim).filter(ScientificClaim.program_id == int(program_id))
    if not include_archived:
        q = q.filter(ScientificClaim.status != "archived")
    return _claim_order_query(q).all()


def list_claims(db: Session, *, include_archived: bool = False, limit: int = 200) -> list[ScientificClaim]:
    q = db.query(ScientificClaim)
    if not include_archived:
        q = q.filter(ScientificClaim.status != "archived")
    return _claim_order_query(q).limit(max(1, int(limit))).all()


def get_claim(db: Session, *, claim_id: int) -> ScientificClaim | None:
    return db.get(ScientificClaim, int(claim_id))


def update_claim_status(db: Session, *, claim_id: int, status: str) -> ScientificClaim:
    c = get_claim(db, claim_id=int(claim_id))
    if c is None:
        raise KeyError("ScientificClaim not found")
    nxt = normalize_claim_status(status)
    cur = normalize_claim_status(c.status)
    if nxt == cur:
        return c
    allowed = _ALLOWED_STATUS_TRANSITIONS.get(cur, set())
    if nxt not in allowed:
        raise ValueError(f"invalid status transition: {cur} -> {nxt}")
    c.status = nxt
    c.updated_at = now_utc()
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def update_claim_confidence(db: Session, *, claim_id: int, confidence_level: str) -> ScientificClaim:
    c = get_claim(db, claim_id=int(claim_id))
    if c is None:
        raise KeyError("ScientificClaim not found")
    c.confidence_level = normalize_claim_confidence(confidence_level)
    c.updated_at = now_utc()
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def archive_claim(db: Session, *, claim_id: int) -> ScientificClaim:
    c = get_claim(db, claim_id=int(claim_id))
    if c is None:
        raise KeyError("ScientificClaim not found")
    if normalize_claim_status(c.status) != "archived":
        c.status = "archived"
        c.updated_at = now_utc()
        db.add(c)
        db.commit()
        db.refresh(c)
    return c


def top_claims_for_molecule(db: Session, *, molecule_id: int, limit: int = 5) -> list[ScientificClaim]:
    return list_claims_for_molecule(db, molecule_id=int(molecule_id), include_archived=False)[: max(1, int(limit))]


def top_claims_for_program(db: Session, *, program_id: int, limit: int = 10) -> list[ScientificClaim]:
    return list_claims_for_program(db, program_id=int(program_id), include_archived=False)[: max(1, int(limit))]


def link_claim_to_data_record(
    db: Session,
    *,
    claim_id: int,
    data_record_id: int,
    direction: str,
    note: str = "",
) -> ScientificClaimEvidenceLink:
    d = str(direction or "").strip().lower()
    if d not in {"supporting", "contradicting", "contextual"}:
        raise ValueError("direction must be supporting|contradicting|contextual")
    row = (
        db.query(ScientificClaimEvidenceLink)
        .filter(
            ScientificClaimEvidenceLink.claim_id == int(claim_id),
            ScientificClaimEvidenceLink.data_record_id == int(data_record_id),
            ScientificClaimEvidenceLink.direction == d,
        )
        .order_by(ScientificClaimEvidenceLink.id.asc())
        .first()
    )
    if row is None:
        row = ScientificClaimEvidenceLink(
            claim_id=int(claim_id),
            data_record_id=int(data_record_id),
            direction=d,
            note=str(note or "").strip() or None,
            created_at=now_utc(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def unlink_claim_from_data_record(
    db: Session,
    *,
    claim_id: int,
    data_record_id: int,
    direction: str | None = None,
) -> int:
    q = db.query(ScientificClaimEvidenceLink).filter(
        ScientificClaimEvidenceLink.claim_id == int(claim_id),
        ScientificClaimEvidenceLink.data_record_id == int(data_record_id),
    )
    if direction is not None:
        q = q.filter(ScientificClaimEvidenceLink.direction == str(direction).strip().lower())
    rows = q.all()
    n = len(rows)
    for r in rows:
        db.delete(r)
    if n:
        db.commit()
    return int(n)


def list_claim_evidence(db: Session, *, claim_id: int) -> list[ScientificClaimEvidenceLink]:
    return (
        db.query(ScientificClaimEvidenceLink)
        .filter(ScientificClaimEvidenceLink.claim_id == int(claim_id))
        .order_by(
            case(
                (ScientificClaimEvidenceLink.direction == "supporting", 0),
                (ScientificClaimEvidenceLink.direction == "contradicting", 1),
                (ScientificClaimEvidenceLink.direction == "contextual", 2),
                else_=3,
            ).asc(),
            ScientificClaimEvidenceLink.created_at.asc(),
            ScientificClaimEvidenceLink.id.asc(),
        )
        .all()
    )


def link_claim_to_decision(
    db: Session,
    *,
    claim_id: int,
    decision_snapshot_id: int,
    relationship_type: str,
) -> ScientificClaimDecisionLink:
    rel = str(relationship_type or "").strip().lower() or "informs"
    row = (
        db.query(ScientificClaimDecisionLink)
        .filter(
            ScientificClaimDecisionLink.claim_id == int(claim_id),
            ScientificClaimDecisionLink.decision_snapshot_id == int(decision_snapshot_id),
            ScientificClaimDecisionLink.relationship_type == rel,
        )
        .order_by(ScientificClaimDecisionLink.id.asc())
        .first()
    )
    if row is None:
        row = ScientificClaimDecisionLink(
            claim_id=int(claim_id),
            decision_snapshot_id=int(decision_snapshot_id),
            relationship_type=rel,
            created_at=now_utc(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def list_claim_decisions(db: Session, *, claim_id: int) -> list[ScientificClaimDecisionLink]:
    return (
        db.query(ScientificClaimDecisionLink)
        .filter(ScientificClaimDecisionLink.claim_id == int(claim_id))
        .order_by(ScientificClaimDecisionLink.created_at.asc(), ScientificClaimDecisionLink.id.asc())
        .all()
    )


def link_claim_to_task(
    db: Session,
    *,
    claim_id: int,
    experiment_task_id: int,
    relationship_type: str,
) -> ScientificClaimTaskLink:
    rel = str(relationship_type or "").strip().lower() or "tests"
    row = (
        db.query(ScientificClaimTaskLink)
        .filter(
            ScientificClaimTaskLink.claim_id == int(claim_id),
            ScientificClaimTaskLink.experiment_task_id == int(experiment_task_id),
            ScientificClaimTaskLink.relationship_type == rel,
        )
        .order_by(ScientificClaimTaskLink.id.asc())
        .first()
    )
    if row is None:
        row = ScientificClaimTaskLink(
            claim_id=int(claim_id),
            experiment_task_id=int(experiment_task_id),
            relationship_type=rel,
            created_at=now_utc(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def list_claim_tasks(db: Session, *, claim_id: int) -> list[ScientificClaimTaskLink]:
    return (
        db.query(ScientificClaimTaskLink)
        .filter(ScientificClaimTaskLink.claim_id == int(claim_id))
        .order_by(ScientificClaimTaskLink.created_at.asc(), ScientificClaimTaskLink.id.asc())
        .all()
    )


def summarize_claim_support(db: Session, *, claim_id: int) -> dict[str, int]:
    rows = list_claim_evidence(db, claim_id=int(claim_id))
    supporting = sum(1 for r in rows if str(r.direction or "") == "supporting")
    contradicting = sum(1 for r in rows if str(r.direction or "") == "contradicting")
    contextual = sum(1 for r in rows if str(r.direction or "") == "contextual")
    return {
        "supporting_count": int(supporting),
        "contradicting_count": int(contradicting),
        "contextual_count": int(contextual),
    }


def summarize_claim_conflict(db: Session, *, claim_id: int) -> dict[str, Any]:
    s = summarize_claim_support(db, claim_id=int(claim_id))
    has_conflict = int(s.get("supporting_count") or 0) > 0 and int(s.get("contradicting_count") or 0) > 0
    return {
        **s,
        "has_conflict": bool(has_conflict),
    }


def summarize_claim_maturity(db: Session, *, claim_id: int) -> dict[str, Any]:
    claim = get_claim(db, claim_id=int(claim_id))
    if claim is None:
        raise KeyError("ScientificClaim not found")
    support = summarize_claim_support(db, claim_id=int(claim_id))
    decisions_n = int(len(list_claim_decisions(db, claim_id=int(claim_id))))
    task_links = list_claim_tasks(db, claim_id=int(claim_id))
    task_ids = [int(x.experiment_task_id) for x in task_links]
    open_n = 0
    done_n = 0
    if task_ids:
        rows = (
            db.query(ExperimentTask.status)
            .filter(ExperimentTask.id.in_(task_ids))
            .all()
        )
        for row in rows:
            st = str(row[0] or "").strip().lower()
            if st == "done":
                done_n += 1
            else:
                open_n += 1
    maturity = "hypothesis"
    status = normalize_claim_status(claim.status)
    if status == "supported" and int(support.get("supporting_count") or 0) > 0:
        maturity = "supported"
    elif status == "contradicted" and int(support.get("contradicting_count") or 0) > 0:
        maturity = "contradicted"
    elif status in {"emerging", "supported", "contradicted"}:
        maturity = status
    return {
        "claim_id": int(claim.id),
        "status": status,
        "supporting_count": int(support.get("supporting_count") or 0),
        "contradicting_count": int(support.get("contradicting_count") or 0),
        "contextual_count": int(support.get("contextual_count") or 0),
        "linked_decisions_count": int(decisions_n),
        "linked_tasks_open": int(open_n),
        "linked_tasks_done": int(done_n),
        "maturity_summary": maturity,
    }


def get_claim_detail(db: Session, *, claim_id: int) -> dict[str, Any]:
    c = get_claim(db, claim_id=int(claim_id))
    if c is None:
        raise KeyError("ScientificClaim not found")
    task_links = list_claim_tasks(db, claim_id=int(claim_id))
    task_ids = [int(x.experiment_task_id) for x in task_links]
    open_tasks = []
    if task_ids:
        trows = (
            db.query(ExperimentTask)
            .filter(ExperimentTask.id.in_(task_ids))
            .filter(ExperimentTask.status != "done")
            .order_by(ExperimentTask.updated_at.desc(), ExperimentTask.id.asc())
            .all()
        )
        open_tasks = [
            {
                "task_id": int(t.id),
                "status": str(t.status or ""),
                "urgency": str(t.urgency or ""),
                "metric_key": str(t.metric_key or ""),
                "suggested_assay": str(t.suggested_assay or ""),
            }
            for t in trows
        ]
    trajectory_candidates = []
    if c.molecule_id is not None:
        all_cands = trajectory_svc.rank_trajectory_candidates(
            trajectory_svc.generate_trajectory_candidates(db, molecule_id=int(c.molecule_id))
        )
        hints = set(claim_relevant_metric_keys(str(c.claim_type or "")))
        if hints:
            trajectory_candidates = [r for r in all_cands if str(r.get("metric_key") or "") in hints][:5]
        else:
            trajectory_candidates = all_cands[:5]
    return {
        "claim": c,
        "evidence_links": list_claim_evidence(db, claim_id=int(claim_id)),
        "decision_links": list_claim_decisions(db, claim_id=int(claim_id)),
        "task_links": task_links,
        "open_linked_tasks": open_tasks,
        "trajectory_candidates": trajectory_candidates,
        "maturity": summarize_claim_maturity(db, claim_id=int(claim_id)),
    }
