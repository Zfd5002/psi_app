from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .db import SessionLocal, ensure_schema
from .models import (
    Program,
    Molecule,
    Batch,
    DataRecord,
    Evidence,
    EvidenceCitation,
    File as StoredFile,
    FileLink,
    DecisionSnapshot,
    AuditEvent,
)
from .registry import REGISTRY, get_allowed_data_sources_for_evidence
from .decision_engine import load_rules, run_decision
from .utils import (
    now_utc,
    safe_filename,
    sha256_fileobj,
    json_dumps_compact,
    model_to_dict,
    diff_json,
)

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
RULES_PATH = BASE_DIR / "psi_rules" / "psirules-0.1.0.yml"

app = FastAPI(title="PSI - Preclinical Systems Intelligence", version="0.1.0")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "psi" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "psi" / "templates"))


# --- DB session dependency ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def _startup():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ensure_schema()


# --- Audit helper ---

def audit(db, entity_type: str, entity_id: int, action: str, before: dict | None, after: dict | None, reason: str | None = None):
    ev = AuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor="local-user",
        timestamp=now_utc(),
        before_json=json_dumps_compact(before) if before is not None else None,
        after_json=json_dumps_compact(after) if after is not None else None,
        diff_json=json_dumps_compact(diff_json(before, after)) if before is not None and after is not None else None,
        reason=reason,
    )
    db.add(ev)


# --- Home ---

@app.get("/", response_class=HTMLResponse)
def home(request: Request, db=Depends(get_db)):
    programs = db.query(Program).order_by(Program.created_at.desc()).limit(10).all()
    molecules = db.query(Molecule).order_by(Molecule.created_at.desc()).limit(10).all()
    batches = db.query(Batch).order_by(Batch.created_at.desc()).limit(10).all()
    return templates.TemplateResponse(
        "home.html",
        {"request": request, "programs": programs, "molecules": molecules, "batches": batches},
    )


# --- Registry API for dynamic forms ---

@app.get("/api/registry")
def api_registry():
    return REGISTRY


@app.get("/api/evidence_allowed_sources")
def api_allowed_sources(evidence_type: str):
    return get_allowed_data_sources_for_evidence(evidence_type)


@app.get("/api/data_records")
def api_data_records(program_id: int, molecule_id: int | None = None, batch_id: int | None = None, q: str = "", db=Depends(get_db)):
    """Lightweight API for the Evidence citation picker.

    Returns a list of data records in scope, with enough metadata to filter client-side.
    """
    query = db.query(DataRecord).filter(DataRecord.program_id == program_id)
    if batch_id:
        query = query.filter((DataRecord.batch_id == batch_id) | (DataRecord.batch_id.is_(None)))
    elif molecule_id:
        query = query.filter((DataRecord.molecule_id == molecule_id) | (DataRecord.molecule_id.is_(None)))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter((DataRecord.title.like(like)) | (DataRecord.notes.like(like)))
    rows = query.order_by(DataRecord.created_at.desc()).limit(200).all()
    return {
        "records": [
            {
                "id": r.id,
                "title": r.title,
                "domain": r.domain,
                "data_type": r.data_type,
                "method": r.method,
                "run_date": r.run_date,
                "batch_id": r.batch_id,
            }
            for r in rows
        ]
    }


# --- Programs ---

@app.get("/programs", response_class=HTMLResponse)
def programs_list(request: Request, db=Depends(get_db)):
    programs = db.query(Program).order_by(Program.created_at.desc()).all()
    return templates.TemplateResponse("programs/list.html", {"request": request, "programs": programs})


@app.get("/programs/new", response_class=HTMLResponse)
def programs_new(request: Request):
    return templates.TemplateResponse("programs/form.html", {"request": request, "program": None})


@app.post("/programs/new")
def programs_create(
    name: str = Form(...),
    description: str = Form(""),
    db=Depends(get_db),
):
    p = Program(name=name.strip(), description=description.strip(), created_at=now_utc(), updated_at=now_utc())
    db.add(p)
    db.commit()
    db.refresh(p)
    audit(db, "Program", p.id, "create", None, model_to_dict(p))
    db.commit()
    return RedirectResponse(url=f"/programs/{p.id}", status_code=303)


@app.get("/programs/{program_id}", response_class=HTMLResponse)
def programs_detail(program_id: int, request: Request, db=Depends(get_db)):
    p = db.get(Program, program_id)
    if not p:
        raise HTTPException(404)
    molecules = db.query(Molecule).filter(Molecule.program_id == program_id).order_by(Molecule.created_at.desc()).all()
    recent_batches = (
        db.query(Batch)
        .join(Molecule)
        .filter(Molecule.program_id == program_id)
        .order_by(Batch.created_at.desc())
        .limit(10)
        .all()
    )
    recent_data = (
        db.query(DataRecord)
        .filter(DataRecord.program_id == program_id)
        .order_by(DataRecord.created_at.desc())
        .limit(10)
        .all()
    )
    recent_evidence = (
        db.query(Evidence)
        .filter(Evidence.program_id == program_id)
        .order_by(Evidence.created_at.desc())
        .limit(10)
        .all()
    )
    recent_decisions = (
        db.query(DecisionSnapshot)
        .filter(DecisionSnapshot.program_id == program_id)
        .order_by(DecisionSnapshot.created_at.desc())
        .limit(10)
        .all()
    )
    audits = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_type == "Program", AuditEvent.entity_id == program_id)
        .order_by(AuditEvent.timestamp.desc())
        .all()
    )
    return templates.TemplateResponse(
        "programs/detail.html",
        {
            "request": request,
            "program": p,
            "molecules": molecules,
            "recent_batches": recent_batches,
            "recent_data": recent_data,
            "recent_evidence": recent_evidence,
            "recent_decisions": recent_decisions,
            "audits": audits,
        },
    )


@app.get("/programs/{program_id}/edit", response_class=HTMLResponse)
def programs_edit(program_id: int, request: Request, db=Depends(get_db)):
    p = db.get(Program, program_id)
    if not p:
        raise HTTPException(404)
    return templates.TemplateResponse("programs/form.html", {"request": request, "program": p})


@app.post("/programs/{program_id}/edit")
def programs_update(
    program_id: int,
    name: str = Form(...),
    description: str = Form(""),
    reason: str = Form(""),
    db=Depends(get_db),
):
    p = db.get(Program, program_id)
    if not p:
        raise HTTPException(404)
    before = model_to_dict(p)
    p.name = name.strip()
    p.description = description.strip()
    p.updated_at = now_utc()
    db.add(p)
    db.commit()
    audit(db, "Program", p.id, "update", before, model_to_dict(p), reason or None)
    db.commit()
    return RedirectResponse(url=f"/programs/{p.id}", status_code=303)


# --- Molecules ---

@app.get("/molecules", response_class=HTMLResponse)
def molecules_list(request: Request, db=Depends(get_db)):
    molecules = db.query(Molecule).order_by(Molecule.created_at.desc()).all()
    programs = db.query(Program).order_by(Program.name.asc()).all()
    return templates.TemplateResponse("molecules/list.html", {"request": request, "molecules": molecules, "programs": programs})


@app.get("/molecules/new", response_class=HTMLResponse)
def molecules_new(request: Request, db=Depends(get_db)):
    programs = db.query(Program).order_by(Program.name.asc()).all()
    return templates.TemplateResponse("molecules/form.html", {"request": request, "molecule": None, "programs": programs})


@app.post("/molecules/new")
def molecules_create(
    program_id: int = Form(...),
    primary_id: str = Form(...),
    title: str = Form(""),
    description: str = Form(""),
    sequences: str = Form(""),
    db=Depends(get_db),
):
    # Uniqueness is per (program_id, primary_id) at the DB layer.
    m = Molecule(
        program_id=program_id,
        primary_id=primary_id.strip(),
        title=title.strip() or None,
        description=description.strip() or None,
        sequences=sequences.strip() or None,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    audit(db, "Molecule", m.id, "create", None, model_to_dict(m))
    db.commit()
    return RedirectResponse(url=f"/molecules/{m.id}", status_code=303)


@app.get("/molecules/{molecule_id}", response_class=HTMLResponse)
def molecules_detail(molecule_id: int, request: Request, db=Depends(get_db)):
    m = db.get(Molecule, molecule_id)
    if not m:
        raise HTTPException(404)
    batches = db.query(Batch).filter(Batch.molecule_id == molecule_id).order_by(Batch.created_at.desc()).all()
    data_records = (
        db.query(DataRecord)
        .filter(DataRecord.molecule_id == molecule_id)
        .order_by(DataRecord.run_date.desc().nullslast(), DataRecord.created_at.desc())
        .limit(50)
        .all()
    )
    evidence = (
        db.query(Evidence)
        .filter(Evidence.molecule_id == molecule_id)
        .order_by(Evidence.created_at.desc())
        .limit(50)
        .all()
    )

    file_links = db.query(FileLink).filter(FileLink.entity_type == "Molecule", FileLink.entity_id == molecule_id).all()
    file_ids = [fl.file_id for fl in file_links]
    files = db.query(StoredFile).filter(StoredFile.id.in_(file_ids)).all() if file_ids else []
    files_by_id = {f.id: f for f in files}

    audits = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_type == "Molecule", AuditEvent.entity_id == molecule_id)
        .order_by(AuditEvent.timestamp.desc())
        .all()
    )
    return templates.TemplateResponse(
        "molecules/detail.html",
        {
            "request": request,
            "molecule": m,
            "batches": batches,
            "data_records": data_records,
            "evidence": evidence,
            "file_links": file_links,
            "files_by_id": files_by_id,
            "audits": audits,
        },
    )


@app.post("/molecules/{molecule_id}/files")
def molecule_add_files(molecule_id: int, files: list[UploadFile] = File(...), db=Depends(get_db)):
    m = db.get(Molecule, molecule_id)
    if not m:
        raise HTTPException(404)
    for uf in files:
        if not uf.filename:
            continue
        data = uf.file.read()
        sha = sha256_fileobj(data)
        safe = safe_filename(uf.filename)
        stored_name = f"{sha[:16]}_{safe}"
        path = UPLOAD_DIR / stored_name
        if not path.exists():
            path.write_bytes(data)
        f = StoredFile(
            stored_name=stored_name,
            original_name=uf.filename,
            size_bytes=len(data),
            mime=uf.content_type or "application/octet-stream",
            sha256=sha,
            created_at=now_utc(),
        )
        db.add(f)
        db.commit()
        db.refresh(f)
        link = FileLink(file_id=f.id, entity_type="Molecule", entity_id=molecule_id, created_at=now_utc())
        db.add(link)
        db.commit()
        audit(db, "FileLink", link.id, "create", None, model_to_dict(link), reason="attach to Molecule")
        db.commit()
    return RedirectResponse(url=f"/molecules/{molecule_id}", status_code=303)


@app.get("/molecules/{molecule_id}/edit", response_class=HTMLResponse)
def molecules_edit(molecule_id: int, request: Request, db=Depends(get_db)):
    m = db.get(Molecule, molecule_id)
    if not m:
        raise HTTPException(404)
    programs = db.query(Program).order_by(Program.name.asc()).all()
    return templates.TemplateResponse("molecules/form.html", {"request": request, "molecule": m, "programs": programs})


@app.post("/molecules/{molecule_id}/edit")
def molecules_update(
    molecule_id: int,
    program_id: int = Form(...),
    primary_id: str = Form(...),
    title: str = Form(""),
    description: str = Form(""),
    sequences: str = Form(""),
    reason: str = Form(""),
    db=Depends(get_db),
):
    m = db.get(Molecule, molecule_id)
    if not m:
        raise HTTPException(404)
    # DB enforces uniqueness per (program_id, primary_id)
    before = model_to_dict(m)
    m.program_id = program_id
    m.primary_id = primary_id.strip()
    m.title = title.strip() or None
    m.description = description.strip() or None
    m.sequences = sequences.strip() or None
    m.updated_at = now_utc()
    db.add(m)
    db.commit()
    audit(db, "Molecule", m.id, "update", before, model_to_dict(m), reason or None)
    db.commit()
    return RedirectResponse(url=f"/molecules/{m.id}", status_code=303)


# --- Batch helpers ---

def next_batch_id(db, molecule: Molecule) -> str:
    prefix = f"{molecule.primary_id}-"
    # find max suffix among existing
    existing = db.query(Batch).filter(Batch.molecule_id == molecule.id).all()
    max_n = 0
    for b in existing:
        if b.batch_id and b.batch_id.startswith(prefix):
            try:
                n = int(b.batch_id.split("-")[-1])
                max_n = max(max_n, n)
            except Exception:
                continue
    return f"{molecule.primary_id}-{max_n+1:03d}"


# --- Batches ---

@app.get("/batches", response_class=HTMLResponse)
def batches_list(request: Request, db=Depends(get_db)):
    batches = db.query(Batch).order_by(Batch.created_at.desc()).all()
    molecules = db.query(Molecule).order_by(Molecule.primary_id.asc()).all()
    return templates.TemplateResponse("batches/list.html", {"request": request, "batches": batches, "molecules": molecules})


@app.get("/batches/new", response_class=HTMLResponse)
def batches_new(request: Request, db=Depends(get_db)):
    molecules = db.query(Molecule).order_by(Molecule.primary_id.asc()).all()
    return templates.TemplateResponse("batches/form.html", {"request": request, "batch": None, "molecules": molecules, "suggested_batch_id": None})


@app.post("/batches/new")
def batches_create(
    molecule_id: int = Form(...),
    title: str = Form(""),
    expression_notes: str = Form(""),
    purification_notes: str = Form(""),
    db=Depends(get_db),
):
    mol = db.get(Molecule, molecule_id)
    if not mol:
        raise HTTPException(400, "Invalid molecule")
    batch_id = next_batch_id(db, mol)
    b = Batch(
        molecule_id=molecule_id,
        batch_id=batch_id,
        title=title.strip() or None,
        expression_notes=expression_notes.strip() or None,
        purification_notes=purification_notes.strip() or None,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    audit(db, "Batch", b.id, "create", None, model_to_dict(b))
    db.commit()
    return RedirectResponse(url=f"/batches/{b.id}", status_code=303)


@app.get("/batches/{batch_id}", response_class=HTMLResponse)
def batches_detail(batch_id: int, request: Request, tab: str = "data", db=Depends(get_db)):
    b = db.get(Batch, batch_id)
    if not b:
        raise HTTPException(404)
    mol = db.get(Molecule, b.molecule_id)

    data_records = (
        db.query(DataRecord)
        .filter(DataRecord.batch_id == batch_id)
        .order_by(DataRecord.run_date.desc().nullslast(), DataRecord.created_at.desc())
        .all()
    )
    evidence = (
        db.query(Evidence)
        .filter(Evidence.batch_id == batch_id)
        .order_by(Evidence.created_at.desc())
        .all()
    )
    file_links = (
        db.query(FileLink)
        .filter(FileLink.entity_type == "Batch", FileLink.entity_id == batch_id)
        .order_by(FileLink.created_at.desc())
        .all()
    )
    files = []
    if file_links:
        fids = [fl.file_id for fl in file_links]
        files = db.query(StoredFile).filter(StoredFile.id.in_(fids)).all()
        files_by_id = {f.id: f for f in files}
    else:
        files_by_id = {}

    audits = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_type == "Batch", AuditEvent.entity_id == batch_id)
        .order_by(AuditEvent.timestamp.desc())
        .all()
    )

    return templates.TemplateResponse(
        "batches/detail.html",
        {
            "request": request,
            "batch": b,
            "molecule": mol,
            "tab": tab,
            "data_records": data_records,
            "evidence": evidence,
            "file_links": file_links,
            "files_by_id": files_by_id,
            "audits": audits,
        },
    )


@app.post("/batches/{batch_id}/files")
def batch_add_files(batch_id: int, files: list[UploadFile] = File(...), db=Depends(get_db)):
    b = db.get(Batch, batch_id)
    if not b:
        raise HTTPException(404)
    for uf in files:
        if not uf.filename:
            continue
        data = uf.file.read()
        sha = sha256_fileobj(data)
        safe = safe_filename(uf.filename)
        stored_name = f"{sha[:16]}_{safe}"
        path = UPLOAD_DIR / stored_name
        if not path.exists():
            path.write_bytes(data)
        f = StoredFile(
            stored_name=stored_name,
            original_name=uf.filename,
            size_bytes=len(data),
            mime=uf.content_type or "application/octet-stream",
            sha256=sha,
            created_at=now_utc(),
        )
        db.add(f)
        db.commit()
        db.refresh(f)
        link = FileLink(file_id=f.id, entity_type="Batch", entity_id=batch_id, created_at=now_utc())
        db.add(link)
        db.commit()
        audit(db, "FileLink", link.id, "create", None, model_to_dict(link), reason="attach to Batch")
        db.commit()
    return RedirectResponse(url=f"/batches/{batch_id}?tab=files", status_code=303)


@app.get("/batches/{batch_id}/edit", response_class=HTMLResponse)
def batches_edit(batch_id: int, request: Request, db=Depends(get_db)):
    b = db.get(Batch, batch_id)
    if not b:
        raise HTTPException(404)
    molecules = db.query(Molecule).order_by(Molecule.primary_id.asc()).all()
    return templates.TemplateResponse("batches/form.html", {"request": request, "batch": b, "molecules": molecules, "suggested_batch_id": None})


@app.post("/batches/{batch_id}/edit")
def batches_update(
    batch_id: int,
    title: str = Form(""),
    expression_notes: str = Form(""),
    purification_notes: str = Form(""),
    reason: str = Form(""),
    db=Depends(get_db),
):
    b = db.get(Batch, batch_id)
    if not b:
        raise HTTPException(404)
    before = model_to_dict(b)
    b.title = title.strip() or None
    b.expression_notes = expression_notes.strip() or None
    b.purification_notes = purification_notes.strip() or None
    b.updated_at = now_utc()
    db.add(b)
    db.commit()
    audit(db, "Batch", b.id, "update", before, model_to_dict(b), reason or None)
    db.commit()
    return RedirectResponse(url=f"/batches/{b.id}", status_code=303)


# --- Data Records ---

@app.get("/data", response_class=HTMLResponse)
def data_list(request: Request, db=Depends(get_db)):
    records = db.query(DataRecord).order_by(DataRecord.created_at.desc()).limit(200).all()
    programs = db.query(Program).order_by(Program.name.asc()).all()
    molecules = db.query(Molecule).order_by(Molecule.primary_id.asc()).all()
    batches = db.query(Batch).order_by(Batch.created_at.desc()).all()
    return templates.TemplateResponse(
        "data/list.html",
        {"request": request, "records": records, "programs": programs, "molecules": molecules, "batches": batches},
    )


@app.get("/data/new", response_class=HTMLResponse)
def data_new(request: Request, program_id: Optional[int] = None, molecule_id: Optional[int] = None, batch_id: Optional[int] = None, db=Depends(get_db)):
    programs = db.query(Program).order_by(Program.name.asc()).all()
    molecules = db.query(Molecule).order_by(Molecule.primary_id.asc()).all()
    batches = db.query(Batch).order_by(Batch.created_at.desc()).all()
    rules = load_rules(RULES_PATH)
    domains = list(rules["domains"].keys())
    # YAML allows evidence_types to be a list (preferred) or a mapping (legacy).
    domain_evidence_types = {}
    for d in domains:
        et = rules["domains"][d].get("evidence_types", [])
        domain_evidence_types[d] = list(et.keys()) if isinstance(et, dict) else list(et)
    return templates.TemplateResponse(
        "data/form.html",
        {
            "request": request,
            "record": None,
            "programs": programs,
            "molecules": molecules,
            "batches": batches,
            "domains": domains,
            "domain_evidence_types": domain_evidence_types,
            "prefill": {"program_id": program_id, "molecule_id": molecule_id, "batch_id": batch_id},
        },
    )


@app.post("/data/new")
def data_create(
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
    db=Depends(get_db),
):
    # enforce batch requirement for experimental types
    if data_type not in REGISTRY.get("program_level_data_types", []) and not batch_id:
        raise HTTPException(400, "batch_id is required for this data type")

    rec = DataRecord(
        program_id=program_id,
        molecule_id=molecule_id,
        batch_id=batch_id,
        domain=domain,
        data_type=data_type,
        method=method,
        title=title.strip(),
        notes=notes.strip() or None,
        run_date=run_date.strip() or None,
        params_json=params_json.strip() or "{}",
        results_json=results_json.strip() or "{}",
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    # files
    if files:
        for uf in files:
            if not uf.filename:
                continue
            content_bytes = uf.file.read()
            sha = sha256_fileobj(content_bytes)
            safe = safe_filename(uf.filename)
            stored_name = f"{sha[:16]}_{safe}"
            path = UPLOAD_DIR / stored_name
            # write once
            if not path.exists():
                path.write_bytes(content_bytes)
            f = StoredFile(
                stored_name=stored_name,
                original_name=uf.filename,
                size_bytes=len(content_bytes),
                mime=uf.content_type or "application/octet-stream",
                sha256=sha,
                created_at=now_utc(),
            )
            db.add(f)
            db.commit()
            db.refresh(f)
            link = FileLink(file_id=f.id, entity_type="DataRecord", entity_id=rec.id, created_at=now_utc())
            db.add(link)
            db.commit()
            audit(db, "FileLink", link.id, "create", None, model_to_dict(link))
            db.commit()

    audit(db, "DataRecord", rec.id, "create", None, model_to_dict(rec))
    db.commit()
    return RedirectResponse(url=f"/data/{rec.id}", status_code=303)


def _load_json_field(s: str) -> dict[str, Any]:
    try:
        return json.loads(s) if s else {}
    except Exception:
        return {}


@app.get("/data/{record_id}", response_class=HTMLResponse)
def data_detail(record_id: int, request: Request, db=Depends(get_db)):
    rec = db.get(DataRecord, record_id)
    if not rec:
        raise HTTPException(404)
    citations = db.query(EvidenceCitation).filter(EvidenceCitation.data_record_id == record_id).all()
    ev_ids = [c.evidence_id for c in citations]
    evidence = db.query(Evidence).filter(Evidence.id.in_(ev_ids)).all() if ev_ids else []

    file_links = (
        db.query(FileLink)
        .filter(FileLink.entity_type == "DataRecord", FileLink.entity_id == record_id)
        .order_by(FileLink.created_at.desc())
        .all()
    )
    files = db.query(StoredFile).filter(StoredFile.id.in_([fl.file_id for fl in file_links])).all() if file_links else []
    files_by_id = {f.id: f for f in files}

    audits = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_type == "DataRecord", AuditEvent.entity_id == record_id)
        .order_by(AuditEvent.timestamp.desc())
        .all()
    )

    return templates.TemplateResponse(
        "data/detail.html",
        {
            "request": request,
            "record": rec,
            "params": _load_json_field(rec.params_json),
            "results": _load_json_field(rec.results_json),
            "evidence": evidence,
            "file_links": file_links,
            "files_by_id": files_by_id,
            "audits": audits,
        },
    )


@app.get("/data/{record_id}/edit", response_class=HTMLResponse)
def data_edit(record_id: int, request: Request, db=Depends(get_db)):
    rec = db.get(DataRecord, record_id)
    if not rec:
        raise HTTPException(404)
    programs = db.query(Program).order_by(Program.name.asc()).all()
    molecules = db.query(Molecule).order_by(Molecule.primary_id.asc()).all()
    batches = db.query(Batch).order_by(Batch.created_at.desc()).all()
    rules = load_rules(RULES_PATH)
    domains = list(rules["domains"].keys())
    return templates.TemplateResponse(
        "data/form.html",
        {"request": request, "record": rec, "programs": programs, "molecules": molecules, "batches": batches, "domains": domains, "prefill": {}},
    )


@app.post("/data/{record_id}/edit")
def data_update(
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
    db=Depends(get_db),
):
    rec = db.get(DataRecord, record_id)
    if not rec:
        raise HTTPException(404)
    if data_type not in REGISTRY.get("program_level_data_types", []) and not batch_id:
        raise HTTPException(400, "batch_id is required for this data type")
    before = model_to_dict(rec)
    rec.program_id = program_id
    rec.molecule_id = molecule_id
    rec.batch_id = batch_id
    rec.domain = domain
    rec.data_type = data_type
    rec.method = method
    rec.title = title.strip()
    rec.notes = notes.strip() or None
    rec.run_date = run_date.strip() or None
    rec.params_json = params_json.strip() or "{}"
    rec.results_json = results_json.strip() or "{}"
    rec.updated_at = now_utc()
    db.add(rec)
    db.commit()

    # add new files
    if files:
        for uf in files:
            if not uf.filename:
                continue
            content_bytes = uf.file.read()
            sha = sha256_fileobj(content_bytes)
            safe = safe_filename(uf.filename)
            stored_name = f"{sha[:16]}_{safe}"
            path = UPLOAD_DIR / stored_name
            if not path.exists():
                path.write_bytes(content_bytes)
            f = StoredFile(
                stored_name=stored_name,
                original_name=uf.filename,
                size_bytes=len(content_bytes),
                mime=uf.content_type or "application/octet-stream",
                sha256=sha,
                created_at=now_utc(),
            )
            db.add(f)
            db.commit()
            db.refresh(f)
            link = FileLink(file_id=f.id, entity_type="DataRecord", entity_id=rec.id, created_at=now_utc())
            db.add(link)
            db.commit()
            audit(db, "FileLink", link.id, "create", None, model_to_dict(link))
            db.commit()

    audit(db, "DataRecord", rec.id, "update", before, model_to_dict(rec), reason or None)
    db.commit()
    return RedirectResponse(url=f"/data/{rec.id}", status_code=303)


@app.post("/filelinks/{filelink_id}/delete")
def filelink_delete(filelink_id: int, db=Depends(get_db)):
    link = db.get(FileLink, filelink_id)
    if not link:
        raise HTTPException(404)
    before = model_to_dict(link)
    db.delete(link)
    db.commit()
    audit(db, "FileLink", filelink_id, "delete", before, None)
    db.commit()

    # orphan cleanup (simple)
    remaining = db.query(FileLink).filter(FileLink.file_id == link.file_id).count()
    if remaining == 0:
        f = db.get(StoredFile, link.file_id)
        if f:
            path = UPLOAD_DIR / f.stored_name
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass
            before_f = model_to_dict(f)
            db.delete(f)
            db.commit()
            audit(db, "File", link.file_id, "delete", before_f, None, reason="orphan cleanup")
            db.commit()

    # redirect back
    return RedirectResponse(url="/data", status_code=303)


@app.get("/files/{file_id}/download")
def file_download(file_id: int, db=Depends(get_db)):
    f = db.get(StoredFile, file_id)
    if not f:
        raise HTTPException(404)
    path = UPLOAD_DIR / f.stored_name
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(str(path), media_type=f.mime, filename=f.original_name)


# --- Evidence ---

@app.get("/evidence", response_class=HTMLResponse)
def evidence_list(request: Request, db=Depends(get_db)):
    ev = db.query(Evidence).order_by(Evidence.created_at.desc()).limit(200).all()
    programs = db.query(Program).order_by(Program.name.asc()).all()
    molecules = db.query(Molecule).order_by(Molecule.primary_id.asc()).all()
    batches = db.query(Batch).order_by(Batch.created_at.desc()).all()
    rules = load_rules(RULES_PATH)
    domains = list(rules["domains"].keys())
    return templates.TemplateResponse(
        "evidence/list.html",
        {"request": request, "evidence": ev, "programs": programs, "molecules": molecules, "batches": batches, "domains": domains},
    )


@app.get("/evidence/new", response_class=HTMLResponse)
def evidence_new(request: Request, program_id: Optional[int] = None, molecule_id: Optional[int] = None, batch_id: Optional[int] = None, db=Depends(get_db)):
    programs = db.query(Program).order_by(Program.name.asc()).all()
    molecules = db.query(Molecule).order_by(Molecule.primary_id.asc()).all()
    batches = db.query(Batch).order_by(Batch.created_at.desc()).all()
    rules = load_rules(RULES_PATH)
    domains = list(rules["domains"].keys())
    # YAML allows evidence_types to be a list (preferred) or a mapping (legacy).
    domain_evidence_types = {}
    for d in domains:
        et = rules["domains"][d].get("evidence_types", [])
        domain_evidence_types[d] = list(et.keys()) if isinstance(et, dict) else list(et)
    return templates.TemplateResponse(
        "evidence/form.html",
        {
            "request": request,
            "ev": None,
            "programs": programs,
            "molecules": molecules,
            "batches": batches,
            "domains": domains,
            "domain_evidence_types": domain_evidence_types,
            "prefill": {"program_id": program_id, "molecule_id": molecule_id, "batch_id": batch_id},
        },
    )


@app.post("/evidence/new")
def evidence_create(
    program_id: int = Form(...),
    molecule_id: Optional[int] = Form(None),
    batch_id: Optional[int] = Form(None),
    domain: str = Form(...),
    evidence_type: str = Form(...),
    strength: int = Form(...),
    summary: str = Form(...),
    details: str = Form(""),
    citation_data_record_ids: str = Form(""),
    # optional inline datarecord creation
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
    db=Depends(get_db),
):
    # citations required
    cited_ids: list[int] = []
    if citation_data_record_ids.strip():
        try:
            cited_ids = [int(x) for x in citation_data_record_ids.split(",") if x.strip()]
        except Exception:
            cited_ids = []

    # inline record if requested
    if create_datarecord_inline:
        if dr_data_type not in REGISTRY.get("program_level_data_types", []) and not batch_id:
            raise HTTPException(400, "batch_id is required to create a lab data record")
        rec = DataRecord(
            program_id=program_id,
            molecule_id=molecule_id,
            batch_id=batch_id,
            domain=dr_domain or domain,
            data_type=dr_data_type,
            method=dr_method,
            title=(dr_title or "Inline data record").strip(),
            notes=dr_notes.strip() or None,
            run_date=dr_run_date.strip() or None,
            params_json=dr_params_json.strip() or "{}",
            results_json=dr_results_json.strip() or "{}",
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        audit(db, "DataRecord", rec.id, "create", None, model_to_dict(rec), reason="created inline from Evidence")
        db.commit()
        # attach files
        for uf in dr_files:
            if not uf.filename:
                continue
            content_bytes = uf.file.read()
            sha = sha256_fileobj(content_bytes)
            safe = safe_filename(uf.filename)
            stored_name = f"{sha[:16]}_{safe}"
            path = UPLOAD_DIR / stored_name
            if not path.exists():
                path.write_bytes(content_bytes)
            f = StoredFile(
                stored_name=stored_name,
                original_name=uf.filename,
                size_bytes=len(content_bytes),
                mime=uf.content_type or "application/octet-stream",
                sha256=sha,
                created_at=now_utc(),
            )
            db.add(f)
            db.commit()
            db.refresh(f)
            link = FileLink(file_id=f.id, entity_type="DataRecord", entity_id=rec.id, created_at=now_utc())
            db.add(link)
            db.commit()
            audit(db, "FileLink", link.id, "create", None, model_to_dict(link), reason="inline Evidence")
            db.commit()
        cited_ids.append(rec.id)

    if not cited_ids:
        raise HTTPException(400, "Evidence must cite at least one Data Record")

    # restrict citations by evidence_type mapping
    allowed = get_allowed_data_sources_for_evidence(evidence_type)
    if allowed.get("allowed"):
        allowed_pairs = set((d["data_type"], d["method"]) for d in allowed["allowed"])
        for rid in cited_ids:
            dr = db.get(DataRecord, rid)
            if not dr:
                raise HTTPException(400, f"Invalid DataRecord id {rid}")
            if (dr.data_type, dr.method) not in allowed_pairs:
                raise HTTPException(400, f"DataRecord {rid} ({dr.data_type}/{dr.method}) cannot be cited for {evidence_type}")

    ev = Evidence(
        program_id=program_id,
        molecule_id=molecule_id,
        batch_id=batch_id,
        domain=domain,
        evidence_type=evidence_type,
        strength=int(strength),
        summary=summary.strip(),
        details=details.strip() or None,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)

    for rid in cited_ids:
        c = EvidenceCitation(evidence_id=ev.id, data_record_id=rid)
        db.add(c)
    db.commit()

    audit(db, "Evidence", ev.id, "create", None, model_to_dict(ev))
    db.commit()

    return RedirectResponse(url=f"/evidence/{ev.id}", status_code=303)


@app.get("/evidence/{evidence_id}", response_class=HTMLResponse)
def evidence_detail(evidence_id: int, request: Request, db=Depends(get_db)):
    ev = db.get(Evidence, evidence_id)
    if not ev:
        raise HTTPException(404)
    citations = db.query(EvidenceCitation).filter(EvidenceCitation.evidence_id == evidence_id).all()
    dr_ids = [c.data_record_id for c in citations]
    data_records = db.query(DataRecord).filter(DataRecord.id.in_(dr_ids)).all() if dr_ids else []

    audits = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_type == "Evidence", AuditEvent.entity_id == evidence_id)
        .order_by(AuditEvent.timestamp.desc())
        .all()
    )

    return templates.TemplateResponse(
        "evidence/detail.html",
        {"request": request, "ev": ev, "citations": citations, "data_records": data_records, "audits": audits},
    )


@app.get("/evidence/{evidence_id}/edit", response_class=HTMLResponse)
def evidence_edit(evidence_id: int, request: Request, db=Depends(get_db)):
    ev = db.get(Evidence, evidence_id)
    if not ev:
        raise HTTPException(404)
    programs = db.query(Program).order_by(Program.name.asc()).all()
    molecules = db.query(Molecule).order_by(Molecule.primary_id.asc()).all()
    batches = db.query(Batch).order_by(Batch.created_at.desc()).all()
    rules = load_rules(RULES_PATH)
    domains = list(rules["domains"].keys())
    # YAML allows evidence_types to be a list (preferred) or a mapping (legacy).
    domain_evidence_types = {}
    for d in domains:
        et = rules["domains"][d].get("evidence_types", [])
        domain_evidence_types[d] = list(et.keys()) if isinstance(et, dict) else list(et)
    citations = db.query(EvidenceCitation).filter(EvidenceCitation.evidence_id == evidence_id).all()
    cited_ids = [c.data_record_id for c in citations]
    return templates.TemplateResponse(
        "evidence/form.html",
        {
            "request": request,
            "ev": ev,
            "programs": programs,
            "molecules": molecules,
            "batches": batches,
            "domains": domains,
            "domain_evidence_types": domain_evidence_types,
            "prefill": {},
            "cited_ids": cited_ids,
        },
    )


@app.post("/evidence/{evidence_id}/edit")
def evidence_update(
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
    db=Depends(get_db),
):
    ev = db.get(Evidence, evidence_id)
    if not ev:
        raise HTTPException(404)

    cited_ids: list[int] = []
    if citation_data_record_ids.strip():
        try:
            cited_ids = [int(x) for x in citation_data_record_ids.split(",") if x.strip()]
        except Exception:
            cited_ids = []
    if not cited_ids:
        raise HTTPException(400, "Evidence must cite at least one Data Record")

    allowed = get_allowed_data_sources_for_evidence(evidence_type)
    if allowed.get("allowed"):
        allowed_pairs = set((d["data_type"], d["method"]) for d in allowed["allowed"])
        for rid in cited_ids:
            dr = db.get(DataRecord, rid)
            if not dr:
                raise HTTPException(400, f"Invalid DataRecord id {rid}")
            if (dr.data_type, dr.method) not in allowed_pairs:
                raise HTTPException(400, f"DataRecord {rid} ({dr.data_type}/{dr.method}) cannot be cited for {evidence_type}")

    before = model_to_dict(ev)
    ev.program_id = program_id
    ev.molecule_id = molecule_id
    ev.batch_id = batch_id
    ev.domain = domain
    ev.evidence_type = evidence_type
    ev.strength = int(strength)
    ev.summary = summary.strip()
    ev.details = details.strip() or None
    ev.updated_at = now_utc()

    # replace citations
    db.query(EvidenceCitation).filter(EvidenceCitation.evidence_id == evidence_id).delete()
    for rid in cited_ids:
        db.add(EvidenceCitation(evidence_id=evidence_id, data_record_id=rid))

    db.add(ev)
    db.commit()

    audit(db, "Evidence", ev.id, "update", before, model_to_dict(ev), reason or None)
    db.commit()

    return RedirectResponse(url=f"/evidence/{ev.id}", status_code=303)


# --- Decisions ---

@app.get("/decisions", response_class=HTMLResponse)
def decisions_list(request: Request, db=Depends(get_db)):
    snaps = db.query(DecisionSnapshot).order_by(DecisionSnapshot.created_at.desc()).limit(200).all()
    return templates.TemplateResponse("decisions/list.html", {"request": request, "snaps": snaps})


@app.get("/decisions/new", response_class=HTMLResponse)
def decisions_new(request: Request, db=Depends(get_db)):
    programs = db.query(Program).order_by(Program.name.asc()).all()
    molecules = db.query(Molecule).order_by(Molecule.primary_id.asc()).all()
    batches = db.query(Batch).order_by(Batch.created_at.desc()).all()
    rules = load_rules(RULES_PATH)
    decision_keys = list(rules.get("decisions", {}).keys())
    return templates.TemplateResponse(
        "decisions/new.html",
        {"request": request, "programs": programs, "molecules": molecules, "batches": batches, "decision_keys": decision_keys, "rules_version": rules.get("version")},
    )


@app.post("/decisions/new")
def decisions_run(
    program_id: int = Form(...),
    molecule_id: Optional[int] = Form(None),
    batch_id: Optional[int] = Form(None),
    decision_key: str = Form(...),
    assumptions_ack: Optional[str] = Form(None),
    db=Depends(get_db),
):
    if not assumptions_ack:
        raise HTTPException(400, "Must acknowledge assumptions")

    rules = load_rules(RULES_PATH)
    if decision_key not in rules.get("decisions", {}):
        raise HTTPException(400, "Invalid decision")

    # Evidence scoping:
    # - Always include program-level (molecule_id NULL, batch_id NULL)
    # - If molecule specified, include molecule-level (molecule_id == x, batch_id NULL)
    # - If batch specified, include batch-level (batch_id == x)
    q = db.query(Evidence).filter(Evidence.program_id == program_id)
    if batch_id:
        q = q.filter(
            (Evidence.molecule_id.is_(None) & Evidence.batch_id.is_(None))
            | ((Evidence.molecule_id == molecule_id) & Evidence.batch_id.is_(None))
            | (Evidence.batch_id == batch_id)
        )
    elif molecule_id:
        q = q.filter(
            (Evidence.molecule_id.is_(None) & Evidence.batch_id.is_(None))
            | ((Evidence.molecule_id == molecule_id) & Evidence.batch_id.is_(None))
        )
    else:
        q = q.filter(Evidence.molecule_id.is_(None), Evidence.batch_id.is_(None))

    evidence = q.all()

    result = run_decision(rules, decision_key, evidence)

    snap = DecisionSnapshot(
        program_id=program_id,
        molecule_id=molecule_id,
        batch_id=batch_id,
        decision_key=decision_key,
        rules_version=str(rules.get("version")),
        inputs_json=json_dumps_compact({"program_id": program_id, "molecule_id": molecule_id, "batch_id": batch_id, "decision_key": decision_key}),
        outputs_json=json_dumps_compact(result),
        evidence_ids_json=json_dumps_compact(result.get("evidence_ids_used", [])),
        created_at=now_utc(),
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    audit(db, "DecisionSnapshot", snap.id, "create", None, model_to_dict(snap))
    db.commit()

    return RedirectResponse(url=f"/decisions/{snap.id}", status_code=303)


@app.get("/decisions/{snap_id}", response_class=HTMLResponse)
def decisions_detail(snap_id: int, request: Request, db=Depends(get_db), print_view: int = 0):
    snap = db.get(DecisionSnapshot, snap_id)
    if not snap:
        raise HTTPException(404)
    output = json.loads(snap.outputs_json)
    evidence_ids = output.get("evidence_ids_used", [])
    evidence = db.query(Evidence).filter(Evidence.id.in_(evidence_ids)).all() if evidence_ids else []

    # evidence -> data records -> files
    citations = db.query(EvidenceCitation).filter(EvidenceCitation.evidence_id.in_(evidence_ids)).all() if evidence_ids else []
    dr_ids = sorted({c.data_record_id for c in citations})
    data_records = db.query(DataRecord).filter(DataRecord.id.in_(dr_ids)).all() if dr_ids else []

    dr_file_links = db.query(FileLink).filter(FileLink.entity_type == "DataRecord", FileLink.entity_id.in_(dr_ids)).all() if dr_ids else []
    file_ids = sorted({fl.file_id for fl in dr_file_links})
    files = db.query(StoredFile).filter(StoredFile.id.in_(file_ids)).all() if file_ids else []

    files_by_id = {f.id: f for f in files}
    file_links_by_dr = {}
    for fl in dr_file_links:
        file_links_by_dr.setdefault(fl.entity_id, []).append(fl)

    tmpl = "decisions/detail_print.html" if print_view else "decisions/detail.html"
    return templates.TemplateResponse(
        tmpl,
        {
            "request": request,
            "snap": snap,
            "output": output,
            "evidence": evidence,
            "citations": citations,
            "data_records": data_records,
            "files_by_id": files_by_id,
            "file_links_by_dr": file_links_by_dr,
        },
    )


# --- Search ---

@app.get("/search", response_class=HTMLResponse)
def search(request: Request, q: str = "", db=Depends(get_db)):
    q = (q or "").strip()
    like = f"%{q}%"

    records = []
    evidence = []
    files = []
    if q:
        records = (
            db.query(DataRecord)
            .filter((DataRecord.title.like(like)) | (DataRecord.notes.like(like)) | (DataRecord.params_json.like(like)) | (DataRecord.results_json.like(like)))
            .order_by(DataRecord.created_at.desc())
            .limit(50)
            .all()
        )
        evidence = (
            db.query(Evidence)
            .filter((Evidence.summary.like(like)) | (Evidence.details.like(like)) | (Evidence.evidence_type.like(like)))
            .order_by(Evidence.created_at.desc())
            .limit(50)
            .all()
        )
        files = (
            db.query(StoredFile)
            .filter((StoredFile.original_name.like(like)) | (StoredFile.sha256.like(like)))
            .order_by(StoredFile.created_at.desc())
            .limit(50)
            .all()
        )

    return templates.TemplateResponse("search.html", {"request": request, "q": q, "records": records, "evidence": evidence, "files": files})
