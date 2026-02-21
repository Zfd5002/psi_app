from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from psi.core.db import get_db
from psi.core.di.policy import load_policy
from psi.core.di.schema import DIInput
from psi.core.models import DecisionSnapshot
from psi.services.di.runner import compute_di_output


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _parse_json_field(raw: str, *, default: Any) -> Any:
    if raw is None:
        return default
    s = str(raw).strip()
    if not s:
        return default
    return json.loads(s)


def _resolve_policy_from_repo(*, policy_id: str, policy_version: str) -> Tuple[Any, Path]:
    base = Path(__file__).resolve().parents[1]  # psi/
    pol_dir = base / "core" / "di" / "policies"
    if not pol_dir.exists():
        raise SystemExit(f"Policy directory not found: {pol_dir}")

    matches: List[Tuple[Any, Path]] = []
    for p in sorted(pol_dir.glob("*.json")):
        try:
            pol = load_policy(p)
        except Exception:
            continue
        if str(pol.policy_id) == str(policy_id) and str(pol.version) == str(policy_version):
            matches.append((pol, p))

    if not matches:
        raise SystemExit(f"Policy not found in repo for policy_id={policy_id!r} policy_version={policy_version!r}")
    if len(matches) > 1:
        # Deterministic choice, but treat as governance warning.
        matches.sort(key=lambda t: str(t[1]))
    return matches[0]


def _extract_evidence_tuples_from_used(used_by_metric: Dict[str, Any]) -> List[List[str]]:
    tuples: List[List[str]] = []
    for mk in sorted(list((used_by_metric or {}).keys())):
        ev = used_by_metric[mk]
        if isinstance(ev, dict):
            measurement_id = str(ev.get("measurement_id") or "")
            qc_status = str(ev.get("qc_status") or "")
            unit = str(ev.get("unit") or "")
            comparator = str(ev.get("comparator") or "")
        else:
            measurement_id = str(getattr(ev, "measurement_id", "") or "")
            qc_status = str(getattr(ev, "qc_status", "") or "")
            unit = str(getattr(ev, "unit", "") or "")
            comparator = str(getattr(ev, "comparator", "") or "")
        tuples.append(
            [
                str(mk),
                measurement_id,
                qc_status,
                unit,
                comparator,
            ]
        )
    return tuples


def _drift_classification(
    *,
    stored_policy_semantics_hash: str,
    stored_policy_package_hash: str,
    recomputed_policy_semantics_hash: str,
    recomputed_policy_package_hash: str,
    stored_evidence_fingerprint: str,
    recomputed_evidence_fingerprint: str,
    stored_snapshot_content_hash: str,
    recomputed_snapshot_content_hash: str,
    stored_evidence_tuples: List[List[str]] | None,
    recomputed_evidence_tuples: List[List[str]] | None,
) -> Tuple[str, Dict[str, Any]]:
    """Return (classification, explain)."""

    explain: Dict[str, Any] = {
        "policy_hash_changed": False,
        "evidence_changed": False,
        "qc_only_changes": False,
        "structural_only": False,
        "missing_stored_integrity_fields": False,
    }

    missing_integrity = (not stored_snapshot_content_hash) or (not stored_evidence_fingerprint)
    if missing_integrity:
        explain["missing_stored_integrity_fields"] = True

    if (stored_policy_semantics_hash != recomputed_policy_semantics_hash) or (stored_policy_package_hash != recomputed_policy_package_hash):
        explain["policy_hash_changed"] = True
        return "POLICY_DRIFT", explain

    # Legacy snapshots without integrity fields cannot be VERIFIED; treat as structural drift.
    if missing_integrity:
        explain["structural_only"] = True
        return "STRUCTURAL_DRIFT", explain

    if stored_evidence_fingerprint != recomputed_evidence_fingerprint:
        explain["evidence_changed"] = True
        qc_only = False
        if stored_evidence_tuples is not None and recomputed_evidence_tuples is not None:
            if len(stored_evidence_tuples) == len(recomputed_evidence_tuples):
                same_metric_and_id = True
                qc_changed = False
                for a, b in zip(stored_evidence_tuples, recomputed_evidence_tuples):
                    # [metric_key, measurement_id, qc_status, unit, comparator]
                    if a[0] != b[0] or a[1] != b[1]:
                        same_metric_and_id = False
                        break
                    if a[2] != b[2]:
                        qc_changed = True
                if same_metric_and_id and qc_changed:
                    qc_only = True
        explain["qc_only_changes"] = qc_only
        return ("QC_DRIFT" if qc_only else "DATA_DRIFT"), explain

    if stored_snapshot_content_hash != recomputed_snapshot_content_hash:
        explain["structural_only"] = True
        return "STRUCTURAL_DRIFT", explain

    return "VERIFIED", explain


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="python -m psi.tools.verify_snapshot",
        description="Verify a persisted PSI DI DecisionSnapshot deterministically (read-only).",
    )
    ap.add_argument("--snapshot-id", required=True, type=int, help="DecisionSnapshot id")
    ap.add_argument("--db", default="", help="Optional path to sqlite db (default uses PSI_DB_PATH or psi/psi.sqlite)")
    args = ap.parse_args()

    with get_db(args.db.strip() or None, ensure=True) as db:
        snap = db.query(DecisionSnapshot).filter(DecisionSnapshot.id == int(args.snapshot_id)).first()
        if not snap:
            raise SystemExit(f"Snapshot not found: {args.snapshot_id}")

        inputs_obj = _parse_json_field(snap.inputs_json, default={})
        outputs_obj = _parse_json_field(snap.outputs_json, default={})
        evidence_ids = _parse_json_field(snap.evidence_ids_json, default=[])
        if not isinstance(evidence_ids, list):
            evidence_ids = []

        # Stored policy identifiers/hashes
        stored_policy_id = str(inputs_obj.get("policy_id") or "")
        stored_policy_version = str(inputs_obj.get("policy_version") or "")
        stored_policy_semantics_hash = str(inputs_obj.get("policy_semantics_hash") or "")
        stored_policy_package_hash = str(inputs_obj.get("policy_package_hash") or "")

        # Resolve policy from repo (do NOT use policy_path)
        pol, pol_path = _resolve_policy_from_repo(policy_id=stored_policy_id, policy_version=stored_policy_version)

        # Compare stored hashes vs resolved policy hashes (policy drift check)
        recomputed_policy_semantics_hash = str(pol.policy_semantics_hash)
        recomputed_policy_package_hash = str(pol.policy_package_hash)

        # Re-run DI using pure computation path (must not persist)
        di_in = DIInput(
            decision_key=str(inputs_obj.get("decision_key") or snap.decision_key),
            scope_type=str(inputs_obj.get("scope_type") or "batch"),
            scope_id=int(inputs_obj.get("scope_id") or snap.batch_id),
            as_of_ts=(str(inputs_obj.get("as_of_ts")).strip() if inputs_obj.get("as_of_ts") is not None else None),
            qc_mode=str(inputs_obj.get("qc_mode") or "model_safe"),
            context=(inputs_obj.get("context") or {}) if isinstance(inputs_obj.get("context") or {}, dict) else {},
        )

        recomputed = compute_di_output(db, di_input=di_in, pol=pol, policy_path=pol_path)
        recomputed_out = recomputed["output"]
        recomputed_inputs_obj = recomputed["inputs_obj"]
        recomputed_evidence_ids = recomputed["evidence_ids"]

        # Integrity fields (stored)
        stored_integrity = {}
        prov = outputs_obj.get("provenance") if isinstance(outputs_obj, dict) else None
        if isinstance(prov, dict):
            stored_integrity = prov.get("integrity") or {}
        stored_snapshot_content_hash = str(stored_integrity.get("snapshot_content_hash") or "")
        stored_evidence_fingerprint = str(stored_integrity.get("evidence_fingerprint") or "")

        # Integrity fields (recomputed)
        recomputed_integrity = {}
        rprov = recomputed_out.get("provenance") if isinstance(recomputed_out, dict) else None
        if isinstance(rprov, dict):
            recomputed_integrity = rprov.get("integrity") or {}
        recomputed_snapshot_content_hash = str(recomputed_integrity.get("snapshot_content_hash") or "")
        recomputed_evidence_fingerprint = str(recomputed_integrity.get("evidence_fingerprint") or "")

        # If stored integrity fields are missing (legacy snapshot), compute them for comparison
        # Evidence tuple payloads for drift explanation
        stored_used = {}
        if isinstance(outputs_obj, dict):
            soe = outputs_obj.get("state_of_evidence")
            if isinstance(soe, dict) and isinstance(soe.get("used"), dict):
                stored_used = soe.get("used") or {}
        stored_evidence_tuples = _extract_evidence_tuples_from_used(stored_used)

        recomputed_used = {}
        if isinstance(recomputed_out, dict):
            rsoe = recomputed_out.get("state_of_evidence")
            if isinstance(rsoe, dict) and isinstance(rsoe.get("used"), dict):
                recomputed_used = rsoe.get("used") or {}
        recomputed_evidence_tuples = _extract_evidence_tuples_from_used(recomputed_used)

        classification, explain = _drift_classification(
            stored_policy_semantics_hash=stored_policy_semantics_hash,
            stored_policy_package_hash=stored_policy_package_hash,
            recomputed_policy_semantics_hash=recomputed_policy_semantics_hash,
            recomputed_policy_package_hash=recomputed_policy_package_hash,
            stored_evidence_fingerprint=stored_evidence_fingerprint,
            recomputed_evidence_fingerprint=recomputed_evidence_fingerprint,
            stored_snapshot_content_hash=stored_snapshot_content_hash,
            recomputed_snapshot_content_hash=recomputed_snapshot_content_hash,
            stored_evidence_tuples=stored_evidence_tuples,
            recomputed_evidence_tuples=recomputed_evidence_tuples,
        )

        report = {
            "snapshot_id": int(snap.id),
            "classification": classification,
            "stored": {
                "policy_id": stored_policy_id,
                "policy_version": stored_policy_version,
                "policy_semantics_hash": stored_policy_semantics_hash,
                "policy_package_hash": stored_policy_package_hash,
                "snapshot_content_hash": stored_snapshot_content_hash,
                "evidence_fingerprint": stored_evidence_fingerprint,
            },
            "recomputed": {
                "policy_semantics_hash": recomputed_policy_semantics_hash,
                "policy_package_hash": recomputed_policy_package_hash,
                "snapshot_content_hash": recomputed_snapshot_content_hash,
                "evidence_fingerprint": recomputed_evidence_fingerprint,
            },
            "explain": explain,
        }

        print(_stable_json(report))


if __name__ == "__main__":
    main()
