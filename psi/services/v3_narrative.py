from __future__ import annotations

import re
from typing import Any

_HEX64_RE = re.compile(r"\b[a-f0-9]{64}\b", flags=re.IGNORECASE)


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
    return _HEX64_RE.sub("[hash-hidden]", txt)


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


def _format_det(title: str, outcome: str, rule_id: str, notes: list[str]) -> dict[str, Any]:
    return {
        "title": _clean_text(title),
        "outcome": _clean_text(outcome or "Not assessed yet"),
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


def render_molecule_narrative(report_payload: dict) -> dict:
    sections, metadata = _collect_sections(_as_dict(report_payload))
    ident = _as_dict(sections.get("identity_context"))
    comp = _comparability_det(sections)
    snapshots = _snapshot_count(sections)
    measurement_keys = _measurement_keys(sections)
    gaps = _as_str_list(sections.get("experimental_gaps"))
    headline = f"Molecule report for {ident.get('primary_id') or ident.get('molecule_id') or 'unidentified molecule'}"
    out = _base_narrative(headline)
    out["status_rows"] = [
        {"label": "Report type", "value": _clean_text(metadata.get("report_type") or "molecule_report")},
        {"label": "Molecule", "value": _clean_text(ident.get("title") or ident.get("primary_id") or "Not available")},
        {"label": "Stage", "value": _clean_text(_as_dict(sections.get("stage_determination")).get("stage") or "Not assessed yet")},
    ]
    out["what_this_means"] = [
        _clean_text("This narrative restates existing report sections and does not add new conclusions."),
        _clean_text(
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
        )
    ]
    if gaps:
        out["next_steps"] = [_clean_text(x) for x in gaps]
    else:
        out["next_steps"] = [_clean_text("No experimental gaps listed yet.")]
    out["technical_notes"] = [_clean_text("Board view hides hashes and raw audit payloads.")]
    return out


def render_program_narrative(report_payload: dict) -> dict:
    sections, metadata = _collect_sections(_as_dict(report_payload))
    ident = _as_dict(sections.get("identity_context"))
    posture = _posture_det(sections)
    snapshots = _snapshot_count(sections)
    headline = f"Program report for {ident.get('program_name') or ident.get('program_id') or 'unidentified program'}"
    out = _base_narrative(headline)
    out["status_rows"] = [
        {"label": "Report type", "value": _clean_text(metadata.get("report_type") or "program_report")},
        {"label": "Program", "value": _clean_text(ident.get("program_name") or "Not available")},
        {"label": "Posture", "value": _clean_text(posture.get("posture_state") or "Not assessed yet")},
    ]
    out["what_this_means"] = [
        _clean_text("Program posture is derived from existing template outcomes and governance flags."),
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
        )
    ]
    gaps = _as_str_list(sections.get("experimental_gaps"))
    out["next_steps"] = [_clean_text(x) for x in gaps] if gaps else [_clean_text("No next steps recorded yet.")]
    out["technical_notes"] = [_clean_text("Use Technical View for policy pins and report fingerprint.")]
    return out


def _comparison_narrative(report_payload: dict, *, subject_label: str) -> dict:
    sections, metadata = _collect_sections(_as_dict(report_payload))
    ident = _as_dict(sections.get("identity_context"))
    subjects = _as_str_list(ident.get("subjects"))
    profile = _as_dict(sections.get("II_general_profile"))
    profile_cols = _as_list(profile.get("columns"))
    friendly_subjects: list[str] = []
    for col in profile_cols:
        if not isinstance(col, dict):
            continue
        primary_id = str(col.get("primary_id") or "").strip()
        title = str(col.get("title") or "").strip()
        program_name = str(col.get("program_name") or "").strip()
        if primary_id and title:
            friendly_subjects.append(f"{primary_id} ({title})")
        elif primary_id:
            friendly_subjects.append(primary_id)
        elif program_name and title:
            friendly_subjects.append(f"{program_name} ({title})")
        elif program_name:
            friendly_subjects.append(program_name)
        elif title:
            friendly_subjects.append(title)
    subjects = friendly_subjects if friendly_subjects else subjects
    comp = _comparability_det(sections)
    out = _base_narrative(f"{subject_label} comparison report")
    out["status_rows"] = [
        {"label": "Report type", "value": _clean_text(metadata.get("report_type") or "comparison_report")},
        {"label": "Subjects", "value": _clean_text(", ".join(subjects) if subjects else "Not yet captured")},
    ]
    out["what_this_means"] = [
        _clean_text("Rows compare existing metrics side-by-side in fixed ordering."),
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
        )
    ]
    gaps = _as_str_list(sections.get("experimental_gaps"))
    out["next_steps"] = [_clean_text(x) for x in gaps] if gaps else [_clean_text("None")]
    out["technical_notes"] = [_clean_text("Technical View includes raw comparison tables and governance warnings.")]
    return out


def render_molecule_comparison_narrative(report_payload: dict) -> dict:
    return _comparison_narrative(report_payload, subject_label="Molecule")


def render_program_comparison_narrative(report_payload: dict) -> dict:
    return _comparison_narrative(report_payload, subject_label="Program")
