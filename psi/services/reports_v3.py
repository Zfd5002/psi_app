from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from sqlalchemy.orm import Session

from psi.core.models import ReportRun
from psi.core.di.policy import sha256_hex_of_canonical_json
from psi.services.report_engine import (
    generate_molecule_comparative_report_v0,
    generate_molecule_report_v0,
    generate_program_comparative_report_v0,
    generate_program_report_v0,
    load_report_run_payload,
)
from psi.services.policy_upgrade import get_unacknowledged_upgrade_warnings, require_upgrade_acknowledged_for_semantic_actions


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


def get_v3_report_policy_pins(report_type: str) -> dict:
    base = Path(__file__).resolve().parents[1] / "core" / "di" / "catalogs"
    template_cat = _load_json(base / "template_catalog_v0_1.json")
    comparability_pol = _load_json(base / "comparability_policy_v0_1.json")
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
    as_of = _parse_as_of(as_of_text)
    policy_pins = get_v3_report_policy_pins(report_type)
    require_upgrade_acknowledged_for_semantic_actions(db, current_policy_pins=policy_pins)
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


def list_report_runs(db: Session) -> list[ReportRun]:
    return db.query(ReportRun).order_by(ReportRun.created_at.desc(), ReportRun.id.desc()).limit(100).all()


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
    return {
        "report_run": row,
        "payload": payload,
        "subject_ids": subject_ids,
        "policy_pins": policy_pins,
        "policy_pin_summary": policy_pin_summary,
        "rule_ids": sorted(rule_ids),
        "measurement_key_citations": sorted(measurement_keys),
        "evidence_snapshot_refs": sorted(snapshot_refs),
        "snapshot_coverage": snapshot_cov,
        "governance_warnings": get_unacknowledged_upgrade_warnings(db, current_policy_pins=policy_pins),
    }
