from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from psi.core.db import get_db
from psi.core.models import DecisionSnapshot, OutcomeLabel
from psi.core.utils import stable_json_dumps
from psi.services import decisions as svc


def _exit(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def _parse_bool(val: str | None) -> bool | None:
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in ("true", "1", "yes", "y"):
        return True
    if s in ("false", "0", "no", "n"):
        return False
    return None


def _parse_outcome_event_date(val: str | None):
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        _exit("--outcome-event-date must be ISO8601 (e.g. 2026-02-26 or 2026-02-26T12:00:00Z)")
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _snapshot_or_exit(db, snapshot_id: int) -> DecisionSnapshot:
    snap = db.get(DecisionSnapshot, int(snapshot_id))
    if not snap:
        _exit(f"DecisionSnapshot not found: {snapshot_id}")
    return snap


def cmd_add(args: argparse.Namespace) -> None:
    with get_db(args.db or None, ensure=True) as db:
        _snapshot_or_exit(db, int(args.snapshot_id))
        value_bool = _parse_bool(args.bool)
        if args.bool is not None and value_bool is None:
            _exit("--bool must be true|false")
        value_num = float(args.num) if args.num is not None else None
        outcome_event_date = _parse_outcome_event_date(args.outcome_event_date)
        lab = svc.add_outcome_label(
            db,
            snapshot_id=int(args.snapshot_id),
            name=str(args.name or "").strip(),
            value_text=(str(args.text) if args.text is not None else None),
            value_num=value_num,
            value_bool=value_bool,
            outcome_event_date=outcome_event_date,
            version=str(args.version or "v1"),
        )
        print(f"OK outcome_label_id={lab.id}")


def cmd_list(args: argparse.Namespace) -> None:
    with get_db(args.db or None, ensure=True) as db:
        snap = _snapshot_or_exit(db, int(args.snapshot_id))
        rows = (
            db.query(OutcomeLabel)
            .filter(OutcomeLabel.snapshot_id == snap.id)
            .order_by(OutcomeLabel.created_at.asc())
            .all()
        )
        out = []
        for r in rows:
            out.append(
                {
                    "id": int(r.id),
                    "snapshot_id": int(r.snapshot_id),
                    "name": r.name,
                    "value_text": r.value_text,
                    "value_num": r.value_num,
                    "value_bool": bool(r.value_bool) if r.value_bool is not None else None,
                    "outcome_event_date": r.outcome_event_date.isoformat() if getattr(r, "outcome_event_date", None) else None,
                    "version": r.version,
                    "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
                }
            )
        print(stable_json_dumps(out))


def cmd_di_review(args: argparse.Namespace) -> None:
    verdict = str(args.verdict or "").strip()
    rationale = str(args.rationale or "").strip()
    if not verdict:
        _exit("--verdict is required")
    if not rationale:
        _exit("--rationale is required")

    with get_db(args.db or None, ensure=True) as db:
        _snapshot_or_exit(db, int(args.snapshot_id))
        snap_ctx = svc.get_snapshot_detail(db, int(args.snapshot_id))
        valid = {lt["key"] for lt in (snap_ctx.get("di_review_verdicts") or []) if isinstance(lt, dict)}
        if verdict not in valid:
            _exit(f"Invalid DI review verdict: {verdict}")

        svc.add_outcome_label(
            db,
            snapshot_id=int(args.snapshot_id),
            name="di_review_verdict",
            value_text=verdict,
        )
        svc.add_outcome_label(
            db,
            snapshot_id=int(args.snapshot_id),
            name="di_review_rationale",
            value_text=rationale,
        )
        print("OK di_review saved")


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m psi.tools.label_outcome", description="Outcome labeling CLI")
    ap.add_argument("--db", default="", help="Optional path to sqlite db (default uses PSI_DB_PATH or psi/psi.sqlite)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_add = sub.add_parser("add", help="Add an outcome label")
    ap_add.add_argument("--snapshot-id", required=True, type=int)
    ap_add.add_argument("--name", required=True)
    ap_add.add_argument("--text", default=None)
    ap_add.add_argument("--num", default=None)
    ap_add.add_argument("--bool", default=None)
    ap_add.add_argument("--outcome-event-date", default=None, help="Optional outcome event timestamp/date (ISO8601)")
    ap_add.add_argument("--version", default="v1")
    ap_add.set_defaults(func=cmd_add)

    ap_list = sub.add_parser("list", help="List outcome labels for a snapshot")
    ap_list.add_argument("--snapshot-id", required=True, type=int)
    ap_list.set_defaults(func=cmd_list)

    ap_review = sub.add_parser("di-review", help="Add DI review verdict + rationale")
    ap_review.add_argument("--snapshot-id", required=True, type=int)
    ap_review.add_argument("--verdict", required=True)
    ap_review.add_argument("--rationale", required=True)
    ap_review.set_defaults(func=cmd_di_review)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
