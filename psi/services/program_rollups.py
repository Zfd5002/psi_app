from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from pathlib import Path

from sqlalchemy.orm import Session

from psi.core.models import DecisionSnapshot, Molecule, ProgramMembership, ProgramRollup
from psi.core.utils import now_utc, stable_json_dumps


def _safe_json_dict(raw: str | None) -> dict[str, Any]:
    try:
        obj = json.loads(raw or "{}")
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


_PROGRAM_POSTURE_POLICY_CACHE: dict[str, Any] | None = None


def _load_program_posture_policy() -> dict[str, Any]:
    global _PROGRAM_POSTURE_POLICY_CACHE
    if isinstance(_PROGRAM_POSTURE_POLICY_CACHE, dict):
        return _PROGRAM_POSTURE_POLICY_CACHE
    p = Path(__file__).resolve().parents[1] / "core" / "di" / "catalogs" / "program_posture_policy_v0_1.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("program_posture_policy_load_error")
    _PROGRAM_POSTURE_POLICY_CACHE = raw
    return _PROGRAM_POSTURE_POLICY_CACHE


def _derive_program_posture(*, stage_counts: dict[str, int], total_molecules: int) -> dict[str, Any]:
    policy = _load_program_posture_policy()
    labels = policy.get("posture_labels") if isinstance(policy.get("posture_labels"), list) else []
    allowed = {str(x) for x in labels if str(x)}
    ready = int(stage_counts.get("ready", 0))
    not_assessed = int(stage_counts.get("not_assessed", 0))
    blockedish = int(stage_counts.get("blocked", 0)) + int(stage_counts.get("failed", 0))
    posture = "at_risk"
    if total_molecules <= 0 or not_assessed >= total_molecules:
        posture = "blocked"
    elif blockedish > 0:
        posture = "blocked"
    elif total_molecules > 0 and ready >= total_molecules:
        posture = "on_track"
    if posture not in allowed and allowed:
        posture = sorted(allowed)[0]
    return {
        "policy_id": str(policy.get("policy_id") or "program_posture_policy_v0_1"),
        "policy_version": str(policy.get("policy_version") or "v0.1"),
        "posture": posture,
        "inputs_used": {
            "total_molecules": int(total_molecules),
            "stage_counts": {str(k): int(stage_counts[k]) for k in sorted(stage_counts.keys())},
        },
    }


def _is_di_snapshot(snap: DecisionSnapshot, out: dict[str, Any], inn: dict[str, Any]) -> bool:
    return bool(
        (getattr(snap, "engine_key", None) == "di")
        or str(getattr(snap, "schema_version", "") or "").startswith("di.")
        or ("decision_state" in out and "gates" in out)
        or str(inn.get("engine_key") or "").strip() == "di"
        or str(inn.get("schema_version") or "").startswith("di.")
    )


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
        out = _safe_json_dict(snap.outputs_json)
        inn = _safe_json_dict(snap.inputs_json)
        if _is_di_snapshot(snap, out, inn):
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
            }
        )
    return {
        "program_id": int(program_id),
        "as_of": as_of.isoformat(),
        "snapshot_ids": sorted(snapshot_ids),
        "policy_versions": sorted(policy_versions),
        "policy_package_hashes": sorted(policy_package_hashes),
        "stage_counts": {k: stage_counts[k] for k in sorted(stage_counts)},
        "molecules": molecules,
        "program_posture": _derive_program_posture(stage_counts=stage_counts, total_molecules=len(molecules)),
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
