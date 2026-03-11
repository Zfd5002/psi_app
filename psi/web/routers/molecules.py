from __future__ import annotations

from datetime import datetime
import re

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from psi.web.deps import get_db, get_storage_cfg, get_templates
from psi.web import ui_surfaces
from psi.web import handoff_context as handoff
from psi.core.db import get_db as get_db_ctx
from psi.services import molecules as svc
from psi.services.measurements import list_measurements_for_record
from psi.services.metric_catalog import metric_catalog_entry, metric_group_sort_key, normalize_metric_key
from psi.services.computed import run_computed_properties, run_immunogenicity_mhci
from psi.services.numbering import trigger_numbering_for_molecule
from psi.services.domains import extract_domains_for_molecule, upsert_user_domain_instance
from psi.services import files as file_svc
from psi.core.models import DomainInstance, MoleculeComponent, Program
from psi.core.deps import numbering_dependency_status

router = APIRouter()


def _db_path_from_session(db: Session) -> str | None:
    try:
        bind = db.get_bind()
        if bind is None or bind.url is None:
            return None
        return bind.url.database
    except Exception:
        return None


def _append_query_params(url: str, params: dict[str, str]) -> str:
    parts = urlsplit(url)
    existing = dict(parse_qsl(parts.query, keep_blank_values=True))
    existing.update({k: v for k, v in params.items() if v is not None})
    query = urlencode(existing)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def _collapse_symmetric_viewer_components(components: list[dict] | None) -> list[dict]:
    """Collapse redundant symmetric chain viewers for sequence display.

    Display-only behavior:
    - HC1 == HC2 -> keep one heavy-chain viewer with explicit collapsed label.
    - LC1 == LC2 -> keep one light-chain viewer with explicit collapsed label.
    - Handle heavy and light symmetry independently.
    """
    rows = list(components or [])
    by_role: dict[str, dict] = {}
    for c in rows:
        role = str((c or {}).get("role") or "").strip().upper()
        if role and role not in by_role:
            by_role[role] = c

    def _seq_for(role: str) -> str:
        c = by_role.get(role) or {}
        return str(c.get("sequence") or "")

    hc_identical = bool(by_role.get("HC1") and by_role.get("HC2") and _seq_for("HC1") == _seq_for("HC2"))
    lc_identical = bool(by_role.get("LC1") and by_role.get("LC2") and _seq_for("LC1") == _seq_for("LC2"))

    out: list[dict] = []
    for c in rows:
        role = str((c or {}).get("role") or "").strip().upper()
        if hc_identical and role == "HC2":
            continue
        if lc_identical and role == "LC2":
            continue
        row = dict(c or {})
        if hc_identical and role in ("HC1", "HC2"):
            row["display_role_label"] = "Heavy Chain (HC1 = HC2)"
        elif lc_identical and role in ("LC1", "LC2"):
            row["display_role_label"] = "Light Chain (LC1 = LC2)"
        else:
            row["display_role_label"] = row.get("role") or role
        out.append(row)
    return out


_RESULT_PARSE_RE = re.compile(r"\b(pass|borderline|fail)\b", flags=re.IGNORECASE)


_EXPERIMENT_GROUP_BY_DATA_TYPE = {
    "EXPRESSION": "Expression",
    "SEC": "Purity/SEC",
    "PURITY": "Purity/SEC",
    "PURIFICATION_RUN": "Purity/SEC",
    "DLS": "Purity/SEC",
    "STABILITY": "Purity/SEC",
    "IDENTITY": "Purity/SEC",
    "BINDING": "Binding",
    "CELL_ASSAY": "Functional",
    "ENDOTOXIN": "Endotoxin",
    "PK_PD": "PK",
    "IN_VIVO_EFFICACY": "In Vivo",
}


_SUMMARY_METRIC_PRIORITIES = {
    "Expression": [
        ("titer_mg_l",),
        ("expr_yield_mgL",),
        ("viability_percent",),
        ("total_yield_mg",),
    ],
    "Purity/SEC": [
        ("monomer_pct", "monomer_percent"),
        ("hmw_pct", "hmw_percent"),
        ("lmw_pct", "lmw_percent"),
    ],
    "Binding": [
        ("kd_nM", "kd"),
        ("kon",),
        ("koff",),
    ],
    "Functional": [
        ("ec50",),
        ("percent_killing",),
        ("surface_expression_pct_24h",),
        ("internalization_t1_2_h",),
    ],
    "Endotoxin": [
        ("value_eu_ml", "endotoxin_eu_ml", "endotoxin_eu_mg"),
        ("limit_eu_ml", "spec_limit_eu_mg"),
    ],
    "PK": [
        ("half_life_days",),
        ("cmax_ug_ml",),
        ("auc",),
    ],
    "In Vivo": [
        ("diabetes_incidence_pct",),
        ("time_to_onset_days",),
    ],
}


_DEFAULT_UNIT_BY_METRIC = {
    "kon": "M^-1 s^-1",
    "ka": "M^-1 s^-1",
    "koff": "s^-1",
    "kdiss": "s^-1",
    "rmax": "RU",
}


def _normalize_unit_display(unit: str) -> str:
    u = str(unit or "").strip()
    if not u:
        return ""
    lookup = {
        "1/M/s": "M^-1 s^-1",
        "1/Ms": "M^-1 s^-1",
        "1/s": "s^-1",
        "M-1 s-1": "M^-1 s^-1",
    }
    return str(lookup.get(u, u))


def _measurement_metric_key(row: dict) -> str:
    return str(row.get("metric_key") or row.get("name") or row.get("key") or "").strip()


def _format_numeric_value(value: float) -> str:
    num = float(value)
    if abs(num - round(num)) < 1e-12:
        return f"{int(round(num)):,}"
    if abs(num) >= 1000:
        return f"{num:,.3f}".rstrip("0").rstrip(".")
    if abs(num) >= 1:
        return f"{num:.4g}"
    return f"{num:.3g}"


def _measurement_value_and_unit(row: dict, *, metric_key: str = "") -> tuple[str, str]:
    metric_key = str(metric_key or _measurement_metric_key(row) or "").strip()
    value_num = row.get("value_num")
    value_text = row.get("value_text")
    unit = str(row.get("unit") or "").strip()
    if not unit and metric_key:
        unit = str(metric_catalog_entry(metric_key).get("unit") or "").strip()
    if not unit and metric_key:
        unit = str(_DEFAULT_UNIT_BY_METRIC.get(metric_key) or "").strip()
    unit = _normalize_unit_display(unit)
    if value_num is not None:
        try:
            return (_format_numeric_value(float(value_num)), unit)
        except Exception:
            return (str(value_num), unit)
    if value_text not in (None, ""):
        return (str(value_text), unit)
    raw = row.get("value")
    if raw not in (None, ""):
        return (str(raw), unit)
    return ("—", unit)


def _record_group_name(record, measurements: list[dict]) -> str:
    dtype = str(getattr(record, "data_type", "") or "").strip().upper()
    if dtype in _EXPERIMENT_GROUP_BY_DATA_TYPE:
        return str(_EXPERIMENT_GROUP_BY_DATA_TYPE[dtype])
    inferred = "Other"
    for m in list(measurements or []):
        mk = _measurement_metric_key(m)
        if not mk:
            continue
        g = str(metric_catalog_entry(mk).get("domain") or "Other").strip() or "Other"
        if g.lower() != "other":
            inferred = g
            break
    return inferred


def _record_experiment_label(record) -> str:
    dtype = str(getattr(record, "data_type", "") or "").strip()
    method = str(getattr(record, "method", "") or "").strip()
    dtype_txt = dtype.replace("_", " ").strip() or "Experiment"
    method_txt = method.replace("_", " ").strip() or "Unknown"
    return f"{dtype_txt} / {method_txt}"


def _summary_for_measurements(*, group_name: str, measurements: list[dict], max_items: int = 3) -> str:
    if not measurements:
        return "—"
    by_key: dict[str, dict] = {}
    for m in list(measurements):
        key = _measurement_metric_key(m)
        if not key:
            continue
        by_key.setdefault(str(key), m)

    selected_keys: list[str] = []
    for alias_group in list(_SUMMARY_METRIC_PRIORITIES.get(group_name) or []):
        for alias in alias_group:
            if alias in by_key and alias not in selected_keys:
                selected_keys.append(alias)
                break
        if len(selected_keys) >= max_items:
            break

    if not selected_keys:
        noisy = {"conclusion", "pass_fail", "fit_model", "chi2", "binding_confirmed"}
        fallback_keys = sorted([k for k in by_key.keys() if k not in noisy]) or sorted(by_key.keys())
        selected_keys = fallback_keys[:max_items]

    parts: list[str] = []
    for k in selected_keys[:max_items]:
        row = by_key.get(k) or {}
        value, unit = _measurement_value_and_unit(row, metric_key=k)
        entry = metric_catalog_entry(k)
        label = str(entry.get("label") or k).strip() or k
        if value == "—":
            continue
        if unit:
            parts.append(f"{label} {value} {unit}")
        else:
            parts.append(f"{label} {value}")
    return "; ".join(parts) if parts else "—"


def _result_for_record(*, measurements: list[dict], primary_result_text: str | None) -> str:
    by_key = {_measurement_metric_key(m): m for m in list(measurements or []) if _measurement_metric_key(m)}
    for key in ("conclusion", "pass_fail"):
        row = by_key.get(key)
        if row is None:
            continue
        value, _unit = _measurement_value_and_unit(row, metric_key=key)
        val = str(value or "").strip()
        if val and val != "—":
            return val
    text = str(primary_result_text or "").strip()
    if text:
        m = _RESULT_PARSE_RE.search(text)
        if m:
            return str(m.group(1)).lower()
    return "—"


def _run_date_epoch(value: str) -> float:
    text = str(value or "").strip()
    if not text:
        return -1.0
    try:
        if len(text) == 10:
            return float(datetime.fromisoformat(text + "T00:00:00").timestamp())
        return float(datetime.fromisoformat(text).timestamp())
    except Exception:
        return -1.0


def _build_experiment_result_rows(
    db: Session,
    exp_batch_panels: list[dict] | None,
    exp_molecule_level_records: list[dict] | None = None,
) -> list[dict]:
    records_by_id = _collect_molecule_records_from_experimental_context(exp_batch_panels, exp_molecule_level_records)
    measurement_cache: dict[int, list[dict]] = {}

    def _measurements_for_record(record_id: int) -> list[dict]:
        if record_id not in measurement_cache:
            try:
                measurement_cache[record_id] = list_measurements_for_record(db, record_id=int(record_id))
            except Exception:
                measurement_cache[record_id] = []
        return measurement_cache.get(record_id, [])

    rows: list[dict] = []
    for record_id, node in records_by_id.items():
        record = node.get("record")
        if record is None:
            continue
        measurements = _measurements_for_record(int(record_id))
        group_name = _record_group_name(record, measurements)
        group_order = int(metric_group_sort_key(group_name)[0])
        run_date = str(getattr(record, "run_date", "") or "")
        rows.append(
            {
                "record_id": int(record_id),
                "record_title": str(getattr(record, "title", "") or ""),
                "run_date": run_date,
                "batch_id": node.get("batch_id"),
                "batch_label": str(node.get("batch_label") or "—"),
                "experiment": _record_experiment_label(record),
                "summary": _summary_for_measurements(group_name=group_name, measurements=measurements, max_items=3),
                "result": _result_for_record(
                    measurements=measurements,
                    primary_result_text=str(getattr(record, "primary_result_text", "") or ""),
                ),
                "group_name": group_name,
                "group_order": group_order,
                "_run_date_epoch": _run_date_epoch(run_date),
            }
        )

    rows.sort(
        key=lambda r: (
            int(r.get("group_order") or 999),
            0 if float(r.get("_run_date_epoch") or -1) >= 0 else 1,
            -float(r.get("_run_date_epoch") or -1),
            -int(r.get("record_id") or 0),
        )
    )
    for row in rows:
        row.pop("_run_date_epoch", None)
    return rows


_MOLECULE_SUMMARY_METRIC_SPECS = [
    {"label": "Expression titer", "experiment": "Expression", "keys": ("titer_mg_l", "expr_yield_mgL"), "best": "max"},
    {"label": "Total yield", "experiment": "Expression", "keys": ("total_yield_mg",), "best": "max"},
    {"label": "Viability", "experiment": "Expression", "keys": ("viability_percent",), "best": "max"},
    {"label": "Monomer %", "experiment": "SEC", "keys": ("monomer_pct", "monomer_percent"), "best": "max"},
    {"label": "HMW %", "experiment": "SEC", "keys": ("hmw_pct", "hmw_percent"), "best": "min"},
    {"label": "Binding KD", "experiment": "SPR", "keys": ("kd_nM", "kd_nm", "kd"), "best": "min"},
    {"label": "Functional EC50", "experiment": "Cell Assay", "keys": ("ec50",), "best": "min"},
    {"label": "Endotoxin", "experiment": "LAL", "keys": ("endotoxin_eu_ml", "endotoxin_eu_mg", "value_eu_ml"), "best": "min"},
]


def _collect_molecule_records_from_experimental_context(
    exp_batch_panels: list[dict] | None,
    exp_molecule_level_records: list[dict] | None,
) -> dict[int, dict]:
    records_by_id: dict[int, dict] = {}
    for panel in list(exp_batch_panels or []):
        batch = panel.get("batch")
        batch_id = int(batch.id) if batch is not None and getattr(batch, "id", None) is not None else None
        batch_label = str(panel.get("batch_label") or (batch.batch_id if batch is not None and getattr(batch, "batch_id", None) else "—"))
        assays = panel.get("assays") if isinstance(panel, dict) else {}
        if not isinstance(assays, dict):
            continue
        for _assay_name, conds in assays.items():
            if not isinstance(conds, dict):
                continue
            for node in conds.values():
                runs = node.get("runs") if isinstance(node, dict) else []
                for item in list(runs or []):
                    record = item.get("record") if isinstance(item, dict) else None
                    if record is None:
                        continue
                    record_id = int(record.id)
                    records_by_id[record_id] = {
                        "record": record,
                        "batch_id": batch_id,
                        "batch_label": batch_label,
                    }
    for item in list(exp_molecule_level_records or []):
        record = item.get("record") if isinstance(item, dict) else None
        if record is None:
            continue
        record_id = int(record.id)
        records_by_id.setdefault(
            record_id,
            {
                "record": record,
                "batch_id": None,
                "batch_label": "Unassigned",
            },
        )
    return records_by_id


def _best_batch_summary_rows(
    db: Session,
    exp_batch_panels: list[dict] | None,
    exp_molecule_level_records: list[dict] | None = None,
) -> list[dict]:
    records_by_id = _collect_molecule_records_from_experimental_context(exp_batch_panels, exp_molecule_level_records)
    if not records_by_id:
        return []

    observations_by_metric: dict[str, list[dict]] = {str(spec["label"]): [] for spec in _MOLECULE_SUMMARY_METRIC_SPECS}

    for node in records_by_id.values():
        record = node.get("record")
        if record is None:
            continue
        record_id = int(getattr(record, "id", 0) or 0)
        if record_id <= 0:
            continue
        run_date = str(getattr(record, "run_date", "") or "")
        run_epoch = _run_date_epoch(run_date)
        batch_label = str(node.get("batch_label") or "—")
        try:
            measurements = list_measurements_for_record(db, record_id=record_id)
        except Exception:
            measurements = []
        for m in list(measurements or []):
            metric_key = normalize_metric_key(_measurement_metric_key(m))
            if not metric_key:
                continue
            value_num = m.get("value_num")
            try:
                numeric_value = float(value_num) if value_num is not None else None
            except Exception:
                numeric_value = None
            if numeric_value is None:
                continue
            unit = str(m.get("unit") or "").strip()
            if not unit:
                unit = str(metric_catalog_entry(metric_key).get("unit") or "").strip()
            unit = _normalize_unit_display(unit)
            for spec in _MOLECULE_SUMMARY_METRIC_SPECS:
                aliases = {normalize_metric_key(str(k)) for k in (spec.get("keys") or ())}
                if metric_key not in aliases:
                    continue
                observations_by_metric[str(spec["label"])].append(
                    {
                        "value": numeric_value,
                        "unit": unit,
                        "record_id": record_id,
                        "run_date": run_date,
                        "run_epoch": run_epoch,
                        "batch_label": batch_label,
                    }
                )

    rows: list[dict] = []
    for spec in _MOLECULE_SUMMARY_METRIC_SPECS:
        metric_label = str(spec["label"])
        observations = list(observations_by_metric.get(metric_label) or [])
        if not observations:
            continue
        unit_counts: dict[str, int] = {}
        for obs in observations:
            unit_counts[str(obs.get("unit") or "")] = int(unit_counts.get(str(obs.get("unit") or ""), 0)) + 1
        chosen_unit = ""
        if unit_counts:
            chosen_unit = sorted(unit_counts.items(), key=lambda kv: (-int(kv[1]), str(kv[0])))[0][0]
        compatible = [obs for obs in observations if str(obs.get("unit") or "") == chosen_unit]
        if not compatible:
            continue

        best = compatible[0]
        for obs in compatible[1:]:
            best_mode = str(spec.get("best") or "max")
            if best_mode == "min":
                better = (
                    float(obs["value"]) < float(best["value"])
                    or (
                        float(obs["value"]) == float(best["value"])
                        and (float(obs["run_epoch"]), int(obs["record_id"])) > (float(best["run_epoch"]), int(best["record_id"]))
                    )
                )
            else:
                better = (
                    float(obs["value"]) > float(best["value"])
                    or (
                        float(obs["value"]) == float(best["value"])
                        and (float(obs["run_epoch"]), int(obs["record_id"])) > (float(best["run_epoch"]), int(best["record_id"]))
                    )
                )
            if better:
                best = obs

        avg_value = sum(float(obs["value"]) for obs in compatible) / float(len(compatible))
        best_txt = _format_numeric_value(float(best["value"]))
        avg_txt = _format_numeric_value(float(avg_value))
        if chosen_unit:
            best_txt = f"{best_txt} {chosen_unit}"
            avg_txt = f"{avg_txt} {chosen_unit}"
        rows.append(
            {
                "metric_label": metric_label,
                "experiment": str(spec.get("experiment") or ""),
                "best_display": best_txt,
                "average_display": avg_txt,
                "best_batch": str(best.get("batch_label") or "—"),
                "best_date": str(best.get("run_date") or "—"),
            }
        )
    return rows


@router.post("/molecules/{molecule_id}/computed/recompute")
def recompute_fast_properties(molecule_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    m = svc.get_molecule(db, molecule_id)
    if not m:
        raise HTTPException(404)
    # Always run in background; consistent UX.
    background_tasks.add_task(svc._background_compute, molecule_id, "manual_recompute", _db_path_from_session(db))
    return RedirectResponse(url=f"/molecules/{molecule_id}", status_code=303)


@router.post("/molecules/{molecule_id}/numbering")
def run_numbering(
    molecule_id: int,
    background_tasks: BackgroundTasks,
    scheme: str = Form("kabat"),
    return_to: str | None = Form(None),
    db: Session = Depends(get_db),
):
    m = svc.get_molecule(db, molecule_id)
    if not m:
        raise HTTPException(404)
    target = f"/molecules/{molecule_id}?scheme={scheme}"
    candidate = str(return_to or "").strip()
    # Allow explicit sequence-page return target for this same molecule only.
    if candidate and candidate.startswith(f"/molecules/{molecule_id}/sequence"):
        target = candidate

    has_domains = (
        db.query(DomainInstance)
        .filter(DomainInstance.molecule_id == int(molecule_id))
        .filter(DomainInstance.domain_type.in_(["VH", "VL"]))
        .filter(DomainInstance.status == "success")
        .count()
        > 0
    )
    if not has_domains:
        return RedirectResponse(
            url=_append_query_params(target, {"scheme": str(scheme), "numbering_status": "no_domains"}),
            status_code=303,
        )

    dep_status = numbering_dependency_status()
    if not dep_status.get("ok"):
        missing = ",".join(str(x) for x in dep_status.get("missing") or [])
        return RedirectResponse(
            url=_append_query_params(
                target,
                {
                    "scheme": str(scheme),
                    "numbering_status": "missing_dependencies",
                    "numbering_missing": missing,
                },
            ),
            status_code=303,
        )

    # Run in background: compute missing artifacts.
    db_path = _db_path_from_session(db)
    def _bg():
        with get_db_ctx(db_path, ensure=True) as s:
            trigger_numbering_for_molecule(s, molecule_id=molecule_id, scheme=scheme, force=True)

    background_tasks.add_task(_bg)
    return RedirectResponse(
        url=_append_query_params(target, {"scheme": str(scheme), "numbering_status": "started"}),
        status_code=303,
    )


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

    db_path = _db_path_from_session(db)
    def _bg():
        with get_db_ctx(db_path, ensure=True) as s:
            run_immunogenicity_mhci(
                s,
                molecule_id=molecule_id,
                trigger_reason="manual_immunogenicity",
                allele=str(allele or "HLA-A0201").strip() or "HLA-A0201",
                min_len=int(min_len),
                max_len=int(max_len),
                binder_threshold_nm=float(binder_threshold_nm),
            )

    background_tasks.add_task(_bg)
    return RedirectResponse(url=f"/molecules/{molecule_id}#computed", status_code=303)


@router.post("/molecules/{molecule_id}/domains/recompute")
def recompute_domains(
    molecule_id: int,
    background_tasks: BackgroundTasks,
    return_to: str | None = Form(None),
    db: Session = Depends(get_db),
):
    m = svc.get_molecule(db, molecule_id)
    if not m:
        raise HTTPException(404)

    db_path = _db_path_from_session(db)
    def _bg():
        with get_db_ctx(db_path, ensure=True) as s:
            extract_domains_for_molecule(s, molecule_id)

    background_tasks.add_task(_bg)
    target = f"/molecules/{molecule_id}#domains"
    candidate = str(return_to or "").strip()
    # Allow explicit sequence-page return target for this same molecule only.
    if candidate and candidate.startswith(f"/molecules/{molecule_id}/sequence"):
        target = candidate
    return RedirectResponse(
        url=_append_query_params(target, {"domains_status": "started"}),
        status_code=303,
    )


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
def list_molecules(request: Request, program_id: int | None = None, db: Session = Depends(get_db)):
    templates = get_templates(request)
    molecules, programs = svc.list_molecules(db, program_id=program_id)
    header_by_molecule_id = svc.build_list_molecule_header_models(
        db,
        molecule_ids=[int(m.id) for m in molecules],
    )
    active_program = db.get(Program, int(program_id)) if program_id is not None else None
    return templates.TemplateResponse(
        "molecules/list.html",
        {
            "request": request,
            "molecules": molecules,
            "programs": programs,
            "header_by_molecule_id": header_by_molecule_id,
            "active_program": active_program,
            "surface": ui_surfaces.molecules_registry_surface(),
        },
    )


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
    # Accept both legacy lowercase keys and current form uppercase keys.
    # This keeps structured creation deterministic across direct form posts and
    # any callers still submitting lowercase field names.
    mapping = [
        (("HC1", "hc1"), "HC1"),
        (("LC1", "lc1"), "LC1"),
        (("HC2", "hc2"), "HC2"),
        (("LC2", "lc2"), "LC2"),
    ]
    for aliases, role in mapping:
        picked = None
        for name in aliases:
            if name in form:
                picked = form.get(name)
                break
        if picked is None:
            continue
        comps[role] = (picked or "").strip()
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
            db_path=_db_path_from_session(db),
        )
    except DuplicateMoleculeError as e:
        # Block duplicate composition; redirect back to form with a clear banner + link.
        return RedirectResponse(url=f"/molecules/new?duplicate={e.existing_primary_id}&existing_id={e.existing_molecule_id}", status_code=303)
    except ValueError as e:
        return RedirectResponse(url=f"/molecules/new?error={str(e)}", status_code=303)

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
    hctx = handoff.get_handoff_context(request)
    ctx["capture_notice"] = handoff.build_capture_notice(
        context=hctx,
        return_to=f"/programs/{int(ctx['molecule'].program_id)}/workflow",
        message="Continue in Program Workflow to unblock, assign, and close the next work item.",
    )
    ctx["surface"] = ui_surfaces.molecule_detail_surface(molecule_id=int(molecule_id))

    # v1.2.7: QC-aware batch-first context. Batches render on all tabs.
    qc_mode = str(request.query_params.get("qc_mode") or "all").strip().lower()
    if qc_mode not in ("all", "model_safe", "approved"):
        qc_mode = "all"
    try:
        ctx.update(
            svc.get_molecule_batch_ui_context(
                db,
                molecule_id,
                selected_batch_id=batch_id if tab == "experimental" else None,
                qc_mode=qc_mode,
            )
        )
    except Exception:
        # UI-only; never block page render.
        ctx.setdefault("data_overview", None)
        ctx.setdefault("exp_qc_mode", qc_mode)
        ctx.setdefault("exp_run_qc", {})
    ctx["best_batch_summary_rows"] = _best_batch_summary_rows(
        db,
        ctx.get("exp_batch_panels"),
        ctx.get("exp_molecule_level_records"),
    )

    return templates.TemplateResponse("molecules/detail.html", ctx)


def _build_molecule_page_context(
    *,
    db: Session,
    request: Request,
    molecule_id: int,
    tab: str = "overview",
    batch_id: int | None = None,
    include_batch_ui: bool = False,
) -> dict:
    mm = request.query_params.get("pdl1_mm", "")
    try:
        pdl1_mm = int(mm) if str(mm).strip() != "" else 0
    except Exception:
        pdl1_mm = 0
    pdl1_mm = max(0, min(25, pdl1_mm))
    ctx = svc.get_molecule_detail(db, molecule_id, pdl1_allowed_mismatches=pdl1_mm)
    ctx["sequence_viewer_components"] = _collapse_symmetric_viewer_components(
        ctx.get("viewer_v2_components") if isinstance(ctx, dict) else None
    )
    ctx["request"] = request
    ctx["tab"] = tab
    hctx = handoff.get_handoff_context(request)
    ctx["capture_notice"] = handoff.build_capture_notice(
        context=hctx,
        return_to=f"/programs/{int(ctx['molecule'].program_id)}/workflow",
        message="Continue in Program Workflow to unblock, assign, and close the next work item.",
    )
    if include_batch_ui:
        qc_mode = str(request.query_params.get("qc_mode") or "all").strip().lower()
        if qc_mode not in ("all", "model_safe", "approved"):
            qc_mode = "all"
        try:
            ctx.update(
                svc.get_molecule_batch_ui_context(
                    db,
                    molecule_id,
                    selected_batch_id=batch_id if tab == "experimental" else None,
                    qc_mode=qc_mode,
                )
            )
        except Exception:
            ctx.setdefault("data_overview", None)
            ctx.setdefault("exp_qc_mode", qc_mode)
            ctx.setdefault("exp_run_qc", {})
    return ctx


@router.get("/molecules/{molecule_id}/results", response_class=HTMLResponse)
def molecule_results(molecule_id: int, request: Request, batch_id: int | None = None, db: Session = Depends(get_db)):
    templates = get_templates(request)
    try:
        ctx = _build_molecule_page_context(
            db=db,
            request=request,
            molecule_id=int(molecule_id),
            tab="experimental",
            batch_id=batch_id,
            include_batch_ui=True,
        )
    except KeyError:
        raise HTTPException(404)
    ctx["surface"] = ui_surfaces.molecule_results_surface(molecule_id=int(molecule_id))
    ctx["experiment_result_rows"] = _build_experiment_result_rows(
        db,
        ctx.get("exp_batch_panels"),
        ctx.get("exp_molecule_level_records"),
    )
    return templates.TemplateResponse("molecules/results.html", ctx)


@router.get("/molecules/{molecule_id}/sequence", response_class=HTMLResponse)
def molecule_sequence(molecule_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    try:
        ctx = _build_molecule_page_context(
            db=db,
            request=request,
            molecule_id=int(molecule_id),
            include_batch_ui=False,
        )
    except KeyError:
        raise HTTPException(404)
    ctx["surface"] = ui_surfaces.molecule_sequence_surface(molecule_id=int(molecule_id))
    return templates.TemplateResponse("molecules/sequence.html", ctx)


@router.get("/molecules/{molecule_id}/governance", response_class=HTMLResponse)
def molecule_governance(molecule_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    try:
        ctx = _build_molecule_page_context(
            db=db,
            request=request,
            molecule_id=int(molecule_id),
            include_batch_ui=True,
        )
    except KeyError:
        raise HTTPException(404)
    ctx["surface"] = ui_surfaces.molecule_governance_surface(molecule_id=int(molecule_id))
    return templates.TemplateResponse("molecules/governance.html", ctx)


@router.post("/molecules/{molecule_id}/files")
def molecule_add_files(
    molecule_id: int,
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
    m = svc.get_molecule(db, molecule_id)
    if not m:
        raise HTTPException(404)

    uploads = []
    for uf in files:
        if uf.filename:
            uploads.append((uf.filename, uf.content_type or "application/octet-stream", uf.file.read()))

    if uploads:
        file_svc.attach_files(
            db,
            storage=storage,
            entity_type="Molecule",
            entity_id=molecule_id,
            uploads=uploads,
            role=(file_role or "other"),
            instrument=instrument or None,
            operator=operator or None,
            run_id=run_id or None,
            collected_at=collected_at or None,
            notes=notes or None,
        )

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
            db_path=_db_path_from_session(db),
            reason=reason,
        )
    except KeyError:
        raise HTTPException(404)

    return RedirectResponse(url=f"/molecules/{m.id}", status_code=303)
