from __future__ import annotations

"""Central registry driving dynamic forms and evidence->data restrictions.

This registry powers:
- DataRecord create/edit: domain -> data_type -> method -> structured fields
- Evidence citations: evidence_type -> allowed data sources

Extend by editing ONLY this file + the rules YAML.
"""

from typing import Any, Dict, List

# Evidence type -> allowed data sources (data_type + methods)
EVIDENCE_TO_DATA_SOURCES: Dict[str, List[Dict[str, Any]]] = {
    "Binding_Affinity": [
        {"data_type": "Binding", "methods": ["SPR", "BLI"]}
    ],
    "InVitro_Potency": [
        {"data_type": "CellAssay", "methods": ["Reporter", "Proliferation"]}
    ],
    "InVivo_Efficacy": [
        {"data_type": "InVivo", "methods": ["NOD", "OtherMouse"]}
    ],
    "Purity_SEC": [
        {"data_type": "CMC_Analytics", "methods": ["SEC"]}
    ],
    "Aggregation_HMW": [
        {"data_type": "CMC_Analytics", "methods": ["SEC", "DLS"]}
    ],
    "CRO_Quote": [
        {"data_type": "Execution", "methods": ["Quote"]}
    ],
    "Study_Protocol": [
        {"data_type": "Execution", "methods": ["Protocol"]}
    ],
    "Safety_RedFlag": [
        {"data_type": "Execution", "methods": ["RiskNote"]}
    ],
}


# Data schemas: data_type -> method -> fields
# Fields format: {key, label, type, required, units?, options?, help?}
DATA_SCHEMAS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "Binding": {
        "SPR": {
            "params_fields": [
                {"key": "analyte", "label": "Analyte", "type": "text", "required": True},
                {"key": "ligand", "label": "Ligand", "type": "text", "required": True},
            ],
            "results_fields": [
                {"key": "kd_nM", "label": "KD", "type": "number", "required": True, "units": "nM"},
                {"key": "kon", "label": "kon", "type": "number", "required": False, "units": "1/Ms"},
                {"key": "koff", "label": "koff", "type": "number", "required": False, "units": "1/s"},
            ],
        },
        "BLI": {
            "params_fields": [
                {"key": "sensor", "label": "Sensor", "type": "text", "required": False},
                {"key": "analyte", "label": "Analyte", "type": "text", "required": True},
            ],
            "results_fields": [
                {"key": "kd_nM", "label": "KD", "type": "number", "required": True, "units": "nM"},
            ],
        },
    },
    "CellAssay": {
        "Reporter": {
            "params_fields": [
                {"key": "cell_line", "label": "Cell line", "type": "text", "required": True},
                {"key": "readout", "label": "Readout", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "ec50_nM", "label": "EC50", "type": "number", "required": False, "units": "nM"},
                {"key": "ic50_nM", "label": "IC50", "type": "number", "required": False, "units": "nM"},
                {"key": "max_effect_pct", "label": "Max effect", "type": "number", "required": False, "units": "%"},
            ],
        },
        "Proliferation": {
            "params_fields": [
                {"key": "cell_type", "label": "Cell type", "type": "text", "required": True},
            ],
            "results_fields": [
                {"key": "inhibition_pct", "label": "Inhibition", "type": "number", "required": True, "units": "%"},
            ],
        },
    },
    "InVivo": {
        "NOD": {
            "params_fields": [
                {"key": "model", "label": "Model", "type": "text", "required": True, "help": "e.g., NOD"},
                {"key": "dose_mgkg", "label": "Dose", "type": "number", "required": False, "units": "mg/kg"},
            ],
            "results_fields": [
                {"key": "endpoint", "label": "Primary endpoint", "type": "text", "required": True},
                {"key": "effect_size", "label": "Effect size", "type": "number", "required": False},
                {"key": "p_value", "label": "p-value", "type": "number", "required": False},
            ],
        },
        "OtherMouse": {
            "params_fields": [
                {"key": "model", "label": "Model", "type": "text", "required": True},
            ],
            "results_fields": [
                {"key": "endpoint", "label": "Primary endpoint", "type": "text", "required": True},
            ],
        },
    },
    "CMC_Analytics": {
        "SEC": {
            "params_fields": [
                {"key": "column", "label": "Column", "type": "text", "required": False},
                {"key": "mobile_phase", "label": "Mobile phase", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "monomer_pct", "label": "Monomer", "type": "number", "required": True, "units": "%"},
                {"key": "hmw_pct", "label": "HMW", "type": "number", "required": False, "units": "%"},
                {"key": "lmw_pct", "label": "LMW", "type": "number", "required": False, "units": "%"},
            ],
        },
        "DLS": {
            "params_fields": [
                {"key": "temp_C", "label": "Temperature", "type": "number", "required": False, "units": "°C"},
            ],
            "results_fields": [
                {"key": "zavg_nm", "label": "Z-average", "type": "number", "required": False, "units": "nm"},
                {"key": "pdi", "label": "PDI", "type": "number", "required": False},
            ],
        },
    },
    "Execution": {
        "Quote": {
            "params_fields": [
                {"key": "vendor", "label": "Vendor", "type": "text", "required": True},
            ],
            "results_fields": [
                {"key": "cost_usd", "label": "Quoted cost", "type": "number", "required": False, "units": "USD"},
                {"key": "lead_time_days", "label": "Lead time", "type": "number", "required": False, "units": "days"},
            ],
        },
        "Protocol": {
            "params_fields": [
                {"key": "study_name", "label": "Study name", "type": "text", "required": True},
            ],
            "results_fields": [
                {"key": "version", "label": "Version", "type": "text", "required": False},
            ],
        },
        "RiskNote": {
            "params_fields": [
                {"key": "category", "label": "Category", "type": "select", "required": True,
                 "options": ["Safety", "Bio", "CMC", "Ops"]},
            ],
            "results_fields": [
                {"key": "severity", "label": "Severity", "type": "select", "required": True,
                 "options": ["Low", "Medium", "High"]},
                {"key": "mitigation", "label": "Mitigation", "type": "text", "required": False},
            ],
        },
    },
}


# For most experimental data types, require a batch.
DATA_TYPES_REQUIRING_BATCH = {"Binding", "CellAssay", "InVivo", "CMC_Analytics"}


# Data types that are allowed to be program-level (batch not required).
PROGRAM_LEVEL_DATA_TYPES = {"Execution"}


def get_allowed_data_sources_for_evidence(evidence_type: str) -> Dict[str, Any]:
    """Return allowed (data_type, method) pairs for a given evidence_type.

    Returned shape is stable for template/JS consumption.
    """
    allowed = EVIDENCE_TO_DATA_SOURCES.get(evidence_type) or []
    out: List[Dict[str, str]] = []
    for item in allowed:
        dt = item.get("data_type")
        for m in (item.get("methods") or []):
            out.append({"data_type": dt, "method": m})
    return {"evidence_type": evidence_type, "allowed": out}


REGISTRY: Dict[str, Any] = {
    "evidence_to_data_sources": EVIDENCE_TO_DATA_SOURCES,
    "data_schemas": DATA_SCHEMAS,
    "data_types_requiring_batch": sorted(DATA_TYPES_REQUIRING_BATCH),
    "program_level_data_types": sorted(PROGRAM_LEVEL_DATA_TYPES),
}
