from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from psi.core.utils import stable_json_dumps
from psi.core.di.policy import sha256_hex_of_canonical_json


def load_ranking_policy_v0_1() -> dict[str, Any]:
    p = Path(__file__).resolve().parents[1] / "core" / "di" / "catalogs" / "ranking_policy_v0_1.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("ranking policy must be object")
    return raw


def load_ranking_policy_v0_2() -> dict[str, Any]:
    p = Path(__file__).resolve().parents[1] / "core" / "di" / "catalogs" / "ranking_policy_v0_2.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("ranking policy must be object")
    method = raw.get("method") if isinstance(raw.get("method"), dict) else {}
    tie_break_keys = [str(x) for x in (method.get("tie_break_keys") or []) if str(x)]
    tie_contract = method.get("tie_break_contract") if isinstance(method.get("tie_break_contract"), dict) else {}
    method["tie_break_contract"] = {
        "deterministic_only": bool(tie_contract.get("deterministic_only", True)),
        "tie_break_keys": tie_break_keys or ["stable_sort_key", "entity_id"],
        "explanation_schema_version": str(tie_contract.get("explanation_schema_version") or "v1"),
        "numeric_scoring_allowed": bool(tie_contract.get("numeric_scoring_allowed", False)),
        "description": str(
            tie_contract.get("description")
            or "Tie-break uses explicit key order only; no numeric scoring."
        ),
    }
    if "weights" in method:
        method.pop("weights", None)
    raw["method"] = method
    return raw


def load_ranking_policy_latest() -> dict[str, Any]:
    return load_ranking_policy_v0_2()


def build_ranking_surface(*, entities: list[dict[str, Any]], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    pol = policy if isinstance(policy, dict) else load_ranking_policy_latest()
    enabled = bool(pol.get("enabled"))
    criteria = pol.get("criteria_registry") if isinstance(pol.get("criteria_registry"), list) else []
    method = pol.get("method") if isinstance(pol.get("method"), dict) else {}
    policy_semantics_hash = sha256_hex_of_canonical_json(pol)
    policy_package_hash = policy_semantics_hash
    normalized: list[dict[str, Any]] = []
    tie_break_keys = [str(x) for x in (method.get("tie_break_keys") or []) if str(x)]

    def _tie_break_tuple(ent: dict[str, Any]) -> tuple:
        parts: list[Any] = []
        for key in tie_break_keys:
            if key == "entity_id":
                parts.append(int(ent.get("entity_id") or 0))
            elif key == "stable_sort_key":
                parts.append(str(ent.get("stable_sort_key") or ""))
            elif key == "entity_type":
                parts.append(str(ent.get("entity_type") or ""))
            else:
                parts.append(str(ent.get(key) or ""))
        if not parts:
            parts = [str(ent.get("stable_sort_key") or ""), int(ent.get("entity_id") or 0)]
        return tuple(parts)

    for ent in entities or []:
        if not isinstance(ent, dict):
            continue
        etype = str(ent.get("entity_type") or "")
        eid = int(ent.get("entity_id") or 0)
        stable_key = str(ent.get("stable_sort_key") or "")
        criteria_hits = ent.get("criteria_hits") if isinstance(ent.get("criteria_hits"), list) else []
        criteria_outcomes = ent.get("criterion_outcomes") if isinstance(ent.get("criterion_outcomes"), dict) else {}
        hits = sorted({str(x) for x in criteria_hits if str(x)})
        outcomes = {str(k): str(v).upper() for k, v in sorted(criteria_outcomes.items(), key=lambda kv: str(kv[0])) if str(k)}
        normalized.append(
            {
                "entity_type": etype,
                "entity_id": eid,
                "stable_sort_key": stable_key,
                "criteria_hits": hits,
                "criterion_outcomes": outcomes,
            }
        )
    normalized = sorted(normalized, key=lambda r: (str(r.get("stable_sort_key") or ""), int(r.get("entity_id") or 0)))
    if not enabled:
        return {
            "enabled": False,
            "policy_id": str(pol.get("policy_id") or ""),
            "policy_version": str(pol.get("policy_version") or ""),
            "policy_semantics_hash": policy_semantics_hash,
            "policy_package_hash": policy_package_hash,
            "reason": "policy_disabled",
            "entities": normalized,
            "criteria_registry": [str((c or {}).get("criterion_id") or "") for c in criteria if isinstance(c, dict)],
            "tie_break_keys": tie_break_keys,
        }
    method_type = str(method.get("type") or "").strip()
    criteria_order = [str(x) for x in (method.get("criteria_order") or []) if str(x)]
    outcome_precedence = [str(x).upper() for x in (method.get("outcome_precedence") or []) if str(x)]
    if method_type != "lexicographic_ladder" or not criteria_order or not outcome_precedence:
        return {
            "enabled": True,
            "policy_id": str(pol.get("policy_id") or ""),
            "policy_version": str(pol.get("policy_version") or ""),
            "policy_semantics_hash": policy_semantics_hash,
            "policy_package_hash": policy_package_hash,
            "reason": "policy_incomplete",
            "entities": [],
            "criteria_registry": [str((c or {}).get("criterion_id") or "") for c in criteria if isinstance(c, dict)],
            "tie_break_keys": tie_break_keys,
        }
    precedence_rank = {k: i for i, k in enumerate(outcome_precedence)}

    def _outcome(ent: dict[str, Any], criterion_id: str) -> str:
        explicit = str((ent.get("criterion_outcomes") or {}).get(criterion_id) or "").upper()
        if explicit in precedence_rank:
            return explicit
        return "PASS" if criterion_id in (ent.get("criteria_hits") or []) else "NA"

    def _lexi_key(ent: dict[str, Any]) -> tuple:
        crit_key = tuple(precedence_rank.get(_outcome(ent, cid), len(precedence_rank) + 1) for cid in criteria_order)
        tb = _tie_break_tuple(ent)
        return crit_key + tb

    ranked = sorted(
        normalized,
        key=_lexi_key,
    )
    for idx, row in enumerate(ranked, start=1):
        row["rank"] = idx
        row["reason_trail"] = [
            {
                "policy_rule_id": c,
                "criterion_id": c,
                "outcome": _outcome(row, c),
                "applied": (_outcome(row, c) == "PASS"),
            }
            for c in criteria_order
        ]
        tie_values = {}
        for k in tie_break_keys:
            if k == "entity_id":
                tie_values[k] = int(row.get("entity_id") or 0)
            elif k == "stable_sort_key":
                tie_values[k] = str(row.get("stable_sort_key") or "")
            elif k == "entity_type":
                tie_values[k] = str(row.get("entity_type") or "")
            else:
                tie_values[k] = str(row.get(k) or "")
        row["tie_break_explanation"] = {
            "keys": tie_break_keys,
            "key_values": tie_values,
            "schema_version": str(
                (
                    method.get("tie_break_contract")
                    if isinstance(method.get("tie_break_contract"), dict)
                    else {}
                ).get("explanation_schema_version")
                or "v1"
            ),
            "stable_sort_key": str(row.get("stable_sort_key") or ""),
            "entity_id": int(row.get("entity_id") or 0),
        }
    return {
        "enabled": True,
        "policy_id": str(pol.get("policy_id") or ""),
        "policy_version": str(pol.get("policy_version") or ""),
        "policy_semantics_hash": policy_semantics_hash,
        "policy_package_hash": policy_package_hash,
        "entities": ranked,
        "criteria_registry": [str((c or {}).get("criterion_id") or "") for c in criteria if isinstance(c, dict)],
        "tie_break_keys": tie_break_keys,
        "explanation_trace_version": "v0.1",
        "surface_hash_basis": stable_json_dumps({"entities": ranked}),
    }
