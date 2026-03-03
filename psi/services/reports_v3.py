from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

from sqlalchemy.orm import Session

from psi.core.models import Batch, DataRecord, DecisionSnapshot, Molecule, Program, ReportRun
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
from psi.services.di.util import is_di_snapshot_record

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


def _safe_json_dict(raw: str | None) -> dict[str, object]:
    try:
        obj = json.loads(raw or "{}")
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _metric_group_for_key(metric_key: str) -> str:
    mk = str(metric_key or "").strip().lower()
    if not mk:
        return "Other"
    if "sec" in mk or "hmw" in mk or "lmw" in mk or "monomer" in mk:
        return "SEC"
    if "sds" in mk or "ce-sds" in mk or "cesds" in mk:
        return "SDS"
    if "dsf" in mk or "tm" in mk:
        return "DSF"
    if "endo" in mk or "lal" in mk:
        return "Endotoxin"
    if "pk" in mk or "pd" in mk:
        return "PK/PD"
    if "ec50" in mk or "ic50" in mk or "potency" in mk or "kd" in mk:
        return "Assay"
    return "Other"


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


def _build_molecule_board_display(
    db: Session,
    *,
    row: ReportRun,
    payload: dict,
    subject_ids: list[int],
    snapshot_coverage: list[int],
) -> dict[str, object]:
    if str(row.report_type or "") != "molecule_report" or not subject_ids:
        return {}
    molecule_id = int(subject_ids[0])
    as_of = row.as_of
    sections = payload.get("sections") if isinstance(payload.get("sections"), dict) else {}
    identity = sections.get("identity_context") if isinstance(sections.get("identity_context"), dict) else {}
    stage = sections.get("stage_determination") if isinstance(sections.get("stage_determination"), dict) else {}
    drift = sections.get("drift_history") if isinstance(sections.get("drift_history"), dict) else {}
    comp_det = drift.get("comparability_determination") if isinstance(drift.get("comparability_determination"), dict) else {}
    repro = sections.get("reproducibility_appendix") if isinstance(sections.get("reproducibility_appendix"), dict) else {}
    risk_profile = sections.get("risk_profile") if isinstance(sections.get("risk_profile"), dict) else {}
    gaps = sections.get("experimental_gaps") if isinstance(sections.get("experimental_gaps"), dict) else {}

    snaps = (
        db.query(DecisionSnapshot)
        .filter(DecisionSnapshot.molecule_id == int(molecule_id))
        .filter(DecisionSnapshot.created_at <= as_of)
        .order_by(DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc())
        .all()
    )
    di_snaps: list[tuple[DecisionSnapshot, dict[str, object]]] = []
    for snap in snaps:
        out = _safe_json_dict(snap.outputs_json)
        inn = _safe_json_dict(snap.inputs_json)
        if is_di_snapshot_record(snap, out, inn):
            di_snaps.append((snap, out))

    latest_by_batch: dict[int | None, tuple[DecisionSnapshot, dict[str, object]]] = {}
    for snap, out in di_snaps:
        bid = int(snap.batch_id) if snap.batch_id is not None else None
        if bid not in latest_by_batch:
            latest_by_batch[bid] = (snap, out)

    batch_ids = sorted({int(bid) for bid in latest_by_batch.keys() if bid is not None})
    batches_by_id = {
        int(b.id): b
        for b in (
            db.query(Batch)
            .filter(Batch.id.in_(batch_ids))
            .order_by(Batch.id.asc())
            .all()
            if batch_ids
            else []
        )
    }

    run_date_by_batch: dict[int, str] = {}
    if batch_ids:
        dr_rows = (
            db.query(DataRecord.batch_id, DataRecord.run_date, DataRecord.created_at, DataRecord.id)
            .filter(DataRecord.molecule_id == int(molecule_id))
            .filter(DataRecord.batch_id.in_(batch_ids))
            .order_by(DataRecord.created_at.desc(), DataRecord.id.desc())
            .all()
        )
        for bid, run_date, _created_at, _rid in dr_rows:
            if bid is None:
                continue
            ibid = int(bid)
            if ibid not in run_date_by_batch and str(run_date or "").strip():
                run_date_by_batch[ibid] = str(run_date)

    batch_rows: list[dict[str, object]] = []
    per_batch_gate_rows: list[dict[str, object]] = []
    batch_metric_map: dict[str, dict[str, str]] = {}
    all_metric_keys: set[str] = set()

    for bid, (snap, out) in latest_by_batch.items():
        bobj = batches_by_id.get(int(bid)) if bid is not None else None
        batch_label = str(bobj.batch_id or "") if bobj is not None else ""
        if not batch_label:
            batch_label = f"batch_id={int(bid)}" if bid is not None else "unassigned"
        batch_date = "unknown"
        if bid is not None and int(bid) in run_date_by_batch:
            batch_date = run_date_by_batch[int(bid)]
        elif snap.created_at is not None:
            batch_date = snap.created_at.isoformat()
        producer = "unknown"
        purpose = _clean_board_text((bobj.title if bobj is not None else "") or (bobj.expression_notes if bobj is not None else "") or (bobj.purification_notes if bobj is not None else "") or "unknown")

        used = out.get("used_by_metric") if isinstance(out.get("used_by_metric"), dict) else {}
        metric_keys = sorted(str(k).strip() for k in used.keys() if str(k).strip())
        for mk in metric_keys:
            all_metric_keys.add(mk)
        coverage_groups = sorted({_metric_group_for_key(mk) for mk in metric_keys}, key=lambda x: str(x))
        coverage_summary = ", ".join(coverage_groups) if coverage_groups else "none"

        gates = out.get("gates") if isinstance(out.get("gates"), list) else []
        normalized_gates = []
        fail_gates: list[str] = []
        missing_gates: list[str] = []
        for g in gates:
            if not isinstance(g, dict):
                continue
            gkey = str(g.get("gate_key") or g.get("key") or "").strip() or "unknown_gate"
            gstatus = _gate_status(g)
            if _is_failing_gate_status(gstatus):
                fail_gates.append(gkey)
            if gstatus in {"missing", "not_assessed", "unknown"}:
                missing_gates.append(gkey)
            normalized_gates.append(
                {
                    "gate_key": gkey,
                    "status": gstatus,
                    "primary_evidence": _clean_board_text(g.get("primary_evidence") or g.get("evidence") or "Not available"),
                    "notes": _clean_board_text(g.get("notes") or ""),
                }
            )
        normalized_gates = sorted(normalized_gates, key=lambda x: str(x.get("gate_key") or ""))
        fail_gates = sorted(set(fail_gates))
        missing_gates = sorted(set(missing_gates))
        overall = _overall_from_snapshot(out)

        for mk in metric_keys:
            cell = _cell_from_metric_refs(used.get(mk))
            batch_metric_map.setdefault(mk, {})[batch_label] = cell

        batch_rows.append(
            {
                "batch_id": int(bid) if bid is not None else None,
                "batch_label": batch_label,
                "batch_date": batch_date,
                "producer": producer,
                "purpose_notes": purpose,
                "coverage_summary": coverage_summary,
                "snapshot_id": int(snap.id),
                "overall": overall,
                "gates": normalized_gates,
                "metric_keys": metric_keys,
            }
        )
        per_batch_gate_rows.append(
            {
                "batch_label": batch_label,
                "overall": overall,
                "fail_gates": fail_gates,
                "missing_gates": missing_gates,
            }
        )

    batch_rows = sorted(
        batch_rows,
        key=lambda r: (
            str(r.get("batch_date") or ""),
            int(r.get("batch_id") or 0),
            str(r.get("batch_label") or ""),
        ),
        reverse=True,
    )
    per_batch_gate_rows = sorted(
        per_batch_gate_rows,
        key=lambda r: (
            str(next((b.get("batch_date") for b in batch_rows if b.get("batch_label") == r.get("batch_label")), "")),
            str(r.get("batch_label") or ""),
        ),
        reverse=True,
    )

    best_batch_id_from_payload = None
    for source in (stage, repro):
        if not isinstance(source, dict):
            continue
        cand = source.get("best_batch_id")
        if str(cand or "").strip().isdigit():
            best_batch_id_from_payload = int(cand)
            break
    best_row = None
    if best_batch_id_from_payload is not None:
        best_row = next((r for r in batch_rows if r.get("batch_id") == best_batch_id_from_payload), None)
    if best_row is None:
        best_row = next((r for r in batch_rows if str(r.get("overall") or "") == "ready"), None)
    if best_row is None and batch_rows:
        best_row = batch_rows[0]

    meaningful_batches = [r for r in batch_rows if r.get("gates") or r.get("metric_keys")]
    stability = "INSUFFICIENT DATA"
    stability_rationale: list[str] = []
    if len(meaningful_batches) < 2:
        stability_rationale.append("Fewer than two batches with gate or metric coverage.")
    else:
        latest_two = meaningful_batches[:2]
        latest_fail = all(str(r.get("overall") or "") != "ready" for r in latest_two)
        best_ready = bool(best_row is not None and str(best_row.get("overall") or "") == "ready")
        if best_ready and latest_fail:
            stability = "UNSTABLE"
            stability_rationale.append("Best batch is ready but the latest two batches are not ready.")
        else:
            stability = "STABLE"
            stability_rationale.append("Recent batch outcomes are not in conflict with best-batch readiness.")

    policy_req = []
    for source in (comp_det.get("missing_inputs"),):
        if isinstance(source, dict):
            policy_req.extend(str(x) for x in (source.get("required_measurement_keys_missing") or []) if str(x).strip())
    required_first = sorted(set(policy_req))
    remaining = sorted([mk for mk in all_metric_keys if mk not in set(required_first)], key=lambda x: str(x))
    ordered_metric_keys = required_first + remaining
    ordered_batch_labels = [str(r.get("batch_label") or "") for r in batch_rows]
    metric_rows = []
    for mk in ordered_metric_keys:
        row_cells = [batch_metric_map.get(mk, {}).get(lbl, "not run") for lbl in ordered_batch_labels]
        metric_rows.append(
            {
                "metric_key": mk,
                "metric_group": _metric_group_for_key(mk),
                "cells": row_cells,
            }
        )

    best_gate_rows = sorted(
        [g for g in (best_row.get("gates") if isinstance(best_row, dict) else []) if isinstance(g, dict)],
        key=lambda x: str(x.get("gate_key") or ""),
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

    notes_rows = (
        db.query(DataRecord.id, DataRecord.batch_id, DataRecord.created_at, DataRecord.notes)
        .filter(DataRecord.molecule_id == int(molecule_id))
        .filter(DataRecord.notes.isnot(None))
        .order_by(DataRecord.created_at.desc(), DataRecord.id.desc())
        .limit(20)
        .all()
    )
    notes = []
    for rid, bid, created_at, notes_text in notes_rows:
        txt = str(notes_text or "").strip()
        if not txt:
            continue
        bobj = batches_by_id.get(int(bid)) if bid is not None else None
        notes.append(
            {
                "record_id": int(rid),
                "author": "local-user",
                "timestamp": (created_at.isoformat() if created_at is not None else ""),
                "scope": (str(bobj.batch_id) if bobj is not None and str(bobj.batch_id or "").strip() else ("molecule" if bid is None else f"batch_id={int(bid)}")),
                "body": _clean_board_text(txt),
            }
        )
    notes = sorted(notes, key=lambda n: (str(n.get("timestamp") or ""), int(n.get("record_id") or 0)), reverse=True)

    readiness = str(stage.get("decision_state") or stage.get("readiness_state") or "not_assessed").strip() or "not_assessed"
    blockers = [str(x).strip() for x in (gaps.get("blockers") if isinstance(gaps.get("blockers"), list) else []) if str(x).strip()]
    comp_status = str(comp_det.get("category") or "not_assessed")
    warnings_compact = sorted(str(w.get("flag_code") or "") for w in governance_warnings if isinstance(w, dict) and str(w.get("flag_code") or "").strip())
    executive_paragraph = (
        f"Readiness is {readiness.replace('_', ' ')}; stability is {stability.lower()}; "
        f"comparability is {comp_status.replace('_', ' ')}; "
        + (
            ("blockers include " + ", ".join(blockers[:3]) + "; ") if blockers else "no explicit blockers were recorded; "
        )
        + (
            ("governance warnings: " + ", ".join(warnings_compact[:3]) + ".") if warnings_compact else "no governance warnings were recorded."
        )
    )

    return {
        "header": {
            "molecule": _clean_board_text(identity.get("primary_id") or identity.get("title") or f"molecule_id={molecule_id}"),
            "program": (f"program_id={identity.get('program_id')}" if identity.get("program_id") is not None else "unknown"),
            "decision_template": _clean_board_text(payload.get("metadata", {}).get("report_type") if isinstance(payload.get("metadata"), dict) else row.report_type),
            "policy_version": _clean_board_text(repro.get("catalog_versions", {}).get("comparability_policy") if isinstance(repro.get("catalog_versions"), dict) else "unknown"),
            "snapshot_id": (int(identity.get("snapshot_id")) if str(identity.get("snapshot_id") or "").isdigit() else None),
            "generated_at": (row.created_at.isoformat() if row.created_at is not None else ""),
        },
        "conclusions": {
            "readiness_status": readiness,
            "best_overall_batch": (str(best_row.get("batch_label")) if isinstance(best_row, dict) else "unknown"),
            "comparability_status": comp_status,
            "confidence": _clean_board_text(sections.get("confidence_decomposition", {}).get("confidence", {}).get("overall") if isinstance(sections.get("confidence_decomposition"), dict) else ""),
            "stability_status": stability,
            "blockers": blockers,
            "governance_warnings": warnings_compact,
            "executive_paragraph": _clean_board_text(executive_paragraph),
            "stability_rationale": stability_rationale,
        },
        "batch_registry": batch_rows,
        "gate_summary": {
            "best_batch_rows": best_gate_rows,
            "per_batch_rows": per_batch_gate_rows,
        },
        "fact_sheet": {
            "batch_labels": ordered_batch_labels,
            "metric_rows": metric_rows,
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
        },
        "scientist_notes": notes,
    }


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
