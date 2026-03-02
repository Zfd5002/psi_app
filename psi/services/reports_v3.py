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
from psi.services.policy_upgrade import get_unacknowledged_upgrade_warnings, run_semantic_action_with_ack_guard
from psi.services.comparability import load_comparability_policy_latest

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


def _clean_board_text(value: object) -> str:
    txt = str(value or "").strip()
    if not txt:
        return ""
    return _HEX64_RE.sub("[hash-hidden]", txt)


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

    return run_semantic_action_with_ack_guard(db, current_policy_pins=policy_pins, action=_run)


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
    return {
        "report_run": row,
        "payload": payload,
        "subject_ids": subject_ids,
        "identity_summary": identity_summary,
        "policy_pins": policy_pins,
        "policy_pin_summary": policy_pin_summary,
        "rule_ids": sorted(rule_ids),
        "measurement_key_citations": sorted(measurement_keys),
        "evidence_snapshot_refs": sorted(snapshot_refs),
        "snapshot_coverage": snapshot_cov,
        "governance_warnings": get_unacknowledged_upgrade_warnings(db, current_policy_pins=policy_pins),
    }
