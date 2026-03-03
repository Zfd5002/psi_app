from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

from sqlalchemy.orm import Session

from psi.core.models import Molecule, Program, ReportRun
from psi.core.di.policy import sha256_hex_of_canonical_json
from psi.services.report_engine import (
    generate_molecule_comparative_report_v0,
    generate_molecule_report_v0,
    generate_program_comparative_report_v0,
    generate_program_report_v0,
    load_report_run_payload,
)
from psi.services.policy_upgrade import get_unacknowledged_upgrade_warnings
from psi.services.comparability import load_comparability_policy_latest
from psi.services.v3_ranking import load_ranking_policy_latest

_HEX64_RE = re.compile(r"\b[a-f0-9]{64}\b", flags=re.IGNORECASE)


def _parse_as_of(as_of_text: str | None) -> datetime:
    txt = str(as_of_text or "").strip()
    if not txt:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    txt = txt.replace("Z", "+00:00")
    dt = datetime.fromisoformat(txt)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _load_json(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _runtime_policy_versions_display() -> dict[str, str]:
    base = Path(__file__).resolve().parents[1] / "core" / "di" / "catalogs"
    template_cat = _load_json(base / "template_catalog_v0_1.json")
    comp = load_comparability_policy_latest()
    ranking = load_ranking_policy_latest()
    return {
        "template_catalog": str(template_cat.get("catalog_version") or ""),
        "comparability_policy": str(comp.get("policy_version") or ""),
        "ranking_policy": str(ranking.get("policy_version") or ""),
    }


def _clean_board_text(value: object) -> str:
    txt = str(value or "").strip()
    if not txt:
        return ""
    return _HEX64_RE.sub("[hash-hidden]", txt)


def _gate_status(gate: dict[str, object]) -> str:
    for k in ("status", "state", "result"):
        v = str(gate.get(k) or "").strip().lower()
        if v:
            return v
    return "not_assessed"


def _overall_from_snapshot(out: dict[str, object]) -> str:
    decision = str(out.get("decision_state") or "").strip().lower()
    if decision in {"ready", "pass", "approved"}:
        return "ready"
    if decision in {"blocked", "fail", "not_ready", "rejected"}:
        return "not_ready"
    readiness = out.get("readiness") if isinstance(out.get("readiness"), dict) else {}
    r_state = str(readiness.get("state") or "").strip().lower()
    if r_state:
        if r_state in {"ready", "pass", "approved"}:
            return "ready"
        if r_state in {"blocked", "fail", "not_ready", "rejected"}:
            return "not_ready"
    return "not_assessed"


def _is_failing_gate_status(status: str) -> bool:
    st = str(status or "").strip().lower()
    return st in {"fail", "failed", "blocked", "not_ready", "reject", "rejected"}


def _cell_from_metric_refs(value: object) -> str:
    refs = value if isinstance(value, list) else []
    if not refs:
        return "not run"
    first = refs[0] if refs and isinstance(refs[0], dict) else {}
    if isinstance(first, dict):
        val_num = first.get("value_num")
        unit = str(first.get("unit") or "").strip()
        if val_num is not None:
            return f"{val_num}{(' ' + unit) if unit else ''}".strip()
        val_text = str(first.get("value_text") or "").strip()
        if val_text:
            return val_text
    return f"{len(refs)} cited"


def build_molecule_board_display_from_payload(*, row: ReportRun, payload: dict) -> dict[str, object]:
    sections = payload.get("sections") if isinstance(payload.get("sections"), dict) else {}
    identity = sections.get("identity_context") if isinstance(sections.get("identity_context"), dict) else {}
    stage = sections.get("stage_determination") if isinstance(sections.get("stage_determination"), dict) else {}
    drift = sections.get("drift_history") if isinstance(sections.get("drift_history"), dict) else {}
    comp_det = drift.get("comparability_determination") if isinstance(drift.get("comparability_determination"), dict) else {}
    repro = sections.get("reproducibility_appendix") if isinstance(sections.get("reproducibility_appendix"), dict) else {}
    risk_profile = sections.get("risk_profile") if isinstance(sections.get("risk_profile"), dict) else {}
    gaps = sections.get("experimental_gaps") if isinstance(sections.get("experimental_gaps"), dict) else {}
    fact = sections.get("fact_sheet") if isinstance(sections.get("fact_sheet"), dict) else {}
    batch_registry = fact.get("batch_registry") if isinstance(fact.get("batch_registry"), list) else []
    matrix = fact.get("metric_matrix") if isinstance(fact.get("metric_matrix"), dict) else {}
    metrics_idx = fact.get("metrics_index") if isinstance(fact.get("metrics_index"), dict) else {}
    coverage = fact.get("coverage_summary") if isinstance(fact.get("coverage_summary"), dict) else {}
    best = fact.get("best_batch") if isinstance(fact.get("best_batch"), dict) else {}
    stability = fact.get("stability") if isinstance(fact.get("stability"), dict) else {}

    batch_cols = matrix.get("batch_columns") if isinstance(matrix.get("batch_columns"), list) else []
    matrix_rows = matrix.get("rows") if isinstance(matrix.get("rows"), list) else []
    descriptor_by_key = {
        str(d.get("metric_key") or ""): d
        for d in (metrics_idx.get("metrics") if isinstance(metrics_idx.get("metrics"), list) else [])
        if isinstance(d, dict) and str(d.get("metric_key") or "").strip()
    }
    fact_rows = []
    for row_obj in matrix_rows:
        if not isinstance(row_obj, dict):
            continue
        mk = str(row_obj.get("metric_key") or "").strip()
        desc = descriptor_by_key.get(mk, {})
        cells = row_obj.get("cells") if isinstance(row_obj.get("cells"), list) else []
        fact_rows.append(
            {
                "metric_key": mk,
                "metric_group": str(desc.get("group") or "Other"),
                "cells": [str((c.get("display") if isinstance(c, dict) else "") or "not run") for c in cells],
            }
        )

    risk_flags = risk_profile.get("risk_flags_enriched") if isinstance(risk_profile.get("risk_flags_enriched"), list) else []
    governance_warnings = repro.get("governance_red_flags") if isinstance(repro.get("governance_red_flags"), list) else []
    missing_metrics = sorted(str(x) for x in (comp_det.get("missing_inputs", {}).get("required_measurement_keys_missing") if isinstance(comp_det.get("missing_inputs"), dict) else []) if str(x).strip())
    risk_qc_bullets: list[str] = []
    if missing_metrics:
        risk_qc_bullets.append("Missing required metrics: " + ", ".join(missing_metrics))
    if risk_flags:
        ordered_flags = sorted(
            [rf for rf in risk_flags if isinstance(rf, dict)],
            key=lambda r: (str(r.get("severity") or ""), str(r.get("key") or "")),
        )
        risk_qc_bullets.append(
            "Risk flags: "
            + ", ".join(
                f"{str(r.get('severity') or 'unknown').upper()}:{str(r.get('key') or 'unknown')}"
                for r in ordered_flags
            )
        )
    if governance_warnings:
        risk_qc_bullets.append(
            "Governance warnings: "
            + ", ".join(sorted(str(w.get("flag_code") or "warning") for w in governance_warnings if isinstance(w, dict)))
        )
    if not risk_qc_bullets:
        risk_qc_bullets.append("No major risk or QC warnings captured by this surface.")

    notes: list[dict[str, object]] = []
    normalized_batch_registry: list[dict[str, object]] = []
    for br in batch_registry:
        if not isinstance(br, dict):
            continue
        normalized_batch_registry.append(
            {
                "batch_id": br.get("batch_id"),
                "batch_label": str(br.get("batch_label") or ""),
                "batch_date": str(br.get("batch_date") or "unknown"),
                "producer": str(br.get("producer") or "unknown"),
                "purpose_notes": str(br.get("purpose_notes") or "unknown"),
                "coverage_summary": str(br.get("data_coverage_summary") or br.get("coverage_summary") or "none"),
            }
        )
        txt = str(br.get("latest_notes") or "").strip()
        if not txt:
            continue
        notes.append(
            {
                "record_id": 0,
                "author": "local-user",
                "timestamp": "",
                "scope": str(br.get("batch_label") or "molecule"),
                "body": _clean_board_text(txt),
            }
        )

    readiness = str(stage.get("decision_state") or stage.get("readiness_state") or "not_assessed").strip() or "not_assessed"
    blockers = [str(x).strip() for x in (gaps.get("blockers") if isinstance(gaps.get("blockers"), list) else []) if str(x).strip()]
    comp_status = str(comp_det.get("category") or "not_assessed")
    warnings_compact = sorted(str(w.get("flag_code") or "") for w in governance_warnings if isinstance(w, dict) and str(w.get("flag_code") or "").strip())
    best_label = "unknown"
    best_id = best.get("selected_batch_id")
    if best_id is not None:
        for br in batch_registry:
            if isinstance(br, dict) and br.get("batch_id") == best_id:
                best_label = str(br.get("batch_label") or best_id)
                break
    executive_paragraph = (
        f"Readiness is {readiness.replace('_', ' ')}; stability is {str(stability.get('status') or 'uncomputed').replace('_', ' ').lower()}; "
        f"comparability is {comp_status.replace('_', ' ')}; "
        + (("blockers include " + ", ".join(blockers[:3]) + "; ") if blockers else "no explicit blockers were recorded; ")
        + (("governance warnings: " + ", ".join(warnings_compact[:3]) + ".") if warnings_compact else "no governance warnings were recorded.")
    )

    return {
        "header": {
            "molecule": _clean_board_text(identity.get("primary_id") or identity.get("title") or f"molecule_id={identity.get('molecule_id') or ''}"),
            "program": (f"program_id={identity.get('program_id')}" if identity.get("program_id") is not None else "unknown"),
            "decision_template": _clean_board_text(payload.get("metadata", {}).get("report_type") if isinstance(payload.get("metadata"), dict) else row.report_type),
            "policy_version": _clean_board_text(repro.get("catalog_versions", {}).get("comparability_policy") if isinstance(repro.get("catalog_versions"), dict) else "unknown"),
            "snapshot_id": (int(identity.get("snapshot_id")) if str(identity.get("snapshot_id") or "").isdigit() else None),
            "generated_at": (row.created_at.isoformat() if row.created_at is not None else ""),
        },
        "conclusions": {
            "readiness_status": readiness,
            "best_overall_batch": best_label,
            "comparability_status": comp_status,
            "confidence": _clean_board_text(sections.get("confidence_decomposition", {}).get("confidence", {}).get("overall") if isinstance(sections.get("confidence_decomposition"), dict) else ""),
            "stability_status": str(stability.get("status") or "uncomputed").upper(),
            "blockers": blockers,
            "governance_warnings": warnings_compact,
            "executive_paragraph": _clean_board_text(executive_paragraph),
            "stability_rationale": [str(x) for x in (stability.get("rationale") if isinstance(stability.get("rationale"), list) else []) if str(x).strip()],
        },
        "batch_registry": normalized_batch_registry,
        "gate_summary": {
            "best_batch_rows": [],
            "per_batch_rows": [],
        },
        "fact_sheet": {
            "batch_labels": [str(c.get("batch_label") or "") for c in batch_cols if isinstance(c, dict)],
            "metric_rows": fact_rows,
        },
        "comparability": {
            "effective_status": _clean_board_text(comp_det.get("category") or "not_assessed"),
            "resolved_status": _clean_board_text(comp_det.get("category") or "not_assessed"),
            "rule_id": _clean_board_text(comp_det.get("rule_id") or "not_available"),
            "as_of_basis": _clean_board_text(payload.get("metadata", {}).get("as_of") if isinstance(payload.get("metadata"), dict) else ""),
            "policy_ref": _clean_board_text(repro.get("catalog_versions", {}).get("comparability_policy") if isinstance(repro.get("catalog_versions"), dict) else "unknown"),
            "governance_warnings": warnings_compact,
        },
        "risk_qc": {
            "bullets": risk_qc_bullets,
            "coverage_summary": coverage,
        },
        "scientist_notes": notes,
    }


def _build_molecule_board_display(
    db: Session,
    *,
    row: ReportRun,
    payload: dict,
    subject_ids: list[int],
    snapshot_coverage: list[int],
) -> dict[str, object]:
    _ = (db, subject_ids, snapshot_coverage)  # rendering is payload-only for fact-sheet replayability
    if str(row.report_type or "") != "molecule_report":
        return {}
    return build_molecule_board_display_from_payload(row=row, payload=payload)


def _format_molecule_row_label(row: dict) -> str:
    primary_id = _clean_board_text(row.get("primary_id"))
    title = _clean_board_text(row.get("title"))
    molecule_id = row.get("molecule_id")
    if primary_id and title:
        return f"{primary_id} ({title})"
    if primary_id:
        return primary_id
    if title:
        return title
    if molecule_id is not None:
        return f"molecule_id={molecule_id}"
    return ""


def _program_name_map(db: Session, program_ids: list[int]) -> dict[int, str]:
    pids = sorted({int(x) for x in program_ids})
    if not pids:
        return {}
    rows = (
        db.query(Program.id, Program.name)
        .filter(Program.id.in_(pids))
        .order_by(Program.id.asc())
        .all()
    )
    return {int(r[0]): _clean_board_text(r[1]) for r in rows}


def build_report_identity_summary(
    db: Session,
    *,
    report_type: str,
    payload: dict,
    subject_ids: list[int],
    snapshot_coverage: list[int],
) -> str:
    sections = payload.get("sections") if isinstance(payload.get("sections"), dict) else {}
    if not isinstance(sections, dict):
        return "missing"
    identity = sections.get("identity_context") if isinstance(sections.get("identity_context"), dict) else {}
    if identity:
        primary_id = _clean_board_text(identity.get("primary_id"))
        title = _clean_board_text(identity.get("title"))
        molecule_id = identity.get("molecule_id")
        out: list[str] = []
        if primary_id and title:
            out.append(f"{primary_id} ({title})")
        elif primary_id:
            out.append(primary_id)
        elif title:
            out.append(title)
        elif molecule_id is not None:
            out.append(f"molecule_id={molecule_id}")
        if identity.get("program_id") is not None:
            out.append(f"program_id={identity.get('program_id')}")
        if identity.get("snapshot_id") is not None:
            out.append(f"snapshot_id={identity.get('snapshot_id')}")
        txt = " · ".join([x for x in out if x])
        return txt if txt else "missing"
    if report_type == "molecule_comparative_report":
        rows = (
            sections.get("molecule_set", {}).get("rows")
            if isinstance(sections.get("molecule_set"), dict)
            else []
        )
        labels = [_format_molecule_row_label(r) for r in (rows if isinstance(rows, list) else []) if isinstance(r, dict)]
        labels = [x for x in labels if x]
        if labels:
            return ", ".join(labels)
    if report_type == "program_comparative_report":
        rows = (
            sections.get("program_set", {}).get("rows")
            if isinstance(sections.get("program_set"), dict)
            else []
        )
        ids = [int(r.get("program_id")) for r in (rows if isinstance(rows, list) else []) if isinstance(r, dict) and r.get("program_id") is not None]
        names = _program_name_map(db, ids)
        labels: list[str] = []
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict) or r.get("program_id") is None:
                continue
            pid = int(r.get("program_id"))
            pname = names.get(pid, "")
            if pname:
                labels.append(f"{pname} (program_id={pid})")
            else:
                labels.append(f"Program #{pid}")
        if labels:
            return ", ".join(labels)
    if report_type == "program_report":
        pid = None
        meta = sections.get("metadata") if isinstance(sections.get("metadata"), dict) else {}
        if isinstance(meta, dict) and meta.get("program_id") is not None:
            pid = int(meta.get("program_id"))
        elif subject_ids:
            pid = int(subject_ids[0])
        if pid is not None:
            name = _program_name_map(db, [pid]).get(pid, "")
            if name:
                return f"{name} (program_id={pid})"
            return f"program_id={pid}"
    if report_type == "molecule_report" and subject_ids:
        mol = db.get(Molecule, int(subject_ids[0]))
        if mol is not None:
            label = _format_molecule_row_label({"primary_id": mol.primary_id, "title": mol.title, "molecule_id": mol.id})
            if label:
                return label
    if subject_ids:
        return ", ".join(str(int(x)) for x in subject_ids)
    if snapshot_coverage:
        return f"snapshots={len(snapshot_coverage)}"
    return "missing"


def get_v3_report_policy_pins(report_type: str) -> dict:
    base = Path(__file__).resolve().parents[1] / "core" / "di" / "catalogs"
    template_cat = _load_json(base / "template_catalog_v0_1.json")
    comparability_pol = load_comparability_policy_latest()
    ranking_pol = _load_json(base / "ranking_policy_v0_2.json")
    pins = {
        "report_type": str(report_type),
        "shortlisting_policy": {
            "status": "deprecated_non_executable",
            "allow_shortlisting": False,
            "effective_version": "v1.3.0a48",
        },
        "template_catalog": {
            "catalog_id": str(template_cat.get("catalog_id") or ""),
            "catalog_version": str(template_cat.get("catalog_version") or ""),
            "catalog_hash": sha256_hex_of_canonical_json(template_cat),
        },
        "comparability_policy": {
            "policy_id": str(comparability_pol.get("policy_id") or ""),
            "policy_version": str(comparability_pol.get("policy_version") or ""),
            "policy_hash": sha256_hex_of_canonical_json(comparability_pol),
        },
        "ranking_policy": {
            "policy_id": str(ranking_pol.get("policy_id") or ""),
            "policy_version": str(ranking_pol.get("policy_version") or ""),
            "policy_hash": sha256_hex_of_canonical_json(ranking_pol),
            "enabled": bool(ranking_pol.get("enabled")),
        },
    }
    return {k: pins[k] for k in sorted(pins.keys())}


def generate_report_from_form(
    db: Session,
    *,
    report_type: str,
    subject_ids_text: str,
    as_of_text: str | None,
) -> ReportRun:
    ids = sorted({int(x.strip()) for x in str(subject_ids_text or "").split(",") if x.strip()})
    if not ids:
        raise ValueError("subject_ids must include at least one integer id")
    if report_type in {"molecule_comparative_report", "program_comparative_report"} and not (2 <= len(ids) <= 5):
        raise ValueError(f"{report_type} requires 2-5 subject ids")
    as_of = _parse_as_of(as_of_text)
    policy_pins = get_v3_report_policy_pins(report_type)

    def _run() -> ReportRun:
        if report_type == "molecule_report":
            if len(ids) != 1:
                raise ValueError("molecule_report requires exactly 1 subject id")
            return generate_molecule_report_v0(db, molecule_id=ids[0], as_of=as_of, policy_pins=policy_pins)
        if report_type == "program_report":
            if len(ids) != 1:
                raise ValueError("program_report requires exactly 1 subject id")
            return generate_program_report_v0(db, program_id=ids[0], as_of=as_of, policy_pins=policy_pins)
        if report_type == "molecule_comparative_report":
            return generate_molecule_comparative_report_v0(db, molecule_ids=ids, as_of=as_of, policy_pins=policy_pins)
        if report_type == "program_comparative_report":
            return generate_program_comparative_report_v0(db, program_ids=ids, as_of=as_of, policy_pins=policy_pins)
        raise ValueError("Unsupported report_type")

    return _run()


def list_report_runs(db: Session) -> list[ReportRun]:
    return db.query(ReportRun).order_by(ReportRun.created_at.desc(), ReportRun.id.desc()).limit(100).all()


def list_report_program_options(db: Session) -> list[dict]:
    rows = db.query(Program).order_by(Program.id.asc()).all()
    out = [{"id": int(r.id), "name": str(r.name or "")} for r in rows]
    return out


def list_report_molecule_options(db: Session, *, program_id: int) -> list[dict]:
    rows = (
        db.query(Molecule)
        .filter(Molecule.program_id == int(program_id))
        .order_by(Molecule.primary_id.asc(), Molecule.id.asc())
        .all()
    )
    out = [
        {
            "id": int(r.id),
            "primary_id": str(r.primary_id or ""),
            "title": str(r.title or ""),
            "program_id": int(r.program_id),
        }
        for r in rows
    ]
    return out


def get_report_run_detail(db: Session, report_run_id: int) -> dict:
    row = db.get(ReportRun, int(report_run_id))
    if row is None:
        raise KeyError("ReportRun not found")
    payload = load_report_run_payload(row)
    try:
        subject_ids = json.loads(row.subject_ids_json or "[]")
    except Exception:
        subject_ids = []
    try:
        policy_pins = json.loads(row.policy_pins_json or "{}")
    except Exception:
        policy_pins = {}
    try:
        snapshot_cov = json.loads(row.snapshot_coverage_json or "[]")
    except Exception:
        snapshot_cov = []
    policy_pin_summary = []
    if isinstance(policy_pins, dict):
        for k in sorted(policy_pins.keys(), key=lambda x: str(x)):
            v = policy_pins.get(k)
            if isinstance(v, dict):
                policy_pin_summary.append(
                    {
                        "pin_key": str(k),
                        "version": str(v.get("policy_version") or v.get("catalog_version") or ""),
                        "hash": str(v.get("policy_hash") or v.get("catalog_hash") or ""),
                    }
                )
            else:
                policy_pin_summary.append({"pin_key": str(k), "version": str(v), "hash": ""})
    rule_ids: set[str] = set()
    measurement_keys: set[str] = set()
    snapshot_refs: set[int] = set()
    sections = payload.get("sections") if isinstance(payload.get("sections"), dict) else {}
    for sec in sections.values():
        if not isinstance(sec, dict):
            continue
        if isinstance(sec.get("assessments"), list):
            for row_obj in sec.get("assessments"):
                if isinstance(row_obj, dict):
                    if str(row_obj.get("rule_id") or "").strip():
                        rule_ids.add(str(row_obj.get("rule_id")))
                    for mk in (row_obj.get("cited_measurement_keys") or []):
                        if str(mk).strip():
                            measurement_keys.add(str(mk))
                    for sid in (row_obj.get("cited_snapshot_ids") or []):
                        try:
                            snapshot_refs.add(int(sid))
                        except Exception:
                            pass
        if isinstance(sec.get("rows"), list):
            for row_obj in sec.get("rows"):
                if isinstance(row_obj, dict) and isinstance(row_obj.get("reason_trail"), list):
                    for rr in row_obj.get("reason_trail"):
                        if isinstance(rr, dict) and str(rr.get("policy_rule_id") or "").strip():
                            rule_ids.add(str(rr.get("policy_rule_id")))
        if isinstance(sec.get("rollup"), dict):
            rc = sec.get("rollup", {}).get("rollup_citations")
            if isinstance(rc, dict):
                for mk in (rc.get("measurement_keys") or []):
                    if str(mk).strip():
                        measurement_keys.add(str(mk))
                for sid in (rc.get("snapshot_ids") or []):
                    try:
                        snapshot_refs.add(int(sid))
                    except Exception:
                        pass
    for sid in snapshot_cov if isinstance(snapshot_cov, list) else []:
        try:
            snapshot_refs.add(int(sid))
        except Exception:
            pass
    report_type = str(getattr(row, "report_type", "") or "")
    identity_summary = build_report_identity_summary(
        db,
        report_type=report_type,
        payload=payload,
        subject_ids=[int(x) for x in subject_ids if str(x).strip().isdigit()],
        snapshot_coverage=[int(x) for x in snapshot_cov if str(x).strip().isdigit()],
    )
    molecule_board_display = _build_molecule_board_display(
        db,
        row=row,
        payload=payload,
        subject_ids=[int(x) for x in subject_ids if str(x).strip().isdigit()],
        snapshot_coverage=[int(x) for x in snapshot_cov if str(x).strip().isdigit()],
    )
    return {
        "report_run": row,
        "payload": payload,
        "subject_ids": subject_ids,
        "identity_summary": identity_summary,
        "molecule_board_display": molecule_board_display,
        "policy_pins": policy_pins,
        "policy_pin_summary": policy_pin_summary,
        "runtime_policy_versions": _runtime_policy_versions_display(),
        "rule_ids": sorted(rule_ids),
        "measurement_key_citations": sorted(measurement_keys),
        "evidence_snapshot_refs": sorted(snapshot_refs),
        "snapshot_coverage": snapshot_cov,
        "governance_warnings": get_unacknowledged_upgrade_warnings(db, current_policy_pins=policy_pins),
    }


def _extract_determination_surface(payload: dict) -> dict[str, str]:
    sections = payload.get("sections") if isinstance(payload.get("sections"), dict) else {}
    out: dict[str, str] = {}
    if not isinstance(sections, dict):
        return out
    drift = sections.get("drift_history") if isinstance(sections.get("drift_history"), dict) else {}
    if isinstance(drift.get("comparability_determination"), dict):
        det = drift.get("comparability_determination") or {}
        out["comparability.category"] = str(det.get("category") or "")
        out["comparability.rule_id"] = str(det.get("rule_id") or "")
    stage = sections.get("stage_determination") if isinstance(sections.get("stage_determination"), dict) else {}
    posture = stage.get("program_posture") if isinstance(stage.get("program_posture"), dict) else {}
    if posture:
        out["posture.state"] = str(posture.get("posture_state") or "")
        out["posture.rule_id"] = str(posture.get("rule_id") or "")
    ranking = sections.get("ranking_surface") if isinstance(sections.get("ranking_surface"), dict) else {}
    if ranking:
        out["ranking.enabled"] = str(bool(ranking.get("enabled"))).lower()
        out["ranking.status"] = str(ranking.get("status") or "")
        out["ranking.reason"] = str(ranking.get("reason") or "")
    nbe = sections.get("next_best_experiments") if isinstance(sections.get("next_best_experiments"), dict) else {}
    if nbe:
        out["next_best_experiments.status"] = str(nbe.get("status") or "")
    return {k: out[k] for k in sorted(out.keys())}


def build_report_upgrade_delta_view(db: Session, *, base_report_run_id: int, candidate_report_run_id: int) -> dict[str, object]:
    base_row = db.get(ReportRun, int(base_report_run_id))
    cand_row = db.get(ReportRun, int(candidate_report_run_id))
    if base_row is None or cand_row is None:
        raise KeyError("ReportRun not found")
    base_payload = load_report_run_payload(base_row)
    cand_payload = load_report_run_payload(cand_row)
    try:
        base_pins = json.loads(base_row.policy_pins_json or "{}")
    except Exception:
        base_pins = {}
    try:
        cand_pins = json.loads(cand_row.policy_pins_json or "{}")
    except Exception:
        cand_pins = {}
    try:
        base_snaps = sorted({int(x) for x in json.loads(base_row.snapshot_coverage_json or "[]") if str(x).strip().isdigit()})
    except Exception:
        base_snaps = []
    try:
        cand_snaps = sorted({int(x) for x in json.loads(cand_row.snapshot_coverage_json or "[]") if str(x).strip().isdigit()})
    except Exception:
        cand_snaps = []

    base_surface = _extract_determination_surface(base_payload)
    cand_surface = _extract_determination_surface(cand_payload)
    surface_keys = sorted(set(base_surface.keys()) | set(cand_surface.keys()))
    surface_rows = []
    for key in surface_keys:
        old = str(base_surface.get(key) or "")
        new = str(cand_surface.get(key) or "")
        changed = old != new
        surface_rows.append({"key": f"surface:{key}", "old": old, "new": new, "changed": changed})

    pin_keys = sorted(set((base_pins.keys() if isinstance(base_pins, dict) else [])) | set((cand_pins.keys() if isinstance(cand_pins, dict) else [])), key=lambda x: str(x))
    pin_rows = []
    for key in pin_keys:
        b = base_pins.get(key) if isinstance(base_pins, dict) else None
        c = cand_pins.get(key) if isinstance(cand_pins, dict) else None
        b_obj = b if isinstance(b, dict) else {}
        c_obj = c if isinstance(c, dict) else {}
        b_ver = str(b_obj.get("policy_version") or b_obj.get("catalog_version") or b or "")
        c_ver = str(c_obj.get("policy_version") or c_obj.get("catalog_version") or c or "")
        b_hash = str(b_obj.get("policy_hash") or b_obj.get("catalog_hash") or "")
        c_hash = str(c_obj.get("policy_hash") or c_obj.get("catalog_hash") or "")
        pin_rows.append(
            {
                "pin_key": str(key),
                "base_version": b_ver,
                "candidate_version": c_ver,
                "base_hash": b_hash,
                "candidate_hash": c_hash,
                "changed": (b_ver != c_ver or b_hash != c_hash),
            }
        )

    pin_change_rows = [
        {
            "key": f"pin:{r['pin_key']}",
            "old": f"{r['base_version']}|{r['base_hash']}",
            "new": f"{r['candidate_version']}|{r['candidate_hash']}",
            "changed": bool(r["changed"]),
        }
        for r in pin_rows
    ]
    all_rows = sorted(surface_rows + pin_change_rows, key=lambda r: str(r.get("key") or ""))
    changed_rows = [r for r in all_rows if bool(r.get("changed"))]
    unchanged_rows = [r for r in all_rows if not bool(r.get("changed"))]
    executive = [
        f"Compared report runs {int(base_row.id)} -> {int(cand_row.id)}.",
        f"Changed rows: {len(changed_rows)}.",
        f"Unchanged rows: {len(unchanged_rows)}.",
    ]
    return {
        "schema_id": "report_upgrade_delta_view_v1",
        "schema_version": "v1",
        "header": {
            "base_report_run_id": int(base_row.id),
            "candidate_report_run_id": int(cand_row.id),
            "base_report_type": str(base_row.report_type or ""),
            "candidate_report_type": str(cand_row.report_type or ""),
            "changed_key_count": len(changed_rows),
        },
        "executive_summary_bullets": {"categorical": executive},
        "change_table": {"rows": changed_rows},
        "unchanged_table": {"rows": unchanged_rows},
        "policy_pin_comparison": {"rows": pin_rows},
        "appendix": {
            "comparison_citations": {
                "base_report_run_id": int(base_row.id),
                "candidate_report_run_id": int(cand_row.id),
                "base_snapshot_ids": base_snaps,
                "candidate_snapshot_ids": cand_snaps,
            },
            "base_policy_pins": base_pins if isinstance(base_pins, dict) else {},
            "candidate_policy_pins": cand_pins if isinstance(cand_pins, dict) else {},
            "surface_rows": surface_rows,
        },
    }
