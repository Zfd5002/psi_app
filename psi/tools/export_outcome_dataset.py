from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from psi.core.db import get_db
from psi.core.models import DecisionSnapshot, OutcomeLabel
from psi.core.utils import stable_json_dumps


def _json_obj(raw: str | None) -> dict[str, Any]:
    try:
        obj = json.loads(raw or "{}")
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _pick_non_empty_str(*vals: Any) -> str:
    for v in vals:
        s = str(v or "").strip()
        if s:
            return s
    return ""


def _extract_snapshot_hash_fields(*, inp: dict[str, Any], out: dict[str, Any]) -> dict[str, str]:
    pol_out = out.get("policy") if isinstance(out.get("policy"), dict) else {}
    prov = out.get("provenance") if isinstance(out.get("provenance"), dict) else {}
    integ = prov.get("integrity") if isinstance(prov.get("integrity"), dict) else {}
    policy_ref = prov.get("policy_ref") if isinstance(prov.get("policy_ref"), dict) else {}
    inputs_fp = prov.get("inputs_fingerprint") if isinstance(prov.get("inputs_fingerprint"), dict) else {}
    return {
        "policy_semantics_hash": _pick_non_empty_str(
            inp.get("policy_semantics_hash"),
            pol_out.get("policy_semantics_hash"),
            policy_ref.get("policy_semantics_hash"),
            policy_ref.get("hash"),
            inp.get("policy_hash"),
            pol_out.get("hash"),
        ),
        "policy_package_hash": _pick_non_empty_str(
            inp.get("policy_package_hash"),
            pol_out.get("policy_package_hash"),
            policy_ref.get("policy_package_hash"),
        ),
        "evidence_fingerprint": _pick_non_empty_str(
            integ.get("evidence_fingerprint"),
            inputs_fp.get("evidence_fingerprint"),
            out.get("evidence_fingerprint"),
        ),
    }


def _label_row(r: OutcomeLabel) -> dict[str, Any]:
    return {
        "id": int(r.id),
        "name": str(r.name or ""),
        "value_text": r.value_text,
        "value_num": r.value_num,
        "value_bool": (bool(r.value_bool) if r.value_bool is not None else None),
        "outcome_event_date": (r.outcome_event_date.isoformat() if getattr(r, "outcome_event_date", None) else None),
        "version": str(r.version or ""),
        "created_at": (r.created_at.isoformat() if getattr(r, "created_at", None) else None),
    }


def _days_between(snapshot_created_at: datetime | None, outcome_event_date_iso: str | None) -> float | None:
    if snapshot_created_at is None or not outcome_event_date_iso:
        return None
    try:
        dt = datetime.fromisoformat(str(outcome_event_date_iso))
    except Exception:
        return None
    # DB timestamps are stored/used as naive UTC in PSI; preserve that convention here.
    delta = dt - snapshot_created_at
    return round(delta.total_seconds() / 86400.0, 6)


def build_outcome_dataset_rows(*, db, engine_key_filter: str = "di") -> list[dict[str, Any]]:
    q = db.query(DecisionSnapshot)
    if str(engine_key_filter or "") != "":
        q = q.filter(DecisionSnapshot.engine_key == str(engine_key_filter))
    snaps = q.order_by(DecisionSnapshot.id.asc()).all()
    snap_ids = [int(s.id) for s in snaps]

    labels_by_snapshot: dict[int, list[dict[str, Any]]] = {}
    if snap_ids:
        for r in (
            db.query(OutcomeLabel)
            .filter(OutcomeLabel.snapshot_id.in_(snap_ids))
            .order_by(OutcomeLabel.snapshot_id.asc(), OutcomeLabel.created_at.asc(), OutcomeLabel.id.asc())
            .all()
        ):
            labels_by_snapshot.setdefault(int(r.snapshot_id), []).append(_label_row(r))

    rows: list[dict[str, Any]] = []
    for s in snaps:
        inp = _json_obj(getattr(s, "inputs_json", None))
        out = _json_obj(getattr(s, "outputs_json", None))
        hash_fields = _extract_snapshot_hash_fields(inp=inp, out=out)

        labels = list(labels_by_snapshot.get(int(s.id)) or [])
        latest_label_by_name: dict[str, dict[str, Any]] = {}
        for lab in labels:
            nm = str(lab.get("name") or "").strip()
            if not nm:
                continue
            latest_label_by_name[nm] = lab
        latest_outcome_event_date = next(
            (str(lab.get("outcome_event_date") or "") for lab in reversed(labels) if str(lab.get("outcome_event_date") or "")),
            "",
        )

        row = {
            "snapshot_id": int(s.id),
            "created_at": (s.created_at.isoformat() if getattr(s, "created_at", None) else None),
            "engine_key": str(getattr(s, "engine_key", "") or ""),
            "decision_key": str(getattr(s, "decision_key", "") or ""),
            "policy_semantics_hash": str(hash_fields.get("policy_semantics_hash") or ""),
            "policy_package_hash": str(hash_fields.get("policy_package_hash") or ""),
            "evidence_fingerprint": str(hash_fields.get("evidence_fingerprint") or ""),
            "decision_state": str(out.get("decision_state") or ""),
            "di_review_verdict": str((latest_label_by_name.get("di_review_verdict") or {}).get("value_text") or ""),
            "di_review_rationale": str((latest_label_by_name.get("di_review_rationale") or {}).get("value_text") or ""),
            "outcome_event_date": (latest_outcome_event_date or None),
            "days_to_outcome": _days_between(getattr(s, "created_at", None), latest_outcome_event_date or None),
            "outcome_labels": labels,
        }
        rows.append(row)
    return rows


def write_outcome_dataset_jsonl(*, rows: list[dict[str, Any]], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(stable_json_dumps(row) + "\n")
            rows_written += 1
    return rows_written


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="python -m psi.tools.export_outcome_dataset",
        description="Export a deterministic closed-loop outcome dataset from existing DB fields (read-only).",
    )
    ap.add_argument("--db", default="", help="Optional sqlite DB path (default uses PSI_DB_PATH / psi/psi.sqlite)")
    ap.add_argument("--output", default="outcome_dataset.jsonl", help="Output JSONL path (default: ./outcome_dataset.jsonl)")
    ap.add_argument("--engine-key", default="di", help="Filter decision_snapshots.engine_key (default: di). Use empty string for all.")
    args = ap.parse_args()

    out_path = Path(str(args.output or "outcome_dataset.jsonl")).expanduser().resolve()
    with get_db(args.db or None, ensure=False) as db:
        rows = build_outcome_dataset_rows(db=db, engine_key_filter=str(args.engine_key or ""))
        rows_written = write_outcome_dataset_jsonl(rows=rows, out_path=out_path)

    print(
        stable_json_dumps(
            {
                "ok": True,
                "output_path": str(out_path),
                "format": "jsonl",
                "rows_written": int(rows_written),
                "order": "snapshot_id_asc",
                "engine_key_filter": str(args.engine_key or ""),
                "db_mode": "read_only",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
