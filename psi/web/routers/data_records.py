from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from psi.core.decision_engine import load_rules
from psi.services import data_records as svc
from psi.web.deps import get_db, get_rules_path, get_storage_cfg, get_templates

router = APIRouter()


@router.get("/data", response_class=HTMLResponse)
def list_data(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    ctx = svc.list_data_records(db)
    ctx["request"] = request
    return templates.TemplateResponse("data/list.html", ctx)


@router.get("/data/new", response_class=HTMLResponse)
def new_data(
    request: Request,
    program_id: Optional[int] = None,
    molecule_id: Optional[int] = None,
    batch_id: Optional[int] = None,
    domain: Optional[str] = None,
    data_type: Optional[str] = None,
    method: Optional[str] = None,
    title: Optional[str] = None,
    db: Session = Depends(get_db),
    rules_path=Depends(get_rules_path),
):
    templates = get_templates(request)
    base = svc.get_form_context(db)
    rules = load_rules(str(rules_path))
    domains = list(rules["domains"].keys())
    domain_evidence_types = {}
    for d in domains:
        et = rules["domains"][d].get("evidence_types", [])
        domain_evidence_types[d] = list(et.keys()) if isinstance(et, dict) else list(et)

    ctx = {
        **base,
        "request": request,
        "record": None,
        "selected_program_id": program_id,
        "selected_batch_id": batch_id,
        "domains": domains,
        "domain_evidence_types": domain_evidence_types,
        "prefill": {
            "program_id": program_id,
            "molecule_id": molecule_id,
            "batch_id": batch_id,
            "domain": domain,
            "data_type": data_type,
            "method": method,
            "title": title,
        },
    }
    return templates.TemplateResponse("data/form.html", ctx)


@router.post("/data/new")
def create_data(
    program_id: int = Form(...),
    molecule_id: Optional[int] = Form(None),
    batch_id: Optional[int] = Form(None),
    domain: str = Form(...),
    data_type: str = Form(...),
    method: str = Form(...),
    title: str = Form(...),
    notes: str = Form(""),
    run_date: str = Form(""),
    params_json: str = Form("{}"),
    results_json: str = Form("{}"),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    storage=Depends(get_storage_cfg),
):
    uploads = []
    for uf in files or []:
        if uf.filename:
            uploads.append((uf.filename, uf.content_type or "application/octet-stream", uf.file.read()))

    try:
        rec = svc.create_data_record(
            db,
            program_id=program_id,
            molecule_id=molecule_id,
            batch_id=batch_id,
            domain=domain,
            data_type=data_type,
            method=method,
            title=title,
            notes=notes,
            run_date=run_date,
            params_json=params_json,
            results_json=results_json,
            uploads=uploads if uploads else None,
            storage=storage,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return RedirectResponse(url=f"/data/{rec.id}", status_code=303)


@router.get("/data/{record_id}", response_class=HTMLResponse)
def detail_data(record_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    try:
        ctx = svc.get_data_record_detail(db, record_id)
    except KeyError:
        raise HTTPException(404)
    ctx["request"] = request
    return templates.TemplateResponse("data/detail.html", ctx)


@router.get("/data/{record_id}/edit", response_class=HTMLResponse)
def edit_data(record_id: int, request: Request, db: Session = Depends(get_db), rules_path=Depends(get_rules_path)):
    templates = get_templates(request)
    rec = svc.get_data_record(db, record_id)
    if not rec:
        raise HTTPException(404)
    base = svc.get_form_context(db)
    rules = load_rules(str(rules_path))
    domains = list(rules["domains"].keys())
    return templates.TemplateResponse(
        "data/form.html",
        {"request": request, "record": rec, **base, "domains": domains, "prefill": {}},
    )


@router.post("/data/{record_id}/edit")
def update_data(
    record_id: int,
    program_id: int = Form(...),
    molecule_id: Optional[int] = Form(None),
    batch_id: Optional[int] = Form(None),
    domain: str = Form(...),
    data_type: str = Form(...),
    method: str = Form(...),
    title: str = Form(...),
    notes: str = Form(""),
    run_date: str = Form(""),
    params_json: str = Form("{}"),
    results_json: str = Form("{}"),
    reason: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    storage=Depends(get_storage_cfg),
):
    uploads = []
    for uf in files or []:
        if uf.filename:
            uploads.append((uf.filename, uf.content_type or "application/octet-stream", uf.file.read()))

    try:
        rec = svc.update_data_record(
            db,
            record_id=record_id,
            program_id=program_id,
            molecule_id=molecule_id,
            batch_id=batch_id,
            domain=domain,
            data_type=data_type,
            method=method,
            title=title,
            notes=notes,
            run_date=run_date,
            params_json=params_json,
            results_json=results_json,
            uploads=uploads if uploads else None,
            storage=storage,
            reason=reason,
        )
    except KeyError:
        raise HTTPException(404)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return RedirectResponse(url=f"/data/{rec.id}", status_code=303)


@router.get("/api/data_records", response_class=JSONResponse)
def api_data_records(
    program_id: int,
    molecule_id: Optional[int] = None,
    batch_id: Optional[int] = None,
    q: str = "",
    db: Session = Depends(get_db),
):
    return svc.api_data_records(db, program_id=program_id, molecule_id=molecule_id, batch_id=batch_id, q=q)
