from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from psi.services import decisions as svc
from psi.web.deps import get_db, get_rules_path, get_templates

router = APIRouter()


@router.get("/decisions", response_class=HTMLResponse)
def list_decisions(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    snaps = svc.list_decision_snapshots(db)
    return templates.TemplateResponse("decisions/list.html", {"request": request, "snaps": snaps})


@router.get("/decisions/new", response_class=HTMLResponse)
def decisions_new(request: Request, db: Session = Depends(get_db), rules_path=Depends(get_rules_path)):
    templates = get_templates(request)
    ctx = svc.get_decision_new_context(db, str(rules_path))
    ctx["request"] = request
    return templates.TemplateResponse("decisions/new.html", ctx)


@router.post("/decisions/new")
def decisions_run(
    program_id: int = Form(...),
    molecule_id: int | None = Form(None),
    batch_id: int | None = Form(None),
    decision_key: str = Form(...),
    assumptions_ack: str | None = Form(None),
    db: Session = Depends(get_db),
    rules_path=Depends(get_rules_path),
):
    try:
        snap = svc.run_and_snapshot(
            db,
            rules_path=str(rules_path),
            program_id=program_id,
            molecule_id=molecule_id,
            batch_id=batch_id,
            decision_key=decision_key,
            assumptions_ack=bool(assumptions_ack),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return RedirectResponse(url=f"/decisions/{snap.id}", status_code=303)


@router.get("/decisions/{snap_id}", response_class=HTMLResponse)
def decisions_detail(snap_id: int, request: Request, print_view: int = 0, db: Session = Depends(get_db)):
    templates = get_templates(request)
    try:
        ctx = svc.get_snapshot_detail(db, snap_id)
    except KeyError:
        raise HTTPException(404)

    tmpl = "decisions/detail_print.html" if print_view else "decisions/detail.html"
    ctx["request"] = request
    return templates.TemplateResponse(tmpl, ctx)
