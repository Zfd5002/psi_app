from __future__ import annotations

from typing import Any, Dict, List

from psi.core.di.schema import DIInput
from psi.services.di.util import parse_iso


RANKING_RULE_VERSION = "v0.5.2"


def _ranking_factor(key: str, direction: str, value: Any) -> Dict[str, Any]:
    return {"key": key, "direction": direction, "value": value}


def _candidate_sort_tuple(cand: Dict[str, Any]) -> tuple:
    # Deterministic lexicographic ranking only; no weighted aggregates.
    values = cand.get("sort_values") if isinstance(cand.get("sort_values"), dict) else {}
    return (
        -float(values.get("decision_ready") or 0.0),
        float(values.get("blockers_count") or 0.0),
        float(values.get("comparability_high_severity") or 0.0),
        -float(values.get("metrics_present") or 0.0),
        float(values.get("metrics_missing") or 0.0),
        float(values.get("warnings_count") or 0.0),
        -float(values.get("metrics_sourced_count") or 0.0),
        -float(values.get("used_metric_count") or 0.0),
        float(values.get("ignored_count") or 0.0),
        float(values.get("warning_count") or 0.0),
    )


def _ranking_sort_key(cand: Dict[str, Any]) -> tuple:
    rank_tuple = _candidate_sort_tuple(cand)
    tb = cand.get("tie_breaker") if isinstance(cand.get("tie_breaker"), dict) else {}
    created_raw = tb.get("created_at")
    dt = parse_iso(str(created_raw)) if created_raw else None
    created_ts = dt.timestamp() if dt is not None else -1.0
    cid = int(cand.get("candidate_id") or 0)
    return rank_tuple + (-created_ts, -cid)


def build_ranking_payload(
    *,
    di_in: DIInput,
    out: Dict[str, Any],
    selection_provenance: Dict[str, Any],
) -> Dict[str, Any]:
    scope_type = str(di_in.scope_type or "batch")
    candidates: List[Dict[str, Any]] = []

    if scope_type == "batch":
        factors: List[Dict[str, Any]] = []
        sort_values: Dict[str, float] = {}
        decision_state = str(out.get("decision_state") or "")
        if decision_state == "ready":
            factors.append(_ranking_factor("decision_state", "pro", 1.0))
            sort_values["decision_ready"] = 1.0
        else:
            factors.append(_ranking_factor("decision_state", "con", 1.0))
            sort_values["decision_ready"] = 0.0

        blockers = out.get("blockers") if isinstance(out.get("blockers"), list) else []
        blockers_count = float(len(blockers))
        factors.append(_ranking_factor("blockers_count", "con", blockers_count))
        sort_values["blockers_count"] = blockers_count

        comp = out.get("comparability") if isinstance(out.get("comparability"), dict) else {}
        summary = comp.get("summary") if isinstance(comp.get("summary"), dict) else {}
        high_sev = float(summary.get("high_severity_count") or 0)
        factors.append(_ranking_factor("comparability_high_severity", "con", high_sev))
        sort_values["comparability_high_severity"] = high_sev

        soe = out.get("state_of_evidence") if isinstance(out.get("state_of_evidence"), dict) else {}
        soe_v0_2 = soe.get("soe_v0_2") if isinstance(soe.get("soe_v0_2"), dict) else {}
        coverage = soe_v0_2.get("coverage") if isinstance(soe_v0_2.get("coverage"), dict) else {}
        missing = float(len(coverage.get("metrics_missing") or []))
        present = float(len(coverage.get("metrics_present") or []))
        factors.append(_ranking_factor("metrics_present", "pro", present))
        factors.append(_ranking_factor("metrics_missing", "con", missing))
        sort_values["metrics_present"] = present
        sort_values["metrics_missing"] = missing

        warnings = soe.get("warnings") if isinstance(soe.get("warnings"), list) else []
        warnings_count = float(len(warnings))
        factors.append(_ranking_factor("warnings_count", "con", warnings_count))
        sort_values["warnings_count"] = warnings_count

        candidates.append(
            {
                "candidate_type": "batch",
                "candidate_id": int(di_in.scope_id),
                "score": None,
                "tie_breaker": {"created_at": None, "id": int(di_in.scope_id)},
                "factors": factors,
                "sort_values": sort_values,
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
            sort_values: Dict[str, float] = {}
            mcount = float(metrics_by_batch.get(int(bid), 0))
            factors.append(_ranking_factor("metrics_sourced_count", "pro", mcount))
            sort_values["metrics_sourced_count"] = mcount
            summ = summary_map.get(int(bid)) or {}
            used_cnt = float(summ.get("used_metric_count") or 0)
            ignored_cnt = float(summ.get("ignored_count") or 0)
            warn_cnt = float(summ.get("warning_count") or 0)
            factors.append(_ranking_factor("used_metric_count", "pro", used_cnt))
            factors.append(_ranking_factor("ignored_count", "con", ignored_cnt))
            factors.append(_ranking_factor("warning_count", "con", warn_cnt))
            sort_values["used_metric_count"] = used_cnt
            sort_values["ignored_count"] = ignored_cnt
            sort_values["warning_count"] = warn_cnt
            candidates.append(
                {
                    "candidate_type": "batch",
                    "candidate_id": int(bid),
                    "score": None,
                    "tie_breaker": {"created_at": created_map.get(str(bid)), "id": int(bid)},
                    "factors": factors,
                    "sort_values": sort_values,
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
