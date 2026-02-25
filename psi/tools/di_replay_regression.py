from __future__ import annotations

"""Replay regression harness for persisted DI DecisionSnapshots (read-only).

Usage:
  python -m psi.tools.di_replay_regression

This tool:
- Enumerates stored decision_snapshots deterministically.
- Replays each snapshot via the anchored replay path (selection bypass using stored SoE used measurement IDs).
- Asserts the anchored replay output matches the stored snapshot across all non-volatile fields.

Governance constraints:
- Must not mutate DB.
- Must not persist new snapshots.
- Must not change policy semantics or selector semantics.

The canonical verification + anchored replay logic lives in `psi.services.di.verify`.
This tool is an orchestrator and report renderer.
"""

import argparse
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Tuple

from sqlalchemy.orm import Session

from psi.core.db import DB_PATH, get_db
from psi.core.models import DecisionSnapshot
from psi.core.utils import stable_json_dumps
from psi.services.di.verify import verify_snapshot
from psi.version import PSI_VERSION

# Internal verifier helpers (kept in verify.py so web + CLI share semantics).
from psi.services.di import verify as verify_mod
from psi.core.di.schema import DIInput


def _iter_snapshots(
    db: Session,
    *,
    decision_key: str | None,
    program_id: int | None,
    molecule_id: int | None,
    batch_id: int | None,
    since_id: int | None,
    order: str,
    limit: int | None,
) -> List[DecisionSnapshot]:
    q = db.query(DecisionSnapshot)

    if decision_key:
        q = q.filter(DecisionSnapshot.decision_key == str(decision_key))
    if program_id is not None:
        q = q.filter(DecisionSnapshot.program_id == int(program_id))
    if molecule_id is not None:
        q = q.filter(DecisionSnapshot.molecule_id == int(molecule_id))
    if batch_id is not None:
        q = q.filter(DecisionSnapshot.batch_id == int(batch_id))
    if since_id is not None:
        q = q.filter(DecisionSnapshot.id >= int(since_id))

    if str(order).lower() == "asc":
        q = q.order_by(DecisionSnapshot.id.asc())
    else:
        q = q.order_by(DecisionSnapshot.id.desc())

    if limit is not None:
        q = q.limit(int(limit))

    return list(q.all())


def _diff_paths(a: Any, b: Any, *, path: str = "$") -> List[str]:
    """Return a deterministic list of differing JSON paths between a and b.

    - Dict keys compared in sorted order.
    - Lists compared by index; length differences recorded.
    - Scalars compared by value.

    This is intentionally minimal (paths only), to keep output concise and stable.
    """

    diffs: List[str] = []

    if type(a) != type(b):
        diffs.append(f"{path} (type {type(a).__name__} != {type(b).__name__})")
        return diffs

    if isinstance(a, dict):
        a_keys = set(a.keys())
        b_keys = set(b.keys())
        for k in sorted(a_keys - b_keys, key=lambda x: str(x)):
            diffs.append(f"{path}.{k} (missing_in_b)")
        for k in sorted(b_keys - a_keys, key=lambda x: str(x)):
            diffs.append(f"{path}.{k} (missing_in_a)")
        for k in sorted(a_keys & b_keys, key=lambda x: str(x)):
            diffs.extend(_diff_paths(a.get(k), b.get(k), path=f"{path}.{k}"))
        return diffs

    if isinstance(a, list):
        if len(a) != len(b):
            diffs.append(f"{path} (len {len(a)} != {len(b)})")
        n = min(len(a), len(b))
        for i in range(n):
            diffs.extend(_diff_paths(a[i], b[i], path=f"{path}[{i}]"))
        return diffs

    # scalar
    if a != b:
        diffs.append(f"{path} (value_mismatch)")
    return diffs


def _compute_semantic_diff_for_snapshot(db: Session, snap: DecisionSnapshot) -> Dict[str, Any]:
    """Best-effort: compute semantic-stripped diff between stored outputs and anchored replay outputs."""

    inputs_obj = verify_mod._parse_json_field(snap.inputs_json, default={})
    outputs_obj = verify_mod._parse_json_field(snap.outputs_json, default={})

    stored_policy_id = str(inputs_obj.get("policy_id") or "")
    stored_policy_version = str(inputs_obj.get("policy_version") or "")

    pol, pol_path = verify_mod._resolve_policy_from_repo(policy_id=stored_policy_id, policy_version=stored_policy_version)

    di_in = DIInput(
        decision_key=str(inputs_obj.get("decision_key") or snap.decision_key),
        scope_type=str(inputs_obj.get("scope_type") or "batch"),
        scope_id=int(inputs_obj.get("scope_id") or snap.batch_id),
        as_of_ts=(str(inputs_obj.get("as_of_ts")).strip() if inputs_obj.get("as_of_ts") is not None else None),
        qc_mode=str(inputs_obj.get("qc_mode") or "model_safe"),
        context=(inputs_obj.get("context") or {}) if isinstance(inputs_obj.get("context") or {}, dict) else {},
    )

    stored_evidence_ids_json = []
    try:
        stored_evidence_ids_json = verify_mod._coerce_int_list(
            verify_mod._parse_json_field(snap.evidence_ids_json, default=[])
        )
    except Exception:
        stored_evidence_ids_json = []

    anchored = verify_mod._compute_anchored_replay(
        db=db,
        di_in=di_in,
        pol=pol,
        policy_path=pol_path,
        stored_outputs_obj=(outputs_obj if isinstance(outputs_obj, dict) else {}),
        stored_evidence_ids_json=stored_evidence_ids_json,
        stored_inputs_obj=(inputs_obj if isinstance(inputs_obj, dict) else {}),
    )

    if not isinstance(anchored, dict) or anchored.get("available") is not True:
        return {
            "available": False,
            "reason": str((anchored or {}).get("reason") if isinstance(anchored, dict) else "unknown"),
            "diff_paths": [],
        }

    anchored_out = anchored.get("output")
    if not isinstance(outputs_obj, dict) or not isinstance(anchored_out, dict):
        return {"available": False, "reason": "outputs_not_dict", "diff_paths": []}

    stored_sem = verify_mod._strip_volatile_fields_for_semantic_compare(outputs_obj)
    replay_sem = verify_mod._strip_volatile_fields_for_semantic_compare(anchored_out)

    diffs = _diff_paths(stored_sem, replay_sem, path="$")
    return {
        "available": True,
        "reason": "ok",
        "diff_paths": diffs,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="python -m psi.tools.di_replay_regression",
        description="Replay regression harness for persisted DI DecisionSnapshots (anchored replay; read-only).",
    )

    ap.add_argument("--db", default="", help="Optional path to sqlite db (default uses PSI_DB_PATH or psi/psi.sqlite)")

    ap.add_argument("--decision-key", default="", help="Filter: decision_key")
    ap.add_argument("--program-id", type=int, default=None, help="Filter: program_id")
    ap.add_argument("--molecule-id", type=int, default=None, help="Filter: molecule_id")
    ap.add_argument("--batch-id", type=int, default=None, help="Filter: batch_id")
    ap.add_argument("--since-id", type=int, default=None, help="Filter: only snapshot ids >= since-id")

    ap.add_argument("--order", choices=["desc", "asc"], default="desc", help="Deterministic ordering by snapshot id")

    ap.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max snapshots to test (default 50). Ignored when --all is provided.",
    )
    ap.add_argument("--all", action="store_true", help="Test all matching snapshots (may be slow)")

    ap.add_argument(
        "--max-diff",
        type=int,
        default=20,
        help="When a snapshot fails, print at most this many semantic diff paths.",
    )
    ap.add_argument(
        "--allow-skip-unavailable",
        action="store_true",
        help="If anchored replay is unavailable for a snapshot, count it as skipped instead of failed.",
    )

    args = ap.parse_args()

    decision_key = args.decision_key.strip() or None
    limit = None if bool(args.all) else int(args.limit)

    if args.db.strip():
        resolved_db = Path(args.db.strip()).expanduser().resolve()
    else:
        resolved_db = Path(DB_PATH).expanduser().resolve()

    print(f"replay_regression: db={resolved_db}")
    print(f"replay_regression: psi_version={PSI_VERSION}")
    print("replay_regression: mode=read-only ensure=False")

    if args.db.strip() and not resolved_db.is_file():
        print(f"replay_regression: ERROR: db file not found: {resolved_db}", file=sys.stderr)
        sys.exit(2)

    tested = 0
    passed = 0
    failed = 0
    skipped = 0

    failures: List[Dict[str, Any]] = []

    with get_db(args.db.strip() or None, ensure=False) as db:
        snaps = _iter_snapshots(
            db,
            decision_key=decision_key,
            program_id=args.program_id,
            molecule_id=args.molecule_id,
            batch_id=args.batch_id,
            since_id=args.since_id,
            order=args.order,
            limit=limit,
        )

        print(f"replay_regression: matched={len(snaps)} order={args.order} limit={'ALL' if limit is None else limit}")

        for snap in snaps:
            tested += 1
            sid = int(snap.id)
            try:
                report = verify_snapshot(db=db, snapshot_id=sid, debug=False)

                anchored = report.get("anchored_replay") if isinstance(report, dict) else None
                av = bool(anchored.get("available")) if isinstance(anchored, dict) else False
                cls = anchored.get("stored_vs_replay_classification") if isinstance(anchored, dict) else None

                if not av:
                    anchored_reason = str(anchored.get("reason") if isinstance(anchored, dict) else "")
                    if anchored_reason == "policy_exact_match_not_found":
                        skipped += 1
                        print(f"SKIP snapshot_id={sid} reason=policy_exact_match_not_found")
                        continue
                    if bool(args.allow_skip_unavailable):
                        skipped += 1
                        print(f"SKIP snapshot_id={sid} reason=anchored_replay_unavailable")
                        continue

                    failed += 1
                    failures.append(
                        {
                            "snapshot_id": sid,
                            "failure_type": "anchored_replay_unavailable",
                            "anchored_reason": anchored.get("reason") if isinstance(anchored, dict) else None,
                        }
                    )
                    print(f"FAIL snapshot_id={sid} type=anchored_replay_unavailable reason={anchored.get('reason') if isinstance(anchored, dict) else ''}")
                    continue

                if str(cls) != "VERIFIED":
                    failed += 1

                    # Best-effort semantic diff snippet for humans.
                    diff = {}
                    try:
                        diff = _compute_semantic_diff_for_snapshot(db, snap)
                    except Exception as e:
                        diff = {"available": False, "reason": f"diff_error:{type(e).__name__}:{e}", "diff_paths": []}

                    # Capture a compact, deterministic failure record.
                    stored = report.get("stored") if isinstance(report, dict) else {}
                    replay = (anchored.get("replay") if isinstance(anchored, dict) else {})

                    fail_rec: Dict[str, Any] = {
                        "snapshot_id": sid,
                        "failure_type": f"replay_mismatch:{cls}",
                        "stored": {
                            "decision_output_hash_v2_effective": (stored.get("decision_output_hash_v2_effective") if isinstance(stored, dict) else None),
                            "evidence_fingerprint": (stored.get("evidence_fingerprint") if isinstance(stored, dict) else None),
                            "semantic_fingerprint": (stored.get("semantic_fingerprint") if isinstance(stored, dict) else None),
                        },
                        "replay": {
                            "decision_output_hash_v2_effective": (replay.get("decision_output_hash_v2_effective") if isinstance(replay, dict) else None),
                            "evidence_fingerprint": (replay.get("evidence_fingerprint") if isinstance(replay, dict) else None),
                            "semantic_fingerprint": (replay.get("semantic_fingerprint") if isinstance(replay, dict) else None),
                        },
                        "semantic_diff": {
                            "available": bool(diff.get("available")),
                            "reason": diff.get("reason"),
                            "diff_paths": (diff.get("diff_paths") or [])[: int(args.max_diff)],
                            "diff_paths_total": len(diff.get("diff_paths") or []),
                        },
                    }
                    failures.append(fail_rec)

                    print(f"FAIL snapshot_id={sid} type=replay_mismatch classification={cls}")
                    # Print a compact diff snippet inline.
                    if bool(fail_rec["semantic_diff"]["available"]):
                        paths = fail_rec["semantic_diff"]["diff_paths"]
                        for p in paths:
                            print(f"  diff: {p}")
                        if fail_rec["semantic_diff"]["diff_paths_total"] > len(paths):
                            print(f"  diff: ... ({fail_rec['semantic_diff']['diff_paths_total'] - len(paths)} more)")
                    else:
                        print(f"  diff: unavailable ({fail_rec['semantic_diff']['reason']})")

                    continue

                passed += 1
                print(f"PASS snapshot_id={sid}")

            except Exception as e:
                failed += 1
                failures.append({"snapshot_id": sid, "failure_type": f"exception:{type(e).__name__}", "error": str(e)})
                print(f"FAIL snapshot_id={sid} type=exception:{type(e).__name__} error={e}")

    summary = {
        "matched": len(snaps),
        "tested": tested,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "allow_skip_unavailable": bool(args.allow_skip_unavailable),
        "failures": failures,
    }

    print("---")
    print(stable_json_dumps(summary))

    if failed > 0:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
