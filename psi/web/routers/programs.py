from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from psi.web.deps import get_db, get_templates
from psi.services import programs as svc

router = APIRouter()


@router.get("/programs", response_class=HTMLResponse)
def list_programs(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    return templates.TemplateResponse("programs/list.html", {"request": request, "programs": svc.list_programs(db)})


@router.get("/programs/new", response_class=HTMLResponse)
def new_program(request: Request):
    templates = get_templates(request)
    return templates.TemplateResponse("programs/form.html", {"request": request, "program": None})


@router.post("/programs/new")
def create_program(
    name: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    p = svc.create_program(db, name=name, description=description)
    return RedirectResponse(url=f"/programs/{p.id}", status_code=303)


@router.get("/programs/{program_id}", response_class=HTMLResponse)
def program_detail(program_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    try:
        pol_filter = request.query_params.get("policy_version")
        verify_lineage = str(request.query_params.get("verify") or "").strip() == "1"
        ctx = svc.get_program_detail(
            db,
            program_id,
            policy_version_filter=(pol_filter or None),
            verify_lineage=verify_lineage,
        )
    except KeyError:
        raise HTTPException(404)
    ctx["request"] = request
    return templates.TemplateResponse("programs/detail.html", ctx)


@router.get("/programs/{program_id}/edit", response_class=HTMLResponse)
def edit_program(program_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    p = svc.get_program(db, program_id)
    if not p:
        raise HTTPException(404)
    return templates.TemplateResponse("programs/form.html", {"request": request, "program": p})


@router.post("/programs/{program_id}/edit")
def update_program(
    program_id: int,
    name: str = Form(...),
    description: str = Form(""),
    reason: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        p = svc.update_program(db, program_id=program_id, name=name, description=description, reason=reason)
    except KeyError:
        raise HTTPException(404)
    return RedirectResponse(url=f"/programs/{p.id}", status_code=303)


@router.post("/programs/{program_id}/memberships/add")
def add_program_membership(
    program_id: int,
    molecule_id: int = Form(...),
    sort_index: int = Form(0),
    db: Session = Depends(get_db),
):
    try:
        svc.add_program_membership(db, program_id=program_id, molecule_id=molecule_id, sort_index=sort_index)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RedirectResponse(url=f"/programs/{program_id}", status_code=303)


@router.post("/programs/{program_id}/memberships/{membership_id}/sort")
def update_program_membership_sort(
    program_id: int,
    membership_id: int,
    sort_index: int = Form(...),
    db: Session = Depends(get_db),
):
    try:
        svc.update_program_membership(db, membership_id=membership_id, sort_index=sort_index)
    except KeyError:
        raise HTTPException(404)
    return RedirectResponse(url=f"/programs/{program_id}", status_code=303)


@router.post("/programs/{program_id}/memberships/{membership_id}/remove")
def remove_program_membership(
    program_id: int,
    membership_id: int,
    db: Session = Depends(get_db),
):
    try:
        svc.remove_program_membership(db, membership_id=membership_id)
    except KeyError:
        raise HTTPException(404)
    return RedirectResponse(url=f"/programs/{program_id}", status_code=303)
