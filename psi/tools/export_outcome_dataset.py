from __future__ import annotations

import argparse
import json
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


def _label_row(r: OutcomeLabel) -> dict[str, Any]:
    return {
        "id": int(r.id),
        "name": str(r.name or ""),
        "value_text": r.value_text,
        "value_num": r.value_num,
        "value_bool": (bool(r.value_bool) if r.value_bool is not None else None),
        "version": str(r.version or ""),
        "created_at": (r.created_at.isoformat() if getattr(r, "created_at", None) else None),
    }


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
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with get_db(args.db or None, ensure=False) as db:
        q = db.query(DecisionSnapshot)
        if str(args.engine_key or "") != "":
            q = q.filter(DecisionSnapshot.engine_key == str(args.engine_key))
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

        rows_written = 0
        with out_path.open("w", encoding="utf-8") as fh:
            for s in snaps:
                inp = _json_obj(getattr(s, "inputs_json", None))
                out = _json_obj(getattr(s, "outputs_json", None))
                pol_out = out.get("policy") if isinstance(out.get("policy"), dict) else {}
                prov = out.get("provenance") if isinstance(out.get("provenance"), dict) else {}
                integ = prov.get("integrity") if isinstance(prov.get("integrity"), dict) else {}

                labels = list(labels_by_snapshot.get(int(s.id)) or [])
                latest_label_by_name: dict[str, dict[str, Any]] = {}
                for lab in labels:
                    nm = str(lab.get("name") or "").strip()
                    if not nm:
                        continue
                    latest_label_by_name[nm] = lab

                row = {
                    "snapshot_id": int(s.id),
                    "created_at": (s.created_at.isoformat() if getattr(s, "created_at", None) else None),
                    "engine_key": str(getattr(s, "engine_key", "") or ""),
                    "decision_key": str(getattr(s, "decision_key", "") or ""),
                    "policy_semantics_hash": str(inp.get("policy_semantics_hash") or pol_out.get("policy_semantics_hash") or ""),
                    "policy_package_hash": str(inp.get("policy_package_hash") or pol_out.get("policy_package_hash") or ""),
                    "evidence_fingerprint": str(integ.get("evidence_fingerprint") or ""),
                    "decision_state": str(out.get("decision_state") or ""),
                    "di_review_verdict": str((latest_label_by_name.get("di_review_verdict") or {}).get("value_text") or ""),
                    "di_review_rationale": str((latest_label_by_name.get("di_review_rationale") or {}).get("value_text") or ""),
                    "outcome_labels": labels,
                }
                fh.write(stable_json_dumps(row) + "\n")
                rows_written += 1

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
