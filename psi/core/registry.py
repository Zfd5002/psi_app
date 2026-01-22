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
        {"data_type": "CMC_Analytics", "methods": ["SEC", "SEC_HPLC"]}
    ],
    "Aggregation_HMW": [
        {"data_type": "CMC_Analytics", "methods": ["SEC", "SEC_HPLC", "DLS"]}
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
                {"key": "platform", "label": "Platform", "type": "select", "required": False, "options": ["SPR"]},
                {"key": "instrument", "label": "Instrument", "type": "text", "required": False},
                {"key": "analyte", "label": "Analyte", "type": "text", "required": True},
                {"key": "ligand", "label": "Ligand / target", "type": "text", "required": True, "help": "e.g., Antigen A"},
                {"key": "orientation", "label": "Orientation", "type": "text", "required": False, "help": "e.g., ligand immobilized"},
                {"key": "model", "label": "Fit model", "type": "text", "required": False, "help": "e.g., 1:1, bivalent"},
                {"key": "buffer", "label": "Running buffer", "type": "text", "required": True, "help": "e.g., HBS-EP+"},
                {"key": "pH", "label": "pH", "type": "number", "required": False},
                {"key": "salt_type", "label": "Salt", "type": "select", "required": False, "options": ["NaCl","KCl","None"]},
                {"key": "salt_mM", "label": "Salt concentration", "type": "number", "required": False, "units": "mM"},
                {"key": "additives", "label": "Additives", "type": "text", "required": False},
                {"key": "temperature_C", "label": "Temperature", "type": "number", "required": False, "units": "°C"},
            ],
            "results_fields": [
                {"key": "kd_nM", "label": "KD", "type": "number", "required": True, "units": "nM"},
                {"key": "kon", "label": "kon", "type": "number", "required": False, "units": "1/M·s"},
                {"key": "koff", "label": "koff", "type": "number", "required": False, "units": "1/s"},
                {"key": "rmax", "label": "Rmax", "type": "number", "required": False},
                {"key": "chi2", "label": "Chi²", "type": "number", "required": False},
            ] ,
        },
        "BLI": {
            "params_fields": [
                {"key": "platform", "label": "Platform", "type": "select", "required": False, "options": ["BLI"]},
                {"key": "instrument", "label": "Instrument", "type": "text", "required": False},
                {"key": "analyte", "label": "Analyte", "type": "text", "required": True},
                {"key": "ligand", "label": "Ligand / target", "type": "text", "required": False},
                {"key": "sensor", "label": "Sensor", "type": "text", "required": False},
                {"key": "model", "label": "Fit model", "type": "text", "required": False},
                {"key": "buffer", "label": "Running buffer", "type": "text", "required": True},
                {"key": "pH", "label": "pH", "type": "number", "required": False},
                {"key": "salt_type", "label": "Salt", "type": "select", "required": False, "options": ["NaCl","KCl","None"]},
                {"key": "salt_mM", "label": "Salt concentration", "type": "number", "required": False, "units": "mM"},
                {"key": "additives", "label": "Additives", "type": "text", "required": False},
                {"key": "temperature_C", "label": "Temperature", "type": "number", "required": False, "units": "°C"},
            ],
            "results_fields": [
                {"key": "kd_nM", "label": "KD", "type": "number", "required": True, "units": "nM"},
                {"key": "kon", "label": "kon", "type": "number", "required": False, "units": "1/M·s"},
                {"key": "koff", "label": "koff", "type": "number", "required": False, "units": "1/s"},
                {"key": "rmax", "label": "Rmax", "type": "number", "required": False},
                {"key": "fit_quality", "label": "Fit quality", "type": "select", "required": False, "options": ["Good","OK","Poor"]},
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
                {"key": "buffer", "label": "Buffer", "type": "text", "required": True, "help": "e.g., PBS"},
                {"key": "pH", "label": "pH", "type": "number", "required": False},
                {"key": "salt_type", "label": "Salt", "type": "select", "required": False, "options": ["NaCl","KCl","None"]},
                {"key": "salt_mM", "label": "Salt concentration", "type": "number", "required": False, "units": "mM"},
                {"key": "additives", "label": "Additives", "type": "text", "required": False, "help": "e.g., 0.01% Tween-20"},
                {"key": "column", "label": "Column", "type": "text", "required": False},
                {"key": "flow_rate_ml_min", "label": "Flow rate", "type": "number", "required": False, "units": "mL/min"},
            ],
            "results_fields": [
                {"key": "monomer_pct", "label": "Monomer", "type": "number", "required": True, "units": "%"},
                {"key": "hmw_pct", "label": "HMW", "type": "number", "required": False, "units": "%"},
                {"key": "lmw_pct", "label": "LMW", "type": "number", "required": False, "units": "%"},
            ],
        },
        "SEC_HPLC": {
            "params_fields": [
                {"key": "instrument", "label": "Instrument", "type": "text", "required": False},
                {"key": "method_name", "label": "Method name", "type": "text", "required": False},
                {"key": "buffer", "label": "Buffer", "type": "text", "required": True, "help": "e.g., PBS"},
                {"key": "pH", "label": "pH", "type": "number", "required": False},
                {"key": "salt_type", "label": "Salt", "type": "select", "required": False, "options": ["NaCl","KCl","None"]},
                {"key": "salt_mM", "label": "Salt concentration", "type": "number", "required": False, "units": "mM"},
                {"key": "additives", "label": "Additives", "type": "text", "required": False, "help": "e.g., 0.01% Tween-20"},
                {"key": "column", "label": "Column", "type": "text", "required": True},
                {"key": "flow_rate_ml_min", "label": "Flow rate", "type": "number", "required": False, "units": "mL/min"},
                {"key": "detection_nm", "label": "Detection", "type": "number", "required": False, "units": "nm"},
                {"key": "injection_ul", "label": "Injection volume", "type": "number", "required": False, "units": "µL"},
                {"key": "injection_ug", "label": "Injection mass", "type": "number", "required": False, "units": "µg"},
            ],
            "results_fields": [
                {"key": "monomer_pct", "label": "Monomer", "type": "number", "required": True, "units": "%"},
                {"key": "hmw_pct", "label": "HMW", "type": "number", "required": False, "units": "%"},
                {"key": "lmw_pct", "label": "LMW", "type": "number", "required": False, "units": "%"},
                {"key": "rt_monomer_min", "label": "Monomer RT", "type": "number", "required": False, "units": "min"},
                {"key": "recovery_pct", "label": "Recovery", "type": "number", "required": False, "units": "%"},
            ],
        },
        "Endotoxin": {
            "params_fields": [
                {"key": "method", "label": "Method", "type": "text", "required": True},
                {"key": "kit_vendor", "label": "Kit vendor", "type": "text", "required": False},
                {"key": "kit_lot", "label": "Kit lot", "type": "text", "required": False},
                {"key": "dilution_factor", "label": "Dilution factor", "type": "number", "required": False},
                {"key": "sample_matrix", "label": "Sample matrix / buffer", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "value_eu_ml", "label": "Endotoxin", "type": "number", "required": True, "units": "EU/mL"},
                {"key": "limit_eu_ml", "label": "Acceptance limit", "type": "number", "required": True, "units": "EU/mL"},
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
