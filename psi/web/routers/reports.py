from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from psi.services import reports_v3 as svc
from psi.services import v3_narrative as narrative_svc
from psi.web.deps import get_db, get_templates

router = APIRouter()


@router.get("/reports", response_class=HTMLResponse)
def list_reports(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    return templates.TemplateResponse("reports/list.html", {"request": request, "report_runs": svc.list_report_runs(db)})


@router.get("/reports/new", response_class=HTMLResponse)
def new_report(request: Request):
    templates = get_templates(request)
    return templates.TemplateResponse("reports/new.html", {"request": request})


@router.post("/reports/new")
def create_report(
    report_type: str = Form(...),
    subject_ids: str = Form(...),
    as_of: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        row = svc.generate_report_from_form(db, report_type=report_type, subject_ids_text=subject_ids, as_of_text=as_of)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RedirectResponse(url=f"/reports/{row.id}", status_code=303)


@router.get("/reports/{report_run_id}", response_class=HTMLResponse)
def report_detail(report_run_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    try:
        ctx = svc.get_report_run_detail(db, report_run_id)
    except KeyError:
        raise HTTPException(404)
    payload = ctx.get("payload") if isinstance(ctx.get("payload"), dict) else {}
    report_type = str((ctx.get("report_run").report_type if ctx.get("report_run") is not None else "") or "")
    renderers = {
        "molecule_report": narrative_svc.render_molecule_narrative,
        "program_report": narrative_svc.render_program_narrative,
        "molecule_comparative_report": narrative_svc.render_molecule_comparison_narrative,
        "molecule_comparison_report": narrative_svc.render_molecule_comparison_narrative,
        "program_comparative_report": narrative_svc.render_program_comparison_narrative,
        "program_comparison_report": narrative_svc.render_program_comparison_narrative,
    }
    renderer = renderers.get(report_type, narrative_svc.render_molecule_narrative)
    ctx["board_narrative"] = renderer(payload)
    ctx["request"] = request
    return templates.TemplateResponse("reports/detail.html", ctx)
