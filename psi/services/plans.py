from __future__ import annotations

from typing import Any

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from psi.core.models import DecisionSnapshot, Evidence, EvidenceCitation, ExperimentTask, Molecule, ScientificClaim, ScientificPlan, ScientificPlanStep
from psi.core.utils import now_utc
from psi.services import claims as claims_svc
from psi.services import experiment_tasks as task_svc
from psi.services.insight_engine import build_insight_bundle
from psi.services import trajectory as trajectory_svc
from psi.services.dev_board import invalidate_program_board_cache

PLAN_STATUSES: tuple[str, ...] = ("draft", "recommended", "accepted", "archived", "superseded")
PLAN_SCOPE_TYPES: tuple[str, ...] = ("molecule", "claim", "program")
STEP_STATUSES: tuple[str, ...] = ("proposed", "task_created", "done", "skipped")
PLAN_TYPES: tuple[str, ...] = (
    "readiness_advancement",
    "claim_de_risking",
    "evidence_completion",
    "developability_followup",
    "confirmatory_bundle",
)
STEP_KINDS: tuple[str, ...] = ("experiment", "builder_exploration", "confirmatory", "claim_test")
PLAN_TYPE_TEMPLATES: dict[str, str] = {
    "readiness_advancement": "Close readiness blockers with highest-impact experiments first.",
    "claim_de_risking": "Generate evidence that supports or falsifies a scientific claim.",
    "evidence_completion": "Complete missing evidence needed for deterministic evaluation.",
    "developability_followup": "Address developability risks before progression.",
    "confirmatory_bundle": "Confirm pivotal findings with orthogonal assays.",
}
ALLOWED_PLAN_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"recommended", "archived"},
    "recommended": {"accepted", "archived", "superseded"},
    "accepted": {"archived", "superseded"},
    "archived": set(),
    "superseded": set(),
}
ALLOWED_STEP_TRANSITIONS: dict[str, set[str]] = {
    "proposed": {"task_created", "skipped"},
    "task_created": {"done", "skipped"},
    "done": set(),
    "skipped": set(),
}


def normalize_plan_status(value: str | None) -> str:
    v = str(value or "").strip().lower()
    return v if v in PLAN_STATUSES else "draft"


def normalize_scope_type(value: str | None) -> str:
    v = str(value or "").strip().lower()
    return v if v in PLAN_SCOPE_TYPES else "molecule"


def normalize_step_status(value: str | None) -> str:
    v = str(value or "").strip().lower()
    return v if v in STEP_STATUSES else "proposed"


def normalize_plan_type(value: str | None) -> str:
    v = str(value or "").strip().lower()
    return v if v in PLAN_TYPES else "readiness_advancement"


def normalize_step_kind(value: str | None) -> str:
    v = str(value or "").strip().lower()
    return v if v in STEP_KINDS else "experiment"


def plan_type_template(plan_type: str) -> str:
    return str(PLAN_TYPE_TEMPLATES.get(normalize_plan_type(plan_type)) or PLAN_TYPE_TEMPLATES["readiness_advancement"])


def format_plan_rationale(*, plan_type: str, title: str, rationale: str | None = None) -> str:
    r = str(rationale or "").strip()
    if r:
        return r
    t = str(title or "").strip() or "Plan"
    pt = normalize_plan_type(plan_type)
    return f"[{pt}] {t}. {plan_type_template(pt)}"


def _plan_order_query(q):
    st_rank = case(
        (ScientificPlan.status == "recommended", 0),
        (ScientificPlan.status == "accepted", 1),
        (ScientificPlan.status == "draft", 2),
        (ScientificPlan.status == "archived", 3),
        (ScientificPlan.status == "superseded", 4),
        else_=5,
    )
    return q.order_by(
        st_rank.asc(),
        ScientificPlan.expected_readiness_gain.desc(),
        ScientificPlan.expected_claim_support_gain.desc(),
        ScientificPlan.expected_evidence_coverage_gain.desc(),
        ScientificPlan.updated_at.desc(),
        ScientificPlan.id.asc(),
    )


def can_transition_plan_status(*, from_status: str, to_status: str) -> bool:
    cur = normalize_plan_status(from_status)
    nxt = normalize_plan_status(to_status)
    return nxt in (ALLOWED_PLAN_TRANSITIONS.get(cur) or set())


def can_transition_step_status(*, from_status: str, to_status: str) -> bool:
    cur = normalize_step_status(from_status)
    nxt = normalize_step_status(to_status)
    return nxt in (ALLOWED_STEP_TRANSITIONS.get(cur) or set())


def create_plan(
    db: Session,
    *,
    scope_type: str,
    molecule_id: int | None,
    program_id: int | None,
    claim_id: int | None,
    title: str,
    plan_type: str,
    status: str = "draft",
    rationale: str = "",
    expected_readiness_gain: float = 0.0,
    expected_claim_support_gain: float = 0.0,
    expected_evidence_coverage_gain: float = 0.0,
) -> ScientificPlan:
    scope = normalize_scope_type(scope_type)
    if scope == "molecule" and molecule_id is None:
        raise ValueError("molecule scope requires molecule_id")
    if scope == "claim" and claim_id is None:
        raise ValueError("claim scope requires claim_id")
    if scope == "program" and program_id is None:
        raise ValueError("program scope requires program_id")
    if molecule_id is None and claim_id is None and program_id is None:
        raise ValueError("plan requires molecule_id and/or claim_id and/or program_id")

    now = now_utc()
    row = ScientificPlan(
        scope_type=scope,
        molecule_id=(int(molecule_id) if molecule_id is not None else None),
        program_id=(int(program_id) if program_id is not None else None),
        claim_id=(int(claim_id) if claim_id is not None else None),
        title=str(title or "").strip() or "Untitled plan",
        plan_type=normalize_plan_type(plan_type),
        status=normalize_plan_status(status),
        rationale=format_plan_rationale(plan_type=plan_type, title=title, rationale=rationale),
        expected_readiness_gain=float(expected_readiness_gain or 0.0),
        expected_claim_support_gain=float(expected_claim_support_gain or 0.0),
        expected_evidence_coverage_gain=float(expected_evidence_coverage_gain or 0.0),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    pid = _program_id_for_plan(db, row)
    if pid is not None:
        invalidate_program_board_cache(program_id=int(pid))
    return row


def get_plan(db: Session, *, plan_id: int) -> ScientificPlan | None:
    return db.get(ScientificPlan, int(plan_id))


def list_plans_for_molecule(db: Session, *, molecule_id: int, include_archived: bool = False) -> list[ScientificPlan]:
    q = db.query(ScientificPlan).filter(ScientificPlan.molecule_id == int(molecule_id))
    if not include_archived:
        q = q.filter(ScientificPlan.status.notin_(["archived", "superseded"]))
    return _plan_order_query(q).all()


def list_plans_for_claim(db: Session, *, claim_id: int, include_archived: bool = False) -> list[ScientificPlan]:
    q = db.query(ScientificPlan).filter(ScientificPlan.claim_id == int(claim_id))
    if not include_archived:
        q = q.filter(ScientificPlan.status.notin_(["archived", "superseded"]))
    return _plan_order_query(q).all()


def list_plans_for_program(db: Session, *, program_id: int, include_archived: bool = False) -> list[ScientificPlan]:
    q = db.query(ScientificPlan).filter(ScientificPlan.program_id == int(program_id))
    if not include_archived:
        q = q.filter(ScientificPlan.status.notin_(["archived", "superseded"]))
    return _plan_order_query(q).all()


def list_plans(db: Session, *, include_archived: bool = False, limit: int = 200) -> list[ScientificPlan]:
    q = db.query(ScientificPlan)
    if not include_archived:
        q = q.filter(ScientificPlan.status.notin_(["archived", "superseded"]))
    return _plan_order_query(q).limit(max(1, int(limit))).all()


def archive_plan(db: Session, *, plan_id: int) -> ScientificPlan:
    return update_plan_status(db, plan_id=int(plan_id), status="archived")


def supersede_plan(db: Session, *, plan_id: int) -> ScientificPlan:
    return update_plan_status(db, plan_id=int(plan_id), status="superseded")


def update_plan_status(db: Session, *, plan_id: int, status: str) -> ScientificPlan:
    row = get_plan(db, plan_id=int(plan_id))
    if row is None:
        raise KeyError("ScientificPlan not found")
    cur = normalize_plan_status(row.status)
    nxt = normalize_plan_status(status)
    if cur != nxt:
        if nxt not in (ALLOWED_PLAN_TRANSITIONS.get(cur) or set()):
            raise ValueError(f"invalid plan transition: {cur} -> {nxt}")
        row.status = nxt
        row.updated_at = now_utc()
        db.add(row)
        db.commit()
        db.refresh(row)
        pid = _program_id_for_plan(db, row)
        if pid is not None:
            invalidate_program_board_cache(program_id=int(pid))
    return row


def top_plans_for_molecule(db: Session, *, molecule_id: int, limit: int = 5) -> list[ScientificPlan]:
    rows = list_plans_for_molecule(db, molecule_id=int(molecule_id), include_archived=False)
    return rank_plans(db, rows)[: max(1, int(limit))]


def top_plans_for_claim(db: Session, *, claim_id: int, limit: int = 5) -> list[ScientificPlan]:
    rows = list_plans_for_claim(db, claim_id=int(claim_id), include_archived=False)
    return rank_plans(db, rows)[: max(1, int(limit))]


def top_plans_for_program(db: Session, *, program_id: int, limit: int = 10) -> list[ScientificPlan]:
    rows = list_plans_for_program(db, program_id=int(program_id), include_archived=False)
    return rank_plans(db, rows)[: max(1, int(limit))]


def add_plan_step(
    db: Session,
    *,
    plan_id: int,
    step_order: int | None = None,
    metric_key: str = "",
    suggested_assay: str = "",
    step_kind: str = "experiment",
    rationale: str = "",
    expected_effect_summary: str = "",
    status: str = "proposed",
) -> ScientificPlanStep:
    plan = get_plan(db, plan_id=int(plan_id))
    if plan is None:
        raise KeyError("ScientificPlan not found")
    if step_order is None:
        max_row = db.query(func.max(ScientificPlanStep.step_order)).filter(ScientificPlanStep.plan_id == int(plan_id)).scalar()
        next_order = int(max_row or 0) + 1
    else:
        next_order = max(1, int(step_order))
    now = now_utc()
    row = ScientificPlanStep(
        plan_id=int(plan_id),
        step_order=next_order,
        metric_key=(str(metric_key or "").strip() or None),
        suggested_assay=(str(suggested_assay or "").strip() or None),
        step_kind=normalize_step_kind(step_kind),
        rationale=(str(rationale or "").strip() or None),
        expected_effect_summary=(str(expected_effect_summary or "").strip() or None),
        status=normalize_step_status(status),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    plan.updated_at = now
    db.add(plan)
    db.commit()
    db.refresh(row)
    pid = _program_id_for_plan(db, plan if plan is not None else row.plan_id)
    if pid is not None:
        invalidate_program_board_cache(program_id=int(pid))
    return row


def list_plan_steps(db: Session, *, plan_id: int) -> list[ScientificPlanStep]:
    st_rank = case(
        (ScientificPlanStep.status == "proposed", 0),
        (ScientificPlanStep.status == "task_created", 1),
        (ScientificPlanStep.status == "done", 2),
        (ScientificPlanStep.status == "skipped", 3),
        else_=4,
    )
    return (
        db.query(ScientificPlanStep)
        .filter(ScientificPlanStep.plan_id == int(plan_id))
        .order_by(st_rank.asc(), ScientificPlanStep.step_order.asc(), ScientificPlanStep.id.asc())
        .all()
    )


def update_plan_step_status(db: Session, *, step_id: int, status: str) -> ScientificPlanStep:
    row = db.get(ScientificPlanStep, int(step_id))
    if row is None:
        raise KeyError("ScientificPlanStep not found")
    cur = normalize_step_status(row.status)
    nxt = normalize_step_status(status)
    if cur != nxt:
        if nxt not in (ALLOWED_STEP_TRANSITIONS.get(cur) or set()):
            raise ValueError(f"invalid step transition: {cur} -> {nxt}")
        row.status = nxt
        row.updated_at = now_utc()
        db.add(row)
    plan = db.get(ScientificPlan, int(row.plan_id))
    if plan is not None:
        plan.updated_at = now_utc()
        db.add(plan)
    db.commit()
    db.refresh(row)
    return row


def build_plan_detail(db: Session, *, plan_id: int) -> dict[str, Any]:
    p = get_plan(db, plan_id=int(plan_id))
    if p is None:
        raise KeyError("ScientificPlan not found")
    steps = list_plan_steps(db, plan_id=int(plan_id))
    linked_task_ids = [int(s.linked_experiment_task_id) for s in steps if s.linked_experiment_task_id is not None]
    recent_completed_tasks: list[ExperimentTask] = []
    if linked_task_ids:
        recent_completed_tasks = (
            db.query(ExperimentTask)
            .filter(ExperimentTask.id.in_(linked_task_ids))
            .filter(ExperimentTask.status == "done")
            .order_by(ExperimentTask.updated_at.desc(), ExperimentTask.id.asc())
            .limit(6)
            .all()
        )
    recent_evidence: list[Evidence] = []
    if p.program_id is not None:
        q = db.query(Evidence).filter(Evidence.program_id == int(p.program_id))
        if p.molecule_id is not None:
            q = q.filter((Evidence.molecule_id == int(p.molecule_id)) | (Evidence.molecule_id.is_(None)))
        recent_evidence = q.order_by(Evidence.created_at.desc(), Evidence.id.desc()).limit(6).all()

    linked_record_ids = [int(t.linked_data_record_id) for t in recent_completed_tasks if t.linked_data_record_id is not None]
    evidence_by_record: dict[int, list[int]] = {}
    if linked_record_ids:
        rows = (
            db.query(EvidenceCitation.data_record_id, EvidenceCitation.evidence_id)
            .filter(EvidenceCitation.data_record_id.in_(linked_record_ids))
            .all()
        )
        for dr_id, ev_id in rows:
            if dr_id is None or ev_id is None:
                continue
            evidence_by_record.setdefault(int(dr_id), []).append(int(ev_id))
        for dr_id in list(evidence_by_record.keys()):
            evidence_by_record[int(dr_id)] = sorted(set(evidence_by_record[int(dr_id)]))
    pending_evidence_links = sum(1 for rid in linked_record_ids if int(rid) not in evidence_by_record)
    header_impact = {
        "new_results_affecting_plan": int(pending_evidence_links),
        "evidence_updates": int(len(recent_evidence)),
        "recent_execution_activity": int(len(recent_completed_tasks)),
    }

    return {
        "plan": p,
        "steps": steps,
        "plan_score": score_plan(db, p),
        "effort_estimate": estimate_plan_effort(db, p),
        "recent_completed_tasks": recent_completed_tasks,
        "recent_evidence": recent_evidence,
        "evidence_by_record": evidence_by_record,
        "header_impact": header_impact,
    }


def estimate_plan_effort(db: Session, plan: ScientificPlan | int) -> int:
    plan_id = int(plan.id) if isinstance(plan, ScientificPlan) else int(plan)
    rows = list_plan_steps(db, plan_id=plan_id)
    effort = 0
    for s in rows:
        kind = str(s.step_kind or "").strip().lower()
        if kind == "builder_exploration":
            effort += 3
        elif kind == "confirmatory":
            effort += 2
        else:
            effort += 1
    return int(max(1, effort)) if rows else 1


def score_plan(db: Session, plan: ScientificPlan | int) -> float:
    p = plan if isinstance(plan, ScientificPlan) else get_plan(db, plan_id=int(plan))
    if p is None:
        raise KeyError("ScientificPlan not found")
    steps_n = len(list_plan_steps(db, plan_id=int(p.id)))
    effort = estimate_plan_effort(db, p)
    score = (
        (2.0 * float(p.expected_readiness_gain or 0.0))
        + (1.5 * float(p.expected_claim_support_gain or 0.0))
        + (1.25 * float(p.expected_evidence_coverage_gain or 0.0))
        - (0.35 * float(effort))
        - (0.1 * float(steps_n))
    )
    return float(round(score, 6))


def rank_plans(db: Session, plans: list[ScientificPlan]) -> list[ScientificPlan]:
    rows = [p for p in plans if isinstance(p, ScientificPlan)]
    scored: list[tuple[float, int, int, int, ScientificPlan]] = []
    for p in rows:
        effort = estimate_plan_effort(db, p)
        steps_n = len(list_plan_steps(db, plan_id=int(p.id)))
        scored.append((score_plan(db, p), effort, steps_n, int(p.id), p))
    scored.sort(key=lambda x: (-x[0], x[1], x[2], x[3]))
    return [x[-1] for x in scored]


def create_task_from_plan_step(db: Session, *, step_id: int) -> ExperimentTask:
    step = db.get(ScientificPlanStep, int(step_id))
    if step is None:
        raise KeyError("ScientificPlanStep not found")
    plan = db.get(ScientificPlan, int(step.plan_id))
    if plan is None:
        raise KeyError("ScientificPlan not found")
    if step.linked_experiment_task_id is not None:
        existing = db.get(ExperimentTask, int(step.linked_experiment_task_id))
        if existing is not None:
            return existing
    if plan.program_id is None or plan.molecule_id is None:
        raise ValueError("plan_step_task_creation_requires_program_and_molecule")

    task = task_svc.create_experiment_task(
        db,
        program_id=int(plan.program_id),
        molecule_id=int(plan.molecule_id),
        metric_key=str(step.metric_key or ""),
        suggested_assay=str(step.suggested_assay or ""),
        status="planned",
        source_kind="manual",
        notes=f"Created from ScientificPlan #{int(plan.id)} step {int(step.step_order)}",
    )
    step.linked_experiment_task_id = int(task.id)
    step.status = "task_created"
    step.updated_at = now_utc()
    plan.updated_at = now_utc()
    db.add(step)
    db.add(plan)
    db.commit()
    db.refresh(step)
    pid = _program_id_for_plan(db, plan)
    if pid is not None:
        invalidate_program_board_cache(program_id=int(pid))
    return task


def create_tasks_from_plan(db: Session, *, plan_id: int) -> list[ExperimentTask]:
    p = get_plan(db, plan_id=int(plan_id))
    if p is None:
        raise KeyError("ScientificPlan not found")
    rows = list_plan_steps(db, plan_id=int(plan_id))
    created: list[ExperimentTask] = []
    for s in rows:
        if str(s.status or "") not in {"proposed", "task_created"}:
            continue
        created.append(create_task_from_plan_step(db, step_id=int(s.id)))
    return created


def _program_id_for_plan(db: Session, plan: ScientificPlan | int) -> int | None:
    row = plan if isinstance(plan, ScientificPlan) else get_plan(db, plan_id=int(plan))
    if row is None:
        return None
    if row.program_id is not None:
        return int(row.program_id)
    if row.claim_id is not None:
        claim = db.get(ScientificClaim, int(row.claim_id))
        if claim is not None and claim.program_id is not None:
            return int(claim.program_id)
    if row.molecule_id is not None:
        mol = db.get(Molecule, int(row.molecule_id))
        if mol is not None and mol.program_id is not None:
            return int(mol.program_id)
    return None


def _find_existing_recommended_plan(
    db: Session,
    *,
    scope_type: str,
    molecule_id: int | None,
    program_id: int | None,
    claim_id: int | None,
    plan_type: str,
) -> ScientificPlan | None:
    q = db.query(ScientificPlan).filter(
        ScientificPlan.scope_type == normalize_scope_type(scope_type),
        ScientificPlan.plan_type == normalize_plan_type(plan_type),
        ScientificPlan.status.in_(["draft", "recommended", "accepted"]),
    )
    if molecule_id is None:
        q = q.filter(ScientificPlan.molecule_id.is_(None))
    else:
        q = q.filter(ScientificPlan.molecule_id == int(molecule_id))
    if program_id is None:
        q = q.filter(ScientificPlan.program_id.is_(None))
    else:
        q = q.filter(ScientificPlan.program_id == int(program_id))
    if claim_id is None:
        q = q.filter(ScientificPlan.claim_id.is_(None))
    else:
        q = q.filter(ScientificPlan.claim_id == int(claim_id))
    return _plan_order_query(q).first()


def _latest_bundle_for_molecule(db: Session, *, molecule_id: int) -> dict[str, Any]:
    snap = (
        db.query(DecisionSnapshot)
        .filter(DecisionSnapshot.molecule_id == int(molecule_id))
        .order_by(DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc())
        .first()
    )
    if snap is None:
        return build_insight_bundle(None)
    import json

    try:
        out = json.loads(snap.outputs_json or "{}")
    except Exception:
        out = {}
    return build_insight_bundle(out if isinstance(out, dict) else None)


def _clear_plan_steps(db: Session, *, plan_id: int) -> None:
    rows = db.query(ScientificPlanStep).filter(ScientificPlanStep.plan_id == int(plan_id)).all()
    for r in rows:
        db.delete(r)
    if rows:
        db.commit()


def _open_task_metric_keys(db: Session, *, molecule_id: int) -> set[str]:
    rows = (
        db.query(ExperimentTask.metric_key)
        .filter(ExperimentTask.molecule_id == int(molecule_id))
        .filter(ExperimentTask.status != "done")
        .all()
    )
    return {str(r[0] or "").strip() for r in rows if str(r[0] or "").strip()}


def _save_generated_steps(
    db: Session,
    *,
    plan_id: int,
    candidates: list[dict[str, Any]],
    step_kind: str,
) -> list[ScientificPlanStep]:
    _clear_plan_steps(db, plan_id=int(plan_id))
    out: list[ScientificPlanStep] = []
    for idx, row in enumerate(candidates, start=1):
        out.append(
            add_plan_step(
                db,
                plan_id=int(plan_id),
                step_order=int(idx),
                metric_key=str(row.get("metric_key") or ""),
                suggested_assay=str(row.get("suggested_assay") or ""),
                step_kind=step_kind,
                rationale=str(row.get("reason") or "") or "trajectory candidate",
                expected_effect_summary=str(
                    row.get("expected_effect_summary")
                    or f"readiness+{int(row.get('expected_readiness_gain') or 0)}, coverage+{int(row.get('metric_coverage_improvement') or 0)}"
                ),
                status="proposed",
            )
        )
    return out


def _rank_molecule_readiness_steps(
    *,
    missing_metrics: list[str],
    ranked_candidates: list[dict[str, Any]],
    open_metrics: set[str],
) -> list[dict[str, Any]]:
    by_metric = {str(r.get("metric_key") or "").strip(): dict(r) for r in ranked_candidates if str(r.get("metric_key") or "").strip()}
    rows: list[dict[str, Any]] = []

    # First: explicit missing gating evidence.
    for mk in sorted({m for m in missing_metrics if m and m not in open_metrics}):
        if mk in by_metric:
            rows.append(dict(by_metric[mk]))
        else:
            rows.append(
                {
                    "metric_key": mk,
                    "suggested_assay": f"Measure {mk}",
                    "reason": "fill missing gating evidence",
                    "expected_readiness_gain": 0,
                    "metric_coverage_improvement": 1,
                    "expected_effect_summary": "close missing evidence gap",
                }
            )

    # Second: top projected experiment impact not already selected/open.
    used = {str(r.get("metric_key") or "").strip() for r in rows}
    for row in ranked_candidates:
        mk = str(row.get("metric_key") or "").strip()
        if not mk or mk in open_metrics or mk in used:
            continue
        rows.append(dict(row))
        used.add(mk)
        if len(rows) >= 3:
            break

    # Third: deterministic confirmatory follow-up when readiness impact is expected.
    if any(
        (int(r.get("expected_readiness_gain") or 0) > 0) or (int(r.get("gate_impact") or 0) > 0)
        for r in rows
    ):
        top = rows[0] if rows else None
        if isinstance(top, dict):
            mk = str(top.get("metric_key") or "").strip()
            if mk:
                rows.append(
                    {
                        "metric_key": mk,
                        "suggested_assay": str(top.get("suggested_assay") or f"Confirm {mk}"),
                        "reason": "confirm projected readiness shift",
                        "expected_readiness_gain": 0,
                        "metric_coverage_improvement": 0,
                        "expected_effect_summary": "confirmatory replication",
                        "step_kind": "confirmatory",
                    }
                )
    return rows[:4]


def generate_readiness_plan_for_molecule(db: Session, *, molecule_id: int) -> dict[str, Any]:
    mol = db.get(Molecule, int(molecule_id))
    if mol is None:
        raise KeyError("Molecule not found")
    bundle = _latest_bundle_for_molecule(db, molecule_id=int(molecule_id))
    missing = sorted(
        {
            str(x.get("metric_key") or "").strip()
            for x in (bundle.get("missing_evidence") or [])
            if isinstance(x, dict) and str(x.get("metric_key") or "").strip()
        }
    )
    ranked = trajectory_svc.rank_trajectory_candidates(
        trajectory_svc.generate_trajectory_candidates(db, molecule_id=int(molecule_id))
    )
    open_metrics = _open_task_metric_keys(db, molecule_id=int(molecule_id))
    selected = _rank_molecule_readiness_steps(
        missing_metrics=missing,
        ranked_candidates=ranked,
        open_metrics=open_metrics,
    )
    if not selected:
        selected = [{"metric_key": mk, "suggested_assay": f"Measure {mk}", "reason": "fill missing evidence"} for mk in missing[:2]]
    readiness_gain = float(sum(int(r.get("expected_readiness_gain") or 0) for r in selected))
    cov_hits = len({str(r.get("metric_key") or "").strip() for r in selected} & set(missing))
    evidence_gain = float((cov_hits / max(1, len(missing))) if missing else 0.0)
    rationale = (
        f"Generated from missing metrics ({len(missing)}), trajectory candidates ({len(ranked)}), "
        f"and open task context ({len(open_metrics)} open metrics)."
    )
    existing = _find_existing_recommended_plan(
        db,
        scope_type="molecule",
        molecule_id=int(molecule_id),
        program_id=int(mol.program_id),
        claim_id=None,
        plan_type="readiness_advancement",
    )
    plan = existing or create_plan(
        db,
        scope_type="molecule",
        molecule_id=int(molecule_id),
        program_id=int(mol.program_id),
        claim_id=None,
        title=f"Readiness plan for {str(mol.primary_id or molecule_id)}",
        plan_type="readiness_advancement",
        status="recommended",
    )
    plan.status = "recommended"
    plan.rationale = rationale
    plan.expected_readiness_gain = float(readiness_gain)
    plan.expected_claim_support_gain = 0.0
    plan.expected_evidence_coverage_gain = float(round(evidence_gain, 4))
    plan.updated_at = now_utc()
    db.add(plan)
    db.commit()
    db.refresh(plan)
    _clear_plan_steps(db, plan_id=int(plan.id))
    steps: list[ScientificPlanStep] = []
    for idx, row in enumerate(selected, start=1):
        steps.append(
            add_plan_step(
                db,
                plan_id=int(plan.id),
                step_order=int(idx),
                metric_key=str(row.get("metric_key") or ""),
                suggested_assay=str(row.get("suggested_assay") or ""),
                step_kind=normalize_step_kind(str(row.get("step_kind") or "experiment")),
                rationale=str(row.get("reason") or ""),
                expected_effect_summary=str(
                    row.get("expected_effect_summary")
                    or f"readiness+{int(row.get('expected_readiness_gain') or 0)}, coverage+{int(row.get('metric_coverage_improvement') or 0)}"
                ),
                status="proposed",
            )
        )
    return {"plan": plan, "steps": steps}


def generate_plan_for_molecule(db: Session, *, molecule_id: int) -> dict[str, Any]:
    return generate_readiness_plan_for_molecule(db, molecule_id=int(molecule_id))


def generate_claim_derisking_plan_for_claim(db: Session, *, claim_id: int) -> dict[str, Any]:
    claim = db.get(ScientificClaim, int(claim_id))
    if claim is None:
        raise KeyError("ScientificClaim not found")
    if claim.molecule_id is None:
        raise ValueError("claim must be molecule-linked for generation")

    support = claims_svc.summarize_claim_support(db, claim_id=int(claim_id))
    maturity = claims_svc.summarize_claim_maturity(db, claim_id=int(claim_id))
    hints = set(claims_svc.claim_relevant_metric_keys(str(claim.claim_type or "")))
    ranked = trajectory_svc.rank_trajectory_candidates(
        trajectory_svc.generate_trajectory_candidates(db, molecule_id=int(claim.molecule_id))
    )
    selected: list[dict[str, Any]] = []
    for row in ranked:
        mk = str(row.get("metric_key") or "").strip()
        if hints and mk and mk not in hints:
            continue
        selected.append(dict(row))
        if len(selected) >= 3:
            break
    if not selected:
        selected = [dict(x) for x in ranked[:2]]
    supporting_n = int(support.get("supporting_count") or 0)
    contradicting_n = int(support.get("contradicting_count") or 0)
    if contradicting_n > 0:
        # Deterministic conflict-resolution step when contradictory evidence exists.
        selected.append(
            {
                "metric_key": str(selected[0].get("metric_key") or "") if selected else "",
                "suggested_assay": str(selected[0].get("suggested_assay") or "orthogonal assay") if selected else "orthogonal assay",
                "reason": "resolve contradictory evidence with orthogonal confirmation",
                "expected_readiness_gain": 0,
                "metric_coverage_improvement": 0,
                "expected_effect_summary": "conflict resolution",
                "step_kind": "confirmatory",
            }
        )
    support_gain = 1.0 if supporting_n == 0 else 0.5
    if contradicting_n > supporting_n:
        support_gain += 0.5
    evidence_gain = float(min(1.0, (supporting_n + len(selected)) / max(1, supporting_n + contradicting_n + 1)))
    rationale = (
        f"Generated from claim maturity ({maturity.get('maturity_summary')}), "
        f"support/conflict ({supporting_n}/{contradicting_n}), and trajectory relevance ({len(selected)} steps)."
    )
    existing = _find_existing_recommended_plan(
        db,
        scope_type="claim",
        molecule_id=int(claim.molecule_id),
        program_id=(int(claim.program_id) if claim.program_id is not None else None),
        claim_id=int(claim_id),
        plan_type="claim_de_risking",
    )
    plan = existing or create_plan(
        db,
        scope_type="claim",
        molecule_id=int(claim.molecule_id),
        program_id=(int(claim.program_id) if claim.program_id is not None else None),
        claim_id=int(claim_id),
        title=f"Claim de-risking plan #{int(claim_id)}",
        plan_type="claim_de_risking",
        status="recommended",
    )
    plan.status = "recommended"
    plan.rationale = rationale
    plan.expected_readiness_gain = float(sum(int(r.get("expected_readiness_gain") or 0) for r in selected))
    plan.expected_claim_support_gain = float(round(support_gain, 4))
    plan.expected_evidence_coverage_gain = float(round(evidence_gain, 4))
    plan.updated_at = now_utc()
    db.add(plan)
    db.commit()
    db.refresh(plan)
    _clear_plan_steps(db, plan_id=int(plan.id))
    steps: list[ScientificPlanStep] = []
    for idx, row in enumerate(selected, start=1):
        steps.append(
            add_plan_step(
                db,
                plan_id=int(plan.id),
                step_order=int(idx),
                metric_key=str(row.get("metric_key") or ""),
                suggested_assay=str(row.get("suggested_assay") or ""),
                step_kind=normalize_step_kind(str(row.get("step_kind") or "claim_test")),
                rationale=str(row.get("reason") or ""),
                expected_effect_summary=str(
                    row.get("expected_effect_summary")
                    or f"claim_support+{float(round(support_gain, 2))}, coverage+{int(row.get('metric_coverage_improvement') or 0)}"
                ),
                status="proposed",
            )
        )
    return {"plan": plan, "steps": steps}


def generate_plan_for_claim(db: Session, *, claim_id: int) -> dict[str, Any]:
    return generate_claim_derisking_plan_for_claim(db, claim_id=int(claim_id))
