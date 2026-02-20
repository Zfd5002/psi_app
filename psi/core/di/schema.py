from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class DIInput:
    decision_key: str
    scope_type: str  # "batch" only in v0.1
    scope_id: int    # batch db id
    as_of_ts: Optional[str] = None
    qc_mode: str = "model_safe"  # strict/model_safe/none
    context: Dict[str, Any] = field(default_factory=dict)  # store-only in v0.1


@dataclass
class EvidenceRef:
    measurement_id: int
    data_record_id: int
    metric_key: str
    metric_key_source: str  # "canonical" or "alias:<key>"
    value_num: Optional[float] = None
    value_text: Optional[str] = None
    value_bool: Optional[bool] = None
    unit: Optional[str] = None
    comparator: Optional[str] = None
    qc_status: str = "unknown"  # approved/unreviewed/rejected/quarantined/unknown
    qc_flag_raw: Optional[str] = None
    qc_source: str = "unknown"  # measurement_qc | qc_flag_fallback | unknown
    is_primary: bool = False
    is_outlier: bool = False
    produced_at: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class IgnoredEvidence:
    measurement_id: int
    data_record_id: int
    metric_key: str
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GateResult:
    gate_key: str
    status: str  # pass/fail
    rationale: str
    evidence_refs: List[EvidenceRef] = field(default_factory=list)


@dataclass
class DIOutput:
    decision_state: str  # ready/not_ready/cannot_assess
    policy: Dict[str, Any]
    provenance: Dict[str, Any]
    state_of_evidence: Dict[str, Any]
    gates: List[GateResult]
    blockers: List[Dict[str, Any]]
    risk_flags: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
