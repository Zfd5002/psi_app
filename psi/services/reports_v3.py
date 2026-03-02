from __future__ import annotations

from datetime import datetime, timezone
import json

from sqlalchemy.orm import Session

from psi.core.models import ReportRun
from psi.services.report_engine import (
    generate_molecule_comparative_report_v0,
    generate_molecule_report_v0,
    generate_program_comparative_report_v0,
    generate_program_report_v0,
    load_report_run_payload,
)


def _parse_as_of(as_of_text: str | None) -> datetime:
    txt = str(as_of_text or "").strip()
    if not txt:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    txt = txt.replace("Z", "+00:00")
    dt = datetime.fromisoformat(txt)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def generate_report_from_form(
    db: Session,
    *,
    report_type: str,
    subject_ids_text: str,
    as_of_text: str | None,
) -> ReportRun:
    ids = sorted({int(x.strip()) for x in str(subject_ids_text or "").split(",") if x.strip()})
    as_of = _parse_as_of(as_of_text)
    policy_pins = {"report_engine": "v3.a11", "ranking_policy": "v0.1", "comparability_policy": "v0.1"}
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
    return {
        "report_run": row,
        "payload": payload,
        "subject_ids": subject_ids,
        "policy_pins": policy_pins,
        "snapshot_coverage": snapshot_cov,
    }
