from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from psi.core.models import Batch, Molecule, Program
from psi.core.registry import REGISTRY, get_allowed_data_sources_for_evidence
from psi.services import search as svc
from psi.web.deps import get_db, get_templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    programs = db.query(Program).order_by(Program.created_at.desc()).limit(10).all()
    molecules = db.query(Molecule).order_by(Molecule.created_at.desc()).limit(10).all()
    batches = db.query(Batch).order_by(Batch.created_at.desc()).limit(10).all()
    return templates.TemplateResponse("home.html", {"request": request, "programs": programs, "molecules": molecules, "batches": batches})


@router.get("/api/registry", response_class=JSONResponse)
def api_registry():
    return REGISTRY


@router.get("/api/evidence_allowed_sources", response_class=JSONResponse)
def api_evidence_allowed_sources(evidence_type: str):
    return get_allowed_data_sources_for_evidence(evidence_type)


@router.get("/search", response_class=HTMLResponse)
def search(request: Request, q: str = "", db: Session = Depends(get_db)):
    templates = get_templates(request)
    ctx = svc.search_all(db, q=q)
    ctx["request"] = request
    return templates.TemplateResponse("search.html", ctx)
