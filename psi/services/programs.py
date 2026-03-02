from __future__ import annotations

import json
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from psi.core.audit import record_audit
from psi.core.models import AuditEvent, Batch, DataRecord, DecisionSnapshot, Evidence, Molecule, Program, ProgramMembership
from psi.core.utils import model_to_dict, now_utc
from psi.services.attribution import record_attribution_event
from psi.services.di.snapshot_diff import compute_snapshot_diff_struct
from psi.services.di.verify import verify_snapshot


def list_programs(db: Session) -> list[Program]:
    return db.query(Program).order_by(Program.name.asc(), Program.id.asc()).all()


def get_program(db: Session, program_id: int) -> Program | None:
    return db.get(Program, program_id)


def get_program_detail(
    db: Session,
    program_id: int,
    *,
    policy_version_filter: str | None = None,
    verify_lineage: bool = False,
) -> dict:
    p = get_program(db, program_id)
    if not p:
        raise KeyError("Program not found")

    molecules = db.query(Molecule).filter(Molecule.program_id == program_id).order_by(Molecule.created_at.desc()).all()
    program_memberships = (
        db.query(ProgramMembership, Molecule)
        .join(Molecule, Molecule.id == ProgramMembership.molecule_id)
        .filter(ProgramMembership.program_id == program_id)
        .order_by(ProgramMembership.sort_index.asc(), ProgramMembership.id.asc())
        .all()
    )
    all_molecules = (
        db.query(Molecule)
        .order_by(Molecule.primary_id.asc(), Molecule.id.asc())
        .all()
    )
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
        .filter(DecisionSnapshot.superseded_by_snapshot_id.is_(None))
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

    def _detect_is_di(snap: DecisionSnapshot, inputs: dict, output: dict) -> bool:
        # Match decisions.py detection logic (read-only, best-effort).
        return bool(
            (getattr(snap, "engine_key", None) == "di")
            or (str(getattr(snap, "schema_version", "") or "").startswith("di."))
            or (isinstance(output, dict) and ("decision_state" in output) and ("gates" in output))
            or (isinstance(inputs, dict) and (str(inputs.get("engine_key") or "").strip() == "di"))
            or (isinstance(inputs, dict) and str(inputs.get("schema_version") or "").startswith("di."))
        )

    # v1.2.9v: DI snapshot lineage (recent, read-only)
    lineage_rows: list[dict[str, Any]] = []
    lineage_snaps = (
        db.query(DecisionSnapshot, Molecule)
        .outerjoin(Molecule, Molecule.id == DecisionSnapshot.molecule_id)
        .filter(DecisionSnapshot.program_id == program_id)
        .order_by(DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc())
        .limit(100)
        .all()
    )

    _tmp_lineage: list[dict[str, Any]] = []
    for snap, mol in lineage_snaps:
        out = _safe_json(snap.outputs_json)
        inn = _safe_json(snap.inputs_json)
        if not _detect_is_di(snap, inn, out):
            continue

        pol = out.get("policy") if isinstance(out.get("policy"), dict) else {}
        policy_id = str(pol.get("policy_id") or pol.get("id") or "").strip()
        policy_version = str(pol.get("policy_version") or pol.get("version") or "").strip()
        decision_state = str(out.get("decision_state") or "")
        readiness = out.get("readiness") if isinstance(out.get("readiness"), dict) else {}
        readiness_state = str(readiness.get("state") or "").lower()

        _tmp_lineage.append(
            {
                "snapshot_id": int(snap.id),
                "created_at": snap.created_at,
                "molecule_id": int(snap.molecule_id) if snap.molecule_id is not None else None,
                "molecule_primary_id": (mol.primary_id if mol else ""),
                "molecule_title": (mol.title if mol else ""),
                "decision_key": str(snap.decision_key or ""),
                "policy_id": policy_id,
                "policy_version": policy_version,
                "decision_state": decision_state,
                "readiness_state": readiness_state,
                "is_superseded": int(snap.is_superseded) if snap.is_superseded is not None else None,
                "superseded_by_snapshot_id": int(snap.superseded_by_snapshot_id) if snap.superseded_by_snapshot_id is not None else None,
                "_out": out,
                "_in": inn,
            }
        )

    # Drift vs previous snapshot (same molecule + policy_id + policy_version)
    _tmp_lineage_sorted = sorted(
        _tmp_lineage, key=lambda r: (r.get("created_at") or "", int(r.get("snapshot_id") or 0))
    )
    prev_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in _tmp_lineage_sorted:
        mid = str(row.get("molecule_id") or "")
        pid = str(row.get("policy_id") or "")
        pver = str(row.get("policy_version") or "")
        key = (mid, pid, pver)
        prev = prev_by_key.get(key)
        if prev is not None:
            try:
                dr = compute_snapshot_diff_struct(
                    out1=prev.get("_out") or {},
                    in1=prev.get("_in") or {},
                    out2=row.get("_out") or {},
                    in2=row.get("_in") or {},
                )
                row["prev_snapshot_id"] = int(prev.get("snapshot_id") or 0)
                row["drift_vs_prev"] = str(dr.drift_label)
            except Exception:
                row["prev_snapshot_id"] = None
                row["drift_vs_prev"] = None
        else:
            row["prev_snapshot_id"] = None
            row["drift_vs_prev"] = None
        prev_by_key[key] = row

    for row in sorted(
        _tmp_lineage_sorted, key=lambda r: (r.get("created_at") or "", int(r.get("snapshot_id") or 0)), reverse=True
    ):
        row.pop("_out", None)
        row.pop("_in", None)
        lineage_rows.append(row)

    if verify_lineage and lineage_rows:
        for row in lineage_rows[:50]:
            sid = int(row.get("snapshot_id") or 0)
            if sid <= 0:
                continue
            try:
                report = verify_snapshot(db=db, snapshot_id=sid, debug=False)
                anchored = report.get("anchored_replay") if isinstance(report, dict) else None
                anchored_avail = bool(anchored.get("available")) if isinstance(anchored, dict) else False
                anchored_status = anchored.get("stored_vs_replay_classification") if anchored_avail else "UNAVAILABLE"
                row["verification"] = {
                    "anchored": str(anchored_status or ""),
                    "current": str(report.get("classification") if isinstance(report, dict) else ""),
                    "replay_vs_current": str(anchored.get("replay_vs_current_classification") if isinstance(anchored, dict) else ""),
                }
            except Exception:
                row["verification"] = {"anchored": "ERROR", "current": "ERROR", "replay_vs_current": "ERROR"}

    status_counts = {"READY": 0, "BLOCKED": 0, "UNKNOWN": 0}
    blocker_counts: dict[str, int] = {}
    gate_fail_counts: dict[str, int] = {}
    metric_present_counts: dict[str, int] = {}
    metric_missing_counts: dict[str, int] = {}
    ignore_reason_counts: dict[str, int] = {}
    qc_failed_metric_counts: dict[str, int] = {}
    qc_unreviewed_metric_counts: dict[str, int] = {}
    policy_version_counts: dict[str, int] = {}
    policy_id_counts: dict[str, int] = {}
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
        policy_id = str(pol.get("policy_id") or pol.get("id") or "").strip()
        policy_version = str(pol.get("policy_version") or pol.get("version") or "").strip()
        if policy_version:
            policy_version_counts[policy_version] = policy_version_counts.get(policy_version, 0) + 1
        if policy_id:
            policy_id_counts[policy_id] = policy_id_counts.get(policy_id, 0) + 1
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
                "policy_version": policy_version,
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

    pol_filter = (policy_version_filter or "").strip()
    if pol_filter:
        molecule_rollup_filtered = [r for r in molecule_rollup if str(r.get("policy_version") or "") == pol_filter]
    else:
        molecule_rollup_filtered = []

    di_dashboard = {
        "counts": status_counts,
        "top_blockers": sorted(blocker_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:15],
        "top_missing_metrics": sorted(metric_missing_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20],
        "top_failing_gates": sorted(gate_fail_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20],
        "metric_coverage": metric_coverage,
        "qc_ignore_reasons": sorted(ignore_reason_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20],
        "qc_failed_metrics": sorted(qc_failed_metric_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20],
        "qc_unreviewed_metrics": sorted(qc_unreviewed_metric_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20],
        "policy_versions": sorted(policy_version_counts.items(), key=lambda kv: (-kv[1], kv[0])),
        "policy_ids": sorted(policy_id_counts.items(), key=lambda kv: (-kv[1], kv[0])),
        "policy_version_filter": pol_filter or None,
        "lineage_verify_enabled": bool(verify_lineage),
        "molecule_rollup_filtered": sorted(molecule_rollup_filtered, key=lambda r: str(r.get("primary_id") or "")),
        "lineage": lineage_rows,
        "molecule_rollup": sorted(molecule_rollup, key=lambda r: str(r.get("primary_id") or "")),
    }

    return {
        "program": p,
        "molecules": molecules,
        "program_memberships_v3": [
            {
                "membership_id": int(pm.id),
                "program_id": int(pm.program_id),
                "molecule_id": int(m.id),
                "sort_index": int(pm.sort_index or 0),
                "primary_id": str(m.primary_id or ""),
                "title": str(m.title or ""),
                "owner_program_id": int(m.program_id) if m.program_id is not None else None,
            }
            for pm, m in program_memberships
        ],
        "all_molecules_for_membership": [
            {
                "id": int(m.id),
                "primary_id": str(m.primary_id or ""),
                "title": str(m.title or ""),
                "owner_program_id": int(m.program_id) if m.program_id is not None else None,
            }
            for m in all_molecules
        ],
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
    record_attribution_event(
        db,
        event_type="program.create",
        entity_type="Program",
        entity_id=int(p.id),
        metadata={"name": p.name},
    )
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
    record_attribution_event(
        db,
        event_type="program.update",
        entity_type="Program",
        entity_id=int(p.id),
        metadata={"reason": reason or "", "name": p.name},
    )
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


def list_program_memberships(db: Session, *, program_id: int) -> list[ProgramMembership]:
    return (
        db.query(ProgramMembership)
        .filter(ProgramMembership.program_id == program_id)
        .order_by(ProgramMembership.sort_index.asc(), ProgramMembership.id.asc())
        .all()
    )


def add_program_membership(
    db: Session,
    *,
    program_id: int,
    molecule_id: int,
    sort_index: int = 0,
) -> ProgramMembership:
    pm = ProgramMembership(
        program_id=int(program_id),
        molecule_id=int(molecule_id),
        sort_index=int(sort_index),
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(pm)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Program membership already exists or references invalid entities") from exc
    db.refresh(pm)
    record_attribution_event(
        db,
        event_type="program_membership.add",
        entity_type="ProgramMembership",
        entity_id=int(pm.id),
        metadata={"program_id": int(pm.program_id), "molecule_id": int(pm.molecule_id), "sort_index": int(pm.sort_index or 0)},
    )
    db.commit()
    return pm


def update_program_membership(
    db: Session,
    *,
    membership_id: int,
    sort_index: int,
) -> ProgramMembership:
    pm = db.get(ProgramMembership, membership_id)
    if not pm:
        raise KeyError("Program membership not found")
    pm.sort_index = int(sort_index)
    pm.updated_at = now_utc()
    db.add(pm)
    db.commit()
    db.refresh(pm)
    record_attribution_event(
        db,
        event_type="program_membership.update",
        entity_type="ProgramMembership",
        entity_id=int(pm.id),
        metadata={"sort_index": int(pm.sort_index or 0)},
    )
    db.commit()
    return pm


def remove_program_membership(db: Session, *, membership_id: int) -> None:
    pm = db.get(ProgramMembership, membership_id)
    if not pm:
        raise KeyError("Program membership not found")
    pm_id = int(pm.id)
    meta = {"program_id": int(pm.program_id), "molecule_id": int(pm.molecule_id), "sort_index": int(pm.sort_index or 0)}
    db.delete(pm)
    db.commit()
    record_attribution_event(
        db,
        event_type="program_membership.remove",
        entity_type="ProgramMembership",
        entity_id=pm_id,
        metadata=meta,
    )
    db.commit()
