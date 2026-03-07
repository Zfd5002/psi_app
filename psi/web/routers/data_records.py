from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from psi.services.legacy_yaml_compat import load_rules_legacy_yaml
from psi.services import data_records as svc
from psi.services import bulk_import as bulk_import_svc
from psi.web.deps import get_db, get_rules_path, get_storage_cfg, get_templates

router = APIRouter()


@router.get("/data", response_class=HTMLResponse)
def list_data(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    ctx = svc.list_data_records(db)
    ctx["request"] = request
    return templates.TemplateResponse("data/list.html", ctx)


@router.get("/data/bulk-import", response_class=HTMLResponse)
def bulk_import_page(request: Request):
    templates = get_templates(request)
    return templates.TemplateResponse(
        "data/bulk_import.html",
        {
            "request": request,
            "pasted_text": "",
            "validated_rows": [],
            "errors": [],
            "validated_json": "[]",
            "imported_count": None,
        },
    )


@router.post("/data/bulk-import", response_class=HTMLResponse)
def bulk_import_submit(
    request: Request,
    action: str = Form("validate"),
    pasted_text: str = Form(""),
    validated_json: str = Form("[]"),
    db: Session = Depends(get_db),
):
    templates = get_templates(request)
    action_key = str(action or "validate").strip().lower()
    parsed_rows = []
    validated_rows = []
    errors = []
    imported_count: int | None = None
    message = ""
    if action_key == "import":
        try:
            validated_rows = [x for x in json.loads(validated_json or "[]") if isinstance(x, dict)]
        except Exception:
            validated_rows = []
        for row in validated_rows:
            metric_key = str(row.get("metric_key") or "")
            value_num = row.get("value_num")
            unit = str(row.get("unit") or "")
            svc.create_data_record(
                db,
                program_id=int(row.get("program_id")),
                molecule_id=int(row.get("molecule_id")),
                batch_id=int(row.get("batch_id")),
                domain=str(row.get("domain") or "Other"),
                data_type=str(row.get("data_type") or "Other"),
                method=str(row.get("method") or metric_key or "Unknown"),
                title=str(row.get("title") or f"Bulk import {metric_key}"),
                notes="bulk import",
                run_date="",
                params_json={},
                results_json={metric_key: value_num, "unit": unit} if metric_key else {"value_num": value_num, "unit": unit},
            )
        imported_count = len(validated_rows)
        message = f"Imported {imported_count} rows."
    else:
        try:
            parsed_rows = bulk_import_svc.parse_bulk_import_rows(pasted_text)
            res = bulk_import_svc.validate_bulk_import_rows(db, parsed_rows=parsed_rows)
            validated_rows = list(res.get("validated_rows") or [])
            errors = list(res.get("errors") or [])
            if not validated_rows and not errors:
                message = "No rows detected."
        except ValueError as e:
            errors = [{"row_num": 1, "error": str(e)}]

    return templates.TemplateResponse(
        "data/bulk_import.html",
        {
            "request": request,
            "pasted_text": pasted_text,
            "validated_rows": validated_rows,
            "errors": errors,
            "validated_json": json.dumps(validated_rows, sort_keys=True),
            "imported_count": imported_count,
            "message": message,
        },
    )


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
    rules = load_rules_legacy_yaml(str(rules_path))
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
    rules = load_rules_legacy_yaml(str(rules_path))
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
    action_intent: str = Form("save"),
    actor: str = Form("scientist"),
    qc_note: str = Form(""),
    return_to: str = Form(""),
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

    intent = str(action_intent or "save").strip().lower()
    if intent in {"approve", "reject"}:
        try:
            svc.apply_bulk_qc_action_for_record(
                db,
                record_id=int(rec.id),
                action=intent,
                actor=(actor or "scientist"),
                note=(qc_note or None),
            )
        except ValueError as e:
            raise HTTPException(400, str(e))
        except KeyError:
            raise HTTPException(404)

    target = str(return_to or "").strip() or f"/data/{rec.id}"
    return RedirectResponse(url=target, status_code=303)


@router.get("/api/data_records", response_class=JSONResponse)
def api_data_records(
    program_id: int,
    molecule_id: Optional[int] = None,
    batch_id: Optional[int] = None,
    q: str = "",
    db: Session = Depends(get_db),
):
    return svc.api_data_records(db, program_id=program_id, molecule_id=molecule_id, batch_id=batch_id, q=q)


@router.post("/data/{record_id}/qc/approve", name="approve_record_qc")
@router.post("/data-records/{record_id}/qc/approve", name="approve_record_qc_alias")
def approve_record_qc(
    record_id: int,
    actor: str = Form("scientist"),
    note: str = Form(""),
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        svc.apply_bulk_qc_action_for_record(
            db,
            record_id=int(record_id),
            action="approve",
            actor=(actor or "scientist"),
            note=(note or None),
        )
    except KeyError:
        raise HTTPException(404)
    except ValueError as e:
        raise HTTPException(400, str(e))
    target = str(redirect_to or "").strip() or f"/data/{int(record_id)}"
    return RedirectResponse(url=target, status_code=303)


@router.post("/data/{record_id}/qc/reject", name="reject_record_qc")
@router.post("/data-records/{record_id}/qc/reject", name="reject_record_qc_alias")
def reject_record_qc(
    record_id: int,
    actor: str = Form("scientist"),
    note: str = Form(""),
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        svc.apply_bulk_qc_action_for_record(
            db,
            record_id=int(record_id),
            action="reject",
            actor=(actor or "scientist"),
            note=(note or None),
        )
    except KeyError:
        raise HTTPException(404)
    except ValueError as e:
        raise HTTPException(400, str(e))
    target = str(redirect_to or "").strip() or f"/data/{int(record_id)}"
    return RedirectResponse(url=target, status_code=303)
