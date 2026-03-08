from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from psi.core.models import Program
from psi.services import claims as claims_svc
from psi.services import plans as plans_svc
from psi.services import portfolio as portfolio_svc
from psi.services import trajectory as trajectory_svc


def _as_list(rows: list[Any] | None) -> list[Any]:
    return list(rows or [])


def synthesize_scientific_thesis(*, top_claims: list[dict[str, Any]]) -> str:
    claims = [c for c in (top_claims or []) if isinstance(c, dict)]
    if not claims:
        return "Scientific thesis is currently framed around generating decisive evidence for advancement"
    c0 = claims[0]
    title = str(c0.get("title") or "leading claim")
    ctype = str(c0.get("claim_type") or "scientific direction").replace("_", " ")
    return f"Program thesis: {title} ({ctype}) is the central assertion being tested"


def synthesize_current_state_summary(
    *,
    molecules_ready: int,
    molecules_missing_data: int,
    blocked_tasks: int,
    active_plans: int,
) -> str:
    return (
        f"Current state: {int(molecules_ready)} molecules ready, "
        f"{int(molecules_missing_data)} molecules with missing data, "
        f"{int(blocked_tasks)} blocked tasks, and {int(active_plans)} active plans"
    )


def synthesize_next_milestone(
    *,
    molecules_ready: int,
    top_trajectory_count: int,
    recommended_plan_count: int,
) -> tuple[str, str, str]:
    if int(molecules_ready) > 0:
        milestone = "Select lead molecule for milestone advancement decision"
        stage = "milestone_decision"
    elif int(top_trajectory_count) > 0 and int(recommended_plan_count) > 0:
        milestone = "Complete high-impact plan bundle to unlock readiness transition"
        stage = "execution_focus"
    else:
        milestone = "Establish minimum evidence package for readiness evaluation"
        stage = "evidence_building"
    rationale = (
        f"Derived from trajectory opportunities ({int(top_trajectory_count)}) and "
        f"recommended plans ({int(recommended_plan_count)})"
    )
    return milestone, rationale, stage


def synthesize_strongest_support(
    *,
    supported_claims: int,
    ready_molecules: int,
    active_plans: int,
) -> list[str]:
    return [
        f"Supported claims: {int(supported_claims)}",
        f"Ready molecules: {int(ready_molecules)}",
        f"Active plans in motion: {int(active_plans)}",
    ]


def synthesize_major_uncertainties(
    *,
    hypothesis_or_emerging_claims: int,
    missing_data_molecules: int,
    evidence_starved_claims: int,
) -> list[str]:
    return [
        f"Hypothesis/emerging claims: {int(hypothesis_or_emerging_claims)}",
        f"Missing-data molecules: {int(missing_data_molecules)}",
        f"Evidence-starved claims: {int(evidence_starved_claims)}",
    ]


def synthesize_active_risks(
    *,
    contradicted_claims: int,
    overdue_tasks: int,
    blocked_tasks: int,
) -> list[str]:
    return [
        f"Contradicted claims: {int(contradicted_claims)}",
        f"Overdue tasks: {int(overdue_tasks)}",
        f"Blocked tasks: {int(blocked_tasks)}",
    ]


def build_claim_maturity_rollup(*, claim_summary: dict[str, Any]) -> dict[str, int]:
    return {
        "supported": int(claim_summary.get("supported") or 0),
        "hypothesis_or_emerging": int(claim_summary.get("hypothesis_or_emerging") or 0),
        "contradicted": int(claim_summary.get("contradicted") or 0),
        "evidence_starved": int(claim_summary.get("evidence_starved") or 0),
    }


def build_evidence_maturity_rollup(*, molecules_ready: int, molecules_missing_data: int) -> dict[str, int]:
    return {
        "ready_molecules": int(molecules_ready),
        "missing_data_molecules": int(molecules_missing_data),
    }


def build_plan_maturity_rollup(*, active_plans: int, recommended_plans: int, accepted_plans: int) -> dict[str, int]:
    return {
        "active_plans": int(active_plans),
        "recommended_plans": int(recommended_plans),
        "accepted_plans": int(accepted_plans),
    }


def synthesize_confidence_summary(
    *,
    claim_rollup: dict[str, int],
    evidence_rollup: dict[str, int],
    plan_rollup: dict[str, int],
) -> str:
    supported = int(claim_rollup.get("supported") or 0)
    contrad = int(claim_rollup.get("contradicted") or 0)
    missing = int(evidence_rollup.get("missing_data_molecules") or 0)
    recommended = int(plan_rollup.get("recommended_plans") or 0)
    accepted = int(plan_rollup.get("accepted_plans") or 0)
    if supported > contrad and missing == 0 and (accepted > 0 or recommended > 0):
        return "high"
    if supported >= contrad and missing <= 1:
        return "moderate"
    return "developing"


def synthesize_milestone_framing(
    *,
    claim_rollup: dict[str, int],
    evidence_rollup: dict[str, int],
    plan_rollup: dict[str, int],
) -> dict[str, list[str]]:
    return {
        "what_is_proven": [
            f"Supported claims: {int(claim_rollup.get('supported') or 0)}",
            f"Ready molecules: {int(evidence_rollup.get('ready_molecules') or 0)}",
        ],
        "what_remains_to_prove": [
            f"Hypothesis/emerging claims: {int(claim_rollup.get('hypothesis_or_emerging') or 0)}",
            f"Missing-data molecules: {int(evidence_rollup.get('missing_data_molecules') or 0)}",
        ],
        "what_would_unlock_next_milestone": [
            f"Recommended plans to execute: {int(plan_rollup.get('recommended_plans') or 0)}",
            "Close top missing metrics and convert leading claims to supported status",
        ],
        "what_is_underway": [
            f"Active plans: {int(plan_rollup.get('active_plans') or 0)}",
            f"Accepted plans: {int(plan_rollup.get('accepted_plans') or 0)}",
        ],
    }


def build_program_narrative(db: Session, *, program_id: int) -> dict[str, Any]:
    program = db.get(Program, int(program_id))
    if program is None:
        raise KeyError("Program not found")

    claim_rows = claims_svc.top_claims_for_program(db, program_id=int(program_id), limit=10)
    claim_preview = []
    claim_summary = {"hypothesis_or_emerging": 0, "supported": 0, "contradicted": 0, "evidence_starved": 0}
    for c in claim_rows:
        msum = claims_svc.summarize_claim_maturity(db, claim_id=int(c.id))
        st = str(c.status or "")
        if st in {"hypothesis", "emerging"}:
            claim_summary["hypothesis_or_emerging"] += 1
        if st == "supported":
            claim_summary["supported"] += 1
        if st == "contradicted":
            claim_summary["contradicted"] += 1
        if int(msum.get("supporting_count") or 0) + int(msum.get("contradicting_count") or 0) == 0:
            claim_summary["evidence_starved"] += 1
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

    plan_rows = plans_svc.top_plans_for_program(db, program_id=int(program_id), limit=10)
    plan_preview = []
    for prow in plan_rows:
        steps = plans_svc.list_plan_steps(db, plan_id=int(prow.id))
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

    trajectory = trajectory_svc.build_program_trajectory(db, program_id=int(program_id), limit=5)
    top_trajectory = _as_list(trajectory.get("experiments"))

    summary = portfolio_svc.build_program_portfolio_summary(db, program_id=int(program_id))

    thesis = synthesize_scientific_thesis(top_claims=claim_preview)
    active_plans_n = len([x for x in plan_preview if str(x.get("status") or "") in {"draft", "recommended", "accepted"}])
    cur_state = synthesize_current_state_summary(
        molecules_ready=int(summary.get("molecules_ready") or 0),
        molecules_missing_data=int(summary.get("molecules_missing_data") or 0),
        blocked_tasks=int(summary.get("blocked_tasks") or 0),
        active_plans=int(active_plans_n),
    )
    next_milestone, milestone_rationale, overall_stage = synthesize_next_milestone(
        molecules_ready=int(summary.get("molecules_ready") or 0),
        top_trajectory_count=len(top_trajectory),
        recommended_plan_count=len([x for x in plan_preview if str(x.get("status") or "") == "recommended"]),
    )
    recommended_plans_n = len([x for x in plan_preview if str(x.get("status") or "") == "recommended"])
    accepted_plans_n = len([x for x in plan_preview if str(x.get("status") or "") == "accepted"])
    claim_rollup = build_claim_maturity_rollup(claim_summary=claim_summary)
    evidence_rollup = build_evidence_maturity_rollup(
        molecules_ready=int(summary.get("molecules_ready") or 0),
        molecules_missing_data=int(summary.get("molecules_missing_data") or 0),
    )
    plan_rollup = build_plan_maturity_rollup(
        active_plans=int(active_plans_n),
        recommended_plans=int(recommended_plans_n),
        accepted_plans=int(accepted_plans_n),
    )
    milestone_framing = synthesize_milestone_framing(
        claim_rollup=claim_rollup,
        evidence_rollup=evidence_rollup,
        plan_rollup=plan_rollup,
    )
    narrative_links = {
        "top_claim_links": [
            {
                "claim_id": int(c.get("claim_id") or 0),
                "label": str(c.get("title") or ""),
            }
            for c in claim_preview[:3]
            if int(c.get("claim_id") or 0) > 0
        ],
        "top_plan_links": [
            {
                "plan_id": int(p.get("plan_id") or 0),
                "label": str(p.get("title") or ""),
            }
            for p in plan_preview[:3]
            if int(p.get("plan_id") or 0) > 0
        ],
        "top_trajectory_links": [
            {
                "molecule_id": int(t.get("molecule_id") or 0),
                "metric_key": str(t.get("metric_key") or ""),
                "assay": str(t.get("suggested_assay") or ""),
            }
            for t in top_trajectory[:3]
        ],
    }
    anchor_blocks = [
        {
            "title": "Claim anchors",
            "summary": f"{len(narrative_links['top_claim_links'])} leading claims define the current scientific thesis",
        },
        {
            "title": "Plan anchors",
            "summary": f"{len(narrative_links['top_plan_links'])} prioritized plans map execution to milestone needs",
        },
        {
            "title": "Trajectory anchors",
            "summary": f"{len(narrative_links['top_trajectory_links'])} high-impact projected experiments indicate likely near-term gains",
        },
    ]

    narrative = {
        "program_id": int(program.id),
        "title": f"Program Narrative: {str(program.name or '')}",
        "scientific_thesis": thesis,
        "current_state_summary": cur_state,
        "strongest_support": synthesize_strongest_support(
            supported_claims=int(claim_summary.get("supported") or 0),
            ready_molecules=int(summary.get("molecules_ready") or 0),
            active_plans=int(active_plans_n),
        ),
        "major_uncertainties": synthesize_major_uncertainties(
            hypothesis_or_emerging_claims=int(claim_summary.get("hypothesis_or_emerging") or 0),
            missing_data_molecules=int(summary.get("molecules_missing_data") or 0),
            evidence_starved_claims=int(claim_summary.get("evidence_starved") or 0),
        ),
        "active_risks": synthesize_active_risks(
            contradicted_claims=int(claim_summary.get("contradicted") or 0),
            overdue_tasks=int(summary.get("overdue_tasks") or 0),
            blocked_tasks=int(summary.get("blocked_tasks") or 0),
        ),
        "active_plans": plan_preview[:5],
        "next_milestone": next_milestone,
        "milestone_rationale": milestone_rationale,
        "overall_stage": overall_stage,
        "confidence_summary": synthesize_confidence_summary(
            claim_rollup=claim_rollup,
            evidence_rollup=evidence_rollup,
            plan_rollup=plan_rollup,
        ),
        "claim_maturity_rollup": claim_rollup,
        "evidence_maturity_rollup": evidence_rollup,
        "plan_maturity_rollup": plan_rollup,
        "narrative_links": narrative_links,
        "narrative_anchor_blocks": anchor_blocks,
        "milestone_framing": milestone_framing,
        "top_claims": claim_preview[:5],
        "top_plans": plan_preview[:5],
        "top_trajectory": top_trajectory[:5],
    }
    return narrative


def build_portfolio_narrative(db: Session) -> dict[str, Any]:
    summary = portfolio_svc.build_portfolio_summary(db)
    programs = portfolio_svc.build_portfolio_program_summaries(db)
    claim_summary = portfolio_svc.build_portfolio_claim_summary(db, limit=10)
    plan_summary = portfolio_svc.build_portfolio_plan_summary(db, limit=10)

    strongest = sorted(
        [r for r in programs if float(r.get("readiness_score") or 0.0) >= 0.0],
        key=lambda r: (
            -float(r.get("readiness_score") or 0.0),
            int(r.get("open_tasks") or 0),
            int(r.get("program_id") or 0),
        ),
    )[:5]
    blocked = sorted(
        [r for r in programs if int(r.get("blocked_tasks") or 0) > 0],
        key=lambda r: (
            -int(r.get("blocked_tasks") or 0),
            -int(r.get("overdue_tasks") or 0),
            int(r.get("program_id") or 0),
        ),
    )[:5]
    bottlenecks: list[str] = []
    for row in programs:
        for b in (row.get("bottleneck_badges") or []):
            s = str(b or "").strip()
            if s:
                bottlenecks.append(s)
    bottleneck_counts: dict[str, int] = {}
    for b in bottlenecks:
        bottleneck_counts[b] = int(bottleneck_counts.get(b, 0)) + 1
    key_bottlenecks = [
        f"{k} ({v})"
        for k, v in sorted(bottleneck_counts.items(), key=lambda x: (-x[1], x[0]))[:5]
    ]
    if not key_bottlenecks:
        key_bottlenecks = [
            f"Missing-data molecules: {int(summary.get('missing_data_molecules') or 0)}",
            f"Blocked tasks: {int(summary.get('blocked_tasks') or 0)}",
        ]
    near_term_inflection_rows = sorted(
        [
            {
                "program_id": int(r.get("program_id") or 0),
                "program_name": str(r.get("program_name") or ""),
                "molecules_ready": int(r.get("molecules_ready") or 0),
                "open_tasks": int(r.get("open_tasks") or 0),
                "readiness_score": float(r.get("readiness_score") or 0.0),
            }
            for r in programs
            if int(r.get("molecules_ready") or 0) > 0 or float(r.get("readiness_score") or 0.0) > 0.0
        ],
        key=lambda r: (
            -int(r["molecules_ready"]),
            -float(r["readiness_score"]),
            int(r["open_tasks"]),
            int(r["program_id"]),
        ),
    )[:5]
    plans_actionable = _as_list(plan_summary.get("most_actionable_plans"))
    plans_pending = [
        p for p in plans_actionable
        if int(p.get("proposed_steps") or 0) > 0 and str(p.get("status") or "") in {"recommended", "accepted"}
    ]
    largest_gap_rows = portfolio_svc.build_evidence_gap_report(db, limit=5)
    leadership_cards = {
        "programs_nearing_milestone": near_term_inflection_rows[:3],
        "programs_needing_support": blocked[:3],
        "highest_value_pending_plans": plans_pending[:3],
        "largest_evidence_gaps": largest_gap_rows[:3],
    }

    out = {
        "portfolio_summary": summary,
        "strongest_programs": strongest,
        "blocked_programs": blocked,
        "most_blocked_programs": blocked,
        "key_bottlenecks": key_bottlenecks,
        "highest_value_plans": _as_list(plan_summary.get("most_actionable_plans"))[:5],
        "near_term_inflection_points": [
            f"Recommended plans: {int(summary.get('recommended_plans') or 0)}",
            f"Programs with ready molecules: {sum(1 for r in programs if int(r.get('molecules_ready') or 0) > 0)}",
        ],
        "near_term_inflection_rows": near_term_inflection_rows,
        "leadership_cards": leadership_cards,
        "task_burden_summary": {
            "tasks_in_progress": int(summary.get("tasks_in_progress") or 0),
            "tasks_overdue": int(summary.get("tasks_overdue") or 0),
            "tasks_blocked": int(summary.get("tasks_blocked") or 0),
            "tasks_unassigned": int(summary.get("tasks_unassigned") or 0),
        },
        "evidence_gap_summary": {
            "missing_data_molecules": int(summary.get("missing_data_molecules") or 0),
            "evidence_starved_claims": len(_as_list(claim_summary.get("most_evidence_starved_claims"))),
        },
    }
    return out
