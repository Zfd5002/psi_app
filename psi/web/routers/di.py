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
    scope_type: str | None = None,
    db: Session = Depends(get_db),
):
    templates = get_templates(request)
    ctx = build_di_run_context(
        db,
        decision_key=decision_key,
        batch_id=batch_id,
        molecule_id=molecule_id,
        scope_type=scope_type,
    )
    ctx["request"] = request
    return templates.TemplateResponse("di/run.html", ctx)


@router.post("/di/run")
def di_run_execute(
    request: Request,
    scope_type: str = Form("batch"),
    batch_id: int | None = Form(None),
    molecule_id: int | None = Form(None),
    decision_key: str = Form(...),
    template_id: str | None = Form(None),
    route: str | None = Form(None),
    study_intent: str | None = Form(None),
    policy_path: str = Form(...),
    qc_mode: str = Form("model_safe"),
    as_of_ts: str | None = Form(None),
    db: Session = Depends(get_db),
):
    scope_type_norm = str(scope_type or "batch").strip().lower()
    if scope_type_norm not in ("batch", "molecule"):
        scope_type_norm = "batch"
    scope_id = molecule_id if scope_type_norm == "molecule" else batch_id
    if scope_id is None:
        templates = get_templates(request)
        ctx = build_di_run_context(
            db,
            decision_key=decision_key,
            batch_id=batch_id,
            molecule_id=molecule_id,
            scope_type=scope_type_norm,
        )
        ctx["request"] = request
        ctx["error"] = (
            "Batch selection is required when scope type is batch."
            if scope_type_norm == "batch"
            else "Molecule selection is required when scope type is molecule."
        )
        return templates.TemplateResponse("di/run.html", ctx, status_code=400)

    try:
        pol_path = resolve_policy_path_for_run(decision_key=decision_key, policy_path=policy_path)
    except ValueError as e:
        templates = get_templates(request)
        ctx = build_di_run_context(
            db,
            decision_key=decision_key,
            batch_id=batch_id,
            molecule_id=molecule_id,
            scope_type=scope_type_norm,
        )
        ctx["request"] = request
        ctx["error"] = str(e)
        return templates.TemplateResponse("di/run.html", ctx, status_code=400)

    di_in = DIInput(
        decision_key=str(decision_key),
        scope_type=scope_type_norm,
        scope_id=int(scope_id),
        qc_mode=str(qc_mode or "model_safe"),
        as_of_ts=(str(as_of_ts).strip() if as_of_ts else None),
        context={
            k: v
            for k, v in {
                "template_id": (str(template_id).strip() if template_id else None),
                "route": (str(route).strip() if route else None),
                "study_intent": (str(study_intent).strip() if study_intent else None),
            }.items()
            if v
        },
    )

    try:
        res = run_di(db, di_input=di_in, policy_path=Path(pol_path))
    except ValueError as e:
        templates = get_templates(request)
        ctx = build_di_run_context(
            db,
            decision_key=decision_key,
            batch_id=batch_id,
            molecule_id=molecule_id,
            scope_type=scope_type_norm,
        )
        ctx["request"] = request
        ctx["error"] = str(e)
        return templates.TemplateResponse("di/run.html", ctx, status_code=400)
    snap_id = int(res.get("snapshot_id"))
    return RedirectResponse(url=f"/decisions/{snap_id}", status_code=303)
