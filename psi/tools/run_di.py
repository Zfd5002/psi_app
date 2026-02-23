from __future__ import annotations

import argparse
import json
from pathlib import Path

from psi.core.db import get_db
from psi.core.di.schema import DIInput
from psi.services.di.runner import run_di


def _json_default(o):
    # Dataclasses and simple objects -> dict; otherwise stringify.
    d = getattr(o, '__dict__', None)
    if isinstance(d, dict):
        return d
    return str(o)


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="python -m psi.tools.run_di",
        description="Run PSI DI v0.3 headlessly and persist a DecisionSnapshot.",
    )
    ap.add_argument("--decision", required=True, help="Decision key (v0.1 supports: advance_to_in_vivo)")
    ap.add_argument("--batch-id", required=True, type=int, help="Batch DB id (integer)")
    ap.add_argument("--qc-mode", default="model_safe", choices=["strict", "model_safe", "none"])
    ap.add_argument("--as-of", default="", help="Optional ISO8601 as-of timestamp (e.g. 2026-02-20T12:00:00-05:00)")
    ap.add_argument("--db", default="", help="Optional path to sqlite db (default uses PSI_DB_PATH or psi/psi.sqlite)")
    ap.add_argument("--policy", default="", help="Optional path to policy JSON")
    ap.add_argument("--context-json", default="", help="Optional JSON object of context knobs (stored only)")
    args = ap.parse_args()

    decision = args.decision.strip()
    if decision != "advance_to_in_vivo":
        raise SystemExit("DI v0.3 only supports --decision advance_to_in_vivo")

    ctx = {}
    if args.context_json.strip():
        ctx = json.loads(args.context_json)
        if not isinstance(ctx, dict):
            raise SystemExit("--context-json must be a JSON object")

    base = Path(__file__).resolve().parents[1]  # psi/
    default_policy = base / "core" / "di" / "policies" / "advance_to_in_vivo_v0_3.json"
    policy_path = Path(args.policy).expanduser().resolve() if args.policy.strip() else default_policy
    if not policy_path.exists():
        raise SystemExit(f"Policy file not found: {policy_path}")

    di_in = DIInput(
        decision_key=decision,
        scope_type="batch",
        scope_id=int(args.batch_id),
        as_of_ts=(args.as_of.strip() or None),
        qc_mode=args.qc_mode,
        context=ctx,
    )

    with get_db(args.db.strip() or None, ensure=True) as db:
        res = run_di(db, di_input=di_in, policy_path=policy_path)

    print(json.dumps(res["output"], sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_json_default))
    print(f"\nSNAPSHOT_ID={res['snapshot_id']}")


if __name__ == "__main__":
    main()
