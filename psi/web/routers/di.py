from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from psi.core.di.schema import DIInput
from psi.services.di.runner import run_di
from psi.services.di.web import build_di_run_context, resolve_policy_path_for_run
from psi.web.deps import get_db, get_templates

router = APIRouter()


@router.get("/di/run", response_class=HTMLResponse)
def di_run_form(
    request: Request,
    decision_key: str | None = None,
    batch_id: int | None = None,
    molecule_id: int | None = None,
    db: Session = Depends(get_db),
):
    templates = get_templates(request)
    ctx = build_di_run_context(db, decision_key=decision_key, batch_id=batch_id, molecule_id=molecule_id)
    ctx["request"] = request
    return templates.TemplateResponse("di/run.html", ctx)


@router.post("/di/run")
def di_run_execute(
    request: Request,
    batch_id: int = Form(...),
    decision_key: str = Form(...),
    policy_path: str = Form(...),
    qc_mode: str = Form("model_safe"),
    as_of_ts: str | None = Form(None),
    db: Session = Depends(get_db),
):
    try:
        pol_path = resolve_policy_path_for_run(decision_key=decision_key, policy_path=policy_path)
    except ValueError as e:
        templates = get_templates(request)
        ctx = build_di_run_context(db, decision_key=decision_key, batch_id=batch_id)
        ctx["request"] = request
        ctx["error"] = str(e)
        return templates.TemplateResponse("di/run.html", ctx, status_code=400)

    di_in = DIInput(
        decision_key=str(decision_key),
        scope_type="batch",
        scope_id=int(batch_id),
        qc_mode=str(qc_mode or "model_safe"),
        as_of_ts=(str(as_of_ts).strip() if as_of_ts else None),
    )

    try:
        res = run_di(db, di_input=di_in, policy_path=Path(pol_path))
    except ValueError as e:
        templates = get_templates(request)
        ctx = build_di_run_context(db, decision_key=decision_key, batch_id=batch_id)
        ctx["request"] = request
        ctx["error"] = str(e)
        return templates.TemplateResponse("di/run.html", ctx, status_code=400)
    snap_id = int(res.get("snapshot_id"))
    return RedirectResponse(url=f"/decisions/{snap_id}", status_code=303)
