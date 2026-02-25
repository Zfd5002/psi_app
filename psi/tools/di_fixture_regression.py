from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from psi.core.di.policy import load_policy
from psi.core.di.schema import DIInput, EvidenceRef
from psi.services.di.nbe import build_experiment_suggestions
from psi.services.di.runner import compute_di_output
from psi.services.di.templates.advance_to_in_vivo import evaluate as eval_advance
from psi.services.di.templates.ready_for_scaleup_screen import evaluate as eval_scaleup


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _ev(metric_key: str, measurement_id: int, *, value_num: float | None = None, value_text: str | None = None) -> EvidenceRef:
    return EvidenceRef(
        measurement_id=int(measurement_id),
        data_record_id=int(measurement_id),
        metric_key=str(metric_key),
        metric_key_source="canonical",
        value_num=value_num,
        value_text=value_text,
    )


def _policy(name: str):
    return load_policy(Path(__file__).resolve().parents[1] / "core" / "di" / "policies" / name)


def _gate_keys(out: Dict[str, Any]) -> List[str]:
    gates = out.get("gates") or []
    return [str(getattr(g, "gate_key", "") or g.get("gate_key") or "") for g in gates]


def _blocker_keys(out: Dict[str, Any]) -> List[str]:
    return [str((b or {}).get("blocker_key") or "") for b in (out.get("blockers") or []) if isinstance(b, dict)]


def _risk_keys(out: Dict[str, Any]) -> List[str]:
    keys: List[str] = []
    for r in (out.get("risk_flags") or []):
        if not isinstance(r, dict):
            continue
        keys.append(str(r.get("risk_key") or r.get("risk_flag") or r.get("key") or ""))
    return keys


def _stub_policy(*, schema_version: str, template_key: str, name: str = "stub", version: str = "v0.test") -> Any:
    return SimpleNamespace(
        policy_id="stub.policy",
        name=name,
        version=version,
        schema_version=schema_version,
        policy_semantics_hash="0" * 64,
        policy_package_hash="1" * 64,
        source_name="fixture_stub.json",
        policy_body={},
        policy_body_canonical_json="{}",
        changelog=[],
        template_key=template_key,
    )


def case_advance_empty_deterministic() -> None:
    pol = _policy("advance_to_in_vivo_v0_4.json")
    out1 = eval_advance(used_by_metric={}, policy=pol.policy_body, context={}, metric_evaluations={}, enforce_value_functions=False)
    out2 = eval_advance(used_by_metric={}, policy=pol.policy_body, context={}, metric_evaluations={}, enforce_value_functions=False)
    _assert(out1.get("decision_state") == "not_ready", "advance empty decision_state must be not_ready")
    _assert(_gate_keys(out1) == _gate_keys(out2), "advance empty gates order must be deterministic")
    _assert(_blocker_keys(out1) == _blocker_keys(out2), "advance empty blockers order must be deterministic")
    _assert(_risk_keys(out1) == _risk_keys(out2), "advance empty risk_flags order must be deterministic")


def case_advance_minimal_functional_deterministic() -> None:
    pol = _policy("advance_to_in_vivo_v0_4.json")
    used = {
        "conclusion": _ev("conclusion", 10, value_text="binding observed"),
        "percent_killing": _ev("percent_killing", 11, value_num=75.0),
    }
    out1 = eval_advance(used_by_metric=used, policy=pol.policy_body, context={}, metric_evaluations={}, enforce_value_functions=False)
    out2 = eval_advance(used_by_metric=used, policy=pol.policy_body, context={}, metric_evaluations={}, enforce_value_functions=False)
    _assert(str(out1.get("decision_state") or ""), "advance minimal decision_state must be present")
    g1 = _gate_keys(out1)
    g2 = _gate_keys(out2)
    _assert(g1 == g2, "advance minimal gate order must be deterministic across reruns")
    _assert("G4_functional" in g1, "advance minimal fixture must include G4_functional")


def case_scaleup_empty_deterministic() -> None:
    pol = _policy("ready_for_scaleup_screen_v0_1.json")
    out1 = eval_scaleup(used_by_metric={}, policy=pol.policy_body, context={}, metric_evaluations={}, enforce_value_functions=False)
    out2 = eval_scaleup(used_by_metric={}, policy=pol.policy_body, context={}, metric_evaluations={}, enforce_value_functions=False)
    _assert(str(out1.get("decision_state") or ""), "scaleup decision_state must be present")
    _assert(_gate_keys(out1) == _gate_keys(out2), "scaleup gates order must be deterministic")
    _assert(_blocker_keys(out1) == _blocker_keys(out2), "scaleup blockers order must be deterministic")


def case_nbe_blocker_ordering() -> None:
    blockers = [
        {"blocker_key": "missing_required_metric", "detail": {"missing": ["percent_killing", "monomer_pct"]}},
        {"blocker_key": "threshold_violation", "detail": {"failed_metrics": ["hmw_pct"]}},
    ]
    sugg, rec = build_experiment_suggestions(
        blockers=blockers,
        risk_flags=[],
        catalog_id="experiment_catalog_v0_1",
        catalog_version="v0.1",
        allow_recommended_list=True,
    )
    _assert(isinstance(sugg, dict), "nbe suggestions must be dict")
    _assert(isinstance(rec, list), "nbe recommended must be list")
    sugg2, rec2 = build_experiment_suggestions(
        blockers=blockers,
        risk_flags=[],
        catalog_id="experiment_catalog_v0_1",
        catalog_version="v0.1",
        allow_recommended_list=True,
    )
    _assert(sugg == sugg2, "nbe blocker suggestions must be deterministic across reruns")
    _assert(rec == rec2, "nbe recommended list must be deterministic across reruns")


def case_nbe_risk_flag_triggering() -> None:
    sugg, rec = build_experiment_suggestions(
        blockers=[],
        risk_flags=[{"risk_flag": "aggregated_purity_interpretation_gap"}],
        catalog_id="experiment_catalog_v0_1",
        catalog_version="v0.1",
        allow_recommended_list=True,
    )
    sugg2, rec2 = build_experiment_suggestions(
        blockers=[],
        risk_flags=[{"risk_flag": "aggregated_purity_interpretation_gap"}],
        catalog_id="experiment_catalog_v0_1",
        catalog_version="v0.1",
        allow_recommended_list=True,
    )
    key = "risk_flag:aggregated_purity_interpretation_gap"
    _assert(key in sugg, "risk flag suggestion key must be present")
    _assert(sugg == sugg2, "risk flag suggestions must be deterministic across reruns")
    _assert(rec == rec2, "risk flag recommended list must be deterministic across reruns")
    rec_with_rf = [r for r in rec if isinstance(r, dict) and (r.get("triggered_by_risk_flags") or [])]
    _assert(rec_with_rf, "recommended experiments must include triggered_by_risk_flags entries")


def case_w61_value_functions_field_on_error_paths() -> None:
    di_in = DIInput(decision_key="advance_to_in_vivo", scope_type="batch", scope_id=1, qc_mode="model_safe", context={})

    mismatch_pol = _stub_policy(schema_version="di.policy_package.v9_9", template_key="advance_to_in_vivo.v0_1")
    mismatch = compute_di_output(None, di_input=di_in, pol=mismatch_pol)  # type: ignore[arg-type]
    mismatch_out = mismatch.get("output") or {}
    _assert("value_functions_enforced" in mismatch_out, "w61 field must exist on policy mismatch error output")
    _assert(mismatch_out.get("value_functions_enforced") is False, "w61 field must be false on policy mismatch error output")

    unsupported_pol = _stub_policy(schema_version="di.policy_package.v0_1", template_key="unknown.template")
    unsupported = compute_di_output(None, di_input=di_in, pol=unsupported_pol)  # type: ignore[arg-type]
    unsupported_out = unsupported.get("output") or {}
    _assert("value_functions_enforced" in unsupported_out, "w61 field must exist on unsupported-template error output")
    _assert(unsupported_out.get("value_functions_enforced") is False, "w61 field must be false on unsupported-template error output")
    for out in (mismatch_out, unsupported_out):
        if "drift_type" in out:
            _assert(isinstance(out.get("drift_type"), str), "drift_type must be string when present")
        if "state_transition" in out:
            _assert(isinstance(out.get("state_transition"), dict), "state_transition must be object when present")


def main() -> None:
    cases = [
        ("advance_empty_deterministic", case_advance_empty_deterministic),
        ("advance_minimal_functional_deterministic", case_advance_minimal_functional_deterministic),
        ("scaleup_empty_deterministic", case_scaleup_empty_deterministic),
        ("nbe_blocker_ordering", case_nbe_blocker_ordering),
        ("nbe_risk_flag_triggering", case_nbe_risk_flag_triggering),
        ("w61_value_functions_field_on_error_paths", case_w61_value_functions_field_on_error_paths),
    ]
    for name, fn in cases:
        fn()
        print(f"PASS {name}")
    print(f"di_fixture_regression OK cases={len(cases)}")


if __name__ == "__main__":
    main()
