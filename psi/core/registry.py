from __future__ import annotations

"""Central registry driving dynamic forms and evidence->data restrictions.

This registry powers:
- DataRecord create/edit: domain -> data_type -> method -> structured fields
- Evidence citations: evidence_type -> allowed data sources

v1.1.7 introduces a canonical, extensible catalogue:
OPS -> PROCESS -> CMC -> BIO -> COMPUTE (chronological pipeline order)

Backward compatibility:
- Existing records store domain/data_type/method as strings. We preserve that.
- We normalize legacy values on read/write where safe via aliases.
- If a legacy record cannot be mapped cleanly, it remains editable via legacy schemas.
"""

from typing import Any, Dict, List, Optional, Tuple


# -----------------------------
# Canonical domain taxonomy (ordered by pipeline)
# -----------------------------
DOMAINS_ORDERED: List[Dict[str, Any]] = [
    {"key": "OPS", "label": "Execution / Operations", "order": 1, "description": "Quotes, work orders, logistics, costs"},
    {"key": "PROCESS", "label": "Process / Expression", "order": 2, "description": "Expression and purification execution"},
    {"key": "CMC", "label": "CMC / Analytics", "order": 3, "description": "Analytics: SEC, purity, identity, endotoxin, stability"},
    {"key": "BIO", "label": "Biology", "order": 4, "description": "Binding, cell assays, in vivo, PK/PD"},
    {"key": "COMPUTE", "label": "Computation / In Silico", "order": 5, "description": "Computational predictions and models"},
]

DOMAIN_ALIASES: Dict[str, str] = {
    # legacy rules YAML domains (decision engine)
    "Biological": "BIO",
    "CMC": "CMC",
    "Execution": "OPS",
    # allow canonical passthrough
    "OPS": "OPS",
    "PROCESS": "PROCESS",
    "BIO": "BIO",
    "COMPUTE": "COMPUTE",
}

DOMAIN_LABELS: Dict[str, str] = {d["key"]: d["label"] for d in DOMAINS_ORDERED}


# -----------------------------
# Canonical data types + metadata
# -----------------------------
# scope:
# - "batch": requires batch_id
# - "program": batch_id optional (program-level docs)
DATA_TYPE_META: Dict[str, Dict[str, Any]] = {
    # OPS
    "WORK_ORDER": {"label": "Work order", "domain_key": "OPS", "scope": "program"},
    "COST": {"label": "Cost / Quote / Invoice", "domain_key": "OPS", "scope": "program"},
    # PROCESS
    "EXPRESSION": {"label": "Expression / Production run", "domain_key": "PROCESS", "scope": "batch"},
    "PURIFICATION_RUN": {"label": "Purification run", "domain_key": "PROCESS", "scope": "batch"},
    # CMC
    "SEC": {"label": "SEC (Size Exclusion Chromatography)", "domain_key": "CMC", "scope": "batch"},
    "PURITY": {"label": "Purity", "domain_key": "CMC", "scope": "batch"},
    "IDENTITY": {"label": "Identity / Mass / Peptide map", "domain_key": "CMC", "scope": "batch"},
    "ENDOTOXIN": {"label": "Endotoxin", "domain_key": "CMC", "scope": "batch"},
    "DLS": {"label": "DLS", "domain_key": "CMC", "scope": "batch"},
    "STABILITY": {"label": "Stability", "domain_key": "CMC", "scope": "batch"},
    # BIO
    "BINDING": {"label": "Binding", "domain_key": "BIO", "scope": "batch"},
    "CELL_ASSAY": {"label": "Cell assay", "domain_key": "BIO", "scope": "batch"},
    "IN_VIVO_EFFICACY": {"label": "In vivo efficacy", "domain_key": "BIO", "scope": "batch"},
    "PK_PD": {"label": "PK / PD", "domain_key": "BIO", "scope": "batch"},
    # COMPUTE
    "IN_SILICO": {"label": "In silico", "domain_key": "COMPUTE", "scope": "program"},
}

def _requires_batch(dt_key: str) -> bool:
    meta = DATA_TYPE_META.get(dt_key) or {}
    return meta.get("scope") == "batch"

DATA_TYPES_BY_DOMAIN: Dict[str, List[str]] = {}
for dt_key, meta in DATA_TYPE_META.items():
    DATA_TYPES_BY_DOMAIN.setdefault(meta["domain_key"], []).append(dt_key)
for dk in list(DATA_TYPES_BY_DOMAIN.keys()):
    DATA_TYPES_BY_DOMAIN[dk] = sorted(DATA_TYPES_BY_DOMAIN[dk])


# -----------------------------
# Canonical method schemas
# Fields format: {key, label, type, required, units?, options?, help?}
# -----------------------------
DATA_SCHEMAS: Dict[str, Dict[str, Dict[str, Any]]] = {
    # OPS
    "WORK_ORDER": {
        "CRO_WORK_ORDER": {
            "params_fields": [
                {"key": "vendor", "label": "Vendor", "type": "text", "required": False},
                {"key": "po_number", "label": "PO number", "type": "text", "required": False},
                {"key": "start_date", "label": "Start date", "type": "date", "required": False},
                {"key": "due_date", "label": "Due date", "type": "date", "required": False},
                {"key": "scope", "label": "Scope", "type": "textarea", "required": False},
                # legacy-ish protocol fields (kept for compatibility with older "Protocol" docs)
                {"key": "study_name", "label": "Study name", "type": "text", "required": False},
                {"key": "protocol_version", "label": "Protocol version", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "status", "label": "Status", "type": "select", "required": False, "options": ["planned", "in_progress", "done", "blocked"]},
                {"key": "delivery_date", "label": "Delivery date", "type": "date", "required": False},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
        }
    },
    "COST": {
        "QUOTE": {
            "params_fields": [
                {"key": "vendor", "label": "Vendor", "type": "text", "required": False},
                {"key": "line_item", "label": "Line item", "type": "text", "required": False},
                {"key": "date", "label": "Date", "type": "date", "required": False},
            ],
            "results_fields": [
                {"key": "amount_usd", "label": "Amount", "type": "number", "required": False, "units": "USD"},
                {"key": "lead_time_days", "label": "Lead time", "type": "number", "required": False, "units": "days"},
                {"key": "status", "label": "Status", "type": "select", "required": False, "options": ["quoted", "approved", "paid", "rejected"]},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
                # legacy support
                {"key": "cost_usd", "label": "(Legacy) Quoted cost", "type": "number", "required": False, "units": "USD"},
            ],
        },
        "INVOICE": {
            "params_fields": [
                {"key": "vendor", "label": "Vendor", "type": "text", "required": False},
                {"key": "line_item", "label": "Line item", "type": "text", "required": False},
                {"key": "date", "label": "Date", "type": "date", "required": False},
            ],
            "results_fields": [
                {"key": "amount_usd", "label": "Amount", "type": "number", "required": False, "units": "USD"},
                {"key": "status", "label": "Status", "type": "select", "required": False, "options": ["quoted", "approved", "paid", "rejected"]},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
        },
    },

    # PROCESS
    "EXPRESSION": {
        "TRANSIENT_HEK": {
            "params_fields": [
                {"key": "host", "label": "Host", "type": "text", "required": False},
                {"key": "construct_id", "label": "Construct ID", "type": "text", "required": False},
                {"key": "culture_volume_l", "label": "Culture volume", "type": "number", "required": False, "units": "L"},
                {"key": "harvest_day", "label": "Harvest day", "type": "number", "required": False},
                {"key": "temperature_c", "label": "Temperature", "type": "number", "required": False, "units": "°C"},
                {"key": "media", "label": "Media", "type": "text", "required": False},
                {"key": "transfection_reagent", "label": "Transfection reagent", "type": "text", "required": False},
                {"key": "cro", "label": "CRO", "type": "text", "required": False},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
            "results_fields": [
                {"key": "titer_mg_l", "label": "Titer", "type": "number", "required": False, "units": "mg/L"},
                {"key": "total_yield_mg", "label": "Total yield", "type": "number", "required": False, "units": "mg"},
                {"key": "viability_percent", "label": "Viability", "type": "number", "required": False, "units": "%"},
                {"key": "qc_notes", "label": "QC notes", "type": "textarea", "required": False},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
            ],
        },
        "STABLE_CHO": {
            "params_fields": [
                {"key": "host", "label": "Host", "type": "text", "required": False},
                {"key": "construct_id", "label": "Construct ID", "type": "text", "required": False},
                {"key": "culture_volume_l", "label": "Culture volume", "type": "number", "required": False, "units": "L"},
                {"key": "harvest_day", "label": "Harvest day", "type": "number", "required": False},
                {"key": "temperature_c", "label": "Temperature", "type": "number", "required": False, "units": "°C"},
                {"key": "media", "label": "Media", "type": "text", "required": False},
                {"key": "cro", "label": "CRO", "type": "text", "required": False},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
            "results_fields": [
                {"key": "titer_mg_l", "label": "Titer", "type": "number", "required": False, "units": "mg/L"},
                {"key": "total_yield_mg", "label": "Total yield", "type": "number", "required": False, "units": "mg"},
                {"key": "viability_percent", "label": "Viability", "type": "number", "required": False, "units": "%"},
                {"key": "qc_notes", "label": "QC notes", "type": "textarea", "required": False},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
            ],
        },
        "OTHER": {
            "params_fields": [
                {"key": "host", "label": "Host", "type": "text", "required": False},
                {"key": "method_details", "label": "Method details", "type": "textarea", "required": False},
                {"key": "cro", "label": "CRO", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "titer_mg_l", "label": "Titer", "type": "number", "required": False, "units": "mg/L"},
                {"key": "total_yield_mg", "label": "Total yield", "type": "number", "required": False, "units": "mg"},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
            ],
        },
    },
    "PURIFICATION_RUN": {
        "PROA": {
            "params_fields": [
                {"key": "step_name", "label": "Step name", "type": "text", "required": False},
                {"key": "resin", "label": "Resin", "type": "text", "required": False},
                {"key": "column_volume_ml", "label": "Column volume", "type": "number", "required": False, "units": "mL"},
                {"key": "load_mg", "label": "Load", "type": "number", "required": False, "units": "mg"},
                {"key": "elution_conditions", "label": "Elution conditions", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "step_yield_percent", "label": "Step yield", "type": "number", "required": False, "units": "%"},
                {"key": "pool_concentration_mg_ml", "label": "Pool concentration", "type": "number", "required": False, "units": "mg/mL"},
                {"key": "pool_volume_ml", "label": "Pool volume", "type": "number", "required": False, "units": "mL"},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
        },
        "PROG": {
            "params_fields": [
                {"key": "step_name", "label": "Step name", "type": "text", "required": False},
                {"key": "resin", "label": "Resin", "type": "text", "required": False},
                {"key": "column_volume_ml", "label": "Column volume", "type": "number", "required": False, "units": "mL"},
                {"key": "load_mg", "label": "Load", "type": "number", "required": False, "units": "mg"},
                {"key": "elution_conditions", "label": "Elution conditions", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "step_yield_percent", "label": "Step yield", "type": "number", "required": False, "units": "%"},
                {"key": "pool_concentration_mg_ml", "label": "Pool concentration", "type": "number", "required": False, "units": "mg/mL"},
                {"key": "pool_volume_ml", "label": "Pool volume", "type": "number", "required": False, "units": "mL"},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
        },
        "PROL": {
            "params_fields": [
                {"key": "step_name", "label": "Step name", "type": "text", "required": False},
                {"key": "resin", "label": "Resin", "type": "text", "required": False},
                {"key": "column_volume_ml", "label": "Column volume", "type": "number", "required": False, "units": "mL"},
                {"key": "load_mg", "label": "Load", "type": "number", "required": False, "units": "mg"},
                {"key": "elution_conditions", "label": "Elution conditions", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "step_yield_percent", "label": "Step yield", "type": "number", "required": False, "units": "%"},
                {"key": "pool_concentration_mg_ml", "label": "Pool concentration", "type": "number", "required": False, "units": "mg/mL"},
                {"key": "pool_volume_ml", "label": "Pool volume", "type": "number", "required": False, "units": "mL"},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
        },
        "IEX": {
            "params_fields": [
                {"key": "step_name", "label": "Step name", "type": "text", "required": False},
                {"key": "resin", "label": "Resin", "type": "text", "required": False},
                {"key": "column_volume_ml", "label": "Column volume", "type": "number", "required": False, "units": "mL"},
                {"key": "load_mg", "label": "Load", "type": "number", "required": False, "units": "mg"},
                {"key": "elution_conditions", "label": "Elution conditions", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "step_yield_percent", "label": "Step yield", "type": "number", "required": False, "units": "%"},
                {"key": "pool_concentration_mg_ml", "label": "Pool concentration", "type": "number", "required": False, "units": "mg/mL"},
                {"key": "pool_volume_ml", "label": "Pool volume", "type": "number", "required": False, "units": "mL"},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
        },
        "HIC": {
            "params_fields": [
                {"key": "step_name", "label": "Step name", "type": "text", "required": False},
                {"key": "resin", "label": "Resin", "type": "text", "required": False},
                {"key": "column_volume_ml", "label": "Column volume", "type": "number", "required": False, "units": "mL"},
                {"key": "load_mg", "label": "Load", "type": "number", "required": False, "units": "mg"},
                {"key": "elution_conditions", "label": "Elution conditions", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "step_yield_percent", "label": "Step yield", "type": "number", "required": False, "units": "%"},
                {"key": "pool_concentration_mg_ml", "label": "Pool concentration", "type": "number", "required": False, "units": "mg/mL"},
                {"key": "pool_volume_ml", "label": "Pool volume", "type": "number", "required": False, "units": "mL"},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
        },
        "SEC_POLISH": {
            "params_fields": [
                {"key": "step_name", "label": "Step name", "type": "text", "required": False},
                {"key": "resin", "label": "Resin", "type": "text", "required": False},
                {"key": "column_volume_ml", "label": "Column volume", "type": "number", "required": False, "units": "mL"},
                {"key": "load_mg", "label": "Load", "type": "number", "required": False, "units": "mg"},
                {"key": "elution_conditions", "label": "Elution conditions", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "step_yield_percent", "label": "Step yield", "type": "number", "required": False, "units": "%"},
                {"key": "pool_concentration_mg_ml", "label": "Pool concentration", "type": "number", "required": False, "units": "mg/mL"},
                {"key": "pool_volume_ml", "label": "Pool volume", "type": "number", "required": False, "units": "mL"},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
        },
    },

    # CMC
    "SEC": {
        "SEC": {
            "params_fields": [
                {"key": "column", "label": "Column", "type": "text", "required": False},
                {"key": "instrument", "label": "Instrument", "type": "text", "required": False, "help": "HPLC/UPLC/FPLC system name"},
                {"key": "mobile_phase", "label": "Mobile phase / buffer", "type": "text", "required": False},
                {"key": "flow_rate_ml_min", "label": "Flow rate", "type": "number", "required": False, "units": "mL/min"},
                {"key": "injection_volume_ul", "label": "Injection volume", "type": "number", "required": False, "units": "µL"},
                {"key": "sample_concentration_mg_ml", "label": "Sample concentration", "type": "number", "required": False, "units": "mg/mL"},
                {"key": "detection_nm", "label": "Detection", "type": "number", "required": False, "units": "nm"},
                {"key": "runtime_min", "label": "Runtime", "type": "number", "required": False, "units": "min"},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
            "results_fields": [
                {"key": "monomer_percent", "label": "Monomer", "type": "number", "required": False, "units": "%"},
                {"key": "hmw_percent", "label": "HMW", "type": "number", "required": False, "units": "%"},
                {"key": "lmw_percent", "label": "LMW", "type": "number", "required": False, "units": "%"},
                {"key": "monomer_rt_min", "label": "Monomer RT", "type": "number", "required": False, "units": "min"},
                {"key": "hmw_rt_min", "label": "HMW RT", "type": "number", "required": False, "units": "min"},
                {"key": "lmw_rt_min", "label": "LMW RT", "type": "number", "required": False, "units": "min"},
                {"key": "peak_table", "label": "Peak table", "type": "textarea", "required": False, "help": "Optional table or JSON summary"},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
                # legacy keys compatibility
                {"key": "monomer_pct", "label": "(Legacy) Monomer", "type": "number", "required": False, "units": "%"},
                {"key": "hmw_pct", "label": "(Legacy) HMW", "type": "number", "required": False, "units": "%"},
                {"key": "lmw_pct", "label": "(Legacy) LMW", "type": "number", "required": False, "units": "%"},
                {"key": "rt_monomer_min", "label": "(Legacy) Monomer RT", "type": "number", "required": False, "units": "min"},
            ],
        }
    },
    "PURITY": {
        "CE_SDS": {
            "params_fields": [
                {"key": "method_details", "label": "Method details", "type": "textarea", "required": False},
                {"key": "reducing", "label": "Reducing", "type": "select", "required": False, "options": ["no", "yes"]},
                {"key": "detection", "label": "Detection", "type": "text", "required": False},
                {"key": "column_or_gel", "label": "Column / gel", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "purity_percent", "label": "Purity", "type": "number", "required": False, "units": "%"},
                {"key": "main_peak_percent", "label": "Main peak", "type": "number", "required": False, "units": "%"},
                {"key": "fragments_percent", "label": "Fragments", "type": "number", "required": False, "units": "%"},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
            ],
        },
        "RP_HPLC": {
            "params_fields": [
                {"key": "method_details", "label": "Method details", "type": "textarea", "required": False},
                {"key": "reducing", "label": "Reducing", "type": "select", "required": False, "options": ["no", "yes"]},
                {"key": "detection", "label": "Detection", "type": "text", "required": False},
                {"key": "column_or_gel", "label": "Column / gel", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "purity_percent", "label": "Purity", "type": "number", "required": False, "units": "%"},
                {"key": "main_peak_percent", "label": "Main peak", "type": "number", "required": False, "units": "%"},
                {"key": "fragments_percent", "label": "Fragments", "type": "number", "required": False, "units": "%"},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
            ],
        },
        "SDS_PAGE": {
            "params_fields": [
                {"key": "method_details", "label": "Method details", "type": "textarea", "required": False},
                {"key": "reducing", "label": "Reducing", "type": "select", "required": False, "options": ["no", "yes"]},
                {"key": "detection", "label": "Detection", "type": "text", "required": False},
                {"key": "column_or_gel", "label": "Gel", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "purity_percent", "label": "Purity (est.)", "type": "number", "required": False, "units": "%"},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
            ],
        },
    },
    "IDENTITY": {
        "LCMS_INTACT": {
            "params_fields": [
                {"key": "instrument", "label": "Instrument", "type": "text", "required": False},
                {"key": "prep", "label": "Prep", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "expected_mass_da", "label": "Expected mass", "type": "number", "required": False, "units": "Da"},
                {"key": "observed_mass_da", "label": "Observed mass", "type": "number", "required": False, "units": "Da"},
                {"key": "delta_mass_da", "label": "Δ mass", "type": "number", "required": False, "units": "Da"},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
            ],
        },
        "PEPTIDE_MAP": {
            "params_fields": [
                {"key": "instrument", "label": "Instrument", "type": "text", "required": False},
                {"key": "prep", "label": "Prep", "type": "text", "required": False},
                {"key": "enzyme", "label": "Enzyme", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "sequence_coverage_percent", "label": "Sequence coverage", "type": "number", "required": False, "units": "%"},
                {"key": "mods_detected", "label": "Mods detected", "type": "text", "required": False},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
            ],
        },
    },
    "ENDOTOXIN": {
        "LAL": {
            "params_fields": [
                {"key": "kit", "label": "Kit", "type": "text", "required": False},
                {"key": "dilution", "label": "Dilution", "type": "text", "required": False},
                {"key": "matrix_interference_tested", "label": "Matrix interference tested", "type": "select", "required": False, "options": ["no", "yes"]},
            ],
            "results_fields": [
                {"key": "endotoxin_eu_ml", "label": "Endotoxin", "type": "number", "required": False, "units": "EU/mL"},
                {"key": "endotoxin_eu_mg", "label": "Endotoxin", "type": "number", "required": False, "units": "EU/mg"},
                {"key": "spec_limit_eu_mg", "label": "Spec limit", "type": "number", "required": False, "units": "EU/mg"},
                {"key": "pass_fail", "label": "Pass/fail", "type": "select", "required": False, "options": ["pass", "fail", "na"]},
                # legacy
                {"key": "value_eu_ml", "label": "(Legacy) Endotoxin", "type": "number", "required": False, "units": "EU/mL"},
                {"key": "limit_eu_ml", "label": "(Legacy) Acceptance limit", "type": "number", "required": False, "units": "EU/mL"},
            ],
        },
        "ENDOSAFE": {
            "params_fields": [
                {"key": "kit", "label": "Kit", "type": "text", "required": False},
                {"key": "dilution", "label": "Dilution", "type": "text", "required": False},
                {"key": "matrix_interference_tested", "label": "Matrix interference tested", "type": "select", "required": False, "options": ["no", "yes"]},
            ],
            "results_fields": [
                {"key": "endotoxin_eu_ml", "label": "Endotoxin", "type": "number", "required": False, "units": "EU/mL"},
                {"key": "endotoxin_eu_mg", "label": "Endotoxin", "type": "number", "required": False, "units": "EU/mg"},
                {"key": "spec_limit_eu_mg", "label": "Spec limit", "type": "number", "required": False, "units": "EU/mg"},
                {"key": "pass_fail", "label": "Pass/fail", "type": "select", "required": False, "options": ["pass", "fail", "na"]},
            ],
        },
    },
    "DLS": {
        "DLS": {
            "params_fields": [
                {"key": "instrument", "label": "Instrument", "type": "text", "required": False},
                {"key": "temperature_c", "label": "Temperature", "type": "number", "required": False, "units": "°C"},
                {"key": "concentration_mg_ml", "label": "Concentration", "type": "number", "required": False, "units": "mg/mL"},
                {"key": "buffer", "label": "Buffer", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "z_avg_nm", "label": "Z-average", "type": "number", "required": False, "units": "nm"},
                {"key": "pdi", "label": "PDI", "type": "number", "required": False},
                {"key": "percent_aggregate", "label": "% aggregate", "type": "number", "required": False, "units": "%"},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
                # legacy
                {"key": "zavg_nm", "label": "(Legacy) Z-average", "type": "number", "required": False, "units": "nm"},
                {"key": "temp_C", "label": "(Legacy) Temperature", "type": "number", "required": False, "units": "°C"},
            ],
        }
    },
    "STABILITY": {
        "REAL_TIME": {
            "params_fields": [
                {"key": "condition", "label": "Condition", "type": "text", "required": False},
                {"key": "duration_days", "label": "Duration", "type": "number", "required": False, "units": "days"},
                {"key": "formulation", "label": "Formulation", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "sec_monomer_percent", "label": "SEC monomer", "type": "number", "required": False, "units": "%"},
                {"key": "binding_kd_nM", "label": "Binding KD", "type": "number", "required": False, "units": "nM"},
                {"key": "visible_particles", "label": "Visible particles", "type": "select", "required": False, "options": ["no", "yes"]},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
            ],
        },
        "ACCELERATED": {
            "params_fields": [
                {"key": "condition", "label": "Condition", "type": "text", "required": False},
                {"key": "duration_days", "label": "Duration", "type": "number", "required": False, "units": "days"},
                {"key": "formulation", "label": "Formulation", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "sec_monomer_percent", "label": "SEC monomer", "type": "number", "required": False, "units": "%"},
                {"key": "binding_kd_nM", "label": "Binding KD", "type": "number", "required": False, "units": "nM"},
                {"key": "visible_particles", "label": "Visible particles", "type": "select", "required": False, "options": ["no", "yes"]},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
            ],
        },
        "FREEZE_THAW": {
            "params_fields": [
                {"key": "condition", "label": "Condition", "type": "text", "required": False},
                {"key": "cycles", "label": "Cycles", "type": "number", "required": False},
                {"key": "formulation", "label": "Formulation", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "sec_monomer_percent", "label": "SEC monomer", "type": "number", "required": False, "units": "%"},
                {"key": "binding_kd_nM", "label": "Binding KD", "type": "number", "required": False, "units": "nM"},
                {"key": "visible_particles", "label": "Visible particles", "type": "select", "required": False, "options": ["no", "yes"]},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
            ],
        },
    },

    # BIO
    "BINDING": {
        "SPR": {
            "params_fields": [
                {"key": "analyte_name", "label": "Analyte", "type": "text", "required": False},
                {"key": "analyte_type", "label": "Analyte type", "type": "select", "required": False, "options": ["protein", "cells", "other"]},
                {"key": "ligand_or_capture", "label": "Ligand / capture", "type": "text", "required": False},
                {"key": "buffer", "label": "Buffer", "type": "text", "required": False},
                {"key": "assay_temperature_c", "label": "Temperature", "type": "number", "required": False, "units": "°C"},
                {"key": "replicates_n", "label": "Replicates", "type": "number", "required": False},
                {"key": "chip_or_sensor", "label": "Chip / sensor", "type": "text", "required": False},
                {"key": "capture_strategy", "label": "Capture strategy", "type": "text", "required": False},
                {"key": "reference_subtraction", "label": "Reference subtraction", "type": "select", "required": False, "options": ["no", "yes"]},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
            "results_fields": [
                {"key": "kd", "label": "KD", "type": "number", "required": False, "units": "nM"},
                {"key": "ka", "label": "ka", "type": "number", "required": False, "units": "1/M·s"},
                {"key": "kdiss", "label": "kdiss", "type": "number", "required": False, "units": "1/s"},
                {"key": "fit_model", "label": "Fit model", "type": "select", "required": False, "options": ["1to1", "heterogeneous", "bivalent", "steady_state", "other"]},
                {"key": "chi2", "label": "Chi²", "type": "number", "required": False},
                {"key": "rmax", "label": "Rmax", "type": "number", "required": False},
                {"key": "binding_confirmed", "label": "Binding confirmed", "type": "select", "required": False, "options": ["no", "yes"]},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
                # legacy keys
                {"key": "kd_nM", "label": "(Legacy) KD", "type": "number", "required": False, "units": "nM"},
                {"key": "kon", "label": "(Legacy) kon", "type": "number", "required": False, "units": "1/M·s"},
                {"key": "koff", "label": "(Legacy) koff", "type": "number", "required": False, "units": "1/s"},
            ],
        },
        "BLI": {
            "params_fields": [
                {"key": "analyte_name", "label": "Analyte", "type": "text", "required": False},
                {"key": "analyte_type", "label": "Analyte type", "type": "select", "required": False, "options": ["protein", "cells", "other"]},
                {"key": "ligand_or_capture", "label": "Ligand / capture", "type": "text", "required": False},
                {"key": "buffer", "label": "Buffer", "type": "text", "required": False},
                {"key": "assay_temperature_c", "label": "Temperature", "type": "number", "required": False, "units": "°C"},
                {"key": "replicates_n", "label": "Replicates", "type": "number", "required": False},
                {"key": "chip_or_sensor", "label": "Sensor", "type": "text", "required": False},
                {"key": "capture_strategy", "label": "Capture strategy", "type": "text", "required": False},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
            "results_fields": [
                {"key": "kd", "label": "KD", "type": "number", "required": False, "units": "nM"},
                {"key": "ka", "label": "ka", "type": "number", "required": False, "units": "1/M·s"},
                {"key": "kdiss", "label": "kdiss", "type": "number", "required": False, "units": "1/s"},
                {"key": "fit_model", "label": "Fit model", "type": "select", "required": False, "options": ["1to1", "heterogeneous", "bivalent", "steady_state", "other"]},
                {"key": "binding_confirmed", "label": "Binding confirmed", "type": "select", "required": False, "options": ["no", "yes"]},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
                # legacy keys
                {"key": "kd_nM", "label": "(Legacy) KD", "type": "number", "required": False, "units": "nM"},
                {"key": "kon", "label": "(Legacy) kon", "type": "number", "required": False, "units": "1/M·s"},
                {"key": "koff", "label": "(Legacy) koff", "type": "number", "required": False, "units": "1/s"},
            ],
        },
        "ELISA": {
            "params_fields": [
                {"key": "analyte_name", "label": "Analyte", "type": "text", "required": False},
                {"key": "analyte_type", "label": "Analyte type", "type": "select", "required": False, "options": ["protein", "cells", "other"]},
                {"key": "ligand_or_capture", "label": "Coating / capture", "type": "text", "required": False},
                {"key": "buffer", "label": "Buffer", "type": "text", "required": False},
                {"key": "assay_temperature_c", "label": "Temperature", "type": "number", "required": False, "units": "°C"},
                {"key": "replicates_n", "label": "Replicates", "type": "number", "required": False},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
            "results_fields": [
                {"key": "ec50", "label": "EC50", "type": "number", "required": False, "units": "nM"},
                {"key": "signal", "label": "Signal (e.g., OD450)", "type": "number", "required": False},
                {"key": "signal_units", "label": "Signal units", "type": "text", "required": False},
                {"key": "curve_fit", "label": "Curve fit", "type": "select", "required": False, "options": ["4PL", "5PL", "none", "other"]},
                {"key": "binding_confirmed", "label": "Binding confirmed", "type": "select", "required": False, "options": ["no", "yes"]},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
            ],
        },
        "FLOW_BINDING": {
            "params_fields": [
                {"key": "analyte_name", "label": "Analyte", "type": "text", "required": False},
                {"key": "analyte_type", "label": "Analyte type", "type": "select", "required": False, "options": ["cells", "other"]},
                {"key": "ligand_or_capture", "label": "Stain / reagent", "type": "text", "required": False},
                {"key": "buffer", "label": "Buffer", "type": "text", "required": False},
                {"key": "assay_temperature_c", "label": "Temperature", "type": "number", "required": False, "units": "°C"},
                {"key": "replicates_n", "label": "Replicates", "type": "number", "required": False},
                {"key": "gate_strategy", "label": "Gate strategy", "type": "text", "required": False},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
            "results_fields": [
                {"key": "ec50", "label": "EC50", "type": "number", "required": False, "units": "nM"},
                {"key": "mfi_shift", "label": "MFI shift", "type": "number", "required": False},
                {"key": "percent_positive", "label": "% positive", "type": "number", "required": False, "units": "%"},
                {"key": "binding_confirmed", "label": "Binding confirmed", "type": "select", "required": False, "options": ["no", "yes"]},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
            ],
        },
    },
    "CELL_ASSAY": {
        "REPORTER": {
            "params_fields": [
                {"key": "cell_system", "label": "Cell system", "type": "text", "required": False},
                {"key": "stimulus", "label": "Stimulus", "type": "text", "required": False},
                {"key": "incubation_time_h", "label": "Incubation time", "type": "number", "required": False, "units": "h"},
                {"key": "plate_format", "label": "Plate format", "type": "select", "required": False, "options": ["96", "384", "other"]},
                {"key": "replicates_n", "label": "Replicates", "type": "number", "required": False},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
            "results_fields": [
                {"key": "ec50", "label": "EC50", "type": "number", "required": False, "units": "nM"},
                {"key": "max_effect", "label": "Max effect", "type": "number", "required": False, "units": "%"},
                {"key": "auc", "label": "AUC", "type": "number", "required": False},
                {"key": "effect_direction", "label": "Effect direction", "type": "select", "required": False, "options": ["agonism", "antagonism", "neutral", "other"]},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
                # legacy keys
                {"key": "ec50_nM", "label": "(Legacy) EC50", "type": "number", "required": False, "units": "nM"},
                {"key": "ic50_nM", "label": "(Legacy) IC50", "type": "number", "required": False, "units": "nM"},
            ],
        },
        "PHOSPHO_FLOW": {
            "params_fields": [
                {"key": "cell_system", "label": "Cell system", "type": "text", "required": False},
                {"key": "stimulus", "label": "Stimulus", "type": "text", "required": False},
                {"key": "incubation_time_h", "label": "Incubation time", "type": "number", "required": False, "units": "h"},
                {"key": "marker", "label": "Marker", "type": "text", "required": False},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
            "results_fields": [
                {"key": "delta_mfi", "label": "Δ MFI", "type": "number", "required": False},
                {"key": "percent_pos", "label": "% positive", "type": "number", "required": False, "units": "%"},
                {"key": "effect_direction", "label": "Effect direction", "type": "select", "required": False, "options": ["agonism", "antagonism", "neutral", "other"]},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
            ],
        },
        "CYTOKINE": {
            "params_fields": [
                {"key": "cell_system", "label": "Cell system", "type": "text", "required": False},
                {"key": "stimulus", "label": "Stimulus", "type": "text", "required": False},
                {"key": "incubation_time_h", "label": "Incubation time", "type": "number", "required": False, "units": "h"},
                {"key": "analyte", "label": "Analyte", "type": "text", "required": False},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
            "results_fields": [
                {"key": "delta_pg_ml", "label": "Δ", "type": "number", "required": False, "units": "pg/mL"},
                {"key": "fold_change", "label": "Fold change", "type": "number", "required": False},
                {"key": "effect_direction", "label": "Effect direction", "type": "select", "required": False, "options": ["agonism", "antagonism", "neutral", "other"]},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
            ],
        },
        "KILLING": {
            "params_fields": [
                {"key": "cell_system", "label": "Cell system", "type": "text", "required": False},
                {"key": "effector_cells", "label": "Effector cells", "type": "text", "required": False},
                {"key": "target_cells", "label": "Target cells", "type": "text", "required": False},
                {"key": "timepoint_h", "label": "Timepoint", "type": "number", "required": False, "units": "h"},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
            "results_fields": [
                {"key": "percent_killing", "label": "% killing", "type": "number", "required": False, "units": "%"},
                {"key": "ec50", "label": "EC50", "type": "number", "required": False, "units": "nM"},
                {"key": "effect_direction", "label": "Effect direction", "type": "select", "required": False, "options": ["agonism", "antagonism", "neutral", "other"]},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
            ],
        },
        "PROLIFERATION": {
            "params_fields": [
                {"key": "cell_system", "label": "Cell system", "type": "text", "required": False},
                {"key": "timepoint_h", "label": "Timepoint", "type": "number", "required": False, "units": "h"},
                {"key": "notes", "label": "Notes", "type": "textarea", "required": False},
            ],
            "results_fields": [
                {"key": "percent_proliferation", "label": "% proliferation", "type": "number", "required": False, "units": "%"},
                {"key": "division_index", "label": "Division index", "type": "number", "required": False},
                {"key": "effect_direction", "label": "Effect direction", "type": "select", "required": False, "options": ["agonism", "antagonism", "neutral", "other"]},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
                # legacy keys
                {"key": "inhibition_pct", "label": "(Legacy) Inhibition", "type": "number", "required": False, "units": "%"},
            ],
        },
    },
    "IN_VIVO_EFFICACY": {
        "NOD": {
            "params_fields": [
                {"key": "model", "label": "Model", "type": "text", "required": False},
                {"key": "sex", "label": "Sex", "type": "select", "required": False, "options": ["M", "F", "mixed"]},
                {"key": "age_weeks_start", "label": "Age at start", "type": "number", "required": False, "units": "weeks"},
                {"key": "n_per_group", "label": "N per group", "type": "number", "required": False},
                {"key": "dose_mg_kg", "label": "Dose", "type": "number", "required": False, "units": "mg/kg"},
                {"key": "route", "label": "Route", "type": "select", "required": False, "options": ["IV", "IP", "SC", "PO", "other"]},
                {"key": "schedule", "label": "Schedule", "type": "text", "required": False},
                {"key": "duration_days", "label": "Duration", "type": "number", "required": False, "units": "days"},
                {"key": "vehicle", "label": "Vehicle", "type": "text", "required": False},
                {"key": "randomization", "label": "Randomization", "type": "select", "required": False, "options": ["no", "yes"]},
                {"key": "blinding", "label": "Blinding", "type": "select", "required": False, "options": ["no", "yes"]},
                {"key": "endpoint_primary", "label": "Primary endpoint", "type": "text", "required": False},
                {"key": "endpoint_secondary", "label": "Secondary endpoints", "type": "text", "required": False},
                {"key": "cro_or_site", "label": "CRO / site", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "primary_outcome_value", "label": "Primary outcome", "type": "number", "required": False},
                {"key": "primary_outcome_units", "label": "Units", "type": "text", "required": False},
                {"key": "effect_size", "label": "Effect size", "type": "number", "required": False},
                {"key": "hazard_ratio", "label": "Hazard ratio", "type": "number", "required": False},
                {"key": "p_value", "label": "p-value", "type": "number", "required": False},
                {"key": "survival_median_days", "label": "Median survival", "type": "number", "required": False, "units": "days"},
                {"key": "responders_n", "label": "Responders", "type": "number", "required": False},
                {"key": "notes_interpretation", "label": "Interpretation", "type": "textarea", "required": False},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
                # legacy keys
                {"key": "endpoint", "label": "(Legacy) Primary endpoint", "type": "text", "required": False},
            ],
        },
        "OTHER_MOUSE": {
            "params_fields": [
                {"key": "model", "label": "Model", "type": "text", "required": False},
                {"key": "sex", "label": "Sex", "type": "select", "required": False, "options": ["M", "F", "mixed"]},
                {"key": "age_weeks_start", "label": "Age at start", "type": "number", "required": False, "units": "weeks"},
                {"key": "n_per_group", "label": "N per group", "type": "number", "required": False},
                {"key": "dose_mg_kg", "label": "Dose", "type": "number", "required": False, "units": "mg/kg"},
                {"key": "route", "label": "Route", "type": "select", "required": False, "options": ["IV", "IP", "SC", "PO", "other"]},
                {"key": "schedule", "label": "Schedule", "type": "text", "required": False},
                {"key": "duration_days", "label": "Duration", "type": "number", "required": False, "units": "days"},
                {"key": "vehicle", "label": "Vehicle", "type": "text", "required": False},
                {"key": "endpoint_primary", "label": "Primary endpoint", "type": "text", "required": False},
                {"key": "cro_or_site", "label": "CRO / site", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "primary_outcome_value", "label": "Primary outcome", "type": "number", "required": False},
                {"key": "primary_outcome_units", "label": "Units", "type": "text", "required": False},
                {"key": "notes_interpretation", "label": "Interpretation", "type": "textarea", "required": False},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
            ],
        },
    },
    "PK_PD": {
        "NONCOMPARTMENTAL": {
            "params_fields": [
                {"key": "species", "label": "Species", "type": "text", "required": False},
                {"key": "strain", "label": "Strain", "type": "text", "required": False},
                {"key": "matrix", "label": "Matrix", "type": "select", "required": False, "options": ["plasma", "serum", "whole_blood", "tissue", "other"]},
                {"key": "n", "label": "N", "type": "number", "required": False},
                {"key": "dose_mg_kg", "label": "Dose", "type": "number", "required": False, "units": "mg/kg"},
                {"key": "route", "label": "Route", "type": "select", "required": False, "options": ["IV", "IP", "SC", "PO", "other"]},
                {"key": "sampling_schedule", "label": "Sampling schedule", "type": "text", "required": False},
                {"key": "bioanalytical_method", "label": "Bioanalytical method", "type": "text", "required": False},
                {"key": "lod_loq", "label": "LOD/LOQ", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "cmax", "label": "Cmax", "type": "number", "required": False},
                {"key": "cmax_units", "label": "Cmax units", "type": "text", "required": False},
                {"key": "tmax_h", "label": "Tmax", "type": "number", "required": False, "units": "h"},
                {"key": "auc", "label": "AUC", "type": "number", "required": False},
                {"key": "auc_units", "label": "AUC units", "type": "text", "required": False},
                {"key": "half_life_h", "label": "Half-life", "type": "number", "required": False, "units": "h"},
                {"key": "clearance", "label": "Clearance", "type": "number", "required": False},
                {"key": "clearance_units", "label": "Clearance units", "type": "text", "required": False},
                {"key": "vd", "label": "Vd", "type": "number", "required": False},
                {"key": "vd_units", "label": "Vd units", "type": "text", "required": False},
                {"key": "pd_marker", "label": "PD marker", "type": "text", "required": False},
                {"key": "pd_effect", "label": "PD effect", "type": "text", "required": False},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
            ],
        },
        "COMPARTMENTAL": {
            "params_fields": [
                {"key": "species", "label": "Species", "type": "text", "required": False},
                {"key": "strain", "label": "Strain", "type": "text", "required": False},
                {"key": "matrix", "label": "Matrix", "type": "select", "required": False, "options": ["plasma", "serum", "whole_blood", "tissue", "other"]},
                {"key": "n", "label": "N", "type": "number", "required": False},
                {"key": "dose_mg_kg", "label": "Dose", "type": "number", "required": False, "units": "mg/kg"},
                {"key": "route", "label": "Route", "type": "select", "required": False, "options": ["IV", "IP", "SC", "PO", "other"]},
                {"key": "sampling_schedule", "label": "Sampling schedule", "type": "text", "required": False},
                {"key": "bioanalytical_method", "label": "Bioanalytical method", "type": "text", "required": False},
                {"key": "lod_loq", "label": "LOD/LOQ", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "cmax", "label": "Cmax", "type": "number", "required": False},
                {"key": "cmax_units", "label": "Cmax units", "type": "text", "required": False},
                {"key": "tmax_h", "label": "Tmax", "type": "number", "required": False, "units": "h"},
                {"key": "auc", "label": "AUC", "type": "number", "required": False},
                {"key": "auc_units", "label": "AUC units", "type": "text", "required": False},
                {"key": "half_life_h", "label": "Half-life", "type": "number", "required": False, "units": "h"},
                {"key": "clearance", "label": "Clearance", "type": "number", "required": False},
                {"key": "clearance_units", "label": "Clearance units", "type": "text", "required": False},
                {"key": "vd", "label": "Vd", "type": "number", "required": False},
                {"key": "vd_units", "label": "Vd units", "type": "text", "required": False},
                {"key": "pd_marker", "label": "PD marker", "type": "text", "required": False},
                {"key": "pd_effect", "label": "PD effect", "type": "text", "required": False},
                {"key": "conclusion", "label": "Conclusion", "type": "select", "required": False, "options": ["pass", "borderline", "fail"]},
            ],
        },
    },

    # COMPUTE
    "IN_SILICO": {
        "DEVELOPABILITY_SCORE": {
            "params_fields": [
                {"key": "tool_name", "label": "Tool name", "type": "text", "required": False},
                {"key": "tool_version", "label": "Tool version", "type": "text", "required": False},
                {"key": "input_description", "label": "Input description", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "score", "label": "Score", "type": "number", "required": False},
                {"key": "units", "label": "Units", "type": "text", "required": False},
                {"key": "interpretation", "label": "Interpretation", "type": "textarea", "required": False},
            ],
        },
        "EPITOPE_PREDICTION": {
            "params_fields": [
                {"key": "tool_name", "label": "Tool name", "type": "text", "required": False},
                {"key": "tool_version", "label": "Tool version", "type": "text", "required": False},
                {"key": "input_description", "label": "Input description", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "score", "label": "Score", "type": "number", "required": False},
                {"key": "units", "label": "Units", "type": "text", "required": False},
                {"key": "interpretation", "label": "Interpretation", "type": "textarea", "required": False},
            ],
        },
        "STRUCTURE_MODEL": {
            "params_fields": [
                {"key": "tool_name", "label": "Tool name", "type": "text", "required": False},
                {"key": "tool_version", "label": "Tool version", "type": "text", "required": False},
                {"key": "input_description", "label": "Input description", "type": "text", "required": False},
            ],
            "results_fields": [
                {"key": "score", "label": "Score", "type": "number", "required": False},
                {"key": "units", "label": "Units", "type": "text", "required": False},
                {"key": "interpretation", "label": "Interpretation", "type": "textarea", "required": False},
            ],
        },
    },
}


# -----------------------------
# Legacy schemas kept for editability (do not use for new records)
# -----------------------------
LEGACY_DATA_SCHEMAS: Dict[str, Dict[str, Dict[str, Any]]] = {
    # prior versions
    "Binding": {
        "SPR": DATA_SCHEMAS["BINDING"]["SPR"],
        "BLI": DATA_SCHEMAS["BINDING"]["BLI"],
    },
    "CellAssay": {
        "Reporter": DATA_SCHEMAS["CELL_ASSAY"]["REPORTER"],
        "Proliferation": DATA_SCHEMAS["CELL_ASSAY"]["PROLIFERATION"],
    },
    "InVivo": {
        "NOD": DATA_SCHEMAS["IN_VIVO_EFFICACY"]["NOD"],
        "OtherMouse": DATA_SCHEMAS["IN_VIVO_EFFICACY"]["OTHER_MOUSE"],
    },
    "CMC_Analytics": {
        "SEC": DATA_SCHEMAS["SEC"]["SEC"],
        "SEC_HPLC": DATA_SCHEMAS["SEC"]["SEC"],
        "Endotoxin": DATA_SCHEMAS["ENDOTOXIN"]["LAL"],
        "DLS": DATA_SCHEMAS["DLS"]["DLS"],
    },
    "Execution": {
        "Quote": DATA_SCHEMAS["COST"]["QUOTE"],
        "Protocol": DATA_SCHEMAS["WORK_ORDER"]["CRO_WORK_ORDER"],
        # RiskNote intentionally left as a legacy-only schema so old records remain editable
        "RiskNote": {
            "params_fields": [
                {"key": "category", "label": "Category", "type": "select", "required": False, "options": ["Safety", "Bio", "CMC", "Ops"]},
            ],
            "results_fields": [
                {"key": "severity", "label": "Severity", "type": "select", "required": False, "options": ["Low", "Medium", "High"]},
                {"key": "mitigation", "label": "Mitigation", "type": "text", "required": False},
            ],
        },
    },
}


# -----------------------------
# Aliases for safe normalization
# -----------------------------
DATA_TYPE_ALIASES: Dict[str, str] = {
    "Binding": "BINDING",
    "CellAssay": "CELL_ASSAY",
    "InVivo": "IN_VIVO_EFFICACY",
    "SEC": "SEC",
    "CMC_Analytics": "CMC_Analytics",  # handled specially
    "Execution": "Execution",  # handled specially
    # passthrough
    "BINDING": "BINDING",
    "CELL_ASSAY": "CELL_ASSAY",
    "IN_VIVO_EFFICACY": "IN_VIVO_EFFICACY",
    "PK_PD": "PK_PD",
    "SEC": "SEC",
    "PURITY": "PURITY",
    "IDENTITY": "IDENTITY",
    "ENDOTOXIN": "ENDOTOXIN",
    "DLS": "DLS",
    "STABILITY": "STABILITY",
    "WORK_ORDER": "WORK_ORDER",
    "COST": "COST",
    "EXPRESSION": "EXPRESSION",
    "PURIFICATION_RUN": "PURIFICATION_RUN",
    "IN_SILICO": "IN_SILICO",
}

METHOD_ALIASES: Dict[str, str] = {
    # legacy -> canonical
    "Reporter": "REPORTER",
    "Proliferation": "PROLIFERATION",
    "OtherMouse": "OTHER_MOUSE",
    "SEC_HPLC": "SEC",
    "SEC": "SEC",
    "Quote": "QUOTE",
    "Protocol": "CRO_WORK_ORDER",
    # passthrough canonical
    "SPR": "SPR",
    "BLI": "BLI",
    "ELISA": "ELISA",
    "FLOW_BINDING": "FLOW_BINDING",
    "REPORTER": "REPORTER",
    "PHOSPHO_FLOW": "PHOSPHO_FLOW",
    "CYTOKINE": "CYTOKINE",
    "KILLING": "KILLING",
    "PROLIFERATION": "PROLIFERATION",
    "NOD": "NOD",
    "OTHER_MOUSE": "OTHER_MOUSE",
    "NONCOMPARTMENTAL": "NONCOMPARTMENTAL",
    "COMPARTMENTAL": "COMPARTMENTAL",
    "TRANSIENT_HEK": "TRANSIENT_HEK",
    "STABLE_CHO": "STABLE_CHO",
    "OTHER": "OTHER",
    "PROA": "PROA",
    "PROG": "PROG",
    "PROL": "PROL",
    "IEX": "IEX",
    "HIC": "HIC",
    "SEC_POLISH": "SEC_POLISH",
    "CE_SDS": "CE_SDS",
    "RP_HPLC": "RP_HPLC",
    "SDS_PAGE": "SDS_PAGE",
    "LCMS_INTACT": "LCMS_INTACT",
    "PEPTIDE_MAP": "PEPTIDE_MAP",
    "LAL": "LAL",
    "ENDOSAFE": "ENDOSAFE",
    "DLS": "DLS",
    "REAL_TIME": "REAL_TIME",
    "ACCELERATED": "ACCELERATED",
    "FREEZE_THAW": "FREEZE_THAW",
    "CRO_WORK_ORDER": "CRO_WORK_ORDER",
    "QUOTE": "QUOTE",
    "INVOICE": "INVOICE",
    "DEVELOPABILITY_SCORE": "DEVELOPABILITY_SCORE",
    "EPITOPE_PREDICTION": "EPITOPE_PREDICTION",
    "STRUCTURE_MODEL": "STRUCTURE_MODEL",
}


def normalize_domain(raw_domain: Optional[str]) -> Optional[str]:
    if raw_domain is None:
        return None
    return DOMAIN_ALIASES.get(raw_domain, raw_domain)


def normalize_data_type_method(raw_data_type: Optional[str], raw_method: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Normalize legacy (data_type, method) to canonical keys when safe.

    Returns (data_type_key, method_key). If mapping is unsafe/unknown, returns inputs unchanged.
    """
    if raw_data_type is None:
        return None, None
    dt = raw_data_type
    m = raw_method

    # handle special legacy buckets
    if dt == "CMC_Analytics":
        if m in ("SEC", "SEC_HPLC"):
            return "SEC", "SEC"
        if m == "DLS":
            return "DLS", "DLS"
        if m == "Endotoxin":
            return "ENDOTOXIN", "LAL"
        # unknown -> leave legacy
        return dt, m
    if dt == "Execution":
        if m == "Quote":
            return "COST", "QUOTE"
        if m == "Protocol":
            return "WORK_ORDER", "CRO_WORK_ORDER"
        if m == "RiskNote":
            # keep legacy; schema exists only in legacy bucket
            return dt, m
        return dt, m

    # general mapping
    dt_key = DATA_TYPE_ALIASES.get(dt, dt)
    m_key = METHOD_ALIASES.get(m, m) if m else m

    # if canonical schema exists for dt_key/m_key, use it, otherwise keep original
    if dt_key in DATA_SCHEMAS and m_key in (DATA_SCHEMAS.get(dt_key) or {}):
        return dt_key, m_key

    return dt, m


def get_schema(data_type: str, method: str) -> Optional[Dict[str, Any]]:
    """Fetch schema for a given data_type/method, supporting canonical + legacy."""
    if data_type in DATA_SCHEMAS and method in (DATA_SCHEMAS.get(data_type) or {}):
        return DATA_SCHEMAS[data_type][method]
    if data_type in LEGACY_DATA_SCHEMAS and method in (LEGACY_DATA_SCHEMAS.get(data_type) or {}):
        return LEGACY_DATA_SCHEMAS[data_type][method]
    return None


def normalize_data_record_for_storage(domain: str, data_type: str, method: str) -> Tuple[str, str, str]:
    """Normalize values for storage on create/update.

    We normalize data_type/method when safe. Domain is normalized only if the data_type/method
    normalized into the canonical catalogue (i.e., not left as legacy buckets).
    """
    dt_norm, m_norm = normalize_data_type_method(data_type, method)
    # if mapping produced canonical catalogue key, normalize domain too
    if dt_norm in DATA_TYPE_META:
        dom_norm = normalize_domain(domain) or domain
        return dom_norm, dt_norm, m_norm or method
    return domain, dt_norm or data_type, m_norm or method


# -----------------------------
# Evidence type -> allowed data sources
# Evidence types are currently defined in rules YAML (psirules-0.1.0.yml)
# -----------------------------
EVIDENCE_TO_DATA_SOURCES: Dict[str, List[Dict[str, Any]]] = {
    "Binding_Affinity": [{"data_type": "BINDING", "methods": ["SPR", "BLI", "ELISA", "FLOW_BINDING"]}],
    "InVitro_Potency": [{"data_type": "CELL_ASSAY", "methods": ["REPORTER", "PROLIFERATION", "KILLING", "PHOSPHO_FLOW", "CYTOKINE"]}],
    "InVivo_Efficacy": [{"data_type": "IN_VIVO_EFFICACY", "methods": ["NOD", "OTHER_MOUSE"]}],
    "Purity_SEC": [{"data_type": "SEC", "methods": ["SEC"]}],
    "Aggregation_HMW": [{"data_type": "SEC", "methods": ["SEC"]}, {"data_type": "DLS", "methods": ["DLS"]}],
    "CRO_Quote": [{"data_type": "COST", "methods": ["QUOTE", "INVOICE"]}],
    "Study_Protocol": [{"data_type": "WORK_ORDER", "methods": ["CRO_WORK_ORDER"]}],
    # legacy safety red flag commonly cites the old Execution/RiskNote record
    "Safety_RedFlag": [{"data_type": "Execution", "methods": ["RiskNote"]}],
}


def get_allowed_data_sources_for_evidence(evidence_type: str) -> Dict[str, Any]:
    """Return allowed (data_type, method) pairs for a given evidence_type.

    Returned shape is stable for template/JS consumption.
    Includes canonical pairs, plus any explicit legacy pairs.
    """
    allowed = EVIDENCE_TO_DATA_SOURCES.get(evidence_type) or []
    out: List[Dict[str, str]] = []
    for item in allowed:
        dt = item.get("data_type")
        for m in (item.get("methods") or []):
            out.append({"data_type": dt, "method": m})
    return {"evidence_type": evidence_type, "allowed": out}


# -----------------------------
# Batch requirement sets (legacy compatibility)
# -----------------------------
DATA_TYPES_REQUIRING_BATCH = sorted([k for k, v in DATA_TYPE_META.items() if v.get("scope") == "batch"])
PROGRAM_LEVEL_DATA_TYPES = sorted([k for k, v in DATA_TYPE_META.items() if v.get("scope") != "batch"])

# legacy sets for older code paths
LEGACY_DATA_TYPES_REQUIRING_BATCH = {"Binding", "CellAssay", "InVivo", "CMC_Analytics"}
LEGACY_PROGRAM_LEVEL_DATA_TYPES = {"Execution"}


REGISTRY: Dict[str, Any] = {
    "version": "v1.1.7",
    "domains_ordered": DOMAINS_ORDERED,
    "domain_labels": DOMAIN_LABELS,
    "domain_aliases": DOMAIN_ALIASES,
    "data_type_meta": {
        k: {
            **v,
            "requires_batch": _requires_batch(k),
        }
        for k, v in DATA_TYPE_META.items()
    },
    "data_types_by_domain": DATA_TYPES_BY_DOMAIN,
    "evidence_to_data_sources": EVIDENCE_TO_DATA_SOURCES,
    "data_schemas": DATA_SCHEMAS,
    "legacy_data_schemas": LEGACY_DATA_SCHEMAS,
    "data_types_requiring_batch": DATA_TYPES_REQUIRING_BATCH,
    "program_level_data_types": PROGRAM_LEVEL_DATA_TYPES,
    "legacy_data_types_requiring_batch": sorted(LEGACY_DATA_TYPES_REQUIRING_BATCH),
    "legacy_program_level_data_types": sorted(LEGACY_PROGRAM_LEVEL_DATA_TYPES),
}
