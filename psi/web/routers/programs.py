from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from psi.core.models import Molecule
from psi.web.deps import get_db, get_templates
from psi.services import programs as svc
from psi.services import data_records as data_records_svc

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


@router.post("/programs/{program_id}/molecules/{molecule_id}/role")
def update_program_molecule_role(
    program_id: int,
    molecule_id: int,
    role: str = Form("active"),
    rationale: str = Form(""),
    db: Session = Depends(get_db),
):
    p = svc.get_program(db, program_id)
    if not p:
        raise HTTPException(404)
    m = db.get(Molecule, int(molecule_id))
    if m is None:
        raise HTTPException(404)
    if int(m.program_id) != int(program_id):
        raise HTTPException(status_code=400, detail="molecule_not_in_program")
    svc.upsert_program_molecule_status(
        db,
        program_id=int(program_id),
        molecule_id=int(molecule_id),
        role=role,
        rationale=rationale,
    )
    return RedirectResponse(url=f"/programs/{program_id}", status_code=303)


@router.post("/programs/{program_id}/review/approve-all", name="program_review_approve_all")
def program_review_approve_all(
    program_id: int,
    actor: str = Form("scientist"),
    db: Session = Depends(get_db),
):
    p = svc.get_program(db, program_id)
    if not p:
        raise HTTPException(404)
    queue = svc.build_program_review_queue(db, program_id=program_id)
    record_ids = sorted(
        {
            int(row.get("record_id"))
            for group in queue
            for row in (group.get("records") or [])
            if isinstance(row, dict) and row.get("record_id") is not None
        }
    )
    for rid in record_ids:
        data_records_svc.apply_bulk_qc_action_for_record(
            db,
            record_id=int(rid),
            action="approve",
            actor=(actor or "scientist"),
            note=None,
        )
    return RedirectResponse(url=f"/programs/{program_id}", status_code=303)


@router.post("/programs/{program_id}/review/reject-all", name="program_review_reject_all")
def program_review_reject_all(
    program_id: int,
    actor: str = Form("scientist"),
    db: Session = Depends(get_db),
):
    p = svc.get_program(db, program_id)
    if not p:
        raise HTTPException(404)
    queue = svc.build_program_review_queue(db, program_id=program_id)
    record_ids = sorted(
        {
            int(row.get("record_id"))
            for group in queue
            for row in (group.get("records") or [])
            if isinstance(row, dict) and row.get("record_id") is not None
        }
    )
    for rid in record_ids:
        data_records_svc.apply_bulk_qc_action_for_record(
            db,
            record_id=int(rid),
            action="reject",
            actor=(actor or "scientist"),
            note=None,
        )
    return RedirectResponse(url=f"/programs/{program_id}", status_code=303)
