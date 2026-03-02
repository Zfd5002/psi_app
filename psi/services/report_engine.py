from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from psi.core.models import DecisionSnapshot, Molecule, ReportRun
from psi.core.utils import now_utc, stable_json_dumps
from psi.services.comparability import list_comparability_assessments
from psi.services.program_rollups import build_program_rollup
from psi.services.v3_ranking import build_ranking_surface, load_ranking_policy_v0_1

REPORT_TYPE_MOLECULE = "molecule_report"
REPORT_TYPE_PROGRAM = "program_report"
REPORT_TYPE_PROGRAM_COMPARATIVE = "program_comparative_report"
REPORT_TYPE_MOLECULE_COMPARATIVE = "molecule_comparative_report"

REPORT_TYPES = (
    REPORT_TYPE_MOLECULE,
    REPORT_TYPE_PROGRAM,
    REPORT_TYPE_PROGRAM_COMPARATIVE,
    REPORT_TYPE_MOLECULE_COMPARATIVE,
)


@dataclass(frozen=True)
class ReportRequest:
    report_type: str
    subject_ids: tuple[int, ...]
    as_of: datetime
    policy_pins: dict[str, Any]
    snapshot_coverage: tuple[int, ...] = ()


def _normalize_subject_ids(ids: list[int] | tuple[int, ...]) -> tuple[int, ...]:
    out = tuple(int(x) for x in ids)
    if not out:
        raise ValueError("subject_ids must be non-empty")
    return out


def _base_metadata(req: ReportRequest) -> dict[str, Any]:
    return {
        "report_type": req.report_type,
        "subject_ids": list(req.subject_ids),
        "as_of": req.as_of.isoformat(),
        "policy_pins": _sorted_dict(req.policy_pins),
        "snapshot_coverage": list(sorted(set(int(x) for x in req.snapshot_coverage))),
    }


def _sorted_dict(obj: dict[str, Any]) -> dict[str, Any]:
    return {str(k): obj[k] for k in sorted(obj.keys(), key=lambda x: str(x))}


def _empty_sections_for_type(report_type: str) -> dict[str, Any]:
    if report_type == REPORT_TYPE_MOLECULE:
        return {
            "identity_context": {},
            "stage_determination": {},
            "confidence_decomposition": {},
            "mechanistic_evidence_map": {},
            "risk_profile": {},
            "experimental_gaps": {},
            "drift_history": {},
            "reproducibility_appendix": {},
        }
    if report_type == REPORT_TYPE_PROGRAM:
        return {
            "metadata": {},
            "stage_determination": {},
            "molecule_overview_table": {"rows": []},
            "cross_molecule_comparability": {},
            "risk_landscape": {},
            "decision_lineage": {},
            "next_best_experiments": {},
            "reproducibility_appendix": {},
        }
    if report_type == REPORT_TYPE_MOLECULE_COMPARATIVE:
        return {
            "metadata": {},
            "molecule_set": {"rows": []},
            "stage_comparison": {},
            "confidence_comparison": {},
            "comparability_surface": {},
            "drift_comparison": {},
            "ranking_surface": {},
            "reproducibility_appendix": {},
        }
    if report_type == REPORT_TYPE_PROGRAM_COMPARATIVE:
        return {
            "metadata": {},
            "program_set": {"rows": []},
            "stage_comparison": {},
            "portfolio_posture_comparison": {},
            "comparability_surface": {},
            "ranking_surface": {},
            "resource_implications": {},
            "reproducibility_appendix": {},
        }
    raise ValueError(f"Unsupported report_type: {report_type}")


def build_report_payload(req: ReportRequest) -> dict[str, Any]:
    if req.report_type not in REPORT_TYPES:
        raise ValueError("Unsupported report_type")
    payload = {
        "metadata": _base_metadata(req),
        "sections": _empty_sections_for_type(req.report_type),
    }
    validate_report_payload(report_type=req.report_type, payload=payload)
    return payload


def _validate_required_keys(obj: dict[str, Any], keys: list[str], *, context: str) -> None:
    for key in keys:
        if key not in obj:
            raise ValueError(f"{context} missing key: {key}")


def validate_report_payload(*, report_type: str, payload: dict[str, Any]) -> None:
    if report_type not in REPORT_TYPES:
        raise ValueError("Unsupported report_type")
    if not isinstance(payload, dict):
        raise ValueError("payload must be object")
    _validate_required_keys(payload, ["metadata", "sections"], context="report payload")
    meta = payload.get("metadata")
    if not isinstance(meta, dict):
        raise ValueError("payload.metadata must be object")
    _validate_required_keys(meta, ["report_type", "subject_ids", "as_of", "policy_pins", "snapshot_coverage"], context="payload.metadata")
    if str(meta.get("report_type") or "") != report_type:
        raise ValueError("payload.metadata.report_type mismatch")
    sections = payload.get("sections")
    if not isinstance(sections, dict):
        raise ValueError("payload.sections must be object")
    expected = _empty_sections_for_type(report_type)
    if set(sections.keys()) != set(expected.keys()):
        raise ValueError(f"payload.sections keys mismatch for {report_type}")


def create_report_request(
    *,
    report_type: str,
    subject_ids: list[int] | tuple[int, ...],
    as_of: datetime,
    policy_pins: dict[str, Any],
    snapshot_coverage: list[int] | tuple[int, ...] = (),
) -> ReportRequest:
    if report_type not in REPORT_TYPES:
        raise ValueError("Unsupported report_type")
    return ReportRequest(
        report_type=report_type,
        subject_ids=_normalize_subject_ids(subject_ids),
        as_of=as_of,
        policy_pins=_sorted_dict(dict(policy_pins or {})),
        snapshot_coverage=tuple(sorted(set(int(x) for x in snapshot_coverage))),
    )


def persist_report_run(db: Session, *, req: ReportRequest, payload: dict[str, Any] | None = None) -> ReportRun:
    out = payload if isinstance(payload, dict) else build_report_payload(req)
    validate_report_payload(report_type=req.report_type, payload=out)
    row = ReportRun(
        report_type=req.report_type,
        subject_ids_json=stable_json_dumps(list(req.subject_ids)),
        as_of=req.as_of,
        policy_pins_json=stable_json_dumps(req.policy_pins),
        snapshot_coverage_json=stable_json_dumps(list(req.snapshot_coverage)),
        payload_json=stable_json_dumps(out),
        created_at=now_utc(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def load_report_run_payload(row: ReportRun) -> dict[str, Any]:
    obj = json.loads(row.payload_json or "{}")
    if not isinstance(obj, dict):
        raise ValueError("stored payload_json must decode to object")
    validate_report_payload(report_type=str(row.report_type or ""), payload=obj)
    return obj


def _safe_json_dict(raw: str | None) -> dict[str, Any]:
    try:
        obj = json.loads(raw or "{}")
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _latest_di_snapshot_for_molecule_as_of(db: Session, *, molecule_id: int, as_of: datetime) -> tuple[DecisionSnapshot | None, dict[str, Any], dict[str, Any]]:
    snaps = (
        db.query(DecisionSnapshot)
        .filter(DecisionSnapshot.molecule_id == int(molecule_id))
        .filter(DecisionSnapshot.created_at <= as_of)
        .order_by(DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc())
        .all()
    )
    for snap in snaps:
        out = _safe_json_dict(snap.outputs_json)
        inn = _safe_json_dict(snap.inputs_json)
        is_di = bool(
            (getattr(snap, "engine_key", None) == "di")
            or str(getattr(snap, "schema_version", "") or "").startswith("di.")
            or ("decision_state" in out and "gates" in out)
            or str(inn.get("engine_key") or "").strip() == "di"
        )
        if is_di:
            return snap, out, inn
    return None, {}, {}


def generate_molecule_report_v0(
    db: Session,
    *,
    molecule_id: int,
    as_of: datetime,
    policy_pins: dict[str, Any],
) -> ReportRun:
    mol = db.get(Molecule, int(molecule_id))
    if mol is None:
        raise KeyError("Molecule not found")
    snap, out, _inn = _latest_di_snapshot_for_molecule_as_of(db, molecule_id=int(molecule_id), as_of=as_of)
    req = create_report_request(
        report_type=REPORT_TYPE_MOLECULE,
        subject_ids=[int(molecule_id)],
        as_of=as_of,
        policy_pins=policy_pins,
        snapshot_coverage=([int(snap.id)] if snap is not None else []),
    )
    payload = build_report_payload(req)
    sections = payload["sections"]
    readiness = out.get("readiness") if isinstance(out.get("readiness"), dict) else {}
    soe = out.get("state_of_evidence") if isinstance(out.get("state_of_evidence"), dict) else {}
    comparability = out.get("comparability") if isinstance(out.get("comparability"), dict) else {}
    risk_flags = out.get("risk_flags_enriched") if isinstance(out.get("risk_flags_enriched"), list) else []
    drift = out.get("drift") if isinstance(out.get("drift"), dict) else {}
    blockers = out.get("blockers") if isinstance(out.get("blockers"), list) else []

    sections["identity_context"] = {
        "molecule_id": int(mol.id),
        "program_id": int(mol.program_id),
        "primary_id": str(mol.primary_id or ""),
        "title": str(mol.title or ""),
        "snapshot_id": (int(snap.id) if snap is not None else None),
        "snapshot_created_at": (snap.created_at.isoformat() if snap is not None and snap.created_at else None),
    }
    sections["stage_determination"] = {
        "decision_state": str(out.get("decision_state") or ""),
        "readiness_state": str(readiness.get("state") or ""),
        "gates": out.get("gates") if isinstance(out.get("gates"), list) else [],
    }
    sections["confidence_decomposition"] = {
        "confidence": out.get("confidence") if isinstance(out.get("confidence"), dict) else {},
        "state_of_evidence_summary": soe.get("summary") if isinstance(soe.get("summary"), dict) else {},
    }
    sections["mechanistic_evidence_map"] = {
        "used_by_metric": out.get("used_by_metric") if isinstance(out.get("used_by_metric"), dict) else {},
        "mechanism": soe.get("mechanism") if isinstance(soe.get("mechanism"), dict) else {},
    }
    sections["risk_profile"] = {
        "risk_flags_enriched": sorted(
            [rf for rf in risk_flags if isinstance(rf, dict)],
            key=lambda r: (str(r.get("severity") or ""), str(r.get("key") or "")),
        )
    }
    sections["experimental_gaps"] = {
        "blockers": blockers,
        "next_best_experiments": out.get("next_best_experiments") if isinstance(out.get("next_best_experiments"), list) else [],
    }
    sections["drift_history"] = {
        "drift": drift,
        "comparability_summary": comparability.get("summary") if isinstance(comparability.get("summary"), dict) else {},
    }
    sections["reproducibility_appendix"] = {
        "state_of_evidence": soe,
        "snapshot_provenance": out.get("di_snapshot_provenance") if isinstance(out.get("di_snapshot_provenance"), dict) else {},
    }
    validate_report_payload(report_type=REPORT_TYPE_MOLECULE, payload=payload)
    return persist_report_run(db, req=req, payload=payload)


def generate_program_report_v0(
    db: Session,
    *,
    program_id: int,
    as_of: datetime,
    policy_pins: dict[str, Any],
) -> ReportRun:
    rollup = build_program_rollup(db, program_id=int(program_id), as_of=as_of)
    snapshot_cov = [int(x) for x in (rollup.get("snapshot_ids") or []) if isinstance(x, int)]
    req = create_report_request(
        report_type=REPORT_TYPE_PROGRAM,
        subject_ids=[int(program_id)],
        as_of=as_of,
        policy_pins=policy_pins,
        snapshot_coverage=snapshot_cov,
    )
    payload = build_report_payload(req)
    sections = payload["sections"]
    molecules = rollup.get("molecules") if isinstance(rollup.get("molecules"), list) else []
    stage_counts = rollup.get("stage_counts") if isinstance(rollup.get("stage_counts"), dict) else {}
    comp_rows = list_comparability_assessments(db, scope_type="program", scope_id=int(program_id))

    sections["metadata"] = {
        "program_id": int(program_id),
        "as_of": as_of.isoformat(),
        "policy_versions_seen": sorted(str(x) for x in (rollup.get("policy_versions") or []) if str(x)),
        "policy_package_hashes_seen": sorted(str(x) for x in (rollup.get("policy_package_hashes") or []) if str(x)),
        "snapshot_coverage": snapshot_cov,
    }
    sections["stage_determination"] = {
        "stage_counts": {str(k): int(stage_counts[k]) for k in sorted(stage_counts.keys())},
        "rollup_policy_pin": "program_rollup.v0",
    }
    sections["molecule_overview_table"] = {
        "rows": [
            {
                "molecule_id": int(m.get("molecule_id") or 0),
                "primary_id": str(m.get("primary_id") or ""),
                "title": str(m.get("title") or ""),
                "stage": str(m.get("stage") or "not_assessed"),
                "snapshot_id": (int(m.get("snapshot_id")) if m.get("snapshot_id") is not None else None),
                "policy_version": (str(m.get("policy_version")) if m.get("policy_version") else None),
            }
            for m in molecules
            if isinstance(m, dict)
        ]
    }
    sections["cross_molecule_comparability"] = (
        {
            "status": "assessed",
            "assessments": comp_rows,
        }
        if comp_rows
        else {
            "status": "not_assessed",
            "assessments": [],
            "placeholder_reason": "no_program_comparability_assessments",
        }
    )
    # Deterministic placeholders for remaining fixed sections.
    sections["risk_landscape"] = {"source": "program_rollup", "molecule_count": len(sections["molecule_overview_table"]["rows"])}
    sections["decision_lineage"] = {"snapshot_ids": snapshot_cov}
    sections["next_best_experiments"] = {"status": "not_assessed", "items": []}
    sections["reproducibility_appendix"] = {"rollup": rollup}
    validate_report_payload(report_type=REPORT_TYPE_PROGRAM, payload=payload)
    return persist_report_run(db, req=req, payload=payload)


def generate_molecule_comparative_report_v0(
    db: Session,
    *,
    molecule_ids: list[int] | tuple[int, ...],
    as_of: datetime,
    policy_pins: dict[str, Any],
) -> ReportRun:
    mids = sorted({int(x) for x in molecule_ids})
    if len(mids) < 2 or len(mids) > 5:
        raise ValueError("molecule comparative report requires 2-5 molecules")
    rows: list[dict[str, Any]] = []
    snapshot_cov: list[int] = []
    for mid in mids:
        mol = db.get(Molecule, mid)
        if mol is None:
            raise KeyError(f"Molecule not found: {mid}")
        snap, out, _inn = _latest_di_snapshot_for_molecule_as_of(db, molecule_id=mid, as_of=as_of)
        if snap is not None:
            snapshot_cov.append(int(snap.id))
        rows.append(
            {
                "molecule_id": int(mol.id),
                "primary_id": str(mol.primary_id or ""),
                "title": str(mol.title or ""),
                "program_id": int(mol.program_id),
                "snapshot_id": (int(snap.id) if snap is not None else None),
                "stage": str(out.get("decision_state") or out.get("readiness", {}).get("state") or "not_assessed"),
                "drift": out.get("drift") if isinstance(out.get("drift"), dict) else {},
                "confidence": out.get("confidence") if isinstance(out.get("confidence"), dict) else {},
            }
        )
    rows = sorted(rows, key=lambda r: (str(r.get("primary_id") or ""), int(r.get("molecule_id") or 0)))
    req = create_report_request(
        report_type=REPORT_TYPE_MOLECULE_COMPARATIVE,
        subject_ids=mids,
        as_of=as_of,
        policy_pins=policy_pins,
        snapshot_coverage=tuple(sorted(set(snapshot_cov))),
    )
    payload = build_report_payload(req)
    sections = payload["sections"]
    sections["metadata"] = {
        "as_of": as_of.isoformat(),
        "policy_pins": _sorted_dict(dict(policy_pins or {})),
        "snapshot_coverage": sorted(set(snapshot_cov)),
    }
    sections["molecule_set"] = {"rows": rows}
    sections["stage_comparison"] = {"rows": [{"molecule_id": r["molecule_id"], "stage": r["stage"]} for r in rows]}
    sections["confidence_comparison"] = {"rows": [{"molecule_id": r["molecule_id"], "confidence": r["confidence"]} for r in rows]}
    comp_assessments: list[dict[str, Any]] = []
    for mid in mids:
        comp_assessments.extend(list_comparability_assessments(db, scope_type="molecule", scope_id=mid))
    # de-dupe deterministically by id
    comp_map = {int(c["id"]): c for c in comp_assessments if isinstance(c, dict) and c.get("id") is not None}
    comp_list = [comp_map[k] for k in sorted(comp_map)]
    sections["comparability_surface"] = (
        {"status": "assessed", "assessments": comp_list}
        if comp_list
        else {"status": "not_assessed", "assessments": [], "placeholder_reason": "no_molecule_comparability_assessments"}
    )
    sections["drift_comparison"] = {"rows": [{"molecule_id": r["molecule_id"], "drift": r["drift"]} for r in rows]}
    ranking_policy = load_ranking_policy_v0_1()
    rank_entities = [
        {
            "entity_type": "molecule",
            "entity_id": int(r["molecule_id"]),
            "stable_sort_key": str(r["primary_id"]),
            "criteria_hits": [x for x in ["stage_ready" if str(r["stage"]).lower() == "ready" else "", "high_severity_risk_present"] if x][:1],
        }
        for r in rows
    ]
    sections["ranking_surface"] = build_ranking_surface(entities=rank_entities, policy=ranking_policy)
    sections["reproducibility_appendix"] = {"rows": [{"molecule_id": r["molecule_id"], "snapshot_id": r["snapshot_id"]} for r in rows]}
    validate_report_payload(report_type=REPORT_TYPE_MOLECULE_COMPARATIVE, payload=payload)
    return persist_report_run(db, req=req, payload=payload)


def generate_program_comparative_report_v0(
    db: Session,
    *,
    program_ids: list[int] | tuple[int, ...],
    as_of: datetime,
    policy_pins: dict[str, Any],
) -> ReportRun:
    pids = sorted({int(x) for x in program_ids})
    if len(pids) < 2 or len(pids) > 5:
        raise ValueError("program comparative report requires 2-5 programs")
    rows: list[dict[str, Any]] = []
    snapshot_cov: list[int] = []
    for pid in pids:
        rollup = build_program_rollup(db, program_id=pid, as_of=as_of)
        rows.append(
            {
                "program_id": int(pid),
                "stage_counts": rollup.get("stage_counts") if isinstance(rollup.get("stage_counts"), dict) else {},
                "molecule_count": len((rollup.get("molecules") or [])) if isinstance(rollup.get("molecules"), list) else 0,
                "policy_versions_seen": sorted(str(x) for x in (rollup.get("policy_versions") or []) if str(x)),
            }
        )
        snapshot_cov.extend([int(x) for x in (rollup.get("snapshot_ids") or []) if isinstance(x, int)])
    rows = sorted(rows, key=lambda r: int(r.get("program_id") or 0))
    req = create_report_request(
        report_type=REPORT_TYPE_PROGRAM_COMPARATIVE,
        subject_ids=pids,
        as_of=as_of,
        policy_pins=policy_pins,
        snapshot_coverage=tuple(sorted(set(snapshot_cov))),
    )
    payload = build_report_payload(req)
    sections = payload["sections"]
    sections["metadata"] = {"as_of": as_of.isoformat(), "policy_pins": _sorted_dict(dict(policy_pins or {})), "snapshot_coverage": sorted(set(snapshot_cov))}
    sections["program_set"] = {"rows": rows}
    sections["stage_comparison"] = {"rows": [{"program_id": r["program_id"], "stage_counts": r["stage_counts"]} for r in rows]}
    sections["portfolio_posture_comparison"] = {"status": "not_assessed", "rows": []}
    comp_rows: list[dict[str, Any]] = []
    for pid in pids:
        comp_rows.extend(list_comparability_assessments(db, scope_type="program", scope_id=pid))
    comp_map = {int(c["id"]): c for c in comp_rows if isinstance(c, dict) and c.get("id") is not None}
    comp_list = [comp_map[k] for k in sorted(comp_map)]
    sections["comparability_surface"] = (
        {"status": "assessed", "assessments": comp_list}
        if comp_list
        else {"status": "not_assessed", "assessments": [], "placeholder_reason": "no_program_comparability_assessments"}
    )
    ranking_policy = load_ranking_policy_v0_1()
    rank_entities = [
        {
            "entity_type": "program",
            "entity_id": int(r["program_id"]),
            "stable_sort_key": f"program:{int(r['program_id'])}",
            "criteria_hits": [],
        }
        for r in rows
    ]
    sections["ranking_surface"] = build_ranking_surface(entities=rank_entities, policy=ranking_policy)
    sections["resource_implications"] = {"status": "not_assessed", "policy_derived_fields_only": True, "rows": []}
    sections["reproducibility_appendix"] = {"rows": [{"program_id": r["program_id"], "molecule_count": r["molecule_count"]} for r in rows]}
    validate_report_payload(report_type=REPORT_TYPE_PROGRAM_COMPARATIVE, payload=payload)
    return persist_report_run(db, req=req, payload=payload)
