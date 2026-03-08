from __future__ import annotations

import csv
from io import StringIO

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from psi.services import portfolio as portfolio_svc
from psi.services import trajectory as trajectory_svc
from psi.services import narratives as narratives_svc
from psi.web.deps import get_db, get_templates
from psi.web import ui_surfaces

router = APIRouter()


@router.get("/portfolio", response_class=HTMLResponse)
def portfolio_overview(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    summary = portfolio_svc.build_portfolio_summary(db)
    programs = portfolio_svc.build_portfolio_program_summaries(db)
    leaderboard = portfolio_svc.build_molecule_leaderboard(db, limit=20)
    gaps = portfolio_svc.build_evidence_gap_report(db, limit=20)
    timeline = portfolio_svc.build_portfolio_timeline(db, weeks=12)
    portfolio_trajectory = trajectory_svc.build_portfolio_trajectory(db, limit=20)
    claim_summary = portfolio_svc.build_portfolio_claim_summary(db, limit=20)
    plan_summary = portfolio_svc.build_portfolio_plan_summary(db, limit=20)
    portfolio_narrative = narratives_svc.build_portfolio_narrative(db)
    q = getattr(request, "query_params", {}) or {}
    brief = str((q.get("view") if hasattr(q, "get") else "") or "").strip().lower() == "brief"
    return templates.TemplateResponse(
        "portfolio/overview.html",
        {
            "request": request,
            "portfolio_summary": summary,
            "program_summaries": programs,
            "molecule_leaderboard": leaderboard,
            "evidence_gap_report": gaps,
            "portfolio_timeline": timeline,
            "portfolio_trajectory": portfolio_trajectory.get("experiments") or [],
            "portfolio_claim_summary": claim_summary,
            "portfolio_plan_summary": plan_summary,
            "portfolio_narrative": portfolio_narrative,
            "narrative_brief": brief,
            "surface": ui_surfaces.portfolio_overview_surface(),
        },
    )


@router.get("/portfolio/export")
def portfolio_export(db: Session = Depends(get_db)):
    rows = portfolio_svc.build_portfolio_export_rows(db)
    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "program_id",
            "program_name",
            "program_status",
            "readiness_score",
            "molecule_count",
            "molecules_ready",
            "molecules_failed",
            "molecules_missing_data",
            "open_tasks",
            "overdue_tasks",
            "blocked_tasks",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    body = buffer.getvalue()
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="portfolio_summary.csv"'},
    )


@router.get("/portfolio/narrative/export")
def portfolio_narrative_export(db: Session = Depends(get_db)):
    n = narratives_svc.build_portfolio_narrative(db)
    s = n.get("portfolio_summary") if isinstance(n.get("portfolio_summary"), dict) else {}
    lines = [
        "Portfolio Narrative Export",
        f"Programs: {int(s.get('program_count') or 0)}",
        f"Molecules: {int(s.get('molecule_count') or 0)}",
        f"Ready molecules: {int(s.get('ready_molecules') or 0)}",
        f"Missing-data molecules: {int(s.get('missing_data_molecules') or 0)}",
        "Key bottlenecks:",
    ]
    for row in (n.get("key_bottlenecks") or []):
        lines.append(f"- {str(row)}")
    lines.append("Near-term inflection points:")
    for row in (n.get("near_term_inflection_points") or []):
        lines.append(f"- {str(row)}")
    return Response(
        content="\\n".join(lines) + "\\n",
        media_type="text/plain",
        headers={"Content-Disposition": 'attachment; filename="portfolio_narrative.txt"'},
    )
