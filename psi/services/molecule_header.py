from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from psi.core.di.catalog import load_confidence_policy_latest, load_progress_policy_latest, load_template_prerequisites_latest
from psi.core.measurement_schema import measurement_cols
from psi.services.di.templates.registry import DECISION_KEY_TO_TEMPLATE_KEY
from psi.services.di.util import heavy_compute_banner_text, is_heavy_compute_enabled

_EARLY_MILESTONE_DISPLAY_ORDER: list[str] = [
    "expression_present",
    "basic_qc_present",
    "purification_present",
    "functional_assay_present",
    "mechanism_present",
    "endotoxin_present",
    "pk_screen_present",
]


def _ordered_milestone_keys(raw_keys: list[str], preferred_order: list[str]) -> list[str]:
    preferred_rank = {k: i for i, k in enumerate(preferred_order)}
    normalized = sorted({str(k).strip() for k in raw_keys if str(k).strip()})
    return sorted(
        normalized,
        key=lambda k: (
            0 if k in preferred_rank else 1,
            preferred_rank.get(k, 10_000),
            k,
        ),
    )


def _query_molecule_metric_keys_present(db: Session, *, molecule_id: int) -> list[str]:
    cols = measurement_cols(db)
    record_fk = cols["record_fk"]
    name_col = cols["name"]
    q = text(
        f"""
        SELECT DISTINCT dm.{name_col} AS metric_key
        FROM data_measurements dm
        JOIN data_records dr ON dr.id = dm.{record_fk}
        WHERE dr.molecule_id = :mid
        ORDER BY dm.{name_col} ASC
        """
    )
    rows = db.execute(q, {"mid": int(molecule_id)}).mappings().all()
    out: list[str] = []
    for r in rows:
        mk = str(r.get("metric_key") or "").strip()
        if mk:
            out.append(mk)
    return sorted(set(out))


def _di_template_key_from_history_row(row: dict[str, Any]) -> str:
    inputs_obj = row.get("_in") if isinstance(row.get("_in"), dict) else {}
    tk = str(inputs_obj.get("template_key") or "").strip()
    if tk:
        return tk
    dk = str(row.get("decision_key") or "").strip()
    return str(DECISION_KEY_TO_TEMPLATE_KEY.get(dk) or "")


def _build_drift_summary_plain(row: dict[str, Any]) -> str:
    out = row.get("_out") if isinstance(row.get("_out"), dict) else {}
    inputs_obj = row.get("_in") if isinstance(row.get("_in"), dict) else {}
    drift_ctx = inputs_obj.get("drift_context") if isinstance(inputs_obj.get("drift_context"), dict) else {}
    drift_type = str(out.get("drift_type") or "")
    st = out.get("state_transition") if isinstance(out.get("state_transition"), dict) else {}
    if not drift_ctx:
        return "No prior DI baseline for drift comparison."
    if drift_type == "NO_CHANGE":
        return "No DI drift detected versus the previous comparable snapshot."
    if drift_type == "EVIDENCE_ONLY":
        return "Evidence changed while policy semantics stayed the same."
    if drift_type == "POLICY_ONLY":
        return "Policy semantics changed while evidence fingerprint stayed the same."
    if drift_type == "BOTH":
        return "Both evidence and policy semantics changed."
    if drift_type == "INCOMPARABLE":
        return "Drift detected (details in governance view): snapshots are not comparable under current comparability rules."
    if st:
        return "Drift detected (details in governance view): " + ", ".join(sorted([str(k) for k in st.keys()]))
    return "Drift detected (details in governance view)."


def _shortlisting_tie_break_dimensions(out_obj: dict[str, Any]) -> list[dict[str, Any]]:
    shortlisting = out_obj.get("shortlisting") if isinstance(out_obj.get("shortlisting"), dict) else {}
    tie_break = shortlisting.get("tie_break") if isinstance(shortlisting.get("tie_break"), dict) else {}
    dims = tie_break.get("dimensions")
    if isinstance(dims, list):
        return [d for d in dims if isinstance(d, dict)]
    ranked = shortlisting.get("ranked_candidates")
    if isinstance(ranked, list) and ranked and isinstance(ranked[0], dict):
        dims = ranked[0].get("tie_break_dimensions")
        if isinstance(dims, list):
            return [d for d in dims if isinstance(d, dict)]
    return []


def _confidence_policy_ui_config() -> dict[str, Any]:
    default_order = ["qc_quality", "reproducibility", "comparability", "interpretability"]
    default_rules: dict[str, dict[str, Any]] = {
        "qc_quality": {
            "label": "QC Quality",
            "preferred_signal_dimension": "qc_confidence",
            "fallback_gate_keys": ["G2_purity_integrity", "G3_endotoxin"],
            "high_severity_if_failed_gate_keys": ["G3_endotoxin"],
        },
        "reproducibility": {
            "label": "Reproducibility",
            "preferred_signal_dimension": "reproducibility",
            "required_metrics_key": "required_metrics",
            "positive_field": "reproducibility_positive",
        },
        "comparability": {
            "label": "Comparability",
            "source_field": "drift_type",
            "concern_drift_types": ["INCOMPARABLE"],
            "concern_severity": "high",
        },
        "interpretability": {
            "label": "Interpretability",
            "source_field": "risk_flags_enriched",
            "severity_order": ["high", "medium", "low", "unspecified"],
            "unspecified_is_neutral": True,
        },
    }
    try:
        conf_pol = load_confidence_policy_latest()
        body = conf_pol.policy if isinstance(conf_pol.policy, dict) else {}
        raw_order = body.get("component_order") if isinstance(body.get("component_order"), list) else []
        order = [str(x).strip() for x in raw_order if str(x).strip() in default_rules]
        if not order:
            order = list(default_order)
        raw_rules = body.get("component_rules") if isinstance(body.get("component_rules"), dict) else {}
        merged_rules = {k: dict(v) for k, v in default_rules.items()}
        for k in order:
            rv = raw_rules.get(k)
            if isinstance(rv, dict):
                nxt = dict(merged_rules.get(k) or {})
                nxt.update(rv)
                merged_rules[k] = nxt
        return {"component_order": order, "component_rules": merged_rules}
    except Exception:
        return {"component_order": list(default_order), "component_rules": default_rules}


def _build_confidence_model(*, latest_di_row: dict[str, Any] | None, risk_severity_counts: dict[str, int]) -> dict[str, Any]:
    conf_cfg = _confidence_policy_ui_config()
    comp_order = conf_cfg.get("component_order") if isinstance(conf_cfg.get("component_order"), list) else []
    comp_rules = conf_cfg.get("component_rules") if isinstance(conf_cfg.get("component_rules"), dict) else {}
    label_by_key = {
        str(k): str((v or {}).get("label") or str(k))
        for k, v in comp_rules.items()
        if isinstance(v, dict)
    }

    if not latest_di_row or not isinstance((latest_di_row.get("_out") or {}), dict):
        ordered_components = []
        for ck in (comp_order or ["qc_quality", "reproducibility", "comparability", "interpretability"]):
            ordered_components.append(
                {
                    "name": label_by_key.get(ck, ck.replace("_", " ").title()),
                    "key": ck,
                    "state": "not_assessed",
                    "details": "No DI snapshot available yet.",
                }
            )
        return {
            "components": ordered_components,
            "scalar_state": "unknown",
            "scalar_label": "Unknown",
            "rule_text": "Confidence summary is derived from component counts only (no weights). Missing components are Not Assessed.",
        }

    out_obj = latest_di_row.get("_out") or {}
    dims = _shortlisting_tie_break_dimensions(out_obj)
    dim_by_key = {str(d.get("key") or ""): d for d in dims if str(d.get("key") or "")}

    components: list[dict[str, Any]] = []

    qc_rules = comp_rules.get("qc_quality") if isinstance(comp_rules.get("qc_quality"), dict) else {}
    qc_label = label_by_key.get("qc_quality", "QC Quality")
    qc_dim_key = str(qc_rules.get("preferred_signal_dimension") or "qc_confidence")
    qc_gate_keys = [
        str(x)
        for x in (
            qc_rules.get("fallback_gate_keys")
            if isinstance(qc_rules.get("fallback_gate_keys"), list)
            else ["G2_purity_integrity", "G3_endotoxin"]
        )
        if str(x)
    ]
    qc_high_gate_keys = {
        str(x)
        for x in (
            qc_rules.get("high_severity_if_failed_gate_keys")
            if isinstance(qc_rules.get("high_severity_if_failed_gate_keys"), list)
            else ["G3_endotoxin"]
        )
        if str(x)
    }
    # QC Quality: prefer tie-break qc_confidence signal (v0.4+), fallback to gate statuses.
    qc_dim = dim_by_key.get(qc_dim_key)
    if isinstance(qc_dim, dict) and str(qc_dim.get("status") or "") == "implemented" and isinstance(qc_dim.get("value"), dict):
        qcv = qc_dim.get("value") or {}
        concerns = qcv.get("concerns") if isinstance(qcv.get("concerns"), list) else []
        high_ct = sum(
            1
            for c in concerns
            if isinstance(c, dict) and str(c.get("severity") or "").strip().lower() == "high"
        )
        state = "concern" if concerns else "good"
        severity = "high" if high_ct > 0 else ("medium" if concerns else None)
        components.append(
            {
                "name": qc_label,
                "key": "qc_quality",
                "state": state,
                "severity": severity,
                "details": f"qc_confidence concerns={len(concerns)}",
            }
        )
    else:
        gates = out_obj.get("gates") if isinstance(out_obj.get("gates"), list) else []
        gate_status = {
            str(g.get("gate_key") or ""): str(g.get("status") or "").strip().lower()
            for g in gates
            if isinstance(g, dict)
        }
        observed = [k for k in qc_gate_keys if k in gate_status]
        if not observed:
            components.append({"name": qc_label, "key": "qc_quality", "state": "not_assessed", "details": "No QC confidence signal in latest snapshot."})
        else:
            failed = [k for k in observed if gate_status.get(k) != "pass"]
            components.append(
                {
                    "name": qc_label,
                    "key": "qc_quality",
                    "state": ("concern" if failed else "good"),
                    "severity": ("high" if any(k in qc_high_gate_keys for k in failed) else ("medium" if failed else None)),
                    "details": ("Failed gates: " + ", ".join(sorted(failed))) if failed else "Purity/endotoxin gates passed.",
                }
            )

    # Reproducibility: use v0.4 tie-break dimension when present.
    rep_rules = comp_rules.get("reproducibility") if isinstance(comp_rules.get("reproducibility"), dict) else {}
    rep_label = label_by_key.get("reproducibility", "Reproducibility")
    rep_dim_key = str(rep_rules.get("preferred_signal_dimension") or "reproducibility")
    rep_metrics_key = str(rep_rules.get("required_metrics_key") or "required_metrics")
    rep_positive_field = str(rep_rules.get("positive_field") or "reproducibility_positive")
    rep_dim = dim_by_key.get(rep_dim_key)
    if isinstance(rep_dim, dict) and str(rep_dim.get("status") or "") == "implemented" and isinstance(rep_dim.get("value"), dict):
        repv = rep_dim.get("value") or {}
        req = repv.get(rep_metrics_key) if isinstance(repv.get(rep_metrics_key), list) else []
        rows = [r for r in req if isinstance(r, dict)]
        if not rows:
            components.append({"name": rep_label, "key": "reproducibility", "state": "not_assessed", "details": "No required metrics in reproducibility signal."})
        else:
            positives = sum(1 for r in rows if bool(r.get(rep_positive_field)))
            total = len(rows)
            components.append(
                {
                    "name": rep_label,
                    "key": "reproducibility",
                    "state": ("good" if positives == total else "concern"),
                    "severity": (None if positives == total else "medium"),
                    "details": f"{positives}/{total} required metrics have reproducibility-positive SoE counts.",
                }
            )
    else:
        components.append({"name": rep_label, "key": "reproducibility", "state": "not_assessed", "details": "No reproducibility tie-break signal on latest snapshot."})

    # Comparability: interpret drift comparability state deterministically from drift_type.
    compa_rules = comp_rules.get("comparability") if isinstance(comp_rules.get("comparability"), dict) else {}
    compa_label = label_by_key.get("comparability", "Comparability")
    compa_source_field = str(compa_rules.get("source_field") or "drift_type")
    compa_concern_drift_types = {
        str(x).strip().upper()
        for x in (
            compa_rules.get("concern_drift_types")
            if isinstance(compa_rules.get("concern_drift_types"), list)
            else ["INCOMPARABLE"]
        )
        if str(x).strip()
    }
    compa_concern_sev = str(compa_rules.get("concern_severity") or "high").strip().lower() or "high"
    drift_type = str(out_obj.get(compa_source_field) or "").strip().upper()
    if not drift_type:
        components.append({"name": compa_label, "key": "comparability", "state": "not_assessed", "details": "No drift comparability signal on latest snapshot."})
    elif drift_type in compa_concern_drift_types:
        components.append({"name": compa_label, "key": "comparability", "state": "concern", "severity": compa_concern_sev, "details": "Latest snapshot is incomparable to prior baseline."})
    else:
        components.append({"name": compa_label, "key": "comparability", "state": "good", "details": f"Drift comparability available (drift_type={drift_type})."})

    # Interpretability: severity-aware, derived from risk flags only (UI/read-only).
    interp_rules = comp_rules.get("interpretability") if isinstance(comp_rules.get("interpretability"), dict) else {}
    interp_label = label_by_key.get("interpretability", "Interpretability")
    interp_severity_order = [
        str(x).strip().lower()
        for x in (
            interp_rules.get("severity_order")
            if isinstance(interp_rules.get("severity_order"), list)
            else ["high", "medium", "low", "unspecified"]
        )
        if str(x).strip()
    ]
    high_n = int(risk_severity_counts.get("high") or 0)
    med_n = int(risk_severity_counts.get("medium") or 0)
    low_n = int(risk_severity_counts.get("low") or 0)
    uns_n = int(risk_severity_counts.get("unspecified") or 0)
    total_risk = high_n + med_n + low_n + uns_n
    if total_risk <= 0:
        components.append({"name": interp_label, "key": "interpretability", "state": "good", "details": "No risk flags on latest snapshot."})
    else:
        sev_counts = {"high": high_n, "medium": med_n, "low": low_n, "unspecified": uns_n}
        sev = next((s for s in interp_severity_order if int(sev_counts.get(s) or 0) > 0), "unspecified")
        components.append(
            {
                "name": interp_label,
                "key": "interpretability",
                "state": "concern",
                "severity": sev,
                "details": f"Risk flags: high={high_n}, medium={med_n}, low={low_n}, unspecified={uns_n}.",
                "detail_items": _sorted_interpretability_detail_items(risk_severity_counts=risk_severity_counts),
            }
        )

    if comp_order:
        comp_index = {str(k): i for i, k in enumerate(comp_order)}
        components = sorted(
            components,
            key=lambda c: (int(comp_index.get(str(c.get("key") or ""), 999)), str(c.get("key") or "")),
        )

    scalar_state, scalar_label, scalar_counts = _derive_confidence_scalar_from_components(components=components)

    return {
        "components": components,
        "scalar_state": scalar_state,
        "scalar_label": scalar_label,
        "scalar_optional": True,
        "scalar_rule_id": "molecule_header_confidence_scalar.v0_1",
        "scalar_counts": scalar_counts,
        "rule_text": (
            "Summary uses counts only (no weights): any high-severity concern => amber; "
            "two or more medium concerns => amber; "
            "otherwise green. Missing components are Not Assessed."
        ),
    }


def _derive_confidence_components(*, latest_di_row: dict[str, Any] | None, risk_severity_counts: dict[str, int]) -> list[dict[str, Any]]:
    """Component-only confidence derivation surface (deterministic, UI-only)."""
    cm = _build_confidence_model(
        latest_di_row=latest_di_row,
        risk_severity_counts=risk_severity_counts,
    )
    comps = cm.get("components") if isinstance(cm, dict) else []
    return [c for c in comps if isinstance(c, dict)]


def _derive_confidence_scalar_from_components(*, components: list[dict[str, Any]]) -> tuple[str, str, dict[str, Any]]:
    concern_components = [c for c in components if str(c.get("state") or "") == "concern"]
    concern_sev = [str(c.get("severity") or "") for c in concern_components]
    medium_concerns = sum(1 for s in concern_sev if s == "medium")
    high_concerns = sum(1 for s in concern_sev if s == "high")
    assessed_count = sum(1 for c in components if str(c.get("state") or "") != "not_assessed")

    high_escalate = "amber"
    medium_amber_min = 2
    unknown_when_zero = True
    try:
        conf_pol = load_confidence_policy_latest()
        conf_body = conf_pol.policy if isinstance(conf_pol.policy, dict) else {}
        sr = conf_body.get("scalar_rules") if isinstance(conf_body.get("scalar_rules"), dict) else {}
        high_escalate = str(sr.get("high_concern_escalates_to") or high_escalate).strip().lower() or high_escalate
        medium_amber_min = int(sr.get("medium_concerns_amber_min") or medium_amber_min)
        unknown_when_zero = bool(sr.get("unknown_when_assessed_count_is_zero")) if "unknown_when_assessed_count_is_zero" in sr else unknown_when_zero
    except Exception:
        pass

    if assessed_count == 0 and unknown_when_zero:
        scalar_state, scalar_label = "unknown", "Unknown"
    elif high_concerns >= 1:
        scalar_state = high_escalate if high_escalate in {"amber", "green", "unknown"} else "amber"
        scalar_label = "Caution (High Concern)" if scalar_state == "amber" else ("Unknown" if scalar_state == "unknown" else "No Concerns")
    elif medium_concerns >= int(medium_amber_min):
        scalar_state, scalar_label = "amber", "Caution (Multiple Medium)"
    else:
        scalar_state, scalar_label = "green", "No Concerns"
    return scalar_state, scalar_label, {
        "assessed_count": assessed_count,
        "concern_count": len(concern_components),
        "high_concerns": high_concerns,
        "medium_concerns": medium_concerns,
    }


def _sorted_interpretability_detail_items(*, risk_severity_counts: dict[str, int]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for sev in ("high", "medium", "low", "unspecified"):
        ct = int((risk_severity_counts or {}).get(sev) or 0)
        if ct <= 0:
            continue
        items.append({"severity": sev, "count": ct, "severity_neutral": bool(sev == "unspecified")})
    return items


def _sorted_prerequisite_blockers_for_advisory(blockers: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    rows = [b for b in (blockers or []) if isinstance(b, dict)]
    # Explicit sort keeps UI advisory blocker ordering stable even if upstream collection order changes.
    return sorted(
        rows,
        key=lambda b: (
            str(b.get("template_key") or ""),
            str(b.get("status") or ""),
            int(b.get("latest_snapshot_id") or 0),
        ),
    )


def _build_progress_stage_advisory(*, prereq_advisories: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    if not isinstance(prereq_advisories, list) or not prereq_advisories:
        return None
    rows = [a for a in prereq_advisories if isinstance(a, dict)]
    if not rows:
        return None
    items = [
        {
            "milestone_key": str(a.get("milestone_key") or ""),
            "template_key": str(a.get("template_key") or ""),
            "blocked_by_text": str(a.get("blocked_by_text") or ""),
        }
        for a in rows
    ]
    items = sorted(
        items,
        key=lambda x: (
            str(x.get("milestone_key") or ""),
            str(x.get("template_key") or ""),
            str(x.get("blocked_by_text") or ""),
        ),
    )
    headline = items[0]
    text_parts = [str(x.get("blocked_by_text") or "") for x in items if str(x.get("blocked_by_text") or "")]
    return {
        "milestone_key": str(headline.get("milestone_key") or ""),
        "blocked_by_text": " | ".join(text_parts),
        "blocked_by_items": items,
    }


def _risk_item_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    sev_rank = {"high": 0, "medium": 1, "moderate": 1, "low": 2, "unspecified": 3}
    sev = str(item.get("severity") or "").strip().lower()
    key = str(item.get("key") or "").strip()
    return (sev_rank.get(sev, 3), key)


def _build_header_risk_items(*, latest_di_row: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not latest_di_row or not isinstance((latest_di_row.get("_out") or {}), dict):
        return []
    out_obj = latest_di_row.get("_out") or {}
    raw = out_obj.get("risk_flags_enriched")
    if not isinstance(raw, list):
        raw = out_obj.get("risk_flags")
    if not isinstance(raw, list):
        return []
    items: list[dict[str, Any]] = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        key = str(r.get("key") or r.get("risk_flag") or "").strip()
        if not key:
            continue
        sev_raw = str(r.get("severity") or "").strip().lower()
        if sev_raw == "moderate":
            sev_norm = "medium"
        elif sev_raw in ("high", "medium", "low"):
            sev_norm = sev_raw
        else:
            sev_norm = "unspecified"
        items.append(
            {
                "key": key,
                "severity": sev_norm,
                "severity_neutral": bool(sev_norm == "unspecified"),
            }
        )
    # Explicit deterministic ordering for the persistent scientist header.
    return sorted(items, key=_risk_item_sort_key)


def _build_progress_hover_text(*, milestones: list[dict[str, Any]]) -> str:
    ms = [m for m in (milestones or []) if isinstance(m, dict)]
    sat = [str(m.get("key") or "") for m in ms if bool(m.get("satisfied")) and str(m.get("key") or "").strip()]
    not_yet = [str(m.get("key") or "") for m in ms if not bool(m.get("satisfied")) and str(m.get("key") or "").strip()]
    parts: list[str] = []
    parts.append("satisfied=" + (",".join(sat) if sat else "none"))
    parts.append("not_yet=" + (",".join(not_yet) if not_yet else "none"))
    return "; ".join(parts)


def _build_molecule_header_model(
    db: Session,
    *,
    molecule_id: int,
    di_rows_chrono: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        prog = load_progress_policy_latest()
        prog_body = prog.policy if isinstance(prog.policy, dict) else {}
    except Exception:
        prog_body = {}
    try:
        prereq_pol = load_template_prerequisites_latest()
        prereq_body = prereq_pol.policy if isinstance(prereq_pol.policy, dict) else {}
    except Exception:
        prereq_body = {}

    early = prog_body.get("early_milestones") if isinstance(prog_body.get("early_milestones"), dict) else {}
    di_m = prog_body.get("di_milestones") if isinstance(prog_body.get("di_milestones"), dict) else {}
    measurement_keys_present = set(_query_molecule_metric_keys_present(db, molecule_id=int(molecule_id)))

    latest_pass_by_template: dict[str, bool] = {}
    latest_snapshot_by_template: dict[str, dict[str, Any]] = {}
    for row in sorted(di_rows_chrono, key=lambda r: (r.get("created_at") or "", int(r.get("snapshot_id") or 0)), reverse=True):
        tk = _di_template_key_from_history_row(row)
        if not tk or tk in latest_pass_by_template:
            continue
        out = row.get("_out") if isinstance(row.get("_out"), dict) else {}
        latest_pass_by_template[tk] = str(out.get("decision_state") or "") == "ready"
        latest_snapshot_by_template[tk] = row

    template_prereqs = (
        prereq_body.get("template_prerequisites")
        if isinstance(prereq_body.get("template_prerequisites"), dict)
        else {}
    )

    milestones: list[dict[str, Any]] = []
    for key in _ordered_milestone_keys([str(k) for k in early.keys()], _EARLY_MILESTONE_DISPLAY_ORDER):
        metrics = [str(x) for x in (early.get(key) or []) if str(x).strip()]
        present = sorted([m for m in metrics if m in measurement_keys_present])
        missing = sorted([m for m in metrics if m not in measurement_keys_present])
        milestones.append(
            {
                "key": key,
                "kind": "early",
                "label": key.replace("_", " "),
                "satisfied": bool(metrics) and len(missing) == 0,
                "detail": {"required_metrics": metrics, "present_metrics": present, "missing_metrics": missing},
            }
        )
    for key in _ordered_milestone_keys([str(k) for k in di_m.keys()], []):
        template_key = str(di_m.get(key) or "").strip()
        is_ready_raw = bool(latest_pass_by_template.get(template_key))
        # Sort prerequisite template keys explicitly to keep UI advisories stable.
        prereqs = sorted([str(x) for x in (template_prereqs.get(template_key) or []) if str(x).strip()])
        blocked_prerequisites = []
        for tk in prereqs:
            latest_row = latest_snapshot_by_template.get(tk) or {}
            is_ready_prereq = bool(latest_pass_by_template.get(tk))
            if is_ready_prereq:
                continue
            blocked_prerequisites.append(
                {
                    "template_key": tk,
                    "status": ("failed" if latest_row else "missing"),
                    "latest_snapshot_id": latest_row.get("snapshot_id"),
                }
            )
        missing_prereqs = [str(x.get("template_key") or "") for x in blocked_prerequisites if str(x.get("template_key") or "")]
        is_advisory_blocked = bool(is_ready_raw and missing_prereqs)
        is_ready = bool(is_ready_raw and not is_advisory_blocked)
        row = latest_snapshot_by_template.get(template_key) or {}
        prereq_statuses = [
            {
                "template_key": tk,
                "latest_snapshot_id": (latest_snapshot_by_template.get(tk) or {}).get("snapshot_id"),
                "ready": bool(latest_pass_by_template.get(tk)),
            }
            for tk in prereqs
        ]
        # Explicitly sort the rendered prerequisite status list for deterministic UI ordering.
        prereq_statuses = sorted(
            prereq_statuses,
            key=lambda x: (
                str(x.get("template_key") or ""),
                0 if bool(x.get("ready")) else 1,
                int(x.get("latest_snapshot_id") or 0),
            ),
        )
        milestones.append(
            {
                "key": key,
                "kind": "di",
                "label": key.replace("_", " "),
                "satisfied": bool(is_ready),
                "detail": {
                    "template_key": template_key,
                    "latest_snapshot_id": row.get("snapshot_id"),
                    "latest_decision_state": ((row.get("_out") or {}).get("decision_state") if isinstance(row.get("_out"), dict) else None),
                    "prerequisites": prereq_statuses,
                    "advisory_blocked": bool(is_advisory_blocked),
                    "advisory_missing_templates": missing_prereqs,
                    "advisory_blocked_prerequisites": _sorted_prerequisite_blockers_for_advisory(blocked_prerequisites),
                },
            }
        )

    last_sat = next((m for m in reversed(milestones) if bool(m.get("satisfied"))), None)
    progress_stage = str(last_sat.get("label")) if isinstance(last_sat, dict) else "not started"
    progress_explain_parts = []
    for m in milestones:
        marker = "yes" if m.get("satisfied") else "no"
        progress_explain_parts.append(f"{m.get('key')}: {marker}")
    progress_hover_text = _build_progress_hover_text(milestones=milestones)

    latest_di_row = next(
        (
            r
            for r in sorted(di_rows_chrono, key=lambda x: (x.get("created_at") or "", int(x.get("snapshot_id") or 0)), reverse=True)
            if isinstance(r.get("_out"), dict)
        ),
        None,
    )
    drift_summary_plain = _build_drift_summary_plain(latest_di_row or {}) if latest_di_row else "No DI snapshots yet."

    risk_severity_counts = {"high": 0, "medium": 0, "low": 0, "unspecified": 0}
    if latest_di_row and isinstance((latest_di_row.get("_out") or {}), dict):
        out_obj = latest_di_row.get("_out") or {}
        rf_list = out_obj.get("risk_flags_enriched")
        if not isinstance(rf_list, list):
            rf_list = out_obj.get("risk_flags")
        if isinstance(rf_list, list):
            for r in rf_list:
                if not isinstance(r, dict):
                    risk_severity_counts["unspecified"] += 1
                    continue
                sev = str(r.get("severity") or "").strip().lower()
                if sev == "moderate":
                    sev = "medium"
                if sev in ("high", "medium", "low"):
                    risk_severity_counts[sev] += 1
                else:
                    risk_severity_counts["unspecified"] += 1

    prereq_advisories = [
        {
            "milestone_key": m.get("key"),
            "template_key": ((m.get("detail") or {}).get("template_key") if isinstance(m.get("detail"), dict) else None),
            "missing_templates": (((m.get("detail") or {}).get("advisory_missing_templates")) if isinstance(m.get("detail"), dict) else []),
            "blocked_prerequisites": (((m.get("detail") or {}).get("advisory_blocked_prerequisites")) if isinstance(m.get("detail"), dict) else []),
        }
        for m in milestones
        if m.get("kind") == "di"
        and isinstance(m.get("detail"), dict)
        and bool((m.get("detail") or {}).get("advisory_blocked"))
    ]
    # Keep advisory rows deterministic for stable UI snapshots/tests.
    prereq_advisories = sorted(
        prereq_advisories,
        key=lambda a: (
            str(a.get("milestone_key") or ""),
            str(a.get("template_key") or ""),
        ),
    )
    for adv in prereq_advisories:
        blocked = _sorted_prerequisite_blockers_for_advisory(
            adv.get("blocked_prerequisites") if isinstance(adv.get("blocked_prerequisites"), list) else []
        )
        adv["blocked_prerequisites"] = blocked
        parts = []
        for b in blocked:
            if not isinstance(b, dict):
                continue
            tk = str(b.get("template_key") or "").strip()
            if not tk:
                continue
            status = str(b.get("status") or "missing").strip() or "missing"
            sid = b.get("latest_snapshot_id")
            if sid:
                parts.append(f"{tk} ({status}, latest snapshot #{sid})")
            else:
                parts.append(f"{tk} ({status})")
        adv["blocked_by_text"] = "Blocked by prerequisites: " + (", ".join(parts) if parts else "unknown prerequisite state")

    progress_stage_advisory = _build_progress_stage_advisory(prereq_advisories=prereq_advisories)

    heavy_compute_enabled = is_heavy_compute_enabled()
    confidence_model = _build_confidence_model(
        latest_di_row=latest_di_row,
        risk_severity_counts=risk_severity_counts,
    )
    risk_items = _build_header_risk_items(latest_di_row=latest_di_row)
    return {
        "view_mode_default": "scientist",
        "progress_stage": progress_stage,
        "progress_explain": "; ".join(progress_explain_parts),
        "progress_hover_text": progress_hover_text,
        "progress_milestones": milestones,
        "heavy_compute_enabled": bool(heavy_compute_enabled),
        "heavy_compute_banner": heavy_compute_banner_text(enabled=heavy_compute_enabled),
        "drift_summary_plain": drift_summary_plain,
        "prerequisite_advisories": prereq_advisories,
        "progress_stage_advisory": progress_stage_advisory,
        "risk_severity_counts": risk_severity_counts,
        "risk_items": risk_items,
        "confidence_model": confidence_model,
        "latest_di_snapshot_id": (latest_di_row or {}).get("snapshot_id"),
        "latest_di_drift_type": (((latest_di_row or {}).get("_out") or {}).get("drift_type") if latest_di_row else None),
    }
