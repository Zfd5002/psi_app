from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from psi.services import evidence as svc
from psi.core.models import EvidenceCitation
from psi.web.deps import get_db, get_rules_path, get_storage_cfg, get_templates

router = APIRouter()


@router.get("/evidence", response_class=HTMLResponse)
def list_evidence(request: Request, db: Session = Depends(get_db), rules_path=Depends(get_rules_path)):
    templates = get_templates(request)
    ctx = svc.list_evidence(db)
    # domains for filters
    form_ctx = svc.get_evidence_form_context(db, str(rules_path))
    ctx.update({"domains": form_ctx["domains"]})
    ctx["request"] = request
    return templates.TemplateResponse("evidence/list.html", ctx)


@router.get("/evidence/new", response_class=HTMLResponse)
def new_evidence(
    request: Request,
    program_id: Optional[int] = None,
    molecule_id: Optional[int] = None,
    batch_id: Optional[int] = None,
    db: Session = Depends(get_db),
    rules_path=Depends(get_rules_path),
):
    templates = get_templates(request)
    ctx = svc.get_evidence_form_context(db, str(rules_path))
    ctx.update({"request": request, "ev": None, "prefill": {"program_id": program_id, "molecule_id": molecule_id, "batch_id": batch_id}})
    return templates.TemplateResponse("evidence/form.html", ctx)


@router.post("/evidence/new")
def create_evidence(
    program_id: int = Form(...),
    molecule_id: Optional[int] = Form(None),
    batch_id: Optional[int] = Form(None),
    domain: str = Form(...),
    evidence_type: str = Form(...),
    strength: int = Form(...),
    summary: str = Form(...),
    details: str = Form(""),
    citation_data_record_ids: str = Form(""),
    create_datarecord_inline: Optional[str] = Form(None),
    dr_domain: str = Form(""),
    dr_data_type: str = Form(""),
    dr_method: str = Form(""),
    dr_title: str = Form(""),
    dr_notes: str = Form(""),
    dr_run_date: str = Form(""),
    dr_params_json: str = Form("{}"),
    dr_results_json: str = Form("{}"),
    dr_files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    storage=Depends(get_storage_cfg),
):
    dr_uploads = []
    for uf in dr_files or []:
        if uf.filename:
            dr_uploads.append((uf.filename, uf.content_type or "application/octet-stream", uf.file.read()))

    try:
        ev = svc.create_evidence(
            db,
            program_id=program_id,
            molecule_id=molecule_id,
            batch_id=batch_id,
            domain=domain,
            evidence_type=evidence_type,
            strength=strength,
            summary=summary,
            details=details,
            citation_data_record_ids=citation_data_record_ids,
            create_datarecord_inline=create_datarecord_inline,
            dr_domain=dr_domain,
            dr_data_type=dr_data_type,
            dr_method=dr_method,
            dr_title=dr_title,
            dr_notes=dr_notes,
            dr_run_date=dr_run_date,
            dr_params_json=dr_params_json,
            dr_results_json=dr_results_json,
            dr_uploads=dr_uploads if dr_uploads else None,
            storage=storage,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return RedirectResponse(url=f"/evidence/{ev.id}", status_code=303)


@router.get("/evidence/{evidence_id}", response_class=HTMLResponse)
def evidence_detail(evidence_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    try:
        ctx = svc.get_evidence_detail(db, evidence_id)
    except KeyError:
        raise HTTPException(404)
    ctx["request"] = request
    return templates.TemplateResponse("evidence/detail.html", ctx)


@router.get("/evidence/{evidence_id}/edit", response_class=HTMLResponse)
def edit_evidence(evidence_id: int, request: Request, db: Session = Depends(get_db), rules_path=Depends(get_rules_path)):
    templates = get_templates(request)
    ev = svc.get_evidence(db, evidence_id)
    if not ev:
        raise HTTPException(404)
    ctx = svc.get_evidence_form_context(db, str(rules_path))
    citations = ctx.pop("domain_evidence_types", None)  # keep in ctx
    # restore
    ctx["domain_evidence_types"] = citations
    cited = [c.data_record_id for c in db.query(EvidenceCitation).filter(EvidenceCitation.evidence_id == evidence_id).all()]
    ctx.update({"request": request, "ev": ev, "prefill": {}, "cited_ids": cited})
    return templates.TemplateResponse("evidence/form.html", ctx)


@router.post("/evidence/{evidence_id}/edit")
def update_evidence(
    evidence_id: int,
    program_id: int = Form(...),
    molecule_id: Optional[int] = Form(None),
    batch_id: Optional[int] = Form(None),
    domain: str = Form(...),
    evidence_type: str = Form(...),
    strength: int = Form(...),
    summary: str = Form(...),
    details: str = Form(""),
    citation_data_record_ids: str = Form(""),
    reason: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        ev = svc.update_evidence(
            db,
            evidence_id=evidence_id,
            program_id=program_id,
            molecule_id=molecule_id,
            batch_id=batch_id,
            domain=domain,
            evidence_type=evidence_type,
            strength=strength,
            summary=summary,
            details=details,
            citation_data_record_ids=citation_data_record_ids,
            reason=reason,
        )
    except KeyError:
        raise HTTPException(404)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return RedirectResponse(url=f"/evidence/{ev.id}", status_code=303)
