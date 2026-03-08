from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from psi.services.legacy_yaml_compat import load_rules_legacy_yaml
from psi.services import data_records as svc
from psi.services import bulk_import as bulk_import_svc
from psi.core.models import ExperimentTask
from psi.web.deps import get_db, get_rules_path, get_storage_cfg, get_templates
from psi.web import ui_surfaces
from psi.web import handoff_context as handoff

router = APIRouter()


@router.get("/data", response_class=HTMLResponse)
def list_data(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    ctx = svc.list_data_records(db)
    ctx["request"] = request
    ctx["surface"] = ui_surfaces.data_registry_surface()
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
    source: Optional[str] = None,
    task_id: Optional[int] = None,
    db: Session = Depends(get_db),
    rules_path=Depends(get_rules_path),
):
    templates = get_templates(request)
    hctx = handoff.get_handoff_context(request)
    base = svc.get_form_context(db)
    rules = load_rules_legacy_yaml(str(rules_path))
    domains = list(rules["domains"].keys())
    domain_evidence_types = {}
    for d in domains:
        et = rules["domains"][d].get("evidence_types", [])
        domain_evidence_types[d] = list(et.keys()) if isinstance(et, dict) else list(et)

    task_ctx = None
    task = None
    if task_id is not None:
        task = db.get(ExperimentTask, int(task_id))
        if task is not None:
            task_ctx = {
                "task_id": int(task.id),
                "program_id": int(task.program_id),
                "molecule_id": int(task.molecule_id),
                "metric_key": str(task.metric_key or ""),
                "suggested_assay": str(task.suggested_assay or ""),
                "status": str(task.status or ""),
                "owner_text": str(task.owner_text or ""),
                "due_date": str(task.due_date or ""),
                "urgency": str(task.urgency or ""),
                "notes": str(task.notes or ""),
            }
            if program_id is None:
                program_id = int(task.program_id)
            if molecule_id is None:
                molecule_id = int(task.molecule_id)
            if not str(method or "").strip():
                method = str(task.suggested_assay or task.metric_key or "").strip() or None
            if not str(title or "").strip():
                mk = str(task.metric_key or "").strip()
                title = (f"Run {mk} experiment" if mk else "Run task-linked experiment")
            if not str(data_type or "").strip():
                data_type = "Binding"

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
            "task_id": task_id,
            "source": source,
        },
        "task_context": task_ctx,
        "handoff_source": str(source or ("task" if task_ctx is not None else "manual")).strip().lower(),
        "return_to": str(hctx.return_to or "").strip(),
        "surface": ui_surfaces.data_entry_surface(
            program_id=int(program_id) if program_id is not None else None,
            molecule_id=int(molecule_id) if molecule_id is not None else None,
            from_task=task_ctx is not None,
        ),
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
    task_id: Optional[int] = Form(None),
    return_to: str = Form(""),
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

    if task_id is not None:
        try:
            from psi.services import experiment_tasks as task_svc

            task_svc.link_task_to_data_record(db, task_id=int(task_id), data_record_id=int(rec.id))
            task_row = db.get(ExperimentTask, int(task_id))
            cur_status = str(task_row.status or "").strip().lower() if task_row is not None else ""
            if cur_status in {"planned", "blocked"}:
                task_svc.update_task_status(db, task_id=int(task_id), status="in_progress")
                cur_status = "in_progress"
            if cur_status != "done":
                task_svc.update_task_status(db, task_id=int(task_id), status="done")
        except KeyError:
            raise HTTPException(404, "ExperimentTask not found")
        except ValueError as e:
            raise HTTPException(400, str(e))

    target = handoff.build_return_url(
        f"/data/{rec.id}",
        return_to=str(return_to or "").strip(),
        captured=True,
        from_task=(task_id is not None),
        next_step=("evidence" if task_id is not None else ""),
    )
    return RedirectResponse(url=target, status_code=303)


@router.get("/data/{record_id}", response_class=HTMLResponse)
def detail_data(record_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    try:
        ctx = svc.get_data_record_detail(db, record_id)
    except KeyError:
        raise HTTPException(404)
    ctx["request"] = request
    rec = ctx.get("record")
    hctx = handoff.get_handoff_context(request)
    ctx["capture_notice"] = handoff.build_capture_notice(
        context=hctx,
        message=("" if str(hctx.next_step or "").strip().lower() == "evidence" else "Review this result and continue the scientific loop."),
    )
    ctx["surface"] = ui_surfaces.data_detail_surface(
        record_id=int(record_id),
        program_id=int(rec.program_id) if rec is not None and getattr(rec, "program_id", None) is not None else None,
        molecule_id=int(rec.molecule_id) if rec is not None and getattr(rec, "molecule_id", None) is not None else None,
    )
    return templates.TemplateResponse("data/detail.html", ctx)


@router.get("/data/{record_id}/edit", response_class=HTMLResponse)
def edit_data(record_id: int, request: Request, db: Session = Depends(get_db), rules_path=Depends(get_rules_path)):
    templates = get_templates(request)
    hctx = handoff.get_handoff_context(request)
    rec = svc.get_data_record(db, record_id)
    if not rec:
        raise HTTPException(404)
    base = svc.get_form_context(db)
    rules = load_rules_legacy_yaml(str(rules_path))
    domains = list(rules["domains"].keys())
    return templates.TemplateResponse(
        "data/form.html",
        {
            "request": request,
            "record": rec,
            **base,
            "domains": domains,
            "prefill": {},
            "task_context": None,
            "return_to": str(hctx.return_to or "").strip(),
            "surface": ui_surfaces.data_entry_surface(
                program_id=int(rec.program_id) if getattr(rec, "program_id", None) is not None else None,
                molecule_id=int(rec.molecule_id) if getattr(rec, "molecule_id", None) is not None else None,
                from_task=False,
            ),
        },
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
