from __future__ import annotations

import json
import re
from typing import Any

_HEX64_RE = re.compile(r"\b[a-f0-9]{64}\b", flags=re.IGNORECASE)
# Display-only cap for long narrative lists in board rendering.
DISPLAY_LIST_LIMIT = 5


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _as_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _as_str_list(v: Any) -> list[str]:
    out: list[str] = []
    for x in _as_list(v):
        s = str(x or "").strip()
        if s:
            out.append(s)
    return out


def _clean_text(s: Any) -> str:
    txt = str(s or "").strip()
    if not txt:
        return "Not available"
    txt = _HEX64_RE.sub("[hash-hidden]", txt)
    txt = " ".join(txt.split())
    txt = re.sub(r"\.{2,}", ".", txt)
    txt = re.sub(r"([!?]){2,}", r"\1", txt)
    txt = re.sub(r"\s+([,.;:!?])", r"\1", txt)
    return txt.strip() or "Not available"


def _normalize_bullet_text(s: str) -> str:
    txt = _clean_text(s)
    if txt and txt[-1] not in ".!?":
        return txt + "."
    return txt


def _display_limited(items: list[str], *, empty_fallback: str, ensure_sentence_punctuation: bool = False) -> list[str]:
    cleaned = [_clean_text(x) for x in items if str(x or "").strip()]
    if ensure_sentence_punctuation:
        cleaned = [_normalize_bullet_text(x) for x in cleaned]
    if not cleaned:
        base = _clean_text(empty_fallback)
        return [_normalize_bullet_text(base) if ensure_sentence_punctuation else base]
    if len(cleaned) <= DISPLAY_LIST_LIMIT:
        return cleaned
    remaining = len(cleaned) - DISPLAY_LIST_LIMIT
    overflow = _clean_text(f"...and {remaining} more.")
    if ensure_sentence_punctuation:
        overflow = _normalize_bullet_text(overflow)
    return cleaned[:DISPLAY_LIST_LIMIT] + [overflow]


def _collect_sections(report_payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = _as_dict(report_payload)
    sections = _as_dict(payload.get("sections"))
    metadata = _as_dict(payload.get("metadata"))
    return sections, metadata


def _comparability_det(sections: dict[str, Any]) -> dict[str, Any]:
    drift = _as_dict(sections.get("drift_history"))
    if isinstance(drift.get("comparability_determination"), dict):
        return _as_dict(drift.get("comparability_determination"))
    cross = _as_dict(sections.get("cross_molecule_comparability"))
    if isinstance(cross.get("comparability_determination"), dict):
        return _as_dict(cross.get("comparability_determination"))
    return {}


def _posture_det(sections: dict[str, Any]) -> dict[str, Any]:
    stage = _as_dict(sections.get("stage_determination"))
    if isinstance(stage.get("program_posture"), dict):
        return _as_dict(stage.get("program_posture"))
    risk = _as_dict(sections.get("risk_landscape"))
    if isinstance(risk.get("program_posture"), dict):
        return _as_dict(risk.get("program_posture"))
    return {}


def _snapshot_count(sections: dict[str, Any]) -> int:
    repro = _as_dict(sections.get("reproducibility_appendix"))
    cited = _as_list(repro.get("cited_snapshot_ids"))
    return len(cited)


def _measurement_keys(sections: dict[str, Any]) -> list[str]:
    repro = _as_dict(sections.get("reproducibility_appendix"))
    return _as_str_list(repro.get("measurement_keys"))


def _format_det(
    title: str,
    outcome: str,
    rule_id: str,
    notes: list[str],
    *,
    snapshot_ids: list[Any] | None = None,
    measurement_keys: list[str] | None = None,
    missing_inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snap_vals = sorted({str(x).strip() for x in (snapshot_ids or []) if str(x).strip()})
    mk_vals = sorted({str(x).strip() for x in (measurement_keys or []) if str(x).strip()})
    miss = missing_inputs if isinstance(missing_inputs, dict) else {}
    rationale = " · ".join([_clean_text(x) for x in notes]) if notes else "Not available"
    return {
        "title": _clean_text(title),
        "outcome": _clean_text(outcome or "Not assessed yet"),
        "rule_id": _clean_text(rule_id or "Not available"),
        "snapshot_ids": snap_vals,
        "measurement_keys": mk_vals,
        "missing_inputs": miss,
        "rationale": rationale,
        "details": [_clean_text(f"Policy rule: {rule_id or 'Not available'}")] + [_clean_text(x) for x in notes],
    }


def _base_narrative(headline: str) -> dict[str, Any]:
    return {
        "headline": _clean_text(headline),
        "status_rows": [],
        "what_this_means": [],
        "evidence_status": [],
        "determinations": [],
        "next_steps": [],
        "technical_notes": [],
    }


def _stringify_item(x: Any) -> str:
    if isinstance(x, str):
        return x
    if isinstance(x, (int, float, bool)):
        return str(x)
    if isinstance(x, dict):
        return json.dumps(x, sort_keys=True, ensure_ascii=False)
    if isinstance(x, list):
        return json.dumps(x, ensure_ascii=False)
    return str(x)


def _molecule_stage(sections: dict[str, Any]) -> str:
    stage = _as_dict(sections.get("stage_determination"))
    decision_state = str(stage.get("decision_state") or "").strip()
    if decision_state:
        return decision_state
    readiness_state = str(stage.get("readiness_state") or "").strip()
    if readiness_state:
        return readiness_state
    return "Not assessed yet"


def _molecule_next_steps(sections: dict[str, Any]) -> list[str]:
    gaps = _as_dict(sections.get("experimental_gaps"))
    blockers = _as_list(gaps.get("blockers"))
    if blockers:
        return [_clean_text(_stringify_item(x)) for x in blockers]
    next_best = _as_list(gaps.get("next_best_experiments"))
    if next_best:
        return [_clean_text(_stringify_item(x)) for x in next_best]
    return ["No experimental gaps listed yet."]


def _program_next_steps(sections: dict[str, Any]) -> list[str]:
    nbe = _as_dict(sections.get("next_best_experiments"))
    items = _as_list(nbe.get("items"))
    out: list[str] = []
    for item in items:
        if isinstance(item, dict):
            label = str(item.get("label") or "").strip()
            skey = str(item.get("suggestion_key") or "").strip()
            if label:
                out.append(_clean_text(label))
            elif skey:
                out.append(_clean_text(skey))
            else:
                out.append(_clean_text(_stringify_item(item)))
        else:
            out.append(_clean_text(_stringify_item(item)))
    if out:
        return out
    return ["No next steps recorded yet."]


def render_molecule_narrative(report_payload: dict) -> dict:
    sections, metadata = _collect_sections(_as_dict(report_payload))
    ident = _as_dict(sections.get("identity_context"))
    comp = _comparability_det(sections)
    snapshots = _snapshot_count(sections)
    measurement_keys = _measurement_keys(sections)
    headline = f"Molecule report for {ident.get('primary_id') or ident.get('molecule_id') or 'unidentified molecule'}"
    out = _base_narrative(headline)
    out["status_rows"] = [
        {"label": "Report type", "value": _clean_text(metadata.get("report_type") or "molecule_report")},
        {"label": "Molecule", "value": _clean_text(ident.get("title") or ident.get("primary_id") or "Not available")},
        {"label": "Stage", "value": _clean_text(_molecule_stage(sections))},
    ]
    out["what_this_means"] = [
        "This narrative restates existing report sections and does not add new conclusions.",
        (
            "Comparability is "
            + str(comp.get("category") or "not assessed yet").replace("_", " ")
            + "."
        ),
    ]
    out["evidence_status"] = [
        {
            "label": "Snapshots",
            "value": _clean_text("Evidence is not yet captured in PSI (0 snapshots)." if snapshots == 0 else f"{snapshots} snapshot(s) cited."),
        },
        {
            "label": "Measurements",
            "value": _clean_text("No cited measurements in this report." if not measurement_keys else ", ".join(measurement_keys)),
        },
    ]
    out["determinations"] = [
        _format_det(
            "Comparability",
            str(comp.get("category") or "not_assessed"),
            str(comp.get("rule_id") or "Not available"),
            [
                "Snapshots: " + (", ".join(_as_str_list(comp.get("snapshot_ids"))) or "none"),
                "Measurements: " + (", ".join(_as_str_list(comp.get("measurement_keys"))) or "none"),
            ],
            snapshot_ids=_as_str_list(comp.get("snapshot_ids")),
            measurement_keys=_as_str_list(comp.get("measurement_keys")),
            missing_inputs=(_as_dict(comp.get("missing_inputs")) if isinstance(comp.get("missing_inputs"), dict) else {}),
        )
    ]
    out["what_this_means"] = _display_limited(out["what_this_means"], empty_fallback="Not assessed yet.", ensure_sentence_punctuation=True)
    out["next_steps"] = _display_limited(_molecule_next_steps(sections), empty_fallback="No experimental gaps listed yet.")
    out["technical_notes"] = [_clean_text("Board view hides hashes and raw audit payloads.")]
    return out


def render_program_narrative(report_payload: dict) -> dict:
    sections, metadata = _collect_sections(_as_dict(report_payload))
    ident = _as_dict(sections.get("identity_context"))
    section_meta = _as_dict(sections.get("metadata"))
    posture = _posture_det(sections)
    snapshots = _snapshot_count(sections)
    program_name = str(ident.get("program_name") or section_meta.get("program_name") or "").strip()
    program_id = str(ident.get("program_id") or section_meta.get("program_id") or "").strip()
    headline_subject = program_name or (f"program_id={program_id}" if program_id else "unidentified program")
    headline = f"Program report for {headline_subject}"
    out = _base_narrative(headline)
    out["status_rows"] = [
        {"label": "Report type", "value": _clean_text(metadata.get("report_type") or "program_report")},
        {"label": "Program", "value": _clean_text(program_name or (f"program_id={program_id}" if program_id else "Not available"))},
        {"label": "Posture", "value": _clean_text(posture.get("posture_state") or "Not assessed yet")},
    ]
    out["what_this_means"] = [
        "Program posture is derived from existing template outcomes and governance flags.",
    ]
    out["evidence_status"] = [
        {
            "label": "Snapshots",
            "value": _clean_text("Evidence is not yet captured in PSI (0 snapshots)." if snapshots == 0 else f"{snapshots} snapshot(s) cited."),
        },
        {
            "label": "Templates",
            "value": _clean_text(
                ", ".join(_as_str_list(_as_dict(_as_dict(sections.get("reproducibility_appendix")).get("rollup")).get("template_keys")))
                or "No template outputs available yet."
            ),
        },
    ]
    out["determinations"] = [
        _format_det(
            "Program posture",
            str(posture.get("posture_state") or "not_assessed"),
            str(posture.get("rule_id") or "Not available"),
            [
                "Cited snapshots: " + (", ".join(_as_str_list(posture.get("cited_snapshot_ids"))) or "none"),
                "Cited decisions: " + (", ".join(_as_str_list(posture.get("cited_decisions"))) or "none"),
            ],
            snapshot_ids=_as_str_list(posture.get("cited_snapshot_ids")),
            measurement_keys=[],
            missing_inputs={},
        )
    ]
    out["what_this_means"] = _display_limited(out["what_this_means"], empty_fallback="Not assessed yet.", ensure_sentence_punctuation=True)
    out["next_steps"] = _display_limited(_program_next_steps(sections), empty_fallback="No next steps recorded yet.")
    out["technical_notes"] = [_clean_text("Use Technical View for policy pins and report fingerprint.")]
    return out


def _comparison_subjects(sections: dict[str, Any], *, subject_kind: str) -> list[str]:
    subjects: list[str] = []
    if subject_kind == "molecule":
        rows = _as_list(_as_dict(sections.get("molecule_set")).get("rows"))
        for row in rows:
            if not isinstance(row, dict):
                continue
            primary_id = str(row.get("primary_id") or "").strip()
            title = str(row.get("title") or "").strip()
            molecule_id = row.get("molecule_id")
            if primary_id and title:
                subjects.append(f"{primary_id} ({title})")
            elif primary_id:
                subjects.append(primary_id)
            elif title:
                subjects.append(title)
            elif molecule_id is not None:
                subjects.append(f"molecule_id={molecule_id}")
    elif subject_kind == "program":
        rows = _as_list(_as_dict(sections.get("program_set")).get("rows"))
        for row in rows:
            if not isinstance(row, dict):
                continue
            program_id = row.get("program_id")
            molecule_count = row.get("molecule_count")
            if program_id is None:
                continue
            if molecule_count is not None:
                subjects.append(f"program_id={program_id} (molecules={molecule_count})")
            else:
                subjects.append(f"program_id={program_id}")
    if subjects:
        return subjects
    ident = _as_dict(sections.get("identity_context"))
    return _as_str_list(ident.get("subjects"))


def _comparison_next_steps(sections: dict[str, Any]) -> list[str]:
    gaps_raw = sections.get("experimental_gaps")
    if isinstance(gaps_raw, list):
        gaps = _as_str_list(gaps_raw)
        if gaps:
            return gaps
    if isinstance(gaps_raw, dict):
        blockers = _as_str_list(gaps_raw.get("blockers"))
        if blockers:
            return blockers
        next_best = _as_str_list(gaps_raw.get("next_best_experiments"))
        if next_best:
            return next_best

    high_risk_count = 0
    molecule_rows = _as_list(_as_dict(sections.get("molecule_set")).get("rows"))
    for row in molecule_rows:
        if not isinstance(row, dict):
            continue
        for rf in _as_list(row.get("risk_flags_enriched")):
            if isinstance(rf, dict) and str(rf.get("severity") or "").strip().lower() == "high":
                high_risk_count += 1
    assessments = _as_list(_as_dict(sections.get("comparability_surface")).get("assessments"))
    for row in assessments:
        if isinstance(row, dict) and str(row.get("severity") or "").strip().lower() == "high":
            high_risk_count += 1
    if high_risk_count > 0:
        return [f"Address high-severity risk signals ({high_risk_count}) before comparative decisions."]

    mk_set: dict[str, bool] = {}
    for row in assessments:
        if not isinstance(row, dict):
            continue
        for mk in _as_str_list(row.get("cited_measurement_keys")):
            if mk not in mk_set:
                mk_set[mk] = True
    if not mk_set:
        repro = _as_dict(sections.get("reproducibility_appendix"))
        for mk in _as_str_list(repro.get("measurement_keys")):
            if mk not in mk_set:
                mk_set[mk] = True
    mks = sorted(mk_set.keys())
    if len(mks) > 1:
        return [f"Resolve measurement comparability across: {', '.join(mks)}."]
    return ["No next steps provided by comparative schema."]


def _comparison_narrative(report_payload: dict, *, subject_label: str, subject_kind: str) -> dict:
    sections, metadata = _collect_sections(_as_dict(report_payload))
    subjects = _comparison_subjects(sections, subject_kind=subject_kind)
    comp = _comparability_det(sections)
    out = _base_narrative(f"{subject_label} comparison report")
    out["status_rows"] = [
        {"label": "Report type", "value": _clean_text(metadata.get("report_type") or "comparison_report")},
        {"label": "Subjects", "value": _clean_text(", ".join(subjects) if subjects else "Not yet captured")},
    ]
    out["what_this_means"] = [
        "Rows compare existing metrics side-by-side in fixed ordering.",
    ]
    out["evidence_status"] = [
        {
            "label": "Snapshots",
            "value": _clean_text(
                "Evidence is not yet captured in PSI (0 snapshots)."
                if _snapshot_count(sections) == 0
                else f"{_snapshot_count(sections)} snapshot(s) cited."
            ),
        },
        {"label": "Measurements", "value": _clean_text(", ".join(_measurement_keys(sections)) or "No cited measurements in this report.")},
    ]
    out["determinations"] = [
        _format_det(
            "Comparability",
            str(comp.get("category") or "not_assessed"),
            str(comp.get("rule_id") or "Not available"),
            [
                "Snapshots: " + (", ".join(_as_str_list(comp.get("snapshot_ids"))) or "none"),
                "Measurements: " + (", ".join(_as_str_list(comp.get("measurement_keys"))) or "none"),
            ],
            snapshot_ids=_as_str_list(comp.get("snapshot_ids")),
            measurement_keys=_as_str_list(comp.get("measurement_keys")),
            missing_inputs=(_as_dict(comp.get("missing_inputs")) if isinstance(comp.get("missing_inputs"), dict) else {}),
        )
    ]
    out["what_this_means"] = _display_limited(out["what_this_means"], empty_fallback="Not assessed yet.", ensure_sentence_punctuation=True)
    out["next_steps"] = _display_limited(_comparison_next_steps(sections), empty_fallback="No next steps provided by comparative schema.", ensure_sentence_punctuation=True)
    out["technical_notes"] = [_clean_text("Technical View includes raw comparison tables and governance warnings.")]
    return out


def render_molecule_comparison_narrative(report_payload: dict) -> dict:
    return _comparison_narrative(report_payload, subject_label="Molecule", subject_kind="molecule")


def render_program_comparison_narrative(report_payload: dict) -> dict:
    return _comparison_narrative(report_payload, subject_label="Program", subject_kind="program")
