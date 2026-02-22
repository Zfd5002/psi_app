from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from psi.services import decisions as svc
from psi.services.di.verify import verify_snapshot
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


@router.get("/decisions/compare", response_class=HTMLResponse)
def decisions_compare(request: Request, snap_a: int, snap_b: int, db: Session = Depends(get_db)):
    templates = get_templates(request)
    ctx = svc.get_snapshot_compare_context(db, snap_a=snap_a, snap_b=snap_b)
    ctx["request"] = request
    return templates.TemplateResponse("decisions/compare.html", ctx)


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


@router.post("/decisions/{snap_id}/verify", response_class=HTMLResponse)
def decisions_verify(snap_id: int, request: Request, debug: int = 0, db: Session = Depends(get_db)):
    templates = get_templates(request)
    try:
        snap_ctx = svc.get_snapshot_detail(db, snap_id)
    except KeyError:
        raise HTTPException(404)

    report = verify_snapshot(db=db, snapshot_id=int(snap_id), debug=bool(int(debug) if debug is not None else 0))

    ctx = {
        "request": request,
        "snap": snap_ctx.get("snap"),
        "report": report,
    }
    return templates.TemplateResponse("decisions/verify.html", ctx)


@router.get("/decisions/{snap_id}/export")
def decisions_export(snap_id: int, db: Session = Depends(get_db)):
    try:
        payload = svc.get_snapshot_export_payload(db, snap_id)
    except KeyError:
        raise HTTPException(404)

    body = svc.stable_json_dumps(payload)
    filename = f"decision_snapshot_{snap_id}.json"
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
