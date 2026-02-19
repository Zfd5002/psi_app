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
    dup = request.query_params.get('duplicate')
    existing_id = request.query_params.get('existing_id')
    error = request.query_params.get('error')
    return templates.TemplateResponse("molecules/form.html", {"request": request, "molecule": None, "programs": programs, "duplicate": dup, "existing_id": existing_id, "error": error})


def _extract_components_from_form(form) -> dict[str, str]:
    """
    Extract component sequences from the molecule form.

    Important: allow "clear" operations. If a field is present in the form but empty,
    we include it with an empty string so the service layer can clear that role.
    """
    comps: dict[str, str] = {}
    mapping = [
        ('hc1','HC1'),
        ('lc1','LC1'),
        ('hc2','HC2'),
        ('lc2','LC2'),
    ]
    for name, role in mapping:
        raw = form.get(name)
        if raw is None:
            continue
        comps[role] = (raw or "").strip()
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
        for role in ["HC1", "HC2", "LC1", "LC2"]:
            if h == role or h.endswith(role) or h.startswith(role):
                out[role] = r.sequence
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


    try:
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
    except DuplicateMoleculeError as e:
        # Block duplicate composition; redirect back to form with a clear banner + link.
        return RedirectResponse(url=f"/molecules/new?duplicate={e.existing_primary_id}&existing_id={e.existing_molecule_id}", status_code=303)
    except ValueError as e:
        return RedirectResponse(url=f"/molecules/new?error={str(e)}", status_code=303)

    return RedirectResponse(url=f"/molecules/{m.id}", status_code=303)



# ---- v1.2.3f: batch-first molecule UX helpers (UI-only, read-only) ----

def _batch_sort_key(batch_id: str) -> tuple:
    """Deterministic batch sort.

    - If batch_id ends with a numeric suffix like '-001', sort by that integer.
    - Otherwise fall back to case-insensitive lexical sort.
    """
    s = (batch_id or "").strip()
    try:
        import re as _re
        m = _re.search(r"-(\d{1,6})$", s)
    except Exception:
        m = None
    if m:
        try:
            return (0, int(m.group(1)), s.lower())
        except Exception:
            pass
    return (1, s.lower())


def _reflect_measurement_cols(db: Session) -> dict:
    """Best-effort reflection of the data_measurements schema (read-only)."""
    from sqlalchemy import text as _text

    try:
        rows = db.execute(_text("PRAGMA table_info(data_measurements)")).mappings().all()
    except Exception:
        return {}

    cols = {str(r["name"]): True for r in rows}

    def pick(*names: str):
        for n in names:
            if n in cols:
                return n
        return None

    out = {
        "record_fk": pick("data_record_id", "record_id"),
        "name": pick("metric_key", "name", "key"),
        "value_num": pick("value_num", "numeric_value", "value"),
        "value_text": pick("value_text", "text_value", "raw_value"),
        "unit": pick("unit"),
        "comparator": pick("comparator", "op"),
        "is_primary": pick("is_primary", "primary", "is_headline"),
        "is_outlier": pick("is_outlier"),
        "qc_flag": pick("qc_flag", "qc_status"),
        "id": pick("id"),
        "created_at": pick("created_at", "updated_at", "timestamp", "ts"),
        "_all": set(cols.keys()),
    }
    if not out["record_fk"] or not out["name"]:
        return {}
    return out


def _fetch_measurements_for_record(db: Session, record_id: int, cols: dict) -> list[dict]:
    """Fetch all measurement rows for a record with deterministic ordering, QC-safe."""
    if not cols:
        return []
    from sqlalchemy import text as _text

    where = [f"{cols['record_fk']}=:rid"]
    params = {"rid": int(record_id)}

    qc_col = cols.get("qc_flag")
    if qc_col:
        where.append(f"({qc_col} IS NULL OR {qc_col}=0 OR {qc_col}='0' OR {qc_col}='')")

    order = []
    if cols.get("is_primary"):
        order.append(f"{cols['is_primary']} DESC")
    if cols.get("created_at"):
        order.append(f"{cols['created_at']} DESC")
    if cols.get("id"):
        order.append(f"{cols['id']} DESC")
    order.append(f"{cols['name']} ASC")

    q = _text(f"SELECT * FROM data_measurements WHERE {' AND '.join(where)} ORDER BY {', '.join(order)}")
    rows = db.execute(q, params).mappings().all()

    out = []
    for r in rows:
        def get(k):
            c = cols.get(k)
            return r.get(c) if c else None
        out.append(
            {
                "id": get("id") or r.get("id"),
                "record_id": record_id,
                "name": get("name"),
                "value_num": get("value_num"),
                "value_text": get("value_text"),
                "unit": get("unit"),
                "comparator": get("comparator"),
                "is_primary": get("is_primary") or 0,
            }
        )
    return out


def _fmt_num(v: float, *, sig: int = 3) -> str:
    try:
        x = float(v)
    except Exception:
        return str(v)
    if x == 0:
        return "0"
    try:
        import math
        digits = sig - int(math.floor(math.log10(abs(x)))) - 1
        digits = max(-2, min(6, digits))
        return f"{x:.{digits}f}".rstrip("0").rstrip(".")
    except Exception:
        return str(v)


def _fmt_percent(v: float) -> str:
    try:
        x = float(v)
    except Exception:
        return str(v)
    if abs(x - round(x)) < 1e-9:
        return f"{int(round(x))}%"
    return f"{x:.1f}%"


def _match_name(name: str, patterns: list) -> bool:
    if not name:
        return False
    n = str(name).strip().lower()
    for p in patterns:
        if isinstance(p, str):
            if p in n:
                return True
        else:
            try:
                if p.search(n):
                    return True
            except Exception:
                continue
    return False


def _best_measurement(measurements: list[dict], patterns: list) -> dict | None:
    cand = [m for m in measurements if _match_name(m.get("name"), patterns)]
    if not cand:
        return None

    def score(m):
        prim = 1 if (m.get("is_primary") in (1, True, "1")) else 0
        has_num = 1 if (m.get("value_num") is not None) else 0
        mid = m.get("id") or 0
        midn = int(mid) if str(mid).isdigit() else 0
        return (prim, has_num, midn, str(m.get("name") or "").lower())

    cand.sort(key=score, reverse=True)
    return cand[0]


def _headline_items_for_record(measurements: list[dict]) -> list[str]:
    """Return up to 3 headline strings (deterministic) from measurement rows."""
    import re as _re

    items: list[str] = []

    # 1) SEC purity block (often monomer_pct/hmw_pct/lmw_pct)
    purity = _best_measurement(measurements, ["monomer_pct", "purity", "sec_purity", _re.compile(r"\bmonomer\b")])
    hmw = _best_measurement(measurements, ["hmw_pct", "sec_hmw", _re.compile(r"\bhmw\b")])
    lmw = _best_measurement(measurements, ["lmw_pct", "sec_lmw", _re.compile(r"\blmw\b")])
    if purity and purity.get("value_num") is not None:
        items.append(f"Purity {_fmt_percent(purity['value_num'])}")
        if hmw and hmw.get("value_num") is not None:
            items.append(f"HMW {_fmt_percent(hmw['value_num'])}")
        if lmw and lmw.get("value_num") is not None:
            items.append(f"LMW {_fmt_percent(lmw['value_num'])}")

    # 2) Binding/affinity potency
    kd = _best_measurement(measurements, ["kd", "kd_nm", "kd_n", "affinity"])
    ec50 = _best_measurement(measurements, ["ec50"])
    ic50 = _best_measurement(measurements, ["ic50"])
    if kd and kd.get("value_num") is not None and len(items) < 3:
        unit = (kd.get("unit") or "").strip()
        u = f" {unit}" if unit else ""
        items.append(f"KD {_fmt_num(kd['value_num'])}{u}")
    if ec50 and ec50.get("value_num") is not None and len(items) < 3:
        unit = (ec50.get("unit") or "").strip()
        u = f" {unit}" if unit else ""
        items.append(f"EC50 {_fmt_num(ec50['value_num'])}{u}")
    if ic50 and ic50.get("value_num") is not None and len(items) < 3:
        unit = (ic50.get("unit") or "").strip()
        u = f" {unit}" if unit else ""
        items.append(f"IC50 {_fmt_num(ic50['value_num'])}{u}")

    # 3) Expression / yield / concentration
    titer = _best_measurement(measurements, ["titer", "expression", "yield", "concentration", "mg/l", "mg/ml"])
    if titer and titer.get("value_num") is not None and len(items) < 3:
        unit = (titer.get("unit") or "").strip()
        u = f" {unit}" if unit else ""
        items.append(f"Titer {_fmt_num(titer['value_num'])}{u}")

    return items[:3]


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

    
    # ---- v1.2.3f UI-only reshaping: Data Overview + batch headline results + Unassigned panel ----
    try:
        from sqlalchemy import text as _text
        from psi.core.models import DataRecord

        meas_cols = _reflect_measurement_cols(db)

        # Total data records for this molecule (including unassigned).
        total_records = (
            db.query(DataRecord)
            .filter(DataRecord.molecule_id == molecule_id)
            .count()
        )

        total_measurements = 0
        outlier_count = None
        if meas_cols:
            try:
                total_measurements = int(
                    db.execute(
                        _text(
                            f"""
                            SELECT COUNT(1) AS n
                            FROM data_measurements dm
                            JOIN data_records dr ON dm.{meas_cols['record_fk']} = dr.id
                            WHERE dr.molecule_id = :mid
                            """
                        ),
                        {"mid": molecule_id},
                    ).mappings().first()["n"]
                )
            except Exception:
                total_measurements = 0

            if meas_cols.get("is_outlier") and meas_cols.get("is_outlier") in meas_cols.get("_all", set()):
                try:
                    outlier_count = int(
                        db.execute(
                            _text(
                                f"""
                                SELECT COUNT(1) AS n
                                FROM data_measurements dm
                                JOIN data_records dr ON dm.{meas_cols['record_fk']} = dr.id
                                WHERE dr.molecule_id = :mid AND dm.{meas_cols['is_outlier']}=1
                                """
                            ),
                            {"mid": molecule_id},
                        ).mappings().first()["n"]
                    )
                except Exception:
                    outlier_count = None

        # Re-shape batch panels deterministically and attach header headline items.
        panels = list(ctx.get("exp_batch_panels") or [])
        batches = list(ctx.get("exp_batches") or [])

        # Deterministic batch ordering by batch_id (numeric suffix where possible).
        panels.sort(key=lambda p: _batch_sort_key(getattr(p.get("batch"), "batch_id", "")))
        batches.sort(key=lambda b: _batch_sort_key(getattr(b, "batch_id", "")))

        # Helper: pick latest record id within a panel (run_date desc, created_at desc, id desc).
        def _latest_record_id(panel: dict) -> int | None:
            best = None
            for _, conds in (panel.get("assays") or {}).items():
                for _, node in (conds or {}).items():
                    runs = node.get("runs") or []
                    # ensure deterministic within node
                    runs.sort(
                        key=lambda item: (
                            0 if (item.get("record") and item["record"].run_date) else 1,
                            str(item.get("record").run_date or ""),
                            item.get("record").created_at if item.get("record") else 0,
                            int(getattr(item.get("record"), "id", 0)),
                        ),
                        reverse=True,
                    )
                    for item in runs:
                        r = item.get("record")
                        if not r:
                            continue
                        key = (
                            0 if r.run_date else 1,
                            str(r.run_date or ""),
                            r.created_at,
                            int(r.id),
                        )
                        if best is None or key > best[0]:
                            best = (key, int(r.id))
            return best[1] if best else None

        batch_metric_values = {"purity": [], "kd": [], "titer": []}

        for p in panels:
            # Stabilize ordering of node runs (ensures refresh determinism).
            for _, conds in (p.get("assays") or {}).items():
                for _, node in (conds or {}).items():
                    runs = node.get("runs") or []
                    runs.sort(
                        key=lambda item: (
                            0 if (item.get("record") and item["record"].run_date) else 1,
                            str(item.get("record").run_date or ""),
                            item.get("record").created_at if item.get("record") else 0,
                            int(getattr(item.get("record"), "id", 0)),
                        ),
                        reverse=True,
                    )

            rid = _latest_record_id(p)
            headline_items = []
            meas_count = None
            if rid and meas_cols:
                meas = _fetch_measurements_for_record(db, rid, meas_cols)
                headline_items = _headline_items_for_record(meas)
                if not headline_items:
                    headline_items = ["No measurements recorded"]
                # measurement count for this batch: cheap join count
                try:
                    bid = int(getattr(p.get("batch"), "id", 0))
                    meas_count = int(
                        db.execute(
                            _text(
                                f"""
                                SELECT COUNT(1) AS n
                                FROM data_measurements dm
                                JOIN data_records dr ON dm.{meas_cols['record_fk']} = dr.id
                                WHERE dr.batch_id = :bid
                                """
                            ),
                            {"bid": bid},
                        ).mappings().first()["n"]
                    )
                except Exception:
                    meas_count = None

                # Collect overview numeric values (latest-per-batch-per-metric).
                import re as _re
                purity = _best_measurement(meas, ["monomer_pct", "purity", "sec_purity", _re.compile(r"\bmonomer\b")])
                kd = _best_measurement(meas, ["kd", "kd_nm", "kd_n", "affinity"])
                titer = _best_measurement(meas, ["titer", "expression", "yield", "concentration"])
                if purity and purity.get("value_num") is not None:
                    batch_metric_values["purity"].append(float(purity["value_num"]))
                if kd and kd.get("value_num") is not None:
                    batch_metric_values["kd"].append(float(kd["value_num"]))
                if titer and titer.get("value_num") is not None:
                    batch_metric_values["titer"].append(float(titer["value_num"]))

            p["headline_items"] = headline_items
            p["measurement_count"] = meas_count

        # Unassigned panel (records without a batch).
        unassigned = list(ctx.get("exp_molecule_level_records") or [])
        if unassigned:
            # deterministic ordering: run_date desc, created_at desc, id desc
            unassigned.sort(
                key=lambda item: (
                    0 if (item.get("record") and item["record"].run_date) else 1,
                    str(item.get("record").run_date or ""),
                    item.get("record").created_at if item.get("record") else 0,
                    int(getattr(item.get("record"), "id", 0)),
                ),
                reverse=True,
            )

            panels.append(
                {
                    "batch": None,
                    "batch_label": "Unassigned",
                    "assays": {},  # no assay tree for unassigned (keeps patch small)
                    "glance": {},
                    "record_count": len(unassigned),
                    "unassigned_records": unassigned,
                    "headline_items": ["No batch assigned"],
                    "measurement_count": None,
                    "details_key": "batch:__unassigned__",
                }
            )

        # Ensure Unassigned always last.
        panels_non = [p for p in panels if p.get("batch") is not None]
        panels_un = [p for p in panels if p.get("batch") is None]
        panels = panels_non + panels_un

        ctx["exp_batch_panels"] = panels
        ctx["exp_batches"] = batches
        ctx["exp_has_unassigned"] = bool(unassigned)

        # Data Overview aggregates (Option A: latest-per-batch-per-metric).
        def _mean(vals: list[float]) -> float | None:
            if not vals:
                return None
            try:
                return float(sum(vals) / len(vals))
            except Exception:
                return None

        ctx["data_overview"] = {
            "total_batches": len(batches) + (1 if unassigned else 0),
            "total_records": int(total_records),
            "total_measurements": int(total_measurements),
            "mean_purity": _mean(batch_metric_values["purity"]),
            "mean_kd": _mean(batch_metric_values["kd"]),
            "mean_titer": _mean(batch_metric_values["titer"]),
            "outlier_count": outlier_count,
        }
    except Exception:
        # UI-only; never block page render.
        ctx["data_overview"] = None

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
