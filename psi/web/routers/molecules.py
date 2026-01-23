from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from psi.web.deps import get_db, get_storage_cfg, get_templates
from psi.services import molecules as svc
from psi.services.computed import run_computed_properties, run_immunogenicity_mhci
from psi.services.numbering import trigger_numbering_for_molecule
from psi.services.domains import extract_domains_for_molecule, upsert_user_domain_instance
from psi.services import files as file_svc
from psi.core.models import MoleculeComponent

router = APIRouter()


@router.post("/molecules/{molecule_id}/computed/recompute")
def recompute_fast_properties(molecule_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    m = svc.get_molecule(db, molecule_id)
    if not m:
        raise HTTPException(404)
    # Always run in background; consistent UX.
    background_tasks.add_task(svc._background_compute, molecule_id, "manual_recompute")
    return RedirectResponse(url=f"/molecules/{molecule_id}", status_code=303)


@router.post("/molecules/{molecule_id}/numbering")
def run_numbering(molecule_id: int, background_tasks: BackgroundTasks, scheme: str = Form("kabat"), db: Session = Depends(get_db)):
    m = svc.get_molecule(db, molecule_id)
    if not m:
        raise HTTPException(404)
    # Run in background: compute missing artifacts.
    def _bg():
        from psi.core.db import SessionLocal

        s = SessionLocal()
        try:
            trigger_numbering_for_molecule(s, molecule_id=molecule_id, scheme=scheme, force=True)
        finally:
            s.close()

    background_tasks.add_task(_bg)
    return RedirectResponse(url=f"/molecules/{molecule_id}?scheme={scheme}", status_code=303)


@router.post("/molecules/{molecule_id}/immunogenicity/mhci")
def run_immunogenicity_mhci_scan(
    molecule_id: int,
    background_tasks: BackgroundTasks,
    allele: str = Form("HLA-A0201"),
    min_len: int = Form(8),
    max_len: int = Form(11),
    binder_threshold_nm: float = Form(500.0),
    db: Session = Depends(get_db),
):
    """Manual-only immunogenicity triage scan.

    Runs in a background session and stores results in property_runs/property_values
    (compute_tier=IMMUNO). This is off by default and only executes when a user clicks.
    """

    m = svc.get_molecule(db, molecule_id)
    if not m:
        raise HTTPException(404)

    def _bg():
        from psi.core.db import SessionLocal

        s = SessionLocal()
        try:
            run_immunogenicity_mhci(
                s,
                molecule_id=molecule_id,
                trigger_reason="manual_immunogenicity",
                allele=str(allele or "HLA-A0201").strip() or "HLA-A0201",
                min_len=int(min_len),
                max_len=int(max_len),
                binder_threshold_nm=float(binder_threshold_nm),
            )
        finally:
            s.close()

    background_tasks.add_task(_bg)
    return RedirectResponse(url=f"/molecules/{molecule_id}#computed", status_code=303)


@router.post("/molecules/{molecule_id}/domains/recompute")
def recompute_domains(molecule_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    m = svc.get_molecule(db, molecule_id)
    if not m:
        raise HTTPException(404)

    def _bg():
        from psi.core.db import SessionLocal

        s = SessionLocal()
        try:
            extract_domains_for_molecule(s, molecule_id)
        finally:
            s.close()

    background_tasks.add_task(_bg)
    return RedirectResponse(url=f"/molecules/{molecule_id}#domains", status_code=303)


@router.post("/molecules/{molecule_id}/domains")
async def create_domain_label(molecule_id: int, request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())
    component_id = int(form.get("component_id"))
    domain_type = str(form.get("domain_type") or "").strip()
    start_idx = int(form.get("start_idx"))
    end_idx = int(form.get("end_idx"))
    if not domain_type:
        raise HTTPException(400)
    try:
        upsert_user_domain_instance(db, molecule_id=molecule_id, component_id=component_id, domain_type=domain_type, start_idx=start_idx, end_idx=end_idx)
    except KeyError:
        raise HTTPException(404)
    except Exception:
        raise HTTPException(400)
    return RedirectResponse(url=f"/molecules/{molecule_id}#domains", status_code=303)


@router.get("/molecules", response_class=HTMLResponse)
def list_molecules(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    molecules, programs = svc.list_molecules(db)
    return templates.TemplateResponse("molecules/list.html", {"request": request, "molecules": molecules, "programs": programs})


@router.get("/molecules/new", response_class=HTMLResponse)
def new_molecule(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    _, programs = svc.list_molecules(db)
    return templates.TemplateResponse("molecules/form.html", {"request": request, "molecule": None, "programs": programs})


def _extract_components_from_form(form: dict) -> dict[str, str]:
    roles = ["HC1", "LC1", "HC2", "LC2", "VH", "VL", "linker", "fusion"]
    comps = {}
    for role in roles:
        val = (form.get(role) or "").strip()
        if val:
            comps[role] = val
    return comps


def _parse_fasta_bundle(bundle: str) -> dict[str, str]:
    """Best-effort assignment from a multi-FASTA blob.

    Headers like >HC1, >VH, etc. are used for mapping.
    """
    from psi.core.fasta import parse_fasta

    out: dict[str, str] = {}
    if not bundle:
        return out
    for r in parse_fasta(bundle):
        h = r.header.strip().upper().replace(" ", "")
        for role in ["HC1", "HC2", "LC1", "LC2", "VH", "VL", "LINKER", "FUSION"]:
            if h == role or h.endswith(role) or h.startswith(role):
                out[role.replace("LINKER", "linker").replace("FUSION", "fusion")] = r.sequence
                break
    # normalize role casing
    norm: dict[str, str] = {}
    for k, v in out.items():
        if k.lower() in ("linker", "fusion"):
            norm[k.lower()] = v
        else:
            norm[k.upper()] = v
    return norm


@router.post("/molecules/new")
async def create_molecule(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    form = dict(await request.form())
    program_id = int(form.get("program_id"))
    primary_id = str(form.get("primary_id") or "")
    title = str(form.get("title") or "")
    description = str(form.get("description") or "")
    sequences = str(form.get("sequences") or "")
    molecule_format = (form.get("molecule_format") or "").strip() or None
    description_user = str(form.get("description_user") or "")
    heavy_compute_enabled = 1 if str(form.get("heavy_compute_enabled") or "") in ("1", "on", "true", "True") else 0
    bundle = str(form.get("fasta_bundle") or "")

    comps = _extract_components_from_form(form)
    if bundle and not comps:
        comps = _parse_fasta_bundle(bundle)

    m = svc.create_molecule(
        db,
        program_id=program_id,
        primary_id=primary_id,
        title=title,
        description=description,
        sequences=sequences,
        molecule_format=molecule_format,
        description_user=description_user,
        heavy_compute_enabled=heavy_compute_enabled,
        components=comps if comps else None,
        background_tasks=background_tasks,
    )
    return RedirectResponse(url=f"/molecules/{m.id}", status_code=303)


@router.get("/molecules/{molecule_id}", response_class=HTMLResponse)
def molecule_detail(molecule_id: int, request: Request, tab: str = "overview", batch_id: int | None = None, db: Session = Depends(get_db)):
    templates = get_templates(request)
    try:
        mm = request.query_params.get("pdl1_mm", "")
        try:
            pdl1_mm = int(mm) if str(mm).strip() != "" else 0
        except Exception:
            pdl1_mm = 0
        # Clamp to a small, safe range for UI.
        if pdl1_mm < 0:
            pdl1_mm = 0
        if pdl1_mm > 25:
            pdl1_mm = 25

        ctx = svc.get_molecule_detail(db, molecule_id, pdl1_allowed_mismatches=pdl1_mm)
    except KeyError:
        raise HTTPException(404)
    ctx["request"] = request
    ctx["tab"] = tab
    # Always include batch-first experimental context so batches render on all tabs.
    # Only apply selected_batch_id when explicitly on the experimental tab.
    try:
        ctx.update(
            svc.get_molecule_experimental_context(
                db,
                molecule_id,
                selected_batch_id=batch_id if tab == "experimental" else None,
            )
        )
    except Exception:
        pass

    return templates.TemplateResponse("molecules/detail.html", ctx)


@router.post("/molecules/{molecule_id}/files")
def molecule_add_files(
    molecule_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    storage=Depends(get_storage_cfg),
):
    m = svc.get_molecule(db, molecule_id)
    if not m:
        raise HTTPException(404)

    uploads = []
    for uf in files:
        if uf.filename:
            uploads.append((uf.filename, uf.content_type or "application/octet-stream", uf.file.read()))

    if uploads:
        file_svc.attach_files(db, storage=storage, entity_type="Molecule", entity_id=molecule_id, uploads=uploads)

    return RedirectResponse(url=f"/molecules/{molecule_id}", status_code=303)


@router.get("/molecules/{molecule_id}/edit", response_class=HTMLResponse)
def edit_molecule(molecule_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    m = svc.get_molecule(db, molecule_id)
    if not m:
        raise HTTPException(404)
    _, programs = svc.list_molecules(db)
    components = {c.role: c.fasta for c in db.query(MoleculeComponent).filter(MoleculeComponent.molecule_id == m.id).all()}
    return templates.TemplateResponse("molecules/form.html", {"request": request, "molecule": m, "programs": programs, "components": components})


@router.post("/molecules/{molecule_id}/edit")
async def update_molecule(
    molecule_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    form = dict(await request.form())
    program_id = int(form.get("program_id"))
    primary_id = str(form.get("primary_id") or "")
    title = str(form.get("title") or "")
    description = str(form.get("description") or "")
    sequences = str(form.get("sequences") or "")
    reason = str(form.get("reason") or "")
    molecule_format = (form.get("molecule_format") or "").strip() or None
    description_user = str(form.get("description_user") or "")
    heavy_compute_enabled = 1 if str(form.get("heavy_compute_enabled") or "") in ("1", "on", "true", "True") else 0
    bundle = str(form.get("fasta_bundle") or "")

    comps = _extract_components_from_form(form)
    if bundle and not comps:
        comps = _parse_fasta_bundle(bundle)

    try:
        m = svc.update_molecule(
            db,
            molecule_id=molecule_id,
            program_id=program_id,
            primary_id=primary_id,
            title=title,
            description=description,
            sequences=sequences,
            molecule_format=molecule_format,
            description_user=description_user,
            heavy_compute_enabled=heavy_compute_enabled,
            components=comps if (molecule_format in ("IgG", "scFv") and comps) else (None if not comps and molecule_format not in ("IgG", "scFv") else comps),
            background_tasks=background_tasks,
            reason=reason,
        )
    except KeyError:
        raise HTTPException(404)

    return RedirectResponse(url=f"/molecules/{m.id}", status_code=303)
