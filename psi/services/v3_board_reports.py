from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from psi.core.models import DecisionSnapshot, Molecule
SECTION_ORDER = [
    "I_governance_header",
    "II_general_profile",
    "III_molecular_structure_and_design",
    "IV_in_vitro_evidence_tables",
    "V_developability_biophys_tables",
    "VI_in_vivo_pk_ada_tables",
    "VII_policy_interpretation_and_governance_state",
    "VIII_executive_summary_bullets",
]


def derive_executive_summary_bullets(
    *,
    decision_state: str,
    readiness_state: str,
    blockers: list[dict[str, Any]],
    comparability_summary: dict[str, Any],
    evidence_summary_rows: list[dict[str, Any]],
) -> dict[str, list[str]]:
    # Stable, rule-based ordering:
    # 1) strengths from readiness/evidence/comparability
    # 2) risks from blockers/comparability/evidence gaps
    # 3) decision status categorical
    # 4) required actions from blockers/gaps
    strengths: list[str] = []
    risks: list[str] = []
    actions: list[str] = []
    ds = str(decision_state or "").strip().lower()
    rs = str(readiness_state or "").strip().lower()
    if ds == "ready" and rs == "ready":
        strengths.append("readiness_and_decision_aligned_ready")
    high_sev = int((comparability_summary or {}).get("high_severity_count") or 0)
    if high_sev == 0:
        strengths.append("comparability_no_high_severity_flags")
    else:
        risks.append("comparability_high_severity_flags_present")
        actions.append("resolve_high_severity_comparability_flags")
    missing_repro = []
    for row in sorted([x for x in evidence_summary_rows if isinstance(x, dict)], key=lambda r: str(r.get("metric_key") or "")):
        total_count = int(row.get("total_count") or 0)
        usable_count = int(row.get("usable_count") or 0)
        metric_key = str(row.get("metric_key") or "")
        if total_count > 1 and usable_count > 1:
            strengths.append(f"reproducibility_present:{metric_key}")
        else:
            missing_repro.append(metric_key)
    if missing_repro:
        risks.append("reproducibility_counts_insufficient")
        actions.append("add_reproducibility_replicates")
    blk = sorted({str((b or {}).get("blocker_key") or "").strip() for b in blockers if str((b or {}).get("blocker_key") or "").strip()})
    if blk:
        risks.append("policy_blockers_present")
        for b in blk:
            actions.append(f"resolve_blocker:{b}")
    decision_status = [ds if ds else "not_assessed"]
    return {
        "strengths": sorted(set(strengths)),
        "risks": sorted(set(risks)),
        "decision_status": sorted(set(decision_status)),
        "required_actions": sorted(set(actions)),
    }


def canonical_v3_report_json(obj: dict[str, Any]) -> str:
    return json.dumps(_canonicalize(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonicalize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _canonicalize(obj[k]) for k in sorted(obj.keys(), key=lambda x: str(x))}
    if isinstance(obj, list):
        return [_canonicalize(x) for x in obj]
    if isinstance(obj, tuple):
        return [_canonicalize(x) for x in obj]
    if isinstance(obj, set):
        return [_canonicalize(x) for x in sorted(obj, key=lambda x: str(x))]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        txt = format(obj, ".15f").rstrip("0").rstrip(".")
        if txt in {"", "-0"}:
            txt = "0"
        return txt
    return obj


def _safe_json_dict(raw: str | None) -> dict[str, Any]:
    try:
        out = json.loads(raw or "{}")
    except Exception:
        return {}
    return out if isinstance(out, dict) else {}


def _latest_snapshot_for_molecule_as_of(db: Session, *, molecule_id: int, as_of: datetime) -> tuple[DecisionSnapshot | None, dict[str, Any]]:
    rows = (
        db.query(DecisionSnapshot)
        .filter(DecisionSnapshot.molecule_id == int(molecule_id))
        .filter(DecisionSnapshot.created_at <= as_of)
        .order_by(DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc())
        .all()
    )
    for row in rows:
        out = _safe_json_dict(row.outputs_json)
        if str(getattr(row, "engine_key", "") or "").strip() == "di" or "decision_state" in out:
            return row, out
    return None, {}


def _fingerprint_basis(payload: dict[str, Any]) -> dict[str, Any]:
    basis = json.loads(canonical_v3_report_json(payload))
    sec = basis.get("sections")
    if isinstance(sec, dict):
        hdr = sec.get("I_governance_header")
        if isinstance(hdr, dict):
            hdr.pop("report_timestamp", None)
    return basis


def _compute_fingerprint(payload: dict[str, Any]) -> str:
    basis = _fingerprint_basis(payload)
    return hashlib.sha256(canonical_v3_report_json(basis).encode("utf-8")).hexdigest()


def build_molecule_report_v3(
    db: Session,
    *,
    molecule_id: int,
    as_of: datetime,
    report_timestamp: str | None = None,
) -> dict[str, Any]:
    mol = db.get(Molecule, int(molecule_id))
    if mol is None:
        raise KeyError("Molecule not found")
    snap, out = _latest_snapshot_for_molecule_as_of(db, molecule_id=int(molecule_id), as_of=as_of)
    readiness = out.get("readiness") if isinstance(out.get("readiness"), dict) else {}
    comparability = out.get("comparability") if isinstance(out.get("comparability"), dict) else {}
    soe = out.get("state_of_evidence") if isinstance(out.get("state_of_evidence"), dict) else {}
    soe_summary = soe.get("evidence_summary") if isinstance(soe.get("evidence_summary"), list) else []
    risk_flags = out.get("risk_flags_enriched") if isinstance(out.get("risk_flags_enriched"), list) else []
    blockers = out.get("blockers") if isinstance(out.get("blockers"), list) else []
    policy = out.get("policy") if isinstance(out.get("policy"), dict) else {}

    executive = derive_executive_summary_bullets(
        decision_state=str(out.get("decision_state") or ""),
        readiness_state=str(readiness.get("state") or ""),
        blockers=[x for x in blockers if isinstance(x, dict)],
        comparability_summary=comparability.get("summary") if isinstance(comparability.get("summary"), dict) else {},
        evidence_summary_rows=[
            {
                "metric_key": str(r.get("metric_key") or ""),
                "total_count": int(r.get("total_count") or 0),
                "usable_count": int(r.get("usable_count") or 0),
            }
            for r in sorted([x for x in soe_summary if isinstance(x, dict)], key=lambda row: str(row.get("metric_key") or ""))
        ],
    )
    sections: dict[str, Any] = {
        "I_governance_header": {
            "schema_id": "v3_molecule_report",
            "schema_version": "v0.1",
            "molecule_id": int(mol.id),
            "snapshot_id": int(snap.id) if snap is not None else None,
            "as_of": as_of.isoformat(),
            "report_timestamp": (str(report_timestamp) if report_timestamp is not None else None),
            "snapshot_content_hash": str((((out.get("provenance") or {}).get("integrity") or {}).get("snapshot_content_hash") or "")),
            "decision_output_hash_v2": str((((out.get("provenance") or {}).get("integrity") or {}).get("decision_output_hash_v2") or "")),
            "report_fingerprint": "",
        },
        "II_general_profile": {
            "program_id": int(mol.program_id),
            "primary_id": str(mol.primary_id or ""),
            "title": str(mol.title or ""),
            "decision_state": str(out.get("decision_state") or ""),
            "readiness_state": str(readiness.get("state") or ""),
        },
        "III_molecular_structure_and_design": {
            "format": str(mol.molecule_format or ""),
            "composition_sha256": str(mol.composition_sha256 or ""),
            "ptm_liability_map": [
                {
                    "key": str(x.get("key") or ""),
                    "severity": str(x.get("severity") or ""),
                    "category": str(x.get("category") or ""),
                }
                for x in sorted(
                    [r for r in risk_flags if isinstance(r, dict)],
                    key=lambda r: (str(r.get("severity") or ""), str(r.get("key") or "")),
                )
            ],
        },
        "IV_in_vitro_evidence_tables": {
            "coverage": soe.get("soe_v0_2", {}).get("coverage") if isinstance(soe.get("soe_v0_2"), dict) else {},
            "evidence_summary_rows": [
                {
                    "metric_key": str(r.get("metric_key") or ""),
                    "total_count": int(r.get("total_count") or 0),
                    "usable_count": int(r.get("usable_count") or 0),
                }
                for r in sorted(
                    [x for x in soe_summary if isinstance(x, dict)],
                    key=lambda row: str(row.get("metric_key") or ""),
                )
            ],
        },
        "V_developability_biophys_tables": {
            "comparability_summary": comparability.get("summary") if isinstance(comparability.get("summary"), dict) else {},
            "confidence": out.get("confidence") if isinstance(out.get("confidence"), dict) else {},
        },
        "VI_in_vivo_pk_ada_tables": {
            "pk_rows": [],
            "ada_rows": [],
        },
        "VII_policy_interpretation_and_governance_state": {
            "blockers": [
                {
                    "blocker_key": str(b.get("blocker_key") or ""),
                    "explanation": str(b.get("explanation") or ""),
                }
                for b in sorted([x for x in blockers if isinstance(x, dict)], key=lambda row: str(row.get("blocker_key") or ""))
            ],
            "policy": {
                "policy_id": str(policy.get("policy_id") or ""),
                "policy_version": str(policy.get("policy_version") or ""),
                "policy_package_hash": str(policy.get("policy_package_hash") or ""),
                "policy_semantics_hash": str(policy.get("policy_semantics_hash") or ""),
            },
        },
        "VIII_executive_summary_bullets": {
            "strengths": executive["strengths"],
            "risks": executive["risks"],
            "decision_status": executive["decision_status"],
            "required_actions": executive["required_actions"],
        },
    }
    payload = {
        "schema_id": "v3_molecule_report",
        "schema_version": "v0.1",
        "sections": {k: sections[k] for k in SECTION_ORDER},
    }
    payload["sections"]["I_governance_header"]["report_fingerprint"] = _compute_fingerprint(payload)
    return payload


def build_comparison_report_v3(
    db: Session,
    *,
    molecule_ids: list[int] | tuple[int, ...],
    as_of: datetime,
    report_timestamp: str | None = None,
) -> dict[str, Any]:
    mids = sorted({int(x) for x in molecule_ids})
    if len(mids) < 2:
        raise ValueError("comparison report requires at least 2 molecules")
    molecules: list[dict[str, Any]] = []
    for mid in mids:
        mol = db.get(Molecule, int(mid))
        if mol is None:
            raise KeyError(f"Molecule not found: {mid}")
        snap, out = _latest_snapshot_for_molecule_as_of(db, molecule_id=int(mid), as_of=as_of)
        molecules.append(
            {
                "molecule_id": int(mol.id),
                "primary_id": str(mol.primary_id or ""),
                "title": str(mol.title or ""),
                "snapshot_id": int(snap.id) if snap is not None else None,
                "decision_state": str(out.get("decision_state") or ""),
                "readiness_state": str(((out.get("readiness") or {}).get("state") or "")),
                "comparability_summary": (out.get("comparability") or {}).get("summary") if isinstance(out.get("comparability"), dict) else {},
                "policy": out.get("policy") if isinstance(out.get("policy"), dict) else {},
                "coverage": ((out.get("state_of_evidence") or {}).get("soe_v0_2") or {}).get("coverage")
                if isinstance((out.get("state_of_evidence") or {}).get("soe_v0_2"), dict)
                else {},
            }
        )
    molecules = sorted(molecules, key=lambda r: int(r["molecule_id"]))
    columns = [{"molecule_id": int(r["molecule_id"]), "primary_id": str(r["primary_id"]), "title": str(r["title"])} for r in molecules]

    def _metric_row(metric_key: str, title: str, value_key: str) -> dict[str, Any]:
        cells = []
        for r in molecules:
            value = ""
            if value_key == "decision_state":
                value = str(r.get("decision_state") or "")
            elif value_key == "readiness_state":
                value = str(r.get("readiness_state") or "")
            elif value_key == "high_severity_count":
                value = str(int(((r.get("comparability_summary") or {}).get("high_severity_count") or 0)))
            cells.append({"molecule_id": int(r["molecule_id"]), "value": value})
        return {"metric_key": metric_key, "label": title, "cells": cells}

    comparison_rows = [
        _metric_row("decision_state", "Decision State", "decision_state"),
        _metric_row("readiness_state", "Readiness State", "readiness_state"),
        _metric_row("comparability_high_severity_count", "Comparability High Severity Count", "high_severity_count"),
    ]
    all_blockers: list[dict[str, Any]] = []
    all_evidence_rows: list[dict[str, Any]] = []
    worst_high_sev = 0
    statuses: list[str] = []
    for r in molecules:
        statuses.append(str(r.get("decision_state") or "not_assessed"))
        csum = r.get("comparability_summary") if isinstance(r.get("comparability_summary"), dict) else {}
        worst_high_sev = max(worst_high_sev, int(csum.get("high_severity_count") or 0))
    executive = derive_executive_summary_bullets(
        decision_state=",".join(sorted(set(statuses))),
        readiness_state="",
        blockers=all_blockers,
        comparability_summary={"high_severity_count": int(worst_high_sev)},
        evidence_summary_rows=all_evidence_rows,
    )

    sections: dict[str, Any] = {
        "I_governance_header": {
            "schema_id": "v3_comparison_report",
            "schema_version": "v0.1",
            "molecule_ids": mids,
            "as_of": as_of.isoformat(),
            "report_timestamp": (str(report_timestamp) if report_timestamp is not None else None),
            "report_fingerprint": "",
        },
        "II_general_profile": {
            "columns": columns,
        },
        "III_molecular_structure_and_design": {
            "rows": [],
        },
        "IV_in_vitro_evidence_tables": {
            "rows": comparison_rows,
        },
        "V_developability_biophys_tables": {
            "rows": [],
        },
        "VI_in_vivo_pk_ada_tables": {
            "rows": [],
        },
        "VII_policy_interpretation_and_governance_state": {
            "comparability_rule_citations": [
                {
                    "molecule_id": int(r["molecule_id"]),
                    "status": ("assessed" if isinstance(r.get("comparability_summary"), dict) and bool(r.get("comparability_summary")) else "not_assessed"),
                    "rule_ids": [],
                }
                for r in molecules
            ],
            "policy_versions": [
                {
                    "molecule_id": int(r["molecule_id"]),
                    "policy_id": str((r.get("policy") or {}).get("policy_id") or ""),
                    "policy_version": str((r.get("policy") or {}).get("policy_version") or ""),
                }
                for r in molecules
            ],
        },
        "VIII_executive_summary_bullets": {
            "strengths": executive["strengths"],
            "risks": executive["risks"],
            "decision_status": sorted({str(r.get("decision_state") or "not_assessed") for r in molecules}),
            "required_actions": executive["required_actions"],
        },
    }
    payload = {
        "schema_id": "v3_comparison_report",
        "schema_version": "v0.1",
        "sections": {k: sections[k] for k in SECTION_ORDER},
    }
    payload["sections"]["I_governance_header"]["report_fingerprint"] = _compute_fingerprint(payload)
    return payload


def render_board_report_html(*, report_payload: dict[str, Any]) -> str:
    schema_id = str(report_payload.get("schema_id") or "")
    template_name = ""
    if schema_id == "v3_molecule_report":
        template_name = "board_molecule_v3.html"
    elif schema_id == "v3_comparison_report":
        template_name = "board_comparison_v3.html"
    else:
        raise ValueError("unsupported_board_report_schema")
    tdir = Path(__file__).resolve().parents[1] / "web" / "templates" / "reports"
    env = Environment(
        loader=FileSystemLoader(str(tdir)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tpl = env.get_template(template_name)
    return str(tpl.render(report=report_payload))
