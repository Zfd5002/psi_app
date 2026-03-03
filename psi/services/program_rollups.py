from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from pathlib import Path

from sqlalchemy.orm import Session

from psi.core.models import DecisionSnapshot, Molecule, ProgramMembership, ProgramRollup
from psi.core.utils import now_utc, stable_json_dumps
from psi.services.di.util import is_di_snapshot_record
from psi.services.policy_upgrade import get_unacknowledged_upgrade_warnings
from psi.services.json_helpers import safe_json_dict


_PROGRAM_POSTURE_POLICY_CACHE: dict[str, Any] | None = None


def _load_program_posture_policy() -> dict[str, Any]:
    global _PROGRAM_POSTURE_POLICY_CACHE
    if isinstance(_PROGRAM_POSTURE_POLICY_CACHE, dict):
        return _PROGRAM_POSTURE_POLICY_CACHE
    p = Path(__file__).resolve().parents[1] / "core" / "di" / "catalogs" / "program_rollup_policy_v0_1.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("program_posture_policy_load_error")
    if not str(raw.get("policy_id") or "").strip():
        raise ValueError("program_posture_policy_load_error")
    if not str(raw.get("policy_version") or "").strip():
        raise ValueError("program_posture_policy_load_error")
    if not isinstance(raw.get("posture_states"), list):
        raise ValueError("program_posture_policy_load_error")
    if not isinstance(raw.get("rule_order"), list):
        raise ValueError("program_posture_policy_load_error")
    _PROGRAM_POSTURE_POLICY_CACHE = raw
    return _PROGRAM_POSTURE_POLICY_CACHE


def _derive_program_posture(
    *,
    stage_counts: dict[str, int],
    total_molecules: int,
    cited_snapshot_ids: list[int],
    cited_templates: list[str],
    cited_decisions: list[str],
    governance_action_required_present: bool,
) -> dict[str, Any]:
    policy = _load_program_posture_policy()
    labels = policy.get("posture_states") if isinstance(policy.get("posture_states"), list) else []
    allowed = [str(x) for x in labels if str(x)]
    ready = int(stage_counts.get("ready", 0))
    not_assessed = int(stage_counts.get("not_assessed", 0))
    blockedish = int(stage_counts.get("blocked", 0)) + int(stage_counts.get("failed", 0))
    required_templates = [str(x) for x in (policy.get("required_template_keys") or []) if str(x)]
    missing_required_templates = [k for k in required_templates if k not in cited_templates]
    flags = {
        "total_molecules_zero": total_molecules <= 0,
        "all_not_assessed": total_molecules > 0 and not_assessed >= total_molecules,
        "missing_required_templates": bool(missing_required_templates),
        "blocked_or_failed_present": blockedish > 0,
        "governance_action_required_present": bool(governance_action_required_present),
        "all_ready": total_molecules > 0 and ready >= total_molecules,
        "otherwise": True,
    }
    matched_rule = {
        "id": "rule_at_risk_fallback",
        "posture_state": "at_risk",
        "rationale_fragments": ["mixed_or_partial_readiness"],
        "when": ["otherwise"],
    }
    for rule in [r for r in (policy.get("rule_order") or []) if isinstance(r, dict)]:
        checks = [str(x) for x in (rule.get("when") or []) if str(x)]
        if not checks:
            continue
        if any(bool(flags.get(c, False)) for c in checks):
            matched_rule = rule
            break
    posture = str(matched_rule.get("posture_state") or "at_risk")
    if posture not in allowed and allowed:
        posture = allowed[0]
    return {
        "policy_id": str(policy.get("policy_id") or "program_rollup_policy_v0_1"),
        "policy_version": str(policy.get("policy_version") or "v0.1"),
        "posture_state": posture,
        "rule_id": str(matched_rule.get("id") or "rule_at_risk_fallback"),
        "cited_snapshot_ids": sorted({int(x) for x in cited_snapshot_ids}),
        "cited_templates": sorted({str(x) for x in cited_templates if str(x)}),
        "cited_decisions": sorted({str(x) for x in cited_decisions if str(x)}),
        "rationale": "|".join([str(x) for x in (matched_rule.get("rationale_fragments") or []) if str(x)]) or "policy_rule_match",
        "notes": (
            ["governance_action_required_present"] if bool(governance_action_required_present) else []
        ) + (
            [f"missing_required_templates:{','.join(sorted(missing_required_templates))}"] if missing_required_templates else []
        ),
    }


def _program_molecule_order(db: Session, *, program_id: int) -> list[dict[str, Any]]:
    memberships = (
        db.query(ProgramMembership, Molecule)
        .join(Molecule, Molecule.id == ProgramMembership.molecule_id)
        .filter(ProgramMembership.program_id == program_id)
        .order_by(ProgramMembership.sort_index.asc(), ProgramMembership.id.asc())
        .all()
    )
    if memberships:
        return [
            {
                "molecule_id": int(m.id),
                "sort_index": int(pm.sort_index or 0),
                "membership_id": int(pm.id),
                "primary_id": str(m.primary_id or ""),
                "title": str(m.title or ""),
            }
            for pm, m in memberships
        ]
    molecules = (
        db.query(Molecule)
        .filter(Molecule.program_id == program_id)
        .order_by(Molecule.primary_id.asc(), Molecule.id.asc())
        .all()
    )
    return [
        {
            "molecule_id": int(m.id),
            "sort_index": None,
            "membership_id": None,
            "primary_id": str(m.primary_id or ""),
            "title": str(m.title or ""),
        }
        for m in molecules
    ]


def _latest_di_snapshot_as_of(db: Session, *, molecule_id: int, as_of: datetime) -> tuple[DecisionSnapshot | None, dict[str, Any], dict[str, Any]]:
    snaps = (
        db.query(DecisionSnapshot)
        .filter(DecisionSnapshot.molecule_id == molecule_id)
        .filter(DecisionSnapshot.created_at <= as_of)
        .order_by(DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc())
        .all()
    )
    for snap in snaps:
        out = safe_json_dict(snap.outputs_json)
        inn = safe_json_dict(snap.inputs_json)
        if is_di_snapshot_record(snap, out, inn, include_input_schema_version=True):
            return snap, out, inn
    return None, {}, {}


def build_program_rollup(db: Session, *, program_id: int, as_of: datetime) -> dict[str, Any]:
    rows = _program_molecule_order(db, program_id=program_id)
    molecules: list[dict[str, Any]] = []
    snapshot_ids: list[int] = []
    policy_versions: set[str] = set()
    policy_package_hashes: set[str] = set()
    template_keys: set[str] = set()
    decision_keys: set[str] = set()
    stage_counts: dict[str, int] = {}
    for row in rows:
        snap, out, _inn = _latest_di_snapshot_as_of(db, molecule_id=int(row["molecule_id"]), as_of=as_of)
        stage = str(out.get("decision_state") or out.get("readiness", {}).get("state") or "not_assessed")
        stage_norm = stage.strip().lower() or "not_assessed"
        stage_counts[stage_norm] = stage_counts.get(stage_norm, 0) + 1
        pol = out.get("policy") if isinstance(out.get("policy"), dict) else {}
        pver = str(pol.get("policy_version") or pol.get("version") or "").strip()
        pph = str(out.get("policy_package_hash") or "").strip()
        if pver:
            policy_versions.add(pver)
        if pph:
            policy_package_hashes.add(pph)
        if snap is not None:
            snapshot_ids.append(int(snap.id))
            if str(snap.decision_key or "").strip():
                decision_keys.add(str(snap.decision_key))
        prov = out.get("di_snapshot_provenance") if isinstance(out.get("di_snapshot_provenance"), dict) else {}
        tkey = str(prov.get("template_key") or "").strip()
        if tkey:
            template_keys.add(tkey)
        used_by_metric = out.get("used_by_metric") if isinstance(out.get("used_by_metric"), dict) else {}
        measurement_keys = sorted(str(k).strip() for k in used_by_metric.keys() if str(k).strip())
        risk_flags = out.get("risk_flags_enriched") if isinstance(out.get("risk_flags_enriched"), list) else []
        high_severity_risk_present = any(
            isinstance(rf, dict) and str(rf.get("severity") or "").strip().lower() == "high"
            for rf in risk_flags
        )
        molecules.append(
            {
                "molecule_id": int(row["molecule_id"]),
                "primary_id": str(row["primary_id"]),
                "title": str(row["title"] or ""),
                "sort_index": row["sort_index"],
                "membership_id": row["membership_id"],
                "snapshot_id": int(snap.id) if snap is not None else None,
                "snapshot_created_at": (snap.created_at.isoformat() if snap is not None and snap.created_at is not None else None),
                "stage": stage_norm,
                "policy_version": pver or None,
                "policy_package_hash": pph or None,
                "measurement_keys": measurement_keys,
                "high_severity_risk_present": bool(high_severity_risk_present),
            }
        )
    governance_warnings = get_unacknowledged_upgrade_warnings(db, current_policy_pins={})
    governance_action_required_present = any(bool((w or {}).get("action_required")) for w in governance_warnings if isinstance(w, dict))
    program_posture = _derive_program_posture(
        stage_counts=stage_counts,
        total_molecules=len(molecules),
        cited_snapshot_ids=sorted(snapshot_ids),
        cited_templates=sorted(template_keys),
        cited_decisions=sorted(decision_keys),
        governance_action_required_present=governance_action_required_present,
    )
    return {
        "program_id": int(program_id),
        "as_of": as_of.isoformat(),
        "snapshot_ids": sorted(snapshot_ids),
        "policy_versions": sorted(policy_versions),
        "policy_package_hashes": sorted(policy_package_hashes),
        "stage_counts": {k: stage_counts[k] for k in sorted(stage_counts)},
        "molecules": molecules,
        "program_posture": program_posture,
        "rollup_citations": {
            "snapshot_ids": sorted(snapshot_ids),
            "policy_versions": sorted(policy_versions),
            "policy_package_hashes": sorted(policy_package_hashes),
            "template_keys": sorted(template_keys),
            "decision_keys": sorted(decision_keys),
            "molecule_ids": [int(m["molecule_id"]) for m in molecules if isinstance(m, dict)],
            "snapshot_coverage_summary": {
                "snapshot_count": len(sorted(snapshot_ids)),
                "molecule_count": len([m for m in molecules if isinstance(m, dict)]),
            },
            "governance_action_required_present": bool(governance_action_required_present),
        },
    }


def persist_program_rollup(
    db: Session,
    *,
    program_id: int,
    as_of: datetime,
    policy_pin: str,
) -> ProgramRollup:
    payload = build_program_rollup(db, program_id=program_id, as_of=as_of)
    snapshot_ids = payload.get("snapshot_ids") if isinstance(payload.get("snapshot_ids"), list) else []
    policy_package_hashes = payload.get("policy_package_hashes") if isinstance(payload.get("policy_package_hashes"), list) else []
    row = ProgramRollup(
        program_id=int(program_id),
        as_of=as_of,
        policy_pin=str(policy_pin),
        policy_package_hash=(str(policy_package_hashes[0]) if len(policy_package_hashes) == 1 else None),
        snapshot_ids_json=stable_json_dumps([int(x) for x in snapshot_ids if isinstance(x, int)]),
        payload_json=stable_json_dumps(payload),
        created_at=now_utc(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
