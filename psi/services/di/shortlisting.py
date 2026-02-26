from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from psi.core.di.schema import DIInput
from psi.services.di.util import parse_iso


RANKING_RULE_VERSION = "v0.5.1"
_SHORTLISTING_POLICY_CACHE: Dict[str, Any] | None = None


def _shortlisting_policy_defaults() -> Dict[str, Any]:
    return {
        "batch_scope": {
            "decision_state_pro": 50.0,
            "decision_state_con": 50.0,
            "blockers_count": 5.0,
            "comparability_high_severity": 3.0,
            "metrics_present": 1.0,
            "metrics_missing": 1.0,
            "warnings_count": 1.0,
        },
        "molecule_scope": {
            "metrics_sourced_count": 2.0,
            "used_metric_count": 1.0,
            "ignored_count": 0.5,
            "warning_count": 1.0,
        },
    }


def _load_shortlisting_policy_weights() -> Dict[str, Any]:
    global _SHORTLISTING_POLICY_CACHE
    if isinstance(_SHORTLISTING_POLICY_CACHE, dict):
        return _SHORTLISTING_POLICY_CACHE
    defaults = _shortlisting_policy_defaults()
    p = Path(__file__).resolve().parents[2] / "core" / "di" / "catalogs" / "shortlisting_policy_v0_1.json"
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        _SHORTLISTING_POLICY_CACHE = defaults
        return _SHORTLISTING_POLICY_CACHE
    body = raw.get("ranking_weights") if isinstance(raw, dict) and isinstance(raw.get("ranking_weights"), dict) else {}
    out = json.loads(json.dumps(defaults))
    for scope_key in ("batch_scope", "molecule_scope"):
        src = body.get(scope_key) if isinstance(body.get(scope_key), dict) else {}
        dst = out.get(scope_key) if isinstance(out.get(scope_key), dict) else {}
        for k in sorted(dst.keys()):
            if k in src:
                try:
                    dst[k] = float(src.get(k))
                except Exception:
                    pass
    _SHORTLISTING_POLICY_CACHE = out
    return _SHORTLISTING_POLICY_CACHE


def _ranking_factor(key: str, direction: str, value: Any, weight: float) -> Dict[str, Any]:
    return {"key": key, "direction": direction, "value": value, "weight": weight}


def _score_from_factors(factors: List[Dict[str, Any]]) -> float:
    score = 0.0
    for f in factors:
        try:
            v = float(f.get("value") or 0.0)
            w = float(f.get("weight") or 0.0)
        except Exception:
            continue
        direction = str(f.get("direction") or "pro").strip().lower()
        if direction == "con":
            score -= v * w
        else:
            score += v * w
    return float(score)


def _ranking_sort_key(cand: Dict[str, Any]) -> tuple:
    score = float(cand.get("score") or 0.0)
    tb = cand.get("tie_breaker") if isinstance(cand.get("tie_breaker"), dict) else {}
    created_raw = tb.get("created_at")
    dt = parse_iso(str(created_raw)) if created_raw else None
    created_ts = dt.timestamp() if dt is not None else -1.0
    cid = int(cand.get("candidate_id") or 0)
    return (-score, -created_ts, -cid)


def build_ranking_payload(
    *,
    di_in: DIInput,
    out: Dict[str, Any],
    selection_provenance: Dict[str, Any],
) -> Dict[str, Any]:
    scope_type = str(di_in.scope_type or "batch")
    ranking_w = _load_shortlisting_policy_weights()
    batch_w = ranking_w.get("batch_scope") if isinstance(ranking_w.get("batch_scope"), dict) else {}
    mol_w = ranking_w.get("molecule_scope") if isinstance(ranking_w.get("molecule_scope"), dict) else {}
    candidates: List[Dict[str, Any]] = []

    if scope_type == "batch":
        factors: List[Dict[str, Any]] = []
        decision_state = str(out.get("decision_state") or "")
        if decision_state == "ready":
            factors.append(_ranking_factor("decision_state", "pro", 1.0, float(batch_w.get("decision_state_pro", 50.0))))
        elif decision_state == "not_ready":
            factors.append(_ranking_factor("decision_state", "con", 1.0, float(batch_w.get("decision_state_con", 50.0))))
        else:
            factors.append(_ranking_factor("decision_state", "con", 1.0, float(batch_w.get("decision_state_con", 50.0))))

        blockers = out.get("blockers") if isinstance(out.get("blockers"), list) else []
        factors.append(_ranking_factor("blockers_count", "con", float(len(blockers)), float(batch_w.get("blockers_count", 5.0))))

        comp = out.get("comparability") if isinstance(out.get("comparability"), dict) else {}
        summary = comp.get("summary") if isinstance(comp.get("summary"), dict) else {}
        high_sev = float(summary.get("high_severity_count") or 0)
        factors.append(_ranking_factor("comparability_high_severity", "con", high_sev, float(batch_w.get("comparability_high_severity", 3.0))))

        soe = out.get("state_of_evidence") if isinstance(out.get("state_of_evidence"), dict) else {}
        soe_v0_2 = soe.get("soe_v0_2") if isinstance(soe.get("soe_v0_2"), dict) else {}
        coverage = soe_v0_2.get("coverage") if isinstance(soe_v0_2.get("coverage"), dict) else {}
        missing = float(len(coverage.get("metrics_missing") or []))
        present = float(len(coverage.get("metrics_present") or []))
        factors.append(_ranking_factor("metrics_present", "pro", present, float(batch_w.get("metrics_present", 1.0))))
        factors.append(_ranking_factor("metrics_missing", "con", missing, float(batch_w.get("metrics_missing", 1.0))))

        warnings = soe.get("warnings") if isinstance(soe.get("warnings"), list) else []
        factors.append(_ranking_factor("warnings_count", "con", float(len(warnings)), float(batch_w.get("warnings_count", 1.0))))

        score = _score_from_factors(factors)
        candidates.append(
            {
                "candidate_type": "batch",
                "candidate_id": int(di_in.scope_id),
                "score": score,
                "tie_breaker": {"created_at": None, "id": int(di_in.scope_id)},
                "factors": factors,
            }
        )
    else:
        batch_ids = selection_provenance.get("batch_ids_ordered") or selection_provenance.get("batch_ids_all") or []
        batch_ids = [int(x) for x in batch_ids if str(x).isdigit()]
        created_map = selection_provenance.get("batch_created_at") if isinstance(selection_provenance.get("batch_created_at"), dict) else {}
        metric_src = selection_provenance.get("metric_source_batch_ids") if isinstance(selection_provenance.get("metric_source_batch_ids"), dict) else {}
        batch_summaries = selection_provenance.get("batch_summaries") if isinstance(selection_provenance.get("batch_summaries"), list) else []
        summary_map: Dict[int, Dict[str, Any]] = {int(s.get("batch_id")): s for s in batch_summaries if isinstance(s, dict) and str(s.get("batch_id") or "").isdigit()}

        metrics_by_batch: Dict[int, int] = {}
        for _, bid in metric_src.items():
            try:
                bid_i = int(bid)
            except Exception:
                continue
            metrics_by_batch[bid_i] = metrics_by_batch.get(bid_i, 0) + 1

        for bid in batch_ids:
            factors = []
            mcount = float(metrics_by_batch.get(int(bid), 0))
            factors.append(_ranking_factor("metrics_sourced_count", "pro", mcount, float(mol_w.get("metrics_sourced_count", 2.0))))
            summ = summary_map.get(int(bid)) or {}
            used_cnt = float(summ.get("used_metric_count") or 0)
            ignored_cnt = float(summ.get("ignored_count") or 0)
            warn_cnt = float(summ.get("warning_count") or 0)
            factors.append(_ranking_factor("used_metric_count", "pro", used_cnt, float(mol_w.get("used_metric_count", 1.0))))
            factors.append(_ranking_factor("ignored_count", "con", ignored_cnt, float(mol_w.get("ignored_count", 0.5))))
            factors.append(_ranking_factor("warning_count", "con", warn_cnt, float(mol_w.get("warning_count", 1.0))))
            score = _score_from_factors(factors)
            candidates.append(
                {
                    "candidate_type": "batch",
                    "candidate_id": int(bid),
                    "score": score,
                    "tie_breaker": {"created_at": created_map.get(str(bid)), "id": int(bid)},
                    "factors": factors,
                }
            )

    candidates = sorted(candidates, key=_ranking_sort_key)
    winner_id = candidates[0]["candidate_id"] if candidates else None
    return {
        "scope_type": scope_type,
        "candidates": candidates,
        "winner_candidate_id": winner_id,
        "ranking_rule_version": RANKING_RULE_VERSION,
    }
