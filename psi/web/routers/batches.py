from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from psi.services import batches as svc
from psi.core.batch_id import next_batch_id
from psi.core.models import Molecule
from psi.services import files as file_svc
from psi.web.deps import get_db, get_storage_cfg, get_templates

router = APIRouter()


@router.get("/batches", response_class=HTMLResponse)
def list_batches(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    batches, molecules = svc.list_batches(db)
    return templates.TemplateResponse("batches/list.html", {"request": request, "batches": batches, "molecules": molecules})


@router.get("/batches/new", response_class=HTMLResponse)
def new_batch(request: Request, molecule_id: int | None = None, db: Session = Depends(get_db)):
    templates = get_templates(request)
    _, molecules = svc.list_batches(db)
    selected_molecule_id = molecule_id
    suggested_batch_id = None
    if molecule_id:
        mol = db.get(Molecule, molecule_id)
        if mol:
            suggested_batch_id = next_batch_id(db, mol)
    return templates.TemplateResponse("batches/form.html", {"request": request, "batch": None, "molecules": molecules, "suggested_batch_id": suggested_batch_id, "selected_molecule_id": selected_molecule_id})


@router.post("/batches/new")
def create_batch(
    molecule_id: int = Form(...),
    title: str = Form(""),
    expression_notes: str = Form(""),
    purification_notes: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        b = svc.create_batch(
            db,
            molecule_id=molecule_id,
            title=title,
            expression_notes=expression_notes,
            purification_notes=purification_notes,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(url=f"/batches/{b.id}", status_code=303)


@router.get("/batches/{batch_id}", response_class=HTMLResponse)
def batch_detail(batch_id: int, request: Request, tab: str = "data", db: Session = Depends(get_db)):
    templates = get_templates(request)
    if tab not in ("data", "evidence", "files", "decisions", "audit"):
        tab = "data"
    try:
        ctx = svc.get_batch_detail(db, batch_id)
    except KeyError:
        raise HTTPException(404)
    ctx.update({"request": request, "tab": tab})
    return templates.TemplateResponse("batches/detail.html", ctx)


@router.post("/batches/{batch_id}/files")
def batch_add_files(
    batch_id: int,
    file_role: str = Form("other"),
    instrument: str = Form(""),
    operator: str = Form(""),
    run_id: str = Form(""),
    collected_at: str = Form(""),
    notes: str = Form(""),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    storage=Depends(get_storage_cfg),
):
    b = svc.get_batch(db, batch_id)
    if not b:
        raise HTTPException(404)

    uploads = []
    for uf in files:
        if uf.filename:
            uploads.append((uf.filename, uf.content_type or "application/octet-stream", uf.file.read()))

    if uploads:
        file_svc.attach_files(
            db,
            storage=storage,
            entity_type="Batch",
            entity_id=batch_id,
            uploads=uploads,
            role=(file_role or "other"),
            instrument=instrument or None,
            operator=operator or None,
            run_id=run_id or None,
            collected_at=collected_at or None,
            notes=notes or None,
        )

    return RedirectResponse(url=f"/batches/{batch_id}", status_code=303)


@router.get("/batches/{batch_id}/edit", response_class=HTMLResponse)
def edit_batch(batch_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    b = svc.get_batch(db, batch_id)
    if not b:
        raise HTTPException(404)
    _, molecules = svc.list_batches(db)
    return templates.TemplateResponse("batches/form.html", {"request": request, "batch": b, "molecules": molecules, "suggested_batch_id": None})


@router.post("/batches/{batch_id}/edit")
def update_batch(
    batch_id: int,
    title: str = Form(""),
    expression_notes: str = Form(""),
    purification_notes: str = Form(""),
    reason: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        b = svc.update_batch(
            db,
            batch_db_id=batch_id,
            title=title,
            expression_notes=expression_notes,
            purification_notes=purification_notes,
            reason=reason,
        )
    except KeyError:
        raise HTTPException(404)

    return RedirectResponse(url=f"/batches/{b.id}", status_code=303)
