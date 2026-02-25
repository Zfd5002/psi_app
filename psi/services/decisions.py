from __future__ import annotations

import json
import datetime
from typing import Optional, Any

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from psi.core.audit import record_audit
from psi.core.decision_engine import load_rules, run_decision
from psi.core.models import (
    Batch,
    DataRecord,
    DecisionSnapshot,
    Evidence,
    EvidenceCitation,
    File as StoredFile,
    FileLink,
    Molecule,
    Program,
    OutcomeLabel,
)

from psi.core.utils import json_dumps_compact, model_to_dict, now_utc, stable_json_dumps

OUTCOME_LABEL_TYPES = [
    {"key": "correct", "label": "Correct", "note_required": False},
    {"key": "overly_conservative", "label": "Overly conservative", "note_required": False},
    {"key": "missed_risk", "label": "Missed risk", "note_required": False},
    {"key": "data_insufficient", "label": "Data insufficient", "note_required": False},
    {"key": "other", "label": "Other (requires note)", "note_required": True},
]

DI_REVIEW_VERDICTS = [
    {"key": "useful", "label": "Useful"},
    {"key": "incorrect", "label": "Incorrect"},
    {"key": "mixed", "label": "Mixed"},
]


def _di_snapshot_provenance_view_model(*, output: dict, inputs: dict) -> dict:
    out = output if isinstance(output, dict) else {}
    ins = inputs if isinstance(inputs, dict) else {}
    policy = out.get("policy") if isinstance(out.get("policy"), dict) else {}
    prov = out.get("provenance") if isinstance(out.get("provenance"), dict) else {}
    prov_template = prov.get("decision_template") if isinstance(prov.get("decision_template"), dict) else {}
    prov_scope = prov.get("decision_scope") if isinstance(prov.get("decision_scope"), dict) else {}
    short = (policy.get("shortlisting") if isinstance(policy.get("shortlisting"), dict) else None)
    if short is None:
        short = out.get("shortlisting")

    shortlisting_enabled = None
    if isinstance(short, dict):
        if "enabled" in short:
            shortlisting_enabled = bool(short.get("enabled"))
        elif "refused" in short or "ranked_candidates" in short:
            shortlisting_enabled = True
    elif "shortlisting" not in out:
        shortlisting_enabled = False

    return {
        "policy_name": str(policy.get("policy_name") or policy.get("name") or ins.get("policy_name") or ""),
        "template_name": str(prov_template.get("template_name") or prov_template.get("template_key") or ins.get("template_name") or ins.get("template_key") or ""),
        "template_key": str(prov_template.get("template_key") or ins.get("template_key") or ""),
        "policy_version": str(policy.get("policy_version") or policy.get("version") or ins.get("policy_version") or ""),
        "policy_semantics_hash": str(policy.get("policy_semantics_hash") or policy.get("hash") or ins.get("policy_semantics_hash") or ins.get("policy_hash") or ""),
        "policy_package_hash": str(policy.get("policy_package_hash") or ins.get("policy_package_hash") or ""),
        "shortlisting_enabled": shortlisting_enabled,
        "scope_type": str(prov_scope.get("scope_type") or ((prov.get("inputs_fingerprint") or {}).get("scope_type") if isinstance(prov.get("inputs_fingerprint"), dict) else "") or ins.get("scope_type") or ""),
        "scope_id": (
            prov_scope.get("scope_id")
            if (prov_scope.get("scope_id") is not None)
            else ((prov.get("inputs_fingerprint") or {}).get("scope_id") if isinstance(prov.get("inputs_fingerprint"), dict) else ins.get("scope_id"))
        ),
    }


def _latest_snapshot_label_summaries(outcomes: list[OutcomeLabel]) -> tuple[dict, dict]:
    latest_outcome = {"name": None, "value_text": None, "created_at": None}
    di_review = {"verdict": None, "rationale": None, "created_at": None}
    if not isinstance(outcomes, list):
        return latest_outcome, di_review

    for o in outcomes:
        name = str(getattr(o, "name", "") or "")
        if name == "di_review_verdict":
            di_review["verdict"] = getattr(o, "value_text", None)
            di_review["created_at"] = getattr(o, "created_at", None)
            continue
        if name == "di_review_rationale":
            di_review["rationale"] = getattr(o, "value_text", None)
            if di_review.get("created_at") is None:
                di_review["created_at"] = getattr(o, "created_at", None)
            continue
        latest_outcome = {
            "name": getattr(o, "name", None),
            "value_text": getattr(o, "value_text", None),
            "created_at": getattr(o, "created_at", None),
        }
    return latest_outcome, di_review


def _di_snapshot_ui_view_model(*, output: dict, outcomes: list[OutcomeLabel]) -> dict:
    out = output if isinstance(output, dict) else {}
    gate_outcomes = out.get("gate_outcomes") if isinstance(out.get("gate_outcomes"), dict) else {}
    ranking = out.get("ranking") if isinstance(out.get("ranking"), dict) else {}
    warnings = ((out.get("state_of_evidence") or {}).get("warnings") if isinstance(out.get("state_of_evidence"), dict) else [])
    blockers = out.get("blockers") if isinstance(out.get("blockers"), list) else []
    readiness = out.get("readiness") if isinstance(out.get("readiness"), dict) else {}

    gate_outcomes_ordered = [
        {"gate_key": gk, "data": (gate_outcomes.get(gk) or {})}
        for gk in sorted([str(k) for k in gate_outcomes.keys()])
    ]

    outcomes_ordered = list(outcomes or [])

    ranking_candidates = ranking.get("candidates") if isinstance(ranking.get("candidates"), list) else []
    ranking_candidates_ordered = sorted(
        [c for c in ranking_candidates if isinstance(c, dict)],
        key=lambda c: (
            str(c.get("candidate_type") or ""),
            -float(c.get("score") or 0.0),
            str(((c.get("tie_breaker") or {}).get("created_at") if isinstance(c.get("tie_breaker"), dict) else "") or ""),
            int(c.get("candidate_id") or 0),
        ),
    )

    warning_items = [w for w in (warnings or []) if isinstance(w, dict)]
    error_kind = ""
    error_detail = None
    if warning_items:
        first = warning_items[0]
        error_kind = str(first.get("kind") or "")
        error_detail = first.get("detail")
    if not error_kind and blockers:
        b0 = blockers[0] if isinstance(blockers[0], dict) else {}
        error_kind = str((b0 or {}).get("blocker_key") or "")
        error_detail = (b0 or {}).get("detail")

    error_block = {
        "present": bool(error_kind),
        "kind": error_kind,
        "detail": error_detail if isinstance(error_detail, (dict, list, str, int, float, bool)) or error_detail is None else str(error_detail),
        "readiness_state": str(readiness.get("state") or ""),
        "blocking_reasons": [str(x) for x in (readiness.get("blocking_reasons") or []) if str(x).strip()],
    }

    return {
        "gate_outcomes_ordered": gate_outcomes_ordered,
        "outcomes_ordered": outcomes_ordered,
        "ranking_candidates_ordered": ranking_candidates_ordered,
        "error_block": error_block,
    }


def _reconcile_single_active_snapshot_for_scope(
    db: Session,
    *,
    decision_key: str,
    program_id: int,
    molecule_id: Optional[int],
    batch_id: Optional[int],
    new_snapshot_id: int,
) -> None:
    """Enforce one active snapshot per exact scope before commit.

    Authoritative "active/latest" semantics use `superseded_by_snapshot_id IS NULL`.
    This reconciles any concurrently-created active rows to point at the new snapshot.
    """
    extra_active_ids = [
        int(r[0])
        for r in db.execute(
            text(
                """
                SELECT id
                FROM decision_snapshots
                WHERE decision_key = :dk
                  AND program_id = :pid
                  AND COALESCE(molecule_id, 0) = COALESCE(:mid, 0)
                  AND COALESCE(batch_id, 0) = COALESCE(:bid, 0)
                  AND superseded_by_snapshot_id IS NULL
                  AND id <> :new_id
                """
            ),
            {
                "dk": str(decision_key),
                "pid": int(program_id),
                "mid": molecule_id,
                "bid": batch_id,
                "new_id": int(new_snapshot_id),
            },
        ).fetchall()
    ]
    if extra_active_ids:
        q = text(
            """
            UPDATE decision_snapshots
            SET is_superseded = 1,
                superseded_at = CURRENT_TIMESTAMP,
                superseded_by_snapshot_id = :new_id
            WHERE id IN :ids
            """
        ).bindparams(bindparam("ids", expanding=True))
        db.execute(q, {"new_id": int(new_snapshot_id), "ids": list(extra_active_ids)})

    active_count = int(
        db.execute(
            text(
                """
                SELECT COUNT(1)
                FROM decision_snapshots
                WHERE decision_key = :dk
                  AND program_id = :pid
                  AND COALESCE(molecule_id, 0) = COALESCE(:mid, 0)
                  AND COALESCE(batch_id, 0) = COALESCE(:bid, 0)
                  AND superseded_by_snapshot_id IS NULL
                """
            ),
            {"dk": str(decision_key), "pid": int(program_id), "mid": molecule_id, "bid": batch_id},
        ).scalar()
        or 0
    )
    if active_count != 1:
        raise RuntimeError(
            "DecisionSnapshot supersession integrity violation: "
            f"expected exactly one active snapshot for scope, found {active_count}"
        )


def list_decision_snapshots(db: Session) -> list[DecisionSnapshot]:
    return db.query(DecisionSnapshot).order_by(DecisionSnapshot.created_at.desc()).limit(200).all()


def get_decision_new_context(db: Session, rules_path: str) -> dict:
    programs = db.query(Program).order_by(Program.name.asc()).all()
    molecules = db.query(Molecule).order_by(Molecule.primary_id.asc()).all()
    batches = db.query(Batch).order_by(Batch.created_at.desc()).all()
    rules = load_rules(rules_path)
    decision_keys = list(rules.get("decisions", {}).keys())

    return {
        "programs": programs,
        "molecules": molecules,
        "batches": batches,
        "decision_keys": decision_keys,
        "rules_version": rules.get("version"),
    }


def run_and_snapshot(
    db: Session,
    *,
    rules_path: str,
    program_id: int,
    molecule_id: Optional[int],
    batch_id: Optional[int],
    decision_key: str,
    assumptions_ack: bool,
) -> DecisionSnapshot:
    if not assumptions_ack:
        raise ValueError("Must acknowledge assumptions")

    rules = load_rules(rules_path)
    if decision_key not in rules.get("decisions", {}):
        raise ValueError("Invalid decision")

    q = db.query(Evidence).filter(Evidence.program_id == program_id)
    if batch_id:
        q = q.filter(
            (Evidence.molecule_id.is_(None) & Evidence.batch_id.is_(None))
            | ((Evidence.molecule_id == molecule_id) & Evidence.batch_id.is_(None))
            | (Evidence.batch_id == batch_id)
        )
    elif molecule_id:
        q = q.filter(
            (Evidence.molecule_id.is_(None) & Evidence.batch_id.is_(None))
            | ((Evidence.molecule_id == molecule_id) & Evidence.batch_id.is_(None))
        )
    else:
        q = q.filter(Evidence.molecule_id.is_(None), Evidence.batch_id.is_(None))

    evidence = q.all()
    result = run_decision(rules, decision_key, evidence)



    # v1.2.9q: supersede prior ACTIVE snapshots for this exact scope, transactionally.
    active_ids = [
        int(r[0])
        for r in db.execute(
            text(
                '''
                SELECT id
                FROM decision_snapshots
                WHERE decision_key = :dk
                  AND program_id = :pid
                  AND COALESCE(molecule_id, 0) = COALESCE(:mid, 0)
                  AND COALESCE(batch_id, 0) = COALESCE(:bid, 0)
                  AND (is_superseded IS NULL OR is_superseded = 0)
                '''
            ),
            {"dk": decision_key, "pid": int(program_id), "mid": molecule_id, "bid": batch_id},
        ).fetchall()
    ]

    try:
        if active_ids:
            q = text(
                '''
                UPDATE decision_snapshots
                SET is_superseded = 1,
                    superseded_at = CURRENT_TIMESTAMP,
                    superseded_by_snapshot_id = NULL
                WHERE id IN :ids
                '''
            ).bindparams(bindparam("ids", expanding=True))
            db.execute(q, {"ids": list(active_ids)})

        snap = DecisionSnapshot(
            program_id=program_id,
            molecule_id=molecule_id,
            batch_id=batch_id,
            decision_key=decision_key,
            rules_version=str(rules.get("version")),
            is_superseded=0,
            inputs_json=json_dumps_compact(
                {
                    "program_id": program_id,
                    "molecule_id": molecule_id,
                    "batch_id": batch_id,
                    "decision_key": decision_key,
                }
            ),
            outputs_json=json_dumps_compact(result),
            evidence_ids_json=json_dumps_compact(result.get("evidence_ids_used", [])),
            created_at=now_utc(),
        )
        db.add(snap)
        db.flush()

        if active_ids:
            q = text(
                '''
                UPDATE decision_snapshots
                SET superseded_by_snapshot_id = :new_id
                WHERE id IN :ids
                '''
            ).bindparams(bindparam("ids", expanding=True))
            db.execute(q, {"new_id": int(snap.id), "ids": list(active_ids)})

        _reconcile_single_active_snapshot_for_scope(
            db,
            decision_key=str(decision_key),
            program_id=int(program_id),
            molecule_id=molecule_id,
            batch_id=batch_id,
            new_snapshot_id=int(snap.id),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(snap)

    record_audit(db, entity_type="DecisionSnapshot", entity_id=snap.id, action="create", before=None, after=model_to_dict(snap))
    db.commit()

    return snap


def create_snapshot_freeze(
    db: Session,
    *,
    program_id: int,
    molecule_id: Optional[int],
    batch_id: Optional[int],
    decision_key: str,
    rules_version: str,
    as_of_ts: str,
    outputs: dict,
    notes: Optional[str] = None,
) -> DecisionSnapshot:
    """Create a DecisionSnapshot that explicitly freezes state 'as-of' time T.

    `as_of_ts` is stored in inputs_json as ISO8601 text.
    The ORM field stores a naive UTC datetime when parseable.
    `outputs` should contain the frozen feature vector / export row / model inputs.
    """
    t = (as_of_ts or "").strip()
    dt_asof = None
    if t:
        if t.endswith("Z"):
            t = t[:-1] + "+00:00"
        try:
            dt_asof = datetime.datetime.fromisoformat(t)
            if dt_asof.tzinfo is not None:
                dt_asof = dt_asof.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        except Exception:
            dt_asof = None

    snap = DecisionSnapshot(
        program_id=program_id,
        molecule_id=molecule_id,
        batch_id=batch_id,
        decision_key=decision_key,
        rules_version=rules_version,
        is_superseded=0,  # v1.2.9s: always explicit; NULL rows cause backfill collision
        inputs_json=json_dumps_compact(
            {
                "program_id": program_id,
                "molecule_id": molecule_id,
                "batch_id": batch_id,
                "decision_key": decision_key,
                "as_of_ts": as_of_ts,
            }
        ),
        outputs_json=json_dumps_compact(outputs),
        evidence_ids_json=json_dumps_compact([]),
        created_at=now_utc(),
        as_of_ts=dt_asof,
        notes=notes,
    )
    db.add(snap)
    db.flush()

    db.commit()
    db.refresh(snap)

    record_audit(db, entity_type="DecisionSnapshot", entity_id=snap.id, action="create_freeze", before=None, after=model_to_dict(snap))
    db.commit()
    return snap


def add_outcome_label(
    db: Session,
    *,
    snapshot_id: int,
    name: str,
    value_text: Optional[str] = None,
    value_num: Optional[float] = None,
    value_bool: Optional[bool] = None,
    version: str = "v1",
) -> OutcomeLabel:
    """Attach an outcome/label to a DecisionSnapshot."""
    lab = OutcomeLabel(
        snapshot_id=snapshot_id,
        name=name.strip(),
        value_text=(value_text.strip() if isinstance(value_text, str) else value_text),
        value_num=value_num,
        value_bool=(1 if value_bool is True else 0 if value_bool is False else None),
        version=version,
        created_at=now_utc(),
    )
    db.add(lab)
    db.commit()
    db.refresh(lab)

    record_audit(db, entity_type="OutcomeLabel", entity_id=lab.id, action="create", before=None, after=model_to_dict(lab))
    db.commit()
    return lab


def _detect_is_di(snap: DecisionSnapshot, inputs: dict, output: dict) -> bool:
    # DI snapshots share the DecisionSnapshot table but have a distinct output shape.
    # Detect robustly to preserve backward compatibility (older DI rows may have NULL engine_key).
    return bool(
        (getattr(snap, "engine_key", None) == "di")
        or (str(getattr(snap, "schema_version", "") or "").startswith("di."))
        or (isinstance(output, dict) and ("decision_state" in output) and ("gates" in output))
        or (isinstance(inputs, dict) and (str(inputs.get("engine_key") or "").strip() == "di"))
        or (isinstance(inputs, dict) and str(inputs.get("schema_version") or "").startswith("di."))
    )


def get_snapshot_detail(db: Session, snap_id: int) -> dict:
    snap = db.get(DecisionSnapshot, snap_id)
    if not snap:
        raise KeyError("DecisionSnapshot not found")

    output = json.loads(snap.outputs_json)
    inputs = json.loads(snap.inputs_json) if snap.inputs_json else {}

    is_di = _detect_is_di(snap, inputs, output)

    outcomes = (
        db.query(OutcomeLabel)
        .filter(OutcomeLabel.snapshot_id == snap.id)
        .order_by(OutcomeLabel.created_at.asc())
        .all()
    )
    latest_outcome_label, di_review = _latest_snapshot_label_summaries(outcomes)

    # Legacy rules-engine evidence tracing
    evidence = []
    citations = []
    data_records = []
    files_by_id = {}
    file_links_by_dr: dict[int, list[FileLink]] = {}

    if not is_di:
        evidence_ids = output.get("evidence_ids_used", []) if isinstance(output, dict) else []
        evidence = db.query(Evidence).filter(Evidence.id.in_(evidence_ids)).all() if evidence_ids else []

        citations = (
            db.query(EvidenceCitation).filter(EvidenceCitation.evidence_id.in_(evidence_ids)).all()
            if evidence_ids
            else []
        )
        dr_ids = sorted({c.data_record_id for c in citations})
        data_records = db.query(DataRecord).filter(DataRecord.id.in_(dr_ids)).all() if dr_ids else []

        dr_file_links = (
            db.query(FileLink)
            .filter(FileLink.entity_type == "DataRecord", FileLink.entity_id.in_(dr_ids))
            .all()
            if dr_ids
            else []
        )
        file_ids = sorted({fl.file_id for fl in dr_file_links})
        files = db.query(StoredFile).filter(StoredFile.id.in_(file_ids)).all() if file_ids else []

        files_by_id = {f.id: f for f in files}
        for fl in dr_file_links:
            file_links_by_dr.setdefault(fl.entity_id, []).append(fl)

    return {
        "snap": snap,
        "outcome_label_types": OUTCOME_LABEL_TYPES,
        "di_review_verdicts": DI_REVIEW_VERDICTS,
        "di_review": di_review,
        "latest_outcome_label": latest_outcome_label,
        "outcomes": outcomes,
        "output": output,
        "inputs": inputs,
        "di_snapshot_provenance": (_di_snapshot_provenance_view_model(output=output, inputs=inputs) if is_di else None),
        "di_snapshot_ui": (_di_snapshot_ui_view_model(output=output, outcomes=outcomes) if is_di else None),
        "is_di": is_di,
        "evidence": evidence,
        "citations": citations,
        "data_records": data_records,
        "files_by_id": files_by_id,
        "file_links_by_dr": file_links_by_dr,
    }


def get_snapshot_history(db: Session, *, snap_id: int) -> dict:
    snap = db.get(DecisionSnapshot, int(snap_id))
    if not snap:
        raise KeyError("DecisionSnapshot not found")

    rows = (
        db.query(DecisionSnapshot)
        .filter(DecisionSnapshot.decision_key == str(snap.decision_key))
        .filter(DecisionSnapshot.program_id == int(snap.program_id))
        .filter(DecisionSnapshot.molecule_id == (int(snap.molecule_id) if snap.molecule_id is not None else None))
        .filter(DecisionSnapshot.batch_id == (int(snap.batch_id) if snap.batch_id is not None else None))
        .order_by(DecisionSnapshot.id.desc())
        .all()
    )

    history = []
    for r in rows:
        out = json.loads(r.outputs_json) if r.outputs_json else {}
        comp = out.get("comparability") if isinstance(out.get("comparability"), dict) else {}
        st = out.get("state_transition") if isinstance(out.get("state_transition"), dict) else {}
        history.append(
            {
                "snapshot_id": int(r.id),
                "created_at": r.created_at,
                "decision_state": str(out.get("decision_state") or ""),
                "drift_type": str(out.get("drift_type") or ""),
                "comparability_is_comparable": (
                    bool(comp.get("is_comparable")) if isinstance(comp, dict) and "is_comparable" in comp else None
                ),
                "state_transition": st if isinstance(st, dict) else {},
                "is_superseded": bool(r.is_superseded) if r.is_superseded is not None else False,
                "superseded_by_snapshot_id": r.superseded_by_snapshot_id,
            }
        )

    return {"snap": snap, "history": history}


def get_snapshot_export_payload(db: Session, snap_id: int) -> dict:
    snap = db.get(DecisionSnapshot, snap_id)
    if not snap:
        raise KeyError("DecisionSnapshot not found")

    inputs = json.loads(snap.inputs_json) if snap.inputs_json else {}
    outputs = json.loads(snap.outputs_json) if snap.outputs_json else {}
    evidence_ids = json.loads(snap.evidence_ids_json) if snap.evidence_ids_json else []

    outcomes = (
        db.query(OutcomeLabel)
        .filter(OutcomeLabel.snapshot_id == snap.id)
        .order_by(OutcomeLabel.created_at.asc())
        .all()
    )

    return {
        "snapshot_meta": {
            "id": snap.id,
            "created_at": snap.created_at,
            "decision_key": snap.decision_key,
            "program_id": snap.program_id,
            "molecule_id": snap.molecule_id,
            "batch_id": snap.batch_id,
            "rules_version": snap.rules_version,
            "engine_key": getattr(snap, "engine_key", None),
            "schema_version": getattr(snap, "schema_version", None),
            "as_of_ts": getattr(snap, "as_of_ts", None),
        },
        "inputs": inputs,
        "outputs": outputs,
        "evidence_ids": evidence_ids,
        "outcome_labels": [
            {
                "id": o.id,
                "snapshot_id": o.snapshot_id,
                "name": o.name,
                "value_text": o.value_text,
                "value_num": o.value_num,
                "value_bool": o.value_bool,
                "version": o.version,
                "created_at": o.created_at,
            }
            for o in outcomes
        ],
    }


def _di_policy_from_output(out: dict) -> dict:
    pol = out.get("policy") if isinstance(out, dict) else {}
    if not isinstance(pol, dict):
        pol = {}
    return {
        "policy_id": str(pol.get("policy_id") or ""),
        "policy_name": str(pol.get("policy_name") or pol.get("name") or ""),
        "policy_version": str(pol.get("policy_version") or pol.get("version") or ""),
        "policy_schema_version": str(pol.get("policy_schema_version") or ""),
        "policy_semantics_hash": str(pol.get("policy_semantics_hash") or pol.get("hash") or ""),
        "policy_package_hash": str(pol.get("policy_package_hash") or ""),
        "source": str(pol.get("source") or ""),
        # Back-compat aliases used by older templates
        "hash": str(pol.get("hash") or pol.get("policy_semantics_hash") or ""),
        "name": str(pol.get("name") or pol.get("policy_name") or ""),
        "version": str(pol.get("version") or pol.get("policy_version") or ""),
    }


def _keys_from_list(items: Any, key_name: str) -> list[str]:
    out: set[str] = set()
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict):
                k = it.get(key_name)
                if k:
                    out.add(str(k))
            elif isinstance(it, str):
                out.add(it)
    return sorted(out)


def _gates_map(out: dict) -> dict[str, dict[str, str]]:
    m: dict[str, dict[str, str]] = {}
    gates = out.get("gates") if isinstance(out, dict) else []
    if not isinstance(gates, list):
        return m
    for g in gates:
        if not isinstance(g, dict):
            continue
        k = str(g.get("gate_key") or "")
        if not k:
            continue
        m[k] = {
            "status": str(g.get("status") or ""),
            "rationale": str(g.get("rationale") or ""),
        }
    return m


def _measurement_ids_used(out: dict) -> list[int]:
    mids = out.get("measurement_ids_used") if isinstance(out, dict) else []
    if isinstance(mids, list):
        try:
            return sorted([int(x) for x in mids])
        except Exception:
            return sorted([x for x in mids if isinstance(x, int)])
    return []


def get_snapshot_compare_context(db: Session, *, snap_a: int, snap_b: int) -> dict:
    # Local import to avoid circular import:
    # snapshot_diff depends on stable_json_dumps from this module.
    from psi.services.di.snapshot_diff import compute_snapshot_diff_by_id

    a = db.get(DecisionSnapshot, int(snap_a))
    b = db.get(DecisionSnapshot, int(snap_b))
    if not a or not b:
        return {"error": "One or both snapshots not found.", "snap_a": a, "snap_b": b}

    out_a = json.loads(a.outputs_json) if a.outputs_json else {}
    out_b = json.loads(b.outputs_json) if b.outputs_json else {}
    in_a = json.loads(a.inputs_json) if a.inputs_json else {}
    in_b = json.loads(b.inputs_json) if b.inputs_json else {}

    is_di_a = _detect_is_di(a, in_a, out_a)
    is_di_b = _detect_is_di(b, in_b, out_b)

    if not (is_di_a and is_di_b):
        return {
            "error": "DI compare is only supported for DI snapshots (engine_key=di / schema_version starts with di.).",
            "snap_a": a,
            "snap_b": b,
        }

    summary_banner = None
    if (a.decision_key != b.decision_key) or (a.program_id != b.program_id) or (a.batch_id != b.batch_id):
        summary_banner = "Note: snapshots differ in scope (decision_key/program/batch). Compare is still shown, but interpret with care."

    policy_a = _di_policy_from_output(out_a)
    policy_b = _di_policy_from_output(out_b)

    # Deterministic shared diff (CLI + web)
    dr = compute_snapshot_diff_by_id(db=db, id1=int(a.id), id2=int(b.id))

    drift_map = {
        "no_change": "VERIFIED",
        "policy_drift": "POLICY_DRIFT",
        "data_drift": "DATA_DRIFT",
        "qc_drift": "QC_DRIFT",
        "structural_drift": "STRUCTURAL_DRIFT",
    }
    drift_label = drift_map.get(str(dr.drift_label or ""), "STRUCTURAL_DRIFT")

    diff = {
        "drift_label": drift_label,
        "summary": dr.summary,
        "changes": dr.changes,
    }

    return {
        "error": None,
        "summary_banner": summary_banner,
        "snap_a": a,
        "snap_b": b,
        "policy_a": policy_a,
        "policy_b": policy_b,
        "diff": diff,
    }
