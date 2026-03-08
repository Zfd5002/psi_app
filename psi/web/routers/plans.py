from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from psi.core.models import Molecule, ScientificClaim
from psi.services import plans as plans_svc
from psi.web.deps import get_db, get_templates
from psi.web import ui_surfaces

router = APIRouter()


@router.get("/plans", response_class=HTMLResponse)
def plans_list(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    rows = plans_svc.list_plans(db, include_archived=False, limit=200)
    return templates.TemplateResponse(
        "plans/list.html",
        {
            "request": request,
            "plans": rows,
            "surface": ui_surfaces.plans_registry_surface(),
        },
    )


@router.get("/plans/new", response_class=HTMLResponse)
def plan_new(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    molecules = (
        db.query(Molecule)
        .order_by(Molecule.primary_id.asc(), Molecule.id.asc())
        .limit(500)
        .all()
    )
    claims = (
        db.query(ScientificClaim)
        .order_by(ScientificClaim.updated_at.desc(), ScientificClaim.id.asc())
        .limit(500)
        .all()
    )
    return templates.TemplateResponse(
        "plans/new.html",
        {
            "request": request,
            "molecules": molecules,
            "claims": claims,
            "plan_types": list(plans_svc.PLAN_TYPES),
            "error": "",
        },
    )


@router.post("/plans/new")
def plan_create(
    request: Request,
    scope_type: str = Form("molecule"),
    molecule_id: int | None = Form(None),
    claim_id: int | None = Form(None),
    title: str = Form(""),
    plan_type: str = Form("readiness_advancement"),
    rationale: str = Form(""),
    db: Session = Depends(get_db),
):
    scope = str(scope_type or "").strip().lower()
    molecule: Molecule | None = None
    claim: ScientificClaim | None = None
    program_id: int | None = None
    out_molecule_id: int | None = None
    out_claim_id: int | None = None
    if scope == "claim":
        if claim_id is None:
            raise HTTPException(status_code=400, detail="claim_id_required")
        claim = db.get(ScientificClaim, int(claim_id))
        if claim is None:
            raise HTTPException(status_code=400, detail="invalid_claim_id")
        out_claim_id = int(claim.id)
        out_molecule_id = int(claim.molecule_id) if claim.molecule_id is not None else None
        program_id = int(claim.program_id) if claim.program_id is not None else None
    else:
        scope = "molecule"
        if molecule_id is None:
            raise HTTPException(status_code=400, detail="molecule_id_required")
        molecule = db.get(Molecule, int(molecule_id))
        if molecule is None:
            raise HTTPException(status_code=400, detail="invalid_molecule_id")
        out_molecule_id = int(molecule.id)
        program_id = int(molecule.program_id)
    row = plans_svc.create_plan(
        db,
        scope_type=scope,
        molecule_id=out_molecule_id,
        program_id=program_id,
        claim_id=out_claim_id,
        title=str(title or "").strip(),
        plan_type=str(plan_type or ""),
        status="draft",
        rationale=str(rationale or "").strip(),
    )
    return RedirectResponse(url=f"/plans/{int(row.id)}", status_code=303)


@router.get("/plans/{plan_id}", response_class=HTMLResponse)
def plan_detail(plan_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    try:
        ctx = plans_svc.build_plan_detail(db, plan_id=int(plan_id))
    except KeyError:
        raise HTTPException(404)
    ctx["request"] = request
    plan_obj = ctx.get("plan")
    pid = int(plan_obj.program_id) if plan_obj is not None and getattr(plan_obj, "program_id", None) is not None else None
    ctx["surface"] = ui_surfaces.plan_detail_surface(program_id=pid)
    return templates.TemplateResponse("plans/detail.html", ctx)


@router.post("/plans/{plan_id}/instantiate")
def instantiate_plan(
    plan_id: int,
    request: Request,
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
):
    plans_svc.create_tasks_from_plan(db, plan_id=int(plan_id))
    target = str(redirect_to or "").strip() or f"/plans/{int(plan_id)}"
    return RedirectResponse(url=target, status_code=303)


@router.post("/plans/{plan_id}/transition")
def transition_plan(
    plan_id: int,
    request: Request,
    status: str = Form(...),
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        plans_svc.update_plan_status(db, plan_id=int(plan_id), status=str(status or ""))
    except KeyError:
        raise HTTPException(404)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    target = str(redirect_to or "").strip() or f"/plans/{int(plan_id)}"
    return RedirectResponse(url=target, status_code=303)


@router.post("/plans/steps/{step_id}/instantiate")
def instantiate_plan_step(
    step_id: int,
    request: Request,
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
):
    plans_svc.create_task_from_plan_step(db, step_id=int(step_id))
    target = str(redirect_to or "").strip() or "/plans"
    return RedirectResponse(url=target, status_code=303)
