from __future__ import annotations

"""Cross-version verification stress test (read-only)."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from psi.core.db import get_db
from psi.core.models import DecisionSnapshot
from psi.services.di.verify import verify_snapshot


def _safe_json(s: str | None) -> dict:
    try:
        obj = json.loads(s or "{}")
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _detect_is_di(snap: DecisionSnapshot, inputs: dict, output: dict) -> bool:
    return bool(
        (getattr(snap, "engine_key", None) == "di")
        or (str(getattr(snap, "schema_version", "") or "").startswith("di."))
        or (isinstance(output, dict) and ("decision_state" in output) and ("gates" in output))
        or (isinstance(inputs, dict) and (str(inputs.get("engine_key") or "").strip() == "di"))
        or (isinstance(inputs, dict) and str(inputs.get("schema_version") or "").startswith("di."))
    )


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="python -m psi.tools.di_cross_version_stress",
        description="Cross-version verification stress test for DI DecisionSnapshots (read-only).",
    )
    ap.add_argument("--db", required=True, help="Path to sqlite db (required)")
    ap.add_argument("--limit", type=int, default=50, help="Max snapshots to test (default 50)")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.is_file():
        print(f"cross_version_stress: ERROR: db file not found: {db_path}", file=sys.stderr)
        sys.exit(2)

    limit = int(args.limit)

    tested = 0
    passed = 0
    warned = 0
    failed = 0
    hard_failed = 0
    skipped = 0
    failures: List[Dict[str, Any]] = []
    counts_by_classification: Dict[str, int] = {}

    with get_db(str(db_path), ensure=False) as db:
        snaps = (
            db.query(DecisionSnapshot)
            .order_by(DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc())
            .limit(limit)
            .all()
        )

        for snap in snaps:
            out = _safe_json(snap.outputs_json)
            inn = _safe_json(snap.inputs_json)
            if not _detect_is_di(snap, inn, out):
                skipped += 1
                print(f"SKIP snapshot_id={int(snap.id)} reason=non_di")
                continue

            tested += 1
            sid = int(snap.id)
            try:
                report = verify_snapshot(db=db, snapshot_id=sid, debug=False)
                classification = str(report.get("classification") if isinstance(report, dict) else "")
                anchored = report.get("anchored_replay") if isinstance(report, dict) else None
                anchored_avail = bool(anchored.get("available")) if isinstance(anchored, dict) else False
                anchored_cls = anchored.get("stored_vs_replay_classification") if isinstance(anchored, dict) else None

                counts_by_classification[classification] = counts_by_classification.get(classification, 0) + 1

                anchored_ok = (not anchored_avail) or (str(anchored_cls) == "VERIFIED")
                if anchored_avail and str(anchored_cls) != "VERIFIED":
                    failed += 1
                    hard_failed += 1
                    failures.append(
                        {
                            "snapshot_id": sid,
                            "classification": classification,
                            "anchored_classification": anchored_cls,
                        }
                    )
                    print(f"FAIL snapshot_id={sid} classification={classification} anchored={anchored_cls}")
                    continue

                if classification == "VERIFIED" and anchored_ok:
                    passed += 1
                    print(f"PASS snapshot_id={sid}")
                elif classification == "DATA_DRIFT" and anchored_ok:
                    warned += 1
                    print(f"WARN snapshot_id={sid} classification={classification} anchored={anchored_cls}")
                else:
                    failed += 1
                    hard_failed += 1
                    failures.append(
                        {
                            "snapshot_id": sid,
                            "classification": classification,
                            "anchored_classification": anchored_cls,
                        }
                    )
                    print(f"FAIL snapshot_id={sid} classification={classification} anchored={anchored_cls}")
            except Exception as e:
                failed += 1
                hard_failed += 1
                counts_by_classification["exception"] = counts_by_classification.get("exception", 0) + 1
                failures.append({"snapshot_id": sid, "classification": "exception", "error": str(e)})
                print(f"FAIL snapshot_id={sid} classification=exception error={e}")

    summary = {
        "db": str(db_path),
        "limit": limit,
        "matched": len(snaps),
        "tested": tested,
        "passed": passed,
        "warned": warned,
        "failed": failed,
        "hard_failed": hard_failed,
        "skipped": skipped,
        "counts_by_classification": counts_by_classification,
        "failures": failures,
    }

    print("---")
    print(_stable_json(summary))

    if hard_failed > 0:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
