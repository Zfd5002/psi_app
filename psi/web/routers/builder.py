from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from psi.services.builder import MoleculeBuildSpec, MoleculeCreateMeta, build_molecule_draft, create_molecule_from_draft
from psi.core.models import Molecule
from psi.web.deps import get_db, get_templates

router = APIRouter()


@router.get("/builder", response_class=HTMLResponse)
def builder_home(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    molecules = (
        db.query(Molecule)
        .order_by(Molecule.primary_id.asc(), Molecule.id.asc())
        .limit(200)
        .all()
    )
    return templates.TemplateResponse(
        "builder/index.html",
        {
            "request": request,
            "molecules": molecules,
        },
    )


@router.get("/builder/clone", response_class=HTMLResponse)
def builder_clone_page(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    molecules = (
        db.query(Molecule)
        .order_by(Molecule.primary_id.asc(), Molecule.id.asc())
        .limit(200)
        .all()
    )
    return templates.TemplateResponse(
        "builder/clone.html",
        {
            "request": request,
            "molecules": molecules,
            "draft": None,
            "form_data": {},
            "error": "",
        },
    )


@router.post("/builder/clone/draft", response_class=HTMLResponse)
async def builder_clone_build_draft(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    form = dict(await request.form())
    parent_molecule_id = int(form.get("parent_molecule_id") or 0)
    new_primary_id = str(form.get("new_primary_id") or "").strip()
    new_title = str(form.get("new_title") or "").strip()
    rationale = str(form.get("rationale") or "").strip()
    draft = build_molecule_draft(
        db,
        MoleculeBuildSpec(
            mode="clone",
            parent_molecule_id=parent_molecule_id,
            new_primary_id=new_primary_id,
            new_title=new_title,
            rationale=rationale,
            operations=[],
        ),
    )
    molecules = (
        db.query(Molecule)
        .order_by(Molecule.primary_id.asc(), Molecule.id.asc())
        .limit(200)
        .all()
    )
    return templates.TemplateResponse(
        "builder/clone.html",
        {
            "request": request,
            "molecules": molecules,
            "draft": draft,
            "form_data": {
                "parent_molecule_id": parent_molecule_id,
                "new_primary_id": new_primary_id,
                "new_title": new_title,
                "rationale": rationale,
            },
            "error": "",
        },
    )


@router.post("/builder/clone/create")
async def builder_clone_create(request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())
    parent_molecule_id = int(form.get("parent_molecule_id") or 0)
    new_primary_id = str(form.get("new_primary_id") or "").strip()
    new_title = str(form.get("new_title") or "").strip()
    rationale = str(form.get("rationale") or "").strip()
    draft = build_molecule_draft(
        db,
        MoleculeBuildSpec(
            mode="clone",
            parent_molecule_id=parent_molecule_id,
            new_primary_id=new_primary_id,
            new_title=new_title,
            rationale=rationale,
            operations=[],
        ),
    )
    if not draft.is_valid:
        return RedirectResponse(url="/builder/clone", status_code=303)
    try:
        m = create_molecule_from_draft(db, draft, MoleculeCreateMeta(actor="builder"))
    except ValueError:
        return RedirectResponse(url="/builder/clone", status_code=303)
    return RedirectResponse(url=f"/molecules/{int(m.id)}", status_code=303)


@router.get("/builder/point-mutation", response_class=HTMLResponse)
def builder_point_mutation_page(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    molecules = (
        db.query(Molecule)
        .order_by(Molecule.primary_id.asc(), Molecule.id.asc())
        .limit(200)
        .all()
    )
    return templates.TemplateResponse(
        "builder/point_mutation.html",
        {
            "request": request,
            "molecules": molecules,
            "draft": None,
            "form_data": {},
            "error": "",
        },
    )


@router.post("/builder/point-mutation/draft", response_class=HTMLResponse)
async def builder_point_mutation_build_draft(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    form = dict(await request.form())
    parent_molecule_id = int(form.get("parent_molecule_id") or 0)
    new_primary_id = str(form.get("new_primary_id") or "").strip()
    new_title = str(form.get("new_title") or "").strip()
    rationale = str(form.get("rationale") or "").strip()
    component = str(form.get("component") or "").strip()
    mutations = str(form.get("mutations") or "").strip()
    draft = build_molecule_draft(
        db,
        MoleculeBuildSpec(
            mode="point_mutation",
            parent_molecule_id=parent_molecule_id,
            new_primary_id=new_primary_id,
            new_title=new_title,
            rationale=rationale,
            operations=[{"type": "point_mutation", "component": component, "mutations": mutations}],
        ),
    )
    molecules = (
        db.query(Molecule)
        .order_by(Molecule.primary_id.asc(), Molecule.id.asc())
        .limit(200)
        .all()
    )
    return templates.TemplateResponse(
        "builder/point_mutation.html",
        {
            "request": request,
            "molecules": molecules,
            "draft": draft,
            "form_data": {
                "parent_molecule_id": parent_molecule_id,
                "new_primary_id": new_primary_id,
                "new_title": new_title,
                "rationale": rationale,
                "component": component,
                "mutations": mutations,
            },
            "error": "",
        },
    )


@router.post("/builder/point-mutation/create")
async def builder_point_mutation_create(request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())
    parent_molecule_id = int(form.get("parent_molecule_id") or 0)
    new_primary_id = str(form.get("new_primary_id") or "").strip()
    new_title = str(form.get("new_title") or "").strip()
    rationale = str(form.get("rationale") or "").strip()
    component = str(form.get("component") or "").strip()
    mutations = str(form.get("mutations") or "").strip()
    draft = build_molecule_draft(
        db,
        MoleculeBuildSpec(
            mode="point_mutation",
            parent_molecule_id=parent_molecule_id,
            new_primary_id=new_primary_id,
            new_title=new_title,
            rationale=rationale,
            operations=[{"type": "point_mutation", "component": component, "mutations": mutations}],
        ),
    )
    if not draft.is_valid:
        return RedirectResponse(url="/builder/point-mutation", status_code=303)
    try:
        m = create_molecule_from_draft(db, draft, MoleculeCreateMeta(actor="builder"))
    except ValueError:
        return RedirectResponse(url="/builder/point-mutation", status_code=303)
    return RedirectResponse(url=f"/molecules/{int(m.id)}", status_code=303)
