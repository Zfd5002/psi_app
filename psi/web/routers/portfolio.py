from __future__ import annotations

import csv
from io import StringIO

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from psi.services import portfolio as portfolio_svc
from psi.web.deps import get_db, get_templates

router = APIRouter()


@router.get("/portfolio", response_class=HTMLResponse)
def portfolio_overview(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    summary = portfolio_svc.build_portfolio_summary(db)
    programs = portfolio_svc.build_portfolio_program_summaries(db)
    leaderboard = portfolio_svc.build_molecule_leaderboard(db, limit=20)
    gaps = portfolio_svc.build_evidence_gap_report(db, limit=20)
    timeline = portfolio_svc.build_portfolio_timeline(db, weeks=12)
    return templates.TemplateResponse(
        "portfolio/overview.html",
        {
            "request": request,
            "portfolio_summary": summary,
            "program_summaries": programs,
            "molecule_leaderboard": leaderboard,
            "evidence_gap_report": gaps,
            "portfolio_timeline": timeline,
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
