from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from psi.core.utils import stable_json_dumps


def load_ranking_policy_v0_1() -> dict[str, Any]:
    p = Path(__file__).resolve().parents[1] / "core" / "di" / "catalogs" / "ranking_policy_v0_1.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("ranking policy must be object")
    return raw


def build_ranking_surface(*, entities: list[dict[str, Any]], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    pol = policy if isinstance(policy, dict) else load_ranking_policy_v0_1()
    enabled = bool(pol.get("enabled"))
    criteria = pol.get("criteria_registry") if isinstance(pol.get("criteria_registry"), list) else []
    tie_break = pol.get("tie_break") if isinstance(pol.get("tie_break"), dict) else {}
    normalized: list[dict[str, Any]] = []
    for ent in entities or []:
        if not isinstance(ent, dict):
            continue
        etype = str(ent.get("entity_type") or "")
        eid = int(ent.get("entity_id") or 0)
        stable_key = str(ent.get("stable_sort_key") or "")
        criteria_hits = ent.get("criteria_hits") if isinstance(ent.get("criteria_hits"), list) else []
        hits = sorted({str(x) for x in criteria_hits if str(x)})
        normalized.append(
            {
                "entity_type": etype,
                "entity_id": eid,
                "stable_sort_key": stable_key,
                "criteria_hits": hits,
            }
        )
    normalized = sorted(normalized, key=lambda r: (str(r.get("stable_sort_key") or ""), int(r.get("entity_id") or 0)))
    if not enabled:
        return {
            "enabled": False,
            "policy_id": str(pol.get("policy_id") or ""),
            "policy_version": str(pol.get("policy_version") or ""),
            "reason": "policy_disabled",
            "entities": normalized,
            "criteria_registry": [str((c or {}).get("criterion_id") or "") for c in criteria if isinstance(c, dict)],
            "tie_break_keys": [str(x) for x in (tie_break.get("keys") or []) if str(x)],
        }
    # Deterministic explainable ordering: count visible criteria hits, then explicit tie-break keys.
    ranked = sorted(
        normalized,
        key=lambda r: (-len(r.get("criteria_hits") or []), str(r.get("stable_sort_key") or ""), int(r.get("entity_id") or 0)),
    )
    for idx, row in enumerate(ranked, start=1):
        row["rank"] = idx
        row["reason_trail"] = [{"criterion_id": c, "hit": True} for c in (row.get("criteria_hits") or [])]
    return {
        "enabled": True,
        "policy_id": str(pol.get("policy_id") or ""),
        "policy_version": str(pol.get("policy_version") or ""),
        "entities": ranked,
        "criteria_registry": [str((c or {}).get("criterion_id") or "") for c in criteria if isinstance(c, dict)],
        "tie_break_keys": [str(x) for x in (tie_break.get("keys") or []) if str(x)],
        "surface_hash_basis": stable_json_dumps({"entities": ranked}),
    }
