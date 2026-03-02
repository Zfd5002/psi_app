from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from psi.core.models import AttributionEvent, Portfolio, PortfolioMembership, ProgramMembership, ProgramRollup, ReportRun
from psi.services.policy_upgrade import get_unacknowledged_upgrade_warnings


def _load_json(raw: str | None, fallback: Any) -> Any:
    try:
        return json.loads(raw or "")
    except Exception:
        return fallback


def get_program_lineage(db: Session, *, program_id: int) -> dict[str, Any]:
    rollups = (
        db.query(ProgramRollup)
        .filter(ProgramRollup.program_id == int(program_id))
        .order_by(ProgramRollup.as_of.desc(), ProgramRollup.id.desc())
        .limit(100)
        .all()
    )
    report_runs = (
        db.query(ReportRun)
        .filter(ReportRun.report_type == "program_report")
        .filter(ReportRun.subject_ids_json == json.dumps([int(program_id)], separators=(",", ":")))
        .order_by(ReportRun.as_of.desc(), ReportRun.id.desc())
        .all()
    )
    reports_for_program: list[dict[str, Any]] = []
    for rr in report_runs:
        payload = _load_json(rr.payload_json, {})
        meta = (payload.get("metadata") if isinstance(payload, dict) else {}) or {}
        reports_for_program.append(
            {
                "id": int(rr.id),
                "report_type": str(rr.report_type),
                "as_of": rr.as_of,
                "created_at": rr.created_at,
                "snapshot_coverage": sorted({int(x) for x in _load_json(rr.snapshot_coverage_json, []) if str(x).isdigit()}),
                "policy_pins": _load_json(rr.policy_pins_json, {}),
                "metadata": meta,
            }
        )
    memberships = (
        db.query(ProgramMembership)
        .filter(ProgramMembership.program_id == int(program_id))
        .order_by(ProgramMembership.sort_index.asc(), ProgramMembership.id.asc())
        .all()
    )
    membership_ids = [int(m.id) for m in memberships]
    attrs = (
        db.query(AttributionEvent)
        .filter(
            (AttributionEvent.entity_type == "Program") & (AttributionEvent.entity_id == int(program_id))
            | ((AttributionEvent.entity_type == "ProgramMembership") & (AttributionEvent.entity_id.in_(membership_ids or [-1])))
        )
        .order_by(AttributionEvent.created_at.desc(), AttributionEvent.id.desc())
        .limit(200)
        .all()
    )
    # Categorized surfaces
    evidence_changes = []
    prev_cov: list[int] | None = None
    for rr in sorted(reports_for_program, key=lambda r: (r["as_of"], r["id"])):
        cov = [int(x) for x in (rr.get("snapshot_coverage") or [])]
        evidence_changed = (prev_cov is not None and cov != prev_cov)
        evidence_changes.append({"report_run_id": int(rr["id"]), "snapshot_coverage": cov, "evidence_changed": bool(evidence_changed)})
        prev_cov = cov
    policy_changes = []
    prev_pins: str | None = None
    for rr in sorted(reports_for_program, key=lambda r: (r["as_of"], r["id"])):
        pins_json = json.dumps(rr.get("policy_pins") or {}, sort_keys=True, separators=(",", ":"))
        policy_changed = (prev_pins is not None and pins_json != prev_pins)
        policy_changes.append({"report_run_id": int(rr["id"]), "policy_pins": rr.get("policy_pins") or {}, "policy_changed": bool(policy_changed)})
        prev_pins = pins_json
    governance_changes = [
        {
            "id": int(a.id),
            "event_type": str(a.event_type),
            "entity_type": str(a.entity_type),
            "entity_id": int(a.entity_id),
            "created_at": a.created_at,
            "metadata": _load_json(a.metadata_json, {}),
        }
        for a in attrs
    ]
    current_policy_pins = reports_for_program[0]["policy_pins"] if reports_for_program else {}
    return {
        "program_id": int(program_id),
        "rollups": [
            {
                "id": int(r.id),
                "as_of": r.as_of,
                "policy_pin": str(r.policy_pin),
                "policy_package_hash": (str(r.policy_package_hash) if r.policy_package_hash else None),
                "snapshot_ids": _load_json(r.snapshot_ids_json, []),
            }
            for r in rollups
        ],
        "report_history": reports_for_program,
        "membership_state": [
            {"id": int(m.id), "molecule_id": int(m.molecule_id), "sort_index": int(m.sort_index or 0)}
            for m in memberships
        ],
        "evidence_changes": evidence_changes,
        "policy_changes": policy_changes,
        "governance_changes": governance_changes,
        "policy_upgrade_warnings": get_unacknowledged_upgrade_warnings(db, current_policy_pins=current_policy_pins),
    }


def get_portfolio_lineage(db: Session, *, portfolio_id: int) -> dict[str, Any]:
    portfolio = db.get(Portfolio, int(portfolio_id))
    if portfolio is None:
        raise KeyError("Portfolio not found")
    memberships = (
        db.query(PortfolioMembership)
        .filter(PortfolioMembership.portfolio_id == int(portfolio_id))
        .order_by(PortfolioMembership.sort_index.asc(), PortfolioMembership.id.asc())
        .all()
    )
    membership_ids = [int(m.id) for m in memberships]
    attrs = (
        db.query(AttributionEvent)
        .filter(
            (AttributionEvent.entity_type == "Portfolio") & (AttributionEvent.entity_id == int(portfolio_id))
            | ((AttributionEvent.entity_type == "PortfolioMembership") & (AttributionEvent.entity_id.in_(membership_ids or [-1])))
        )
        .order_by(AttributionEvent.created_at.desc(), AttributionEvent.id.desc())
        .limit(200)
        .all()
    )
    child_program_lineage = [get_program_lineage(db, program_id=int(m.program_id)) for m in memberships]
    return {
        "portfolio_id": int(portfolio.id),
        "portfolio_name": str(portfolio.name or ""),
        "membership_state": [
            {"id": int(m.id), "program_id": int(m.program_id), "sort_index": int(m.sort_index or 0)}
            for m in memberships
        ],
        "governance_changes": [
            {
                "id": int(a.id),
                "event_type": str(a.event_type),
                "entity_type": str(a.entity_type),
                "entity_id": int(a.entity_id),
                "created_at": a.created_at,
                "metadata": _load_json(a.metadata_json, {}),
            }
            for a in attrs
        ],
        "policy_upgrade_warnings": get_unacknowledged_upgrade_warnings(db, current_policy_pins={}),
        "child_program_lineage_summary": [
            {
                "program_id": int(pl["program_id"]),
                "report_count": len(pl.get("report_history") or []),
                "rollup_count": len(pl.get("rollups") or []),
                "evidence_change_events": sum(1 for e in (pl.get("evidence_changes") or []) if bool(e.get("evidence_changed"))),
                "policy_change_events": sum(1 for e in (pl.get("policy_changes") or []) if bool(e.get("policy_changed"))),
            }
            for pl in sorted(child_program_lineage, key=lambda x: int(x.get("program_id") or 0))
        ],
    }
