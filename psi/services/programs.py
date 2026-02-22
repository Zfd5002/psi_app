from __future__ import annotations

import json

from sqlalchemy.orm import Session

from psi.core.audit import record_audit
from psi.core.models import AuditEvent, Batch, DataRecord, DecisionSnapshot, Evidence, Molecule, Program
from psi.core.utils import model_to_dict, now_utc


def list_programs(db: Session) -> list[Program]:
    return db.query(Program).order_by(Program.created_at.desc()).all()


def get_program(db: Session, program_id: int) -> Program | None:
    return db.get(Program, program_id)


def get_program_detail(db: Session, program_id: int) -> dict:
    p = get_program(db, program_id)
    if not p:
        raise KeyError("Program not found")

    molecules = db.query(Molecule).filter(Molecule.program_id == program_id).order_by(Molecule.created_at.desc()).all()
    recent_batches = (
        db.query(Batch)
        .join(Molecule)
        .filter(Molecule.program_id == program_id)
        .order_by(Batch.created_at.desc())
        .limit(10)
        .all()
    )
    recent_data = (
        db.query(DataRecord)
        .filter(DataRecord.program_id == program_id)
        .order_by(DataRecord.created_at.desc())
        .limit(10)
        .all()
    )
    recent_evidence = (
        db.query(Evidence)
        .filter(Evidence.program_id == program_id)
        .order_by(Evidence.created_at.desc())
        .limit(10)
        .all()
    )
    recent_decisions = (
        db.query(DecisionSnapshot)
        .filter(DecisionSnapshot.program_id == program_id)
        .order_by(DecisionSnapshot.created_at.desc())
        .limit(10)
        .all()
    )
    audits = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_type == "Program", AuditEvent.entity_id == program_id)
        .order_by(AuditEvent.timestamp.desc())
        .all()
    )

    # v1.2.9m: deterministic DI rollups (latest snapshot per molecule)
    all_snaps = (
        db.query(DecisionSnapshot)
        .filter(DecisionSnapshot.program_id == program_id)
        .order_by(DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc())
        .all()
    )

    latest_by_mol: dict[int, DecisionSnapshot] = {}
    for s in all_snaps:
        if s.molecule_id is None:
            continue
        mid = int(s.molecule_id)
        if mid not in latest_by_mol:
            latest_by_mol[mid] = s

    def _safe_json(s: str | None) -> dict:
        try:
            obj = json.loads(s or "{}")
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    status_counts = {"READY": 0, "BLOCKED": 0, "UNKNOWN": 0}
    blocker_counts: dict[str, int] = {}
    gate_fail_counts: dict[str, int] = {}
    metric_present_counts: dict[str, int] = {}
    metric_missing_counts: dict[str, int] = {}
    ignore_reason_counts: dict[str, int] = {}
    qc_failed_metric_counts: dict[str, int] = {}
    qc_unreviewed_metric_counts: dict[str, int] = {}
    molecule_rollup: list[dict] = []

    for m in molecules:
        snap = latest_by_mol.get(int(m.id))
        if not snap:
            molecule_rollup.append(
                {
                    "molecule_id": int(m.id),
                    "primary_id": m.primary_id,
                    "title": m.title,
                    "latest_snapshot_id": None,
                    "decision_state": None,
                    "readiness_state": "UNKNOWN",
                    "blocker_count": 0,
                    "policy_version": None,
                }
            )
            status_counts["UNKNOWN"] += 1
            continue

        out = _safe_json(snap.outputs_json)
        pol = out.get("policy") if isinstance(out.get("policy"), dict) else {}
        readiness = out.get("readiness") if isinstance(out.get("readiness"), dict) else {}
        decision_state = str(out.get("decision_state") or "")
        readiness_state = str(readiness.get("state") or "").lower()

        if readiness_state == "ready" or decision_state == "ready":
            bucket = "READY"
        elif readiness_state == "blocked" or decision_state == "blocked":
            bucket = "BLOCKED"
        else:
            bucket = "UNKNOWN"
        status_counts[bucket] += 1

        blockers = out.get("blockers") if isinstance(out.get("blockers"), list) else []
        for b in blockers:
            if isinstance(b, dict):
                k = str(b.get("blocker_key") or b.get("key") or "")
                if k:
                    blocker_counts[k] = blocker_counts.get(k, 0) + 1

        gates = out.get("gates") if isinstance(out.get("gates"), list) else []
        for g in gates:
            if not isinstance(g, dict):
                continue
            gk = str(g.get("gate_key") or "").strip()
            st = str(g.get("status") or g.get("outcome") or "").strip().lower()
            if gk and st and st != "pass":
                gate_fail_counts[gk] = gate_fail_counts.get(gk, 0) + 1

        soe = out.get("state_of_evidence") if isinstance(out.get("state_of_evidence"), dict) else {}
        soe3 = soe.get("soe_v0_3") if isinstance(soe.get("soe_v0_3"), dict) else {}
        cov = soe3.get("coverage") if isinstance(soe3.get("coverage"), dict) else {}
        present = cov.get("metrics_present") if isinstance(cov.get("metrics_present"), list) else []
        missing = cov.get("metrics_missing") if isinstance(cov.get("metrics_missing"), list) else []
        for mk in present:
            if mk is None:
                continue
            key = str(mk)
            if key:
                metric_present_counts[key] = metric_present_counts.get(key, 0) + 1
        for mk in missing:
            if mk is None:
                continue
            key = str(mk)
            if key:
                metric_missing_counts[key] = metric_missing_counts.get(key, 0) + 1

        ignored = soe.get("ignored_evidence") if isinstance(soe.get("ignored_evidence"), list) else []
        for ig in ignored:
            if not isinstance(ig, dict):
                continue
            rk = str(ig.get("reason_key") or ig.get("reason") or "").strip()
            mk = str(ig.get("metric_key") or "").strip()
            if rk:
                ignore_reason_counts[rk] = ignore_reason_counts.get(rk, 0) + 1
            if mk and rk == "qc_failed":
                qc_failed_metric_counts[mk] = qc_failed_metric_counts.get(mk, 0) + 1
            if mk and rk == "qc_unreviewed_strict":
                qc_unreviewed_metric_counts[mk] = qc_unreviewed_metric_counts.get(mk, 0) + 1

        molecule_rollup.append(
            {
                "molecule_id": int(m.id),
                "primary_id": m.primary_id,
                "title": m.title,
                "latest_snapshot_id": int(snap.id),
                "decision_state": decision_state,
                "readiness_state": bucket,
                "blocker_count": int(len(blockers)),
                "policy_version": str(pol.get("policy_version") or ""),
            }
        )

    total_molecules = len(latest_by_mol)
    metric_keys = set(metric_present_counts.keys()) | set(metric_missing_counts.keys())
    metric_coverage = []
    for mk in sorted(metric_keys):
        present = int(metric_present_counts.get(mk, 0))
        missing = int(metric_missing_counts.get(mk, 0))
        pct = round((present / float(total_molecules)), 1) if total_molecules > 0 else 0.0
        metric_coverage.append(
            {
                "metric_key": mk,
                "present_count": present,
                "missing_count": missing,
                "percent_present": pct,
            }
        )
    metric_coverage = sorted(metric_coverage, key=lambda r: (-int(r.get("missing_count") or 0), str(r.get("metric_key") or "")))

    di_dashboard = {
        "counts": status_counts,
        "top_blockers": sorted(blocker_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:15],
        "top_missing_metrics": sorted(metric_missing_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20],
        "top_failing_gates": sorted(gate_fail_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20],
        "metric_coverage": metric_coverage,
        "qc_ignore_reasons": sorted(ignore_reason_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20],
        "qc_failed_metrics": sorted(qc_failed_metric_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20],
        "qc_unreviewed_metrics": sorted(qc_unreviewed_metric_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20],
        "molecule_rollup": sorted(molecule_rollup, key=lambda r: str(r.get("primary_id") or "")),
    }

    return {
        "program": p,
        "molecules": molecules,
        "recent_batches": recent_batches,
        "recent_data": recent_data,
        "recent_evidence": recent_evidence,
        "recent_decisions": recent_decisions,
        "di_dashboard": di_dashboard,
        "audits": audits,
    }


def create_program(db: Session, *, name: str, description: str = "") -> Program:
    p = Program(
        name=name.strip(),
        description=description.strip(),
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    record_audit(db, entity_type="Program", entity_id=p.id, action="create", before=None, after=model_to_dict(p))
    db.commit()
    return p


def update_program(db: Session, *, program_id: int, name: str, description: str = "", reason: str = "") -> Program:
    p = get_program(db, program_id)
    if not p:
        raise KeyError("Program not found")
    before = model_to_dict(p)
    p.name = name.strip()
    p.description = description.strip()
    p.updated_at = now_utc()
    db.add(p)
    db.commit()
    record_audit(
        db,
        entity_type="Program",
        entity_id=p.id,
        action="update",
        before=before,
        after=model_to_dict(p),
        reason=reason or None,
    )
    db.commit()
    return p
