from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from psi.core.models import Molecule, Program
from psi.services import claims as claims_svc
from psi.web.deps import get_db, get_templates
from psi.web import ui_surfaces

router = APIRouter()


@router.get("/claims", response_class=HTMLResponse)
def claims_list(request: Request, program_id: int | None = None, db: Session = Depends(get_db)):
    templates = get_templates(request)
    rows = (
        claims_svc.list_claims_for_program(db, program_id=int(program_id), include_archived=False)
        if program_id is not None
        else claims_svc.list_claims(db, include_archived=False, limit=200)
    )
    active_program = db.get(Program, int(program_id)) if program_id is not None else None
    return templates.TemplateResponse(
        "claims/list.html",
        {
            "request": request,
            "claims": rows,
            "active_program": active_program,
            "surface": ui_surfaces.claims_registry_surface(program_id=program_id),
        },
    )


@router.get("/claims/new", response_class=HTMLResponse)
def claim_new(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    molecules = (
        db.query(Molecule)
        .order_by(Molecule.primary_id.asc(), Molecule.id.asc())
        .limit(500)
        .all()
    )
    return templates.TemplateResponse(
        "claims/new.html",
        {
            "request": request,
            "molecules": molecules,
            "claim_types": list(claims_svc.CLAIM_TYPES),
            "error": "",
        },
    )


@router.post("/claims/new")
def claim_create(
    request: Request,
    molecule_id: int = Form(...),
    title: str = Form(""),
    claim_type: str = Form("mechanism"),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    mol = db.get(Molecule, int(molecule_id))
    if mol is None:
        raise HTTPException(status_code=400, detail="invalid_molecule_id")
    claim = claims_svc.create_claim(
        db,
        scope_type="molecule",
        molecule_id=int(mol.id),
        program_id=int(mol.program_id),
        title=str(title or "").strip(),
        claim_type=str(claim_type or "mechanism"),
        statement=str(description or "").strip(),
        status="hypothesis",
        confidence_level="low",
        rationale="",
    )
    return RedirectResponse(url=f"/claims/{int(claim.id)}", status_code=303)


@router.post("/claims/{claim_id}/transition")
def claim_transition(
    claim_id: int,
    request: Request,
    status: str = Form(...),
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        claims_svc.update_claim_status(db, claim_id=int(claim_id), status=str(status or ""))
    except KeyError:
        raise HTTPException(404)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    target = str(redirect_to or "").strip() or f"/claims/{int(claim_id)}"
    return RedirectResponse(url=target, status_code=303)


@router.get("/claims/{claim_id}", response_class=HTMLResponse)
def claim_detail(claim_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    try:
        ctx = claims_svc.get_claim_detail(db, claim_id=int(claim_id))
    except KeyError:
        raise HTTPException(404)
    ctx["request"] = request
    claim_obj = ctx.get("claim")
    pid = int(claim_obj.program_id) if claim_obj is not None and getattr(claim_obj, "program_id", None) is not None else None
    ctx["surface"] = ui_surfaces.claim_detail_surface(program_id=pid)
    return templates.TemplateResponse("claims/detail.html", ctx)
