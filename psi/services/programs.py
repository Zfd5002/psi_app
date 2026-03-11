from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from psi.core.audit import record_audit
from psi.core.models import (
    AuditEvent,
    Batch,
    DataRecord,
    DecisionSnapshot,
    ExperimentTask,
    Evidence,
    Molecule,
    Program,
    ProgramMembership,
    ProgramMoleculeStatus,
)
from psi.core.utils import model_to_dict, now_utc
from psi.services.attribution import record_attribution_event
from psi.services.di.snapshot_diff import compute_snapshot_diff_struct
from psi.services.di.verify import verify_snapshot
from psi.services.metric_catalog import metric_catalog_entry, metric_group_for_key, metric_group_sort_key
from psi.services.evidence_preview import build_record_evidence_preview
from psi.web.ui_labels import humanize_key
from psi.services import claims as claims_svc
from psi.services import plans as plans_svc
from psi.services import narratives as narratives_svc

PROGRAM_MOLECULE_ROLES: tuple[str, ...] = (
    "lead",
    "backup",
    "active",
    "watchlist",
    "deprioritized",
    "archived",
)

PROGRAM_EVIDENCE_ROWS_SQL = """
            SELECT
              dr.molecule_id AS molecule_id,
              dm.metric_key AS metric_key
            FROM data_records dr
            JOIN data_measurements dm ON dm.data_record_id = dr.id
            WHERE dr.program_id = :pid
              AND dr.molecule_id IS NOT NULL
            ORDER BY dr.molecule_id ASC, dm.metric_key ASC, dm.id ASC
            """


def _normalize_program_molecule_role(role: str | None) -> str:
    r = str(role or "").strip().lower()
    return r if r in PROGRAM_MOLECULE_ROLES else "active"


def list_program_molecule_statuses(db: Session, *, program_id: int) -> list[ProgramMoleculeStatus]:
    return (
        db.query(ProgramMoleculeStatus)
        .filter(ProgramMoleculeStatus.program_id == int(program_id))
        .order_by(ProgramMoleculeStatus.molecule_id.asc(), ProgramMoleculeStatus.id.asc())
        .all()
    )


def upsert_program_molecule_status(
    db: Session,
    *,
    program_id: int,
    molecule_id: int,
    role: str,
    rationale: str = "",
) -> ProgramMoleculeStatus:
    row = (
        db.query(ProgramMoleculeStatus)
        .filter(
            ProgramMoleculeStatus.program_id == int(program_id),
            ProgramMoleculeStatus.molecule_id == int(molecule_id),
        )
        .order_by(ProgramMoleculeStatus.id.asc())
        .first()
    )
    norm_role = _normalize_program_molecule_role(role)
    norm_rationale = str(rationale or "").strip()
    if row is None:
        row = ProgramMoleculeStatus(
            program_id=int(program_id),
            molecule_id=int(molecule_id),
            role=norm_role,
            rationale=norm_rationale,
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        db.add(row)
    else:
        row.role = norm_role
        row.rationale = norm_rationale
        row.updated_at = now_utc()
        db.add(row)
    db.commit()
    db.refresh(row)
    record_attribution_event(
        db,
        event_type="program_molecule_status.upsert",
        entity_type="ProgramMoleculeStatus",
        entity_id=int(row.id),
        metadata={
            "program_id": int(program_id),
            "molecule_id": int(molecule_id),
            "role": norm_role,
        },
    )
    db.commit()
    return row


def list_programs(db: Session) -> list[Program]:
    return db.query(Program).order_by(Program.name.asc(), Program.id.asc()).all()


def get_program(db: Session, program_id: int) -> Program | None:
    return db.get(Program, program_id)


def _build_open_experiment_tasks_preview(db: Session, *, program_id: int) -> list[dict[str, Any]]:
    open_task_rows = (
        db.query(ExperimentTask, Molecule)
        .join(Molecule, Molecule.id == ExperimentTask.molecule_id)
        .filter(ExperimentTask.program_id == int(program_id))
        .filter(ExperimentTask.status != "done")
        .order_by(
            ExperimentTask.urgency.asc(),
            ExperimentTask.due_date.asc().nullslast(),
            ExperimentTask.created_at.asc(),
            ExperimentTask.id.asc(),
        )
        .limit(25)
        .all()
    )
    return [
        {
            "task_id": int(t.id),
            "molecule_id": int(t.molecule_id),
            "molecule_primary_id": str(m.primary_id or ""),
            "status": str(t.status or ""),
            "urgency": str(t.urgency or ""),
            "due_date": str(t.due_date or ""),
            "owner_text": str(t.owner_text or ""),
            "metric_key": str(t.metric_key or ""),
            "suggested_assay": str(t.suggested_assay or ""),
            "source_kind": str(t.source_kind or ""),
        }
        for t, m in open_task_rows
    ]


def _collect_program_detail_inputs(db: Session, *, program_id: int) -> dict[str, Any]:
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
    review_queue = build_program_review_queue(db, program_id=program_id)
    open_experiment_tasks_preview = _build_open_experiment_tasks_preview(db, program_id=int(program_id))
    status_rows = list_program_molecule_statuses(db, program_id=int(program_id))
    status_by_mid = {
        int(s.molecule_id): {
            "role": _normalize_program_molecule_role(str(s.role or "")),
            "rationale": str(s.rationale or "").strip(),
            "updated_at": (s.updated_at.isoformat() if s.updated_at is not None else ""),
        }
        for s in status_rows
        if s.molecule_id is not None
    }
    return {
        "molecules": molecules,
        "program_memberships": program_memberships,
        "all_molecules": all_molecules,
        "recent_batches": recent_batches,
        "recent_data": recent_data,
        "recent_evidence": recent_evidence,
        "recent_decisions": recent_decisions,
        "audits": audits,
        "review_queue": review_queue,
        "open_experiment_tasks_preview": open_experiment_tasks_preview,
        "status_by_mid": status_by_mid,
    }


def _build_program_claim_plan_context(db: Session, *, program_id: int) -> dict[str, Any]:
    claim_rows = claims_svc.top_claims_for_program(db, program_id=int(program_id), limit=20)
    claim_summary_counts = {
        "hypothesis_or_emerging": 0,
        "supported": 0,
        "contradicted": 0,
        "evidence_starved": 0,
    }
    claim_preview = []
    for c in claim_rows:
        msum = claims_svc.summarize_claim_maturity(db, claim_id=int(c.id))
        st = str(c.status or "")
        if st in {"hypothesis", "emerging"}:
            claim_summary_counts["hypothesis_or_emerging"] += 1
        if st == "supported":
            claim_summary_counts["supported"] += 1
        if st == "contradicted":
            claim_summary_counts["contradicted"] += 1
        if int(msum.get("supporting_count") or 0) + int(msum.get("contradicting_count") or 0) == 0:
            claim_summary_counts["evidence_starved"] += 1
        claim_preview.append(
            {
                "claim_id": int(c.id),
                "title": str(c.title or ""),
                "claim_type": str(c.claim_type or ""),
                "status": str(c.status or ""),
                "confidence_level": str(c.confidence_level or ""),
                "supporting_count": int(msum.get("supporting_count") or 0),
                "contradicting_count": int(msum.get("contradicting_count") or 0),
            }
        )
    plan_rows = plans_svc.list_plans_for_program(db, program_id=int(program_id), include_archived=True)
    plan_preview_rows = plans_svc.top_plans_for_program(db, program_id=int(program_id), limit=10)
    plan_step_map = plans_svc.list_plan_steps_for_plan_ids(
        db,
        plan_ids=[int(p.id) for p in plan_rows] + [int(p.id) for p in plan_preview_rows],
    )
    plan_summary = {
        "recommended": 0,
        "accepted": 0,
        "awaiting_task_instantiation": 0,
        "bottleneck_targeting": 0,
    }
    for prow in plan_rows:
        st = str(prow.status or "")
        if st == "recommended":
            plan_summary["recommended"] += 1
        if st == "accepted":
            plan_summary["accepted"] += 1
        steps = plan_step_map.get(int(prow.id), [])
        if any(str(s.status or "") == "proposed" for s in steps):
            plan_summary["awaiting_task_instantiation"] += 1
        if any(str(s.metric_key or "").strip() for s in steps):
            plan_summary["bottleneck_targeting"] += 1
    plan_preview = []
    for prow in plan_preview_rows:
        steps = plan_step_map.get(int(prow.id), [])
        plan_preview.append(
            {
                "plan_id": int(prow.id),
                "title": str(prow.title or ""),
                "plan_type": str(prow.plan_type or ""),
                "status": str(prow.status or ""),
                "expected_readiness_gain": float(prow.expected_readiness_gain or 0.0),
                "expected_claim_support_gain": float(prow.expected_claim_support_gain or 0.0),
                "expected_evidence_coverage_gain": float(prow.expected_evidence_coverage_gain or 0.0),
                "proposed_steps": int(sum(1 for s in steps if str(s.status or "") == "proposed")),
            }
        )
    return {
        "program_claim_summary": claim_summary_counts,
        "program_claims_preview": claim_preview[:10],
        "program_plan_summary": plan_summary,
        "program_plans_preview": plan_preview[:10],
    }


def _build_program_dashboard_context(
    *,
    molecules: list[Molecule],
    status_by_mid: dict[int, dict[str, Any]],
    review_queue: list[dict[str, Any]],
    status_counts: dict[str, int],
    program_memberships: list[tuple[ProgramMembership, Molecule]],
    molecule_rollup: list[dict[str, Any]],
    di_dashboard: dict[str, Any],
) -> dict[str, Any]:
    role_counts: dict[str, int] = {k: 0 for k in PROGRAM_MOLECULE_ROLES}
    for m in molecules:
        role = str((status_by_mid.get(int(m.id)) or {}).get("role") or "active")
        role_norm = _normalize_program_molecule_role(role)
        role_counts[role_norm] = int(role_counts.get(role_norm, 0)) + 1
    pending_entry_count = int(sum(len(g.get("records") or []) for g in review_queue))
    ready_count = int(status_counts.get("READY", 0))
    blocked_count = int(status_counts.get("BLOCKED", 0))
    known_count = int(ready_count + blocked_count)
    progress_percent = (round((ready_count * 100.0 / known_count), 1) if known_count > 0 else 0.0)
    confidence_percent = (
        round(((known_count - blocked_count) * 100.0 / known_count), 1)
        if known_count > 0
        else 0.0
    )
    program_dashboard = {
        "molecule_count": int(len(molecules)),
        "pending_entry_count": pending_entry_count,
        "role_counts": {k: int(role_counts.get(k, 0)) for k in PROGRAM_MOLECULE_ROLES},
        "active_contender_count": int(
            role_counts.get("lead", 0) + role_counts.get("backup", 0) + role_counts.get("active", 0)
        ),
        "posture_label": (
            "READY"
            if ready_count > 0 and blocked_count == 0
            else ("BLOCKED" if blocked_count > 0 else "UNKNOWN")
        ),
        # Display-only bars, deterministic from molecule rollup state counts.
        "progress_percent": progress_percent,
        "confidence_percent": confidence_percent,
        "progress_basis": "derived_from_latest_molecule_readiness_states",
        "confidence_basis": "derived_from_non_blocked_fraction_of_known_states",
        "progress_label": (
            "advanced"
            if progress_percent >= 80.0
            else ("developing" if progress_percent >= 40.0 else "early")
        ),
        "confidence_label": (
            "high"
            if confidence_percent >= 80.0
            else ("moderate" if confidence_percent >= 40.0 else "low")
        ),
    }
    role_grouped: dict[str, list[dict[str, Any]]] = {k: [] for k in PROGRAM_MOLECULE_ROLES}
    for pm, m in program_memberships:
        role_info = status_by_mid.get(int(m.id)) or {}
        role = _normalize_program_molecule_role(str(role_info.get("role") or "active"))
        role_grouped[role].append(
            {
                "molecule_id": int(m.id),
                "primary_id": str(m.primary_id or ""),
                "title": str(m.title or ""),
                "rationale": str(role_info.get("rationale") or "").strip(),
                "sort_index": int(pm.sort_index or 0),
            }
        )
    candidate_set = {
        role: sorted(
            role_grouped.get(role) or [],
            key=lambda x: (int(x.get("sort_index") or 0), str(x.get("primary_id") or ""), int(x.get("molecule_id") or 0)),
        )
        for role in PROGRAM_MOLECULE_ROLES
    }
    status_board = sorted(
        [
            {
                "molecule_id": int(r.get("molecule_id") or 0),
                "primary_id": str(r.get("primary_id") or ""),
                "title": str(r.get("title") or ""),
                "role": _normalize_program_molecule_role(str((status_by_mid.get(int(r.get("molecule_id") or 0)) or {}).get("role") or "active")),
                "readiness_state": str(r.get("readiness_state") or "UNKNOWN"),
                "key_blocker": str(r.get("key_blocker") or ""),
                "latest_evidence_update": str(r.get("latest_evidence_update") or ""),
            }
            for r in molecule_rollup
            if int(r.get("molecule_id") or 0) > 0
        ],
        key=lambda x: (str(x.get("primary_id") or ""), int(x.get("molecule_id") or 0)),
    )
    prioritized_subjects = [
        f"{role}:{item['primary_id']}"
        for role in ("lead", "backup", "active")
        for item in (candidate_set.get(role) or [])
        if isinstance(item, dict) and str(item.get("primary_id") or "").strip()
    ]
    top_missing_metric = (
        str((di_dashboard.get("top_missing_metrics") or [("", 0)])[0][0] or "")
        if isinstance(di_dashboard.get("top_missing_metrics"), list) and di_dashboard.get("top_missing_metrics")
        else ""
    )
    top_failing_gate = (
        str((di_dashboard.get("top_failing_gates") or [("", 0)])[0][0] or "")
        if isinstance(di_dashboard.get("top_failing_gates"), list) and di_dashboard.get("top_failing_gates")
        else ""
    )
    suggestion_items: list[str] = []
    if top_missing_metric:
        suggestion_items.append(
            f"Close missing evidence for {humanize_key(top_missing_metric)} in priority candidates ({', '.join(prioritized_subjects[:3]) if prioritized_subjects else 'lead/backup/active set'})."
        )
    if top_failing_gate:
        suggestion_items.append(
            f"Address failing gate {humanize_key(top_failing_gate)} first for lead and backup candidates."
        )
    if pending_entry_count > 0:
        suggestion_items.append(
            f"Resolve pending review queue entries ({pending_entry_count}) to stabilize evidence availability before the next program review."
        )
    if not suggestion_items:
        suggestion_items.append("No prioritized experiment suggestions available from current program evidence surfaces.")
    return {
        "program_dashboard": program_dashboard,
        "candidate_set": candidate_set,
        "program_molecule_status_board": status_board,
        "program_suggested_experiments": suggestion_items[:5],
    }


def _serialize_program_detail_context(
    *,
    program: Program,
    molecules: list[Molecule],
    program_memberships: list[tuple[ProgramMembership, Molecule]],
    all_molecules: list[Molecule],
    recent_batches: list[Batch],
    recent_data: list[DataRecord],
    recent_evidence: list[Evidence],
    recent_decisions: list[DecisionSnapshot],
    review_queue: list[dict[str, Any]],
    open_experiment_tasks_preview: list[dict[str, Any]],
    status_by_mid: dict[int, dict[str, Any]],
    candidate_set: dict[str, list[dict[str, Any]]],
    status_board: list[dict[str, Any]],
    program_evidence_summary: list[dict[str, Any]],
    program_evidence_matrix: dict[str, Any],
    program_suggested_experiments: list[str],
    claim_summary_counts: dict[str, Any],
    claim_preview: list[dict[str, Any]],
    plan_summary: dict[str, Any],
    plan_preview: list[dict[str, Any]],
    program_narrative: dict[str, Any],
    program_dashboard: dict[str, Any],
    di_dashboard: dict[str, Any],
    audits: list[AuditEvent],
) -> dict[str, Any]:
    return {
        "program": program,
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
                "candidate_role": str((status_by_mid.get(int(m.id)) or {}).get("role") or "active"),
                "candidate_role_rationale": str((status_by_mid.get(int(m.id)) or {}).get("rationale") or ""),
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
        "review_queue_by_molecule": review_queue,
        "open_experiment_tasks_preview": open_experiment_tasks_preview,
        "program_molecule_role_options": list(PROGRAM_MOLECULE_ROLES),
        "candidate_set": candidate_set,
        "program_molecule_status_board": status_board,
        "program_evidence_summary": program_evidence_summary,
        "program_evidence_matrix": program_evidence_matrix,
        "program_suggested_experiments": program_suggested_experiments,
        "program_claim_summary": claim_summary_counts,
        "program_claims_preview": claim_preview[:10],
        "program_plan_summary": plan_summary,
        "program_plans_preview": plan_preview[:10],
        "program_narrative": program_narrative,
        "program_dashboard": program_dashboard,
        "di_dashboard": di_dashboard,
        "audits": audits,
    }


def _build_program_lineage_context(
    *,
    db: Session,
    program_id: int,
    verify_lineage: bool,
) -> dict[str, Any]:
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
        .filter(DecisionSnapshot.program_id == int(program_id))
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
    return {"lineage_rows": lineage_rows}


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

    base_ctx = _collect_program_detail_inputs(db, program_id=int(program_id))
    molecules = list(base_ctx["molecules"])
    program_memberships = list(base_ctx["program_memberships"])
    all_molecules = list(base_ctx["all_molecules"])
    recent_batches = list(base_ctx["recent_batches"])
    recent_data = list(base_ctx["recent_data"])
    recent_evidence = list(base_ctx["recent_evidence"])
    recent_decisions = list(base_ctx["recent_decisions"])
    audits = list(base_ctx["audits"])
    review_queue = list(base_ctx["review_queue"])
    open_experiment_tasks_preview = list(base_ctx["open_experiment_tasks_preview"])
    status_by_mid = dict(base_ctx["status_by_mid"])

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

    lineage_ctx = _build_program_lineage_context(
        db=db,
        program_id=int(program_id),
        verify_lineage=bool(verify_lineage),
    )
    lineage_rows = list(lineage_ctx["lineage_rows"])

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
        blocker_keys = sorted(
            {
                str(b.get("blocker_key") or b.get("key") or "").strip()
                for b in blockers
                if isinstance(b, dict) and str(b.get("blocker_key") or b.get("key") or "").strip()
            }
        )
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
                "key_blocker": (blocker_keys[0] if blocker_keys else ""),
                "latest_evidence_update": (snap.created_at.isoformat() if snap.created_at is not None else ""),
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
    evidence_rows = db.execute(text(PROGRAM_EVIDENCE_ROWS_SQL), {"pid": int(program_id)}).mappings().all()
    group_to_mols: dict[str, set[int]] = {}
    group_to_keys: dict[str, set[str]] = {}
    mol_to_groups: dict[int, set[str]] = {}
    for er in evidence_rows:
        mid = int(er.get("molecule_id") or 0)
        mk = str(er.get("metric_key") or "").strip()
        if mid <= 0 or not mk:
            continue
        grp = str(metric_group_for_key(mk) or "Other")
        group_to_mols.setdefault(grp, set()).add(mid)
        group_to_keys.setdefault(grp, set()).add(mk)
        mol_to_groups.setdefault(mid, set()).add(grp)
    program_evidence_summary = sorted(
        [
            {
                "group": grp,
                "molecule_coverage_count": int(len(group_to_mols.get(grp, set()))),
                "metric_key_count": int(len(group_to_keys.get(grp, set()))),
            }
            for grp in sorted(set(group_to_mols.keys()) | set(group_to_keys.keys()))
        ],
        key=lambda r: metric_group_sort_key(str(r.get("group") or "Other")),
    )
    evidence_groups = [str(r.get("group") or "") for r in program_evidence_summary if str(r.get("group") or "").strip()]
    matrix_rows = []
    for m in sorted(molecules, key=lambda x: (str(x.primary_id or ""), int(x.id))):
        present = mol_to_groups.get(int(m.id), set())
        matrix_rows.append(
            {
                "molecule_id": int(m.id),
                "primary_id": str(m.primary_id or ""),
                "title": str(m.title or ""),
                "cells": [
                    {
                        "group": grp,
                        "present": bool(grp in present),
                    }
                    for grp in evidence_groups
                ],
            }
        )
    program_evidence_matrix = {
        "groups": evidence_groups,
        "rows": matrix_rows,
    }

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
    dashboard_ctx = _build_program_dashboard_context(
        molecules=molecules,
        status_by_mid=status_by_mid,
        review_queue=review_queue,
        status_counts=status_counts,
        program_memberships=program_memberships,
        molecule_rollup=molecule_rollup,
        di_dashboard=di_dashboard,
    )
    program_dashboard = dict(dashboard_ctx["program_dashboard"])
    candidate_set = dict(dashboard_ctx["candidate_set"])
    status_board = list(dashboard_ctx["program_molecule_status_board"])
    program_suggested_experiments = list(dashboard_ctx["program_suggested_experiments"])
    claim_plan_ctx = _build_program_claim_plan_context(db, program_id=int(program_id))
    claim_summary_counts = dict(claim_plan_ctx["program_claim_summary"])
    claim_preview = list(claim_plan_ctx["program_claims_preview"])
    plan_summary = dict(claim_plan_ctx["program_plan_summary"])
    plan_preview = list(claim_plan_ctx["program_plans_preview"])
    program_narrative = narratives_svc.build_program_narrative(db, program_id=int(program_id))

    return _serialize_program_detail_context(
        program=p,
        molecules=molecules,
        program_memberships=program_memberships,
        all_molecules=all_molecules,
        recent_batches=recent_batches,
        recent_data=recent_data,
        recent_evidence=recent_evidence,
        recent_decisions=recent_decisions,
        review_queue=review_queue,
        open_experiment_tasks_preview=open_experiment_tasks_preview,
        status_by_mid=status_by_mid,
        candidate_set=candidate_set,
        status_board=status_board,
        program_evidence_summary=program_evidence_summary,
        program_evidence_matrix=program_evidence_matrix,
        program_suggested_experiments=program_suggested_experiments,
        claim_summary_counts=claim_summary_counts,
        claim_preview=claim_preview,
        plan_summary=plan_summary,
        plan_preview=plan_preview,
        program_narrative=program_narrative,
        program_dashboard=program_dashboard,
        di_dashboard=di_dashboard,
        audits=audits,
    )


def build_program_review_queue(db: Session, *, program_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT
              dr.id AS record_id,
              dr.created_at AS created_at,
              dr.batch_id AS batch_id,
              dr.data_type AS data_type,
              dr.method AS method,
              dr.title AS title,
              m.id AS molecule_id,
              m.primary_id AS molecule_primary_id,
              m.title AS molecule_title,
              COUNT(dm.id) AS total_measurements,
              SUM(CASE WHEN COALESCE(qc.status, 'unreviewed') = 'approved' THEN 1 ELSE 0 END) AS approved_measurements
            FROM data_records dr
            JOIN molecules m ON m.id = dr.molecule_id
            LEFT JOIN data_measurements dm ON dm.data_record_id = dr.id
            LEFT JOIN measurement_qc qc ON qc.measurement_id = dm.id
            WHERE dr.program_id = :pid
              AND dr.molecule_id IS NOT NULL
            GROUP BY dr.id, dr.created_at, dr.batch_id, dr.data_type, dr.method, dr.title, m.id, m.primary_id, m.title
            ORDER BY m.primary_id ASC, m.id ASC, dr.created_at DESC, dr.id DESC
            """
        ),
        {"pid": int(program_id)},
    ).mappings().all()
    pending_rows = [
        r
        for r in rows
        if int(r.get("total_measurements") or 0) == 0
        or int(r.get("approved_measurements") or 0) < int(r.get("total_measurements") or 0)
    ]
    record_ids = [int(r.get("record_id")) for r in pending_rows]
    metric_by_record: dict[int, list[str]] = {}
    if record_ids:
        bind_params = {f"rid{i}": int(rid) for i, rid in enumerate(sorted(set(record_ids)))}
        in_clause = ", ".join(f":rid{i}" for i in range(len(bind_params)))
        mrows = db.execute(
            text(
                f"""
                SELECT dm.data_record_id AS record_id, dm.metric_key AS metric_key
                FROM data_measurements dm
                WHERE dm.data_record_id IN ({in_clause})
                ORDER BY dm.data_record_id ASC, dm.metric_key ASC, dm.id ASC
                """
            ),
            bind_params,
        ).mappings().all()
        seen: dict[tuple[int, str], bool] = {}
        for mr in mrows:
            rid = int(mr.get("record_id"))
            mk = str(mr.get("metric_key") or "").strip()
            if not mk:
                continue
            key = (rid, mk)
            if key in seen:
                continue
            seen[key] = True
            metric_by_record.setdefault(rid, []).append(mk)
    grouped: dict[int, dict[str, Any]] = {}
    latest_snapshot_cache: dict[int, dict[str, Any]] = {}
    for r in pending_rows:
        mid = int(r.get("molecule_id"))
        grp = grouped.get(mid)
        if grp is None:
            grp = {
                "molecule_id": mid,
                "molecule_primary_id": str(r.get("molecule_primary_id") or ""),
                "molecule_title": str(r.get("molecule_title") or ""),
                "records": [],
            }
            grouped[mid] = grp
        rid = int(r.get("record_id"))
        metric_keys = metric_by_record.get(rid, [])
        labels = [str(metric_catalog_entry(mk).get("label") or humanize_key(mk)) for mk in metric_keys]
        preview = ", ".join(labels[:5]) if labels else "No extracted measurements"
        ev_preview = build_record_evidence_preview(
            db,
            record_id=rid,
            latest_snapshot_cache=latest_snapshot_cache,
            record_metric_keys=metric_keys,
            molecule_id=mid,
        )
        ev_counts = ev_preview.get("counts") if isinstance(ev_preview.get("counts"), dict) else {}
        ev_short = (
            f"New: {int(ev_counts.get('new_vs_last_snapshot') or 0)} · "
            f"Already present: {int(ev_counts.get('already_present') or 0)}"
        )
        grp["records"].append(
            {
                "record_id": rid,
                "created_at": str(r.get("created_at") or ""),
                "batch_id": (int(r.get("batch_id")) if r.get("batch_id") is not None else None),
                "assay_key": f"{str(r.get('data_type') or '')}/{str(r.get('method') or '')}",
                "preview_snippet": preview,
                "evidence_preview_short": ev_short,
                "evidence_preview": ev_preview,
                "metric_keys": metric_keys,
                "total_measurements": int(r.get("total_measurements") or 0),
                "approved_measurements": int(r.get("approved_measurements") or 0),
            }
        )
    out = [grouped[mid] for mid in sorted(grouped.keys(), key=lambda x: (str(grouped[x]["molecule_primary_id"]), int(x)))]
    for g in out:
        g["records"] = sorted(
            [x for x in g.get("records", []) if isinstance(x, dict)],
            key=lambda x: (
                str(x.get("created_at") or ""),
                int(x.get("record_id") or 0),
            ),
            reverse=True,
        )
    return out


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
