from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from pathlib import Path

from sqlalchemy.orm import Session

from psi.core.models import DecisionSnapshot, Molecule, ReportRun
from psi.core.utils import now_utc, stable_json_dumps
from psi.services.attribution import record_attribution_event
from psi.services.comparability import list_comparability_assessments
from psi.services.policy_upgrade import get_unacknowledged_upgrade_warnings
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

_V3_SUGGESTIONS_CACHE: dict[str, Any] | None = None


def _load_v3_suggestions_catalog() -> dict[str, Any]:
    global _V3_SUGGESTIONS_CACHE
    if isinstance(_V3_SUGGESTIONS_CACHE, dict):
        return _V3_SUGGESTIONS_CACHE
    p = Path(__file__).resolve().parents[1] / "core" / "di" / "catalogs" / "v3_experiment_suggestions_v0_1.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    _V3_SUGGESTIONS_CACHE = raw if isinstance(raw, dict) else {}
    return _V3_SUGGESTIONS_CACHE


def _priority_rank(priority: str, priority_order: list[str]) -> int:
    norm = str(priority or "").strip().lower()
    try:
        return [str(x).strip().lower() for x in priority_order].index(norm)
    except ValueError:
        return len(priority_order) + 1


def _derive_v3_next_best_experiments(*, report_type: str, decision_state: str | None = None, stage_counts: dict[str, Any] | None = None) -> dict[str, Any]:
    cat = _load_v3_suggestions_catalog()
    rules = cat.get("rules") if isinstance(cat.get("rules"), list) else []
    order = cat.get("priority_order") if isinstance(cat.get("priority_order"), list) else ["high", "medium", "low"]
    state = str(decision_state or "").strip().lower()
    sc = {str(k): int(v) for k, v in (stage_counts or {}).items() if str(k)}
    items: list[dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if str(rule.get("report_type") or "") != str(report_type):
            continue
        include = False
        reason_trail: list[str] = []
        if report_type == REPORT_TYPE_MOLECULE:
            states = [str(x).strip().lower() for x in (rule.get("decision_states") or []) if str(x).strip()]
            include = bool(states) and (state in states)
            if include:
                reason_trail = [f"decision_state={state}", str(rule.get("reason") or "")]
        elif report_type == REPORT_TYPE_PROGRAM:
            stage_keys = [str(x).strip().lower() for x in (rule.get("stage_keys") or []) if str(x).strip()]
            hit_keys = sorted([k for k in stage_keys if int(sc.get(k, 0)) > 0])
            include = bool(hit_keys)
            if include:
                reason_trail = [f"stage_keys_hit={','.join(hit_keys)}", str(rule.get("reason") or "")]
        if include:
            items.append(
                {
                    "suggestion_key": str(rule.get("suggestion_key") or ""),
                    "label": str(rule.get("label") or ""),
                    "priority": str(rule.get("priority") or "low"),
                    "reason_trail": [x for x in reason_trail if str(x)],
                }
            )
    items = sorted(
        items,
        key=lambda i: (
            _priority_rank(str(i.get("priority") or "low"), [str(x) for x in order]),
            str(i.get("suggestion_key") or ""),
            str(i.get("label") or ""),
        ),
    )
    return {
        "status": ("assessed" if items else "not_assessed"),
        "catalog_id": str(cat.get("catalog_id") or "v3_experiment_suggestions_v0_1"),
        "catalog_version": str(cat.get("catalog_version") or "v0.1"),
        "items": items,
    }


def _derive_governance_red_flags(db: Session, *, req: ReportRequest, sections: dict[str, Any]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []

    pins = req.policy_pins if isinstance(req.policy_pins, dict) else {}
    missing_pin_hashes: list[str] = []
    if not pins:
        missing_pin_hashes.append("all")
    else:
        for k in sorted(pins.keys(), key=lambda x: str(x)):
            v = pins.get(k)
            if isinstance(v, dict):
                hash_keys = [hk for hk in ("policy_hash", "catalog_hash") if str(v.get(hk) or "").strip()]
                if not hash_keys:
                    missing_pin_hashes.append(str(k))
    if missing_pin_hashes:
        flags.append(
            {
                "flag_code": "missing_policy_pins_or_hashes",
                "message": "report policy pins are missing required hash fields",
                "details": {"missing": missing_pin_hashes},
            }
        )

    up_warnings = get_unacknowledged_upgrade_warnings(db, current_policy_pins=pins)
    if up_warnings:
        flags.append(
            {
                "flag_code": "unacknowledged_policy_upgrade_affecting_pins",
                "message": "an unacknowledged policy upgrade may affect current policy pins",
                "details": {"session_ids": [int(w.get("session_id") or 0) for w in up_warnings]},
            }
        )

    comp_rows: list[dict[str, Any]] = []
    if isinstance(sections.get("comparability_surface"), dict):
        comp_rows = [x for x in (sections.get("comparability_surface") or {}).get("assessments", []) if isinstance(x, dict)]
    elif isinstance(sections.get("cross_molecule_comparability"), dict):
        comp_rows = [x for x in (sections.get("cross_molecule_comparability") or {}).get("assessments", []) if isinstance(x, dict)]
    if comp_rows:
        seen: dict[tuple[str, str, str, str, str], int] = {}
        for row in comp_rows:
            key = (
                str(row.get("left_scope_type") or ""),
                str(row.get("left_scope_id") or ""),
                str(row.get("right_scope_type") or ""),
                str(row.get("right_scope_id") or ""),
                str(row.get("rule_id") or ""),
            )
            seen[key] = seen.get(key, 0) + 1
        ambiguous = [k for k, c in sorted(seen.items()) if c > 1]
        if ambiguous:
            flags.append(
                {
                    "flag_code": "comparability_ambiguous_multiple_effective_candidates",
                    "message": "comparability surface includes duplicate pair/rule candidates",
                    "details": {"duplicate_pair_rule_keys": [":".join(k) for k in ambiguous]},
                }
            )

    if req.report_type in {REPORT_TYPE_PROGRAM_COMPARATIVE, REPORT_TYPE_MOLECULE_COMPARATIVE}:
        ranking = sections.get("ranking_surface") if isinstance(sections.get("ranking_surface"), dict) else {}
        if bool(ranking.get("enabled")) is False:
            flags.append(
                {
                    "flag_code": "ranking_disabled_or_policy_incomplete",
                    "message": "ranking is disabled by policy or ranking policy is incomplete",
                    "details": {"enabled": False, "status": str(ranking.get("status") or "")},
                }
            )
        elif str(ranking.get("status") or "") == "policy_incomplete":
            flags.append(
                {
                    "flag_code": "ranking_disabled_or_policy_incomplete",
                    "message": "ranking is disabled by policy or ranking policy is incomplete",
                    "details": {"enabled": bool(ranking.get("enabled")), "status": "policy_incomplete"},
                }
            )

    return sorted(flags, key=lambda x: str(x.get("flag_code") or ""))


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
    repro_base = {
        "policy_pins": {},
        "catalog_versions": {},
        "cited_snapshot_ids": [],
        "inputs_summary": {},
    }
    if report_type == REPORT_TYPE_MOLECULE:
        return {
            "identity_context": {},
            "stage_determination": {},
            "confidence_decomposition": {},
            "mechanistic_evidence_map": {},
            "risk_profile": {},
            "experimental_gaps": {},
            "drift_history": {},
            "reproducibility_appendix": dict(repro_base),
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
            "reproducibility_appendix": dict(repro_base),
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
            "reproducibility_appendix": dict(repro_base),
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
            "reproducibility_appendix": dict(repro_base),
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
    record_attribution_event(
        db,
        event_type="report_run.create",
        entity_type="ReportRun",
        entity_id=int(row.id),
        metadata={
            "report_type": str(row.report_type),
            "as_of": row.as_of.isoformat(),
            "subject_ids": list(req.subject_ids),
            "snapshot_count": len(req.snapshot_coverage),
        },
    )
    db.commit()
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
        "policy_pins": _sorted_dict(dict(policy_pins or {})),
        "catalog_versions": {"template_catalog": "v0.1", "comparability_policy": "v0.1", "ranking_policy": "v0.2"},
        "cited_snapshot_ids": ([int(snap.id)] if snap is not None else []),
        "inputs_summary": {"entity_ids": [int(mol.id)], "as_of": as_of.isoformat(), "snapshot_count": (1 if snap is not None else 0)},
        "state_of_evidence": soe,
        "snapshot_provenance": out.get("di_snapshot_provenance") if isinstance(out.get("di_snapshot_provenance"), dict) else {},
    }
    suggestions = _derive_v3_next_best_experiments(
        report_type=REPORT_TYPE_MOLECULE,
        decision_state=str(out.get("decision_state") or ""),
    )
    if suggestions.get("status") == "assessed":
        sections["experimental_gaps"]["next_best_experiments"] = suggestions.get("items") if isinstance(suggestions.get("items"), list) else []
    sections["reproducibility_appendix"]["governance_red_flags"] = _derive_governance_red_flags(db, req=req, sections=sections)
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
    sections["next_best_experiments"] = _derive_v3_next_best_experiments(
        report_type=REPORT_TYPE_PROGRAM,
        stage_counts={str(k): int(stage_counts[k]) for k in stage_counts},
    )
    sections["reproducibility_appendix"] = {
        "policy_pins": _sorted_dict(dict(policy_pins or {})),
        "catalog_versions": {"template_catalog": "v0.1", "comparability_policy": "v0.1", "ranking_policy": "v0.2"},
        "cited_snapshot_ids": snapshot_cov,
        "inputs_summary": {"entity_ids": [int(program_id)], "as_of": as_of.isoformat(), "snapshot_count": len(snapshot_cov)},
        "rollup": rollup,
    }
    sections["reproducibility_appendix"]["governance_red_flags"] = _derive_governance_red_flags(db, req=req, sections=sections)
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
    sections["reproducibility_appendix"] = {
        "policy_pins": _sorted_dict(dict(policy_pins or {})),
        "catalog_versions": {"template_catalog": "v0.1", "comparability_policy": "v0.1", "ranking_policy": "v0.2"},
        "cited_snapshot_ids": sorted(set(snapshot_cov)),
        "inputs_summary": {"entity_ids": mids, "as_of": as_of.isoformat(), "snapshot_count": len(sorted(set(snapshot_cov)))},
        "rows": [{"molecule_id": r["molecule_id"], "snapshot_id": r["snapshot_id"]} for r in rows],
    }
    sections["reproducibility_appendix"]["governance_red_flags"] = _derive_governance_red_flags(db, req=req, sections=sections)
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
    sections["reproducibility_appendix"] = {
        "policy_pins": _sorted_dict(dict(policy_pins or {})),
        "catalog_versions": {"template_catalog": "v0.1", "comparability_policy": "v0.1", "ranking_policy": "v0.2"},
        "cited_snapshot_ids": sorted(set(snapshot_cov)),
        "inputs_summary": {"entity_ids": pids, "as_of": as_of.isoformat(), "snapshot_count": len(sorted(set(snapshot_cov)))},
        "rows": [{"program_id": r["program_id"], "molecule_count": r["molecule_count"]} for r in rows],
    }
    sections["reproducibility_appendix"]["governance_red_flags"] = _derive_governance_red_flags(db, req=req, sections=sections)
    validate_report_payload(report_type=REPORT_TYPE_PROGRAM_COMPARATIVE, payload=payload)
    return persist_report_run(db, req=req, payload=payload)
