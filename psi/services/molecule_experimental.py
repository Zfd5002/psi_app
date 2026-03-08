from __future__ import annotations

import re
from typing import Any

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from psi.core.models import Batch, DataRecord, Evidence, ExperimentTask, Molecule
from psi.services.evidence_preview import build_pending_evidence_preview_for_molecule
from psi.services import qc as qc_svc


def get_molecule_experimental_context(db: Session, molecule_id: int, *, selected_batch_id: int | None = None) -> dict:
    """Batch-first experimental view context for molecule detail.

    v1.1.6 update:
    - Provide ALL batch-linked records (not just selected batch) so the molecule page can render
      a nested, glanceable Batch → Assay → Condition → Runs tree.
    - Keep schema flexibility by using existing DataRecord.params_json for structured conditions.
    - Notes remain free-form and are displayed at the run level.
    """
    import json as _json

    from psi.core import assays as assay_norm

    m = db.get(Molecule, int(molecule_id))
    if not m:
        raise KeyError("Molecule not found")

    batches = db.query(Batch).filter(Batch.molecule_id == molecule_id).order_by(Batch.created_at.desc()).all()

    qc_counts_by_batch = qc_svc.get_qc_counts_for_batches(db, molecule_id=molecule_id)


    def _load(s: str | None) -> dict:
        try:
            return _json.loads(s) if s else {}
        except Exception:
            return {}

    def _summary_for(r: DataRecord) -> dict:
        res = _load(r.results_json)
        if r.data_type == "CMC_Analytics" and r.method in ("SEC_HPLC", "SEC"):
            return {
                "kind": "SEC",
                "monomer_pct": res.get("monomer_pct"),
                "hmw_pct": res.get("hmw_pct"),
                "lmw_pct": res.get("lmw_pct"),
                "rt_monomer_min": res.get("rt_monomer_min"),
            }
        if r.data_type == "CMC_Analytics" and r.method == "Endotoxin":
            return {
                "kind": "Endotoxin",
                "value_eu_ml": res.get("value_eu_ml"),
                "limit_eu_ml": res.get("limit_eu_ml"),
            }
        if r.data_type == "Binding" and r.method in ("BLI", "SPR"):
            return {
                "kind": "Binding",
                "kd_nM": res.get("kd_nM"),
                "kon": res.get("kon"),
                "koff": res.get("koff"),
                "chi2": res.get("chi2") or res.get("fit_quality"),
            }
        return {"kind": "Other"}

    def _assay_bucket(r: DataRecord) -> str:
        # UI-facing buckets, normalized via psi.core.assays
        return assay_norm.assay_key(r)

    def _normalize_params(p: dict) -> dict:
        # Remove empty strings/nulls for stable grouping.
        out = {}
        for k, v in (p or {}).items():
            if v is None:
                continue
            if isinstance(v, str) and not v.strip():
                continue
            out[k] = v
        return out

    def _fingerprint(p: dict) -> str:
        try:
            norm = _normalize_params(p)
            return _json.dumps(norm, sort_keys=True, separators=(",", ":"))
        except Exception:
            return ""

    def _condition_label(r: DataRecord, p: dict) -> str:
        # Human label for the third-level grouping under an assay bucket.
        # Prefer structured fields; fall back to legacy fields.
        if r.data_type == "CMC_Analytics" and r.method in ("SEC_HPLC", "SEC"):
            buf = (p.get("buffer") or p.get("mobile_phase") or "").strip()
            salt = p.get("salt_mM")
            salt_type = p.get("salt_type") or "NaCl"
            parts = []
            if buf:
                parts.append(buf)
            if salt not in (None, "", 0, "0"):
                try:
                    parts.append(f"+ {int(float(salt))} mM {salt_type}")
                except Exception:
                    parts.append(f"+ {salt} mM {salt_type}")
            if not parts:
                parts.append("Unspecified condition")
            return " ".join(parts)

        if r.data_type == "Binding" and r.method in ("SPR", "BLI"):
            ligand = (p.get("ligand") or "").strip()
            analyte = (p.get("analyte") or "").strip()
            buf = (p.get("buffer") or "").strip()
            parts = []
            if ligand and analyte:
                parts.append(f"{r.method} — {ligand} vs {analyte}")
            elif ligand:
                parts.append(f"{r.method} — {ligand}")
            elif analyte:
                parts.append(f"{r.method} — {analyte}")
            else:
                parts.append(f"{r.method}")
            if buf:
                parts.append(f"({buf})")
            return " ".join(parts)

        if r.data_type == "CMC_Analytics" and r.method == "Endotoxin":
            matrix = (p.get("sample_matrix") or p.get("buffer") or "").strip()
            return f"Matrix: {matrix}" if matrix else "Endotoxin"

        return "Condition"

    def _batch_tree_for(batch: Batch) -> dict:
        # Pull enough history to be useful without going unbounded.
        recs: list[DataRecord] = (
            db.query(DataRecord)
            .filter(DataRecord.batch_id == batch.id)
            .order_by(DataRecord.run_date.desc().nullslast(), DataRecord.created_at.desc())
            .limit(500)
            .all()
        )

        # Build: assay -> condition_fp -> {label, runs[]}
        assay_map: dict[str, dict[str, dict]] = {}
        for r in recs:
            p = _load(r.params_json)
            fp = _fingerprint(p)
            assay = _assay_bucket(r)
            cond_label = _condition_label(r, p)

            if assay not in assay_map:
                assay_map[assay] = {}
            if fp not in assay_map[assay]:
                assay_map[assay][fp] = {"label": cond_label, "params": _normalize_params(p), "runs": []}

            assay_map[assay][fp]["runs"].append(
                {
                    "record": r,
                    "params": _normalize_params(p),
                    "summary": _summary_for(r),
                    "result_text": assay_norm.record_result_text(r),
                }
            )

        # Create small "glance" summaries per assay+condition
        glance: dict[str, list[str]] = {}
        for assay, conds in assay_map.items():
            display = assay_norm.assay_display_name(assay)
            glance[display] = []
            for fp, node in conds.items():
                runs = node["runs"]
                if not runs:
                    continue
                # For known assays, show result-first summaries that remain descriptive.
                first = runs[0]
                s = first.get("summary") or {}
                label = node["label"]
                if s.get("kind") == "SEC":
                    # Show monomer/hmw/lmw. If multiple runs, show range on monomer.
                    monos = [rr.get("summary", {}).get("monomer_pct") for rr in runs]
                    monos = [x for x in monos if x is not None]
                    if len(monos) >= 2:
                        try:
                            lo = min(float(x) for x in monos)
                            hi = max(float(x) for x in monos)
                            mono_txt = f"{lo:.1f}–{hi:.1f}% monomer"
                        except Exception:
                            mono_txt = f"{monos[0]}% monomer"
                    elif len(monos) == 1:
                        mono_txt = f"{monos[0]}% monomer"
                    else:
                        mono_txt = "monomer n/a"
                    hmw = s.get("hmw_pct")
                    lmw = s.get("lmw_pct")
                    parts = [mono_txt]
                    if hmw is not None:
                        parts.append(f"{hmw}% HMW")
                    if lmw is not None:
                        parts.append(f"{lmw}% LMW")
                    glance[display].append(f"{label}: " + " / ".join(parts) + f" (n={len(runs)})")
                elif s.get("kind") == "Binding":
                    kd = s.get("kd_nM")
                    if kd is not None:
                        glance[display].append(f"{label}: KD {kd} nM (n={len(runs)})")
                    else:
                        glance[display].append(f"{label}: KD n/a (n={len(runs)})")
                elif s.get("kind") == "Endotoxin":
                    val = s.get("value_eu_ml")
                    lim = s.get("limit_eu_ml")
                    if val is not None and lim is not None:
                        glance[display].append(f"{label}: {val} EU/mL (limit {lim}) (n={len(runs)})")
                    else:
                        glance[display].append(f"{label} (n={len(runs)})")
                else:
                    glance[display].append(f"{label} (n={len(runs)})")

        return {
            "batch": batch,
            "assays": assay_map,
            "glance": glance,
            "record_count": len(recs),
            "qc": qc_counts_by_batch.get(int(batch.id), {}),
        }

    batch_panels = [_batch_tree_for(b) for b in batches]

    # Also provide molecule-level records not linked to a batch (still important sometimes).
    molecule_level_records: list[DataRecord] = (
        db.query(DataRecord)
        .filter(DataRecord.molecule_id == molecule_id)
        .filter(DataRecord.batch_id.is_(None))
        .order_by(DataRecord.run_date.desc().nullslast(), DataRecord.created_at.desc())
        .limit(200)
        .all()
    )
    molecule_level_enriched = [{"record": r, "summary": _summary_for(r), "result_text": assay_norm.record_result_text(r), "params": _normalize_params(_load(r.params_json))} for r in molecule_level_records]

    return {
        "exp_batches": batches,
        "exp_batch_panels": batch_panels,
        "exp_molecule_level_records": molecule_level_enriched,
        # Legacy keys kept for backwards compatibility with older templates (safe to remove later):
        "exp_selected_batch": None,
        "exp_records": [],
        "exp_latest_sec": None,
        "exp_latest_binding": None,
        "exp_latest_endotoxin": None,
    }


def build_molecule_evidence_context(db: Session, *, molecule_id: int) -> dict[str, Any]:
    data_records = (
        db.query(DataRecord)
        .filter(DataRecord.molecule_id == int(molecule_id))
        .order_by(DataRecord.run_date.desc().nullslast(), DataRecord.created_at.desc())
        .limit(50)
        .all()
    )
    evidence = (
        db.query(Evidence)
        .filter(Evidence.molecule_id == int(molecule_id))
        .order_by(Evidence.created_at.desc())
        .limit(50)
        .all()
    )
    pending_evidence_preview = build_pending_evidence_preview_for_molecule(db, molecule_id=int(molecule_id))
    return {
        "data_records": data_records,
        "evidence": evidence,
        "pending_evidence_preview": pending_evidence_preview,
    }


def build_molecule_experiment_context(db: Session, *, molecule_id: int) -> dict[str, Any]:
    urgency_rank = case(
        (ExperimentTask.urgency == "critical", 0),
        (ExperimentTask.urgency == "high", 1),
        (ExperimentTask.urgency == "normal", 2),
        (ExperimentTask.urgency == "low", 3),
        else_=4,
    )
    open_task_rows = (
        db.query(ExperimentTask)
        .filter(ExperimentTask.molecule_id == int(molecule_id))
        .filter(ExperimentTask.status != "done")
        .order_by(
            urgency_rank.asc(),
            func.coalesce(ExperimentTask.due_date, "9999-12-31").asc(),
            ExperimentTask.created_at.asc(),
            ExperimentTask.id.asc(),
        )
        .all()
    )
    open_experiment_tasks = [
        {
            "id": int(t.id),
            "status": str(t.status or ""),
            "urgency": str(t.urgency or ""),
            "owner_text": str(t.owner_text or ""),
            "due_date": str(t.due_date or ""),
            "metric_key": str(t.metric_key or ""),
            "suggested_assay": str(t.suggested_assay or ""),
            "notes": str(t.notes or ""),
            "source_kind": str(t.source_kind or ""),
        }
        for t in open_task_rows
    ]
    return {"open_experiment_tasks": open_experiment_tasks}


# ---- v1.2.7: batch-first molecule UI decoration (QC-aware headlines) ----

def _batch_sort_key(batch_id: str) -> tuple:
    """Deterministic batch sort.

    - If batch_id ends with a numeric suffix like '-001', sort by that integer.
    - Otherwise fall back to case-insensitive lexical sort.
    """
    s = (batch_id or "").strip()
    try:
        m = re.search(r"-(\d{1,6})$", s)
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
        "ignore_for_model": pick("ignore_for_model"),
        "id": pick("id"),
        "created_at": pick("created_at", "updated_at", "timestamp", "ts"),
        "_all": set(cols.keys()),
    }
    if not out["record_fk"] or not out["name"]:
        return {}
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
    items: list[str] = []

    purity = _best_measurement(measurements, ["monomer_pct", "purity", "sec_purity", re.compile(r"\bmonomer\b")])
    hmw = _best_measurement(measurements, ["hmw_pct", "sec_hmw", re.compile(r"\bhmw\b")])
    lmw = _best_measurement(measurements, ["lmw_pct", "sec_lmw", re.compile(r"\blmw\b")])
    if purity and purity.get("value_num") is not None:
        items.append(f"Purity {_fmt_percent(purity['value_num'])}")
        if hmw and hmw.get("value_num") is not None:
            items.append(f"HMW {_fmt_percent(hmw['value_num'])}")
        if lmw and lmw.get("value_num") is not None:
            items.append(f"LMW {_fmt_percent(lmw['value_num'])}")

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

    titer = _best_measurement(measurements, ["titer", "expression", "yield", "concentration", "mg/l", "mg/ml"])
    if titer and titer.get("value_num") is not None and len(items) < 3:
        unit = (titer.get("unit") or "").strip()
        u = f" {unit}" if unit else ""
        items.append(f"Titer {_fmt_num(titer['value_num'])}{u}")

    return items[:3]


def _fetch_measurements_for_record(db: Session, record_id: int, cols: dict, *, qc_mode: str = "all") -> list[dict]:
    """Fetch measurement rows for a record with deterministic ordering and optional QC filtering.

    qc_mode:
      - all: legacy behavior (exclude qc_flag if present)
      - model_safe: exclude ignore_for_model=1, ignore_policy!=include, and rejected/quarantined statuses
      - approved: require status==approved and ignore_for_model=0
    """
    if not cols:
        return []

    from sqlalchemy import text as _text

    qc_mode = (qc_mode or "all").strip().lower()
    if qc_mode not in ("all", "model_safe", "approved"):
        qc_mode = "all"

    where = [f"dm.{cols['record_fk']}=:rid"]
    params = {"rid": int(record_id)}

    # Legacy qc_flag filtering (kept for backwards compatibility).
    qc_col = cols.get("qc_flag")
    if qc_col:
        where.append(f"(dm.{qc_col} IS NULL OR dm.{qc_col}=0 OR dm.{qc_col}='0' OR dm.{qc_col}='')")

    # QC-aware selection (measurement_qc is optional; missing rows are treated as unreviewed/include).
    if qc_mode == "model_safe":
        if cols.get("ignore_for_model"):
            where.append(f"(dm.{cols['ignore_for_model']} IS NULL OR dm.{cols['ignore_for_model']}=0)")
        where.append("(mq.ignore_policy IS NULL OR mq.ignore_policy='include')")
        where.append("(mq.status IS NULL OR mq.status NOT IN ('rejected','quarantined'))")
    elif qc_mode == "approved":
        if cols.get("ignore_for_model"):
            where.append(f"(dm.{cols['ignore_for_model']} IS NULL OR dm.{cols['ignore_for_model']}=0)")
        where.append("mq.status='approved'")

    order = []
    if cols.get("is_primary"):
        order.append(f"dm.{cols['is_primary']} DESC")
    if cols.get("created_at"):
        order.append(f"dm.{cols['created_at']} DESC")
    if cols.get("id"):
        order.append(f"dm.{cols['id']} DESC")
    order.append(f"dm.{cols['name']} ASC")

    q = _text(
        f"""
        SELECT dm.*,
               mq.status AS qc_status,
               mq.ignore_policy AS qc_ignore_policy
        FROM data_measurements dm
        LEFT JOIN measurement_qc mq ON mq.measurement_id = dm.id
        WHERE {' AND '.join(where)}
        ORDER BY {', '.join(order)}
        """
    )
    rows = db.execute(q, params).mappings().all()

    out: list[dict] = []

    def get(r, k):
        c = cols.get(k)
        return r.get(c) if c else None

    for r in rows:
        out.append(
            {
                "id": get(r, "id") or r.get("id"),
                "record_id": int(record_id),
                "name": get(r, "name"),
                "value_num": get(r, "value_num"),
                "value_text": get(r, "value_text"),
                "unit": get(r, "unit"),
                "comparator": get(r, "comparator"),
                "is_primary": get(r, "is_primary") or 0,
                "qc_status": r.get("qc_status"),
                "qc_ignore_policy": r.get("qc_ignore_policy"),
            }
        )
    return out


def _latest_record_id(panel: dict) -> int | None:
    """Pick latest record id within a panel (run_date desc, created_at desc, id desc)."""
    best = None
    for _, conds in (panel.get("assays") or {}).items():
        for _, node in (conds or {}).items():
            runs = node.get("runs") or []
            for item in runs:
                r = item.get("record")
                if not r:
                    continue
                key = (0 if r.run_date else 1, str(r.run_date or ""), r.created_at, int(r.id))
                if best is None or key > best[0]:
                    best = (key, int(r.id))
    return best[1] if best else None


def _collect_record_ids_from_panels(panels: list[dict]) -> list[int]:
    ids: list[int] = []
    seen = set()
    for p in panels:
        for _, conds in (p.get("assays") or {}).items():
            for _, node in (conds or {}).items():
                for item in (node.get("runs") or []):
                    r = item.get("record")
                    if not r:
                        continue
                    rid = int(getattr(r, "id", 0) or 0)
                    if rid and rid not in seen:
                        seen.add(rid)
                        ids.append(rid)
    return ids


def _run_qc_summary_for_records(db: Session, record_ids: list[int], cols: dict) -> dict[int, dict]:
    """Return per-record QC rollups for measurement rows.

    Missing measurement_qc rows are treated as 'pending' (unreviewed).
    """
    if not record_ids or not cols:
        return {}

    from sqlalchemy import bindparam as _bindparam, text as _text

    record_ids = [int(rid) for rid in record_ids if rid]

    q = _text(
        f"""
        SELECT dm.{cols['record_fk']} AS rid,
               SUM(CASE WHEN mq.status='approved' THEN 1 ELSE 0 END) AS approved,
               SUM(CASE WHEN mq.status='rejected' THEN 1 ELSE 0 END) AS rejected,
               SUM(CASE WHEN mq.status='quarantined' THEN 1 ELSE 0 END) AS quarantined,
               SUM(CASE WHEN mq.status IS NULL OR mq.status='unreviewed' THEN 1 ELSE 0 END) AS pending,
               COUNT(1) AS total
        FROM data_measurements dm
        LEFT JOIN measurement_qc mq ON mq.measurement_id = dm.id
        WHERE dm.{cols['record_fk']} IN :record_ids
        GROUP BY dm.{cols['record_fk']}
        """
    ).bindparams(_bindparam("record_ids", expanding=True))
    rows = db.execute(q, {"record_ids": record_ids}).mappings().all()
    out: dict[int, dict] = {}
    for r in rows:
        rid = int(r.get("rid") or 0)
        if not rid:
            continue
        out[rid] = {
            "approved": int(r.get("approved") or 0),
            "rejected": int(r.get("rejected") or 0),
            "quarantined": int(r.get("quarantined") or 0),
            "pending": int(r.get("pending") or 0),
            "total": int(r.get("total") or 0),
        }
    return out


def get_molecule_batch_ui_context(
    db: Session,
    molecule_id: int,
    *,
    selected_batch_id: int | None = None,
    qc_mode: str = "all",
) -> dict:
    """Return batch-first molecule context with QC-aware headline metrics and run-level QC badges."""
    from sqlalchemy import text as _text
    from psi.core.models import DataRecord

    qc_mode = (qc_mode or "all").strip().lower()
    if qc_mode not in ("all", "model_safe", "approved"):
        qc_mode = "all"

    base = get_molecule_experimental_context(db, molecule_id, selected_batch_id=selected_batch_id)

    panels = list(base.get("exp_batch_panels") or [])
    batches = list(base.get("exp_batches") or [])
    unassigned = list(base.get("exp_molecule_level_records") or [])

    cols = _reflect_measurement_cols(db)

    # Totals for Data Overview.
    total_records = db.query(DataRecord).filter(DataRecord.molecule_id == molecule_id).count()
    total_measurements = 0
    outlier_count = None
    if cols:
        try:
            total_measurements = int(
                db.execute(
                    _text(
                        f"""
                        SELECT COUNT(1) AS n
                        FROM data_measurements dm
                        JOIN data_records dr ON dm.{cols['record_fk']} = dr.id
                        WHERE dr.molecule_id = :mid
                        """
                    ),
                    {"mid": molecule_id},
                ).mappings().first()["n"]
            )
        except Exception:
            total_measurements = 0

        if cols.get("is_outlier") and cols.get("is_outlier") in cols.get("_all", set()):
            try:
                outlier_count = int(
                    db.execute(
                        _text(
                            f"""
                            SELECT COUNT(1) AS n
                            FROM data_measurements dm
                            JOIN data_records dr ON dm.{cols['record_fk']} = dr.id
                            WHERE dr.molecule_id = :mid AND dm.{cols['is_outlier']}=1
                            """
                        ),
                        {"mid": molecule_id},
                    ).mappings().first()["n"]
                )
            except Exception:
                outlier_count = None

    # Deterministic batch ordering.
    panels.sort(key=lambda p: _batch_sort_key(getattr(p.get("batch"), "batch_id", "")))
    batches.sort(key=lambda b: _batch_sort_key(getattr(b, "batch_id", "")))

    # Stabilize run ordering (ensures refresh determinism).
    for p in panels:
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

    # Compute latest record ids for headline extraction.
    latest_by_panel: dict[int, int] = {}
    for idx, p in enumerate(panels):
        rid = _latest_record_id(p)
        if rid:
            latest_by_panel[idx] = int(rid)

    # Batch measurement counts in one query.
    meas_count_by_batch: dict[int, int] = {}
    if cols:
        try:
            rows = db.execute(
                _text(
                    f"""
                    SELECT dr.batch_id AS bid, COUNT(1) AS n
                    FROM data_measurements dm
                    JOIN data_records dr ON dm.{cols['record_fk']} = dr.id
                    WHERE dr.molecule_id = :mid AND dr.batch_id IS NOT NULL
                    GROUP BY dr.batch_id
                    """
                ),
                {"mid": molecule_id},
            ).mappings().all()
            for r in rows:
                bid = int(r.get("bid") or 0)
                if bid:
                    meas_count_by_batch[bid] = int(r.get("n") or 0)
        except Exception:
            meas_count_by_batch = {}

    # Run-level QC summaries (for small badges in tables).
    run_ids = _collect_record_ids_from_panels(panels)
    run_qc = _run_qc_summary_for_records(db, run_ids, cols)

    # Headline measurements and overview metric collection.
    batch_metric_values = {"purity": [], "kd": [], "titer": []}
    if cols:
        for idx, p in enumerate(panels):
            rid = latest_by_panel.get(idx)
            meas = _fetch_measurements_for_record(db, rid, cols, qc_mode=qc_mode) if rid else []
            headline_items = _headline_items_for_record(meas) if meas else []
            if not headline_items:
                headline_items = ["No measurements recorded"]
            p["headline_items"] = headline_items
            # attach per-batch measurement counts
            try:
                bid = int(getattr(p.get("batch"), "id", 0) or 0)
            except Exception:
                bid = 0
            p["measurement_count"] = meas_count_by_batch.get(bid) if bid else None

            purity = _best_measurement(meas, ["monomer_pct", "purity", "sec_purity", re.compile(r"\bmonomer\b")])
            kd = _best_measurement(meas, ["kd", "kd_nm", "kd_n", "affinity"])
            titer = _best_measurement(meas, ["titer", "expression", "yield", "concentration"])
            if purity and purity.get("value_num") is not None:
                batch_metric_values["purity"].append(float(purity["value_num"]))
            if kd and kd.get("value_num") is not None:
                batch_metric_values["kd"].append(float(kd["value_num"]))
            if titer and titer.get("value_num") is not None:
                batch_metric_values["titer"].append(float(titer["value_num"]))
    else:
        for p in panels:
            p.setdefault("headline_items", ["No measurements recorded"])
            p.setdefault("measurement_count", None)

    # Unassigned panel always last.
    if unassigned:
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
                "assays": {},
                "glance": {},
                "record_count": len(unassigned),
                "unassigned_records": unassigned,
                "headline_items": ["No batch assigned"],
                "measurement_count": None,
                "details_key": "batch:__unassigned__",
            }
        )

    panels_non = [p for p in panels if p.get("batch") is not None]
    panels_un = [p for p in panels if p.get("batch") is None]
    panels = panels_non + panels_un

    def _mean(vals: list[float]) -> float | None:
        if not vals:
            return None
        try:
            return float(sum(vals) / len(vals))
        except Exception:
            return None

    data_overview = {
        "total_batches": len(batches) + (1 if unassigned else 0),
        "total_records": int(total_records),
        "total_measurements": int(total_measurements),
        "mean_purity": _mean(batch_metric_values["purity"]),
        "mean_kd": _mean(batch_metric_values["kd"]),
        "mean_titer": _mean(batch_metric_values["titer"]),
        "outlier_count": outlier_count,
    }

    return {
        "exp_batches": batches,
        "exp_batch_panels": panels,
        "exp_has_unassigned": bool(unassigned),
        "data_overview": data_overview,
        "exp_qc_mode": qc_mode,
        "exp_run_qc": run_qc,
    }
