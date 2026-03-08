from __future__ import annotations

from psi.services.trajectory import predict_readiness_shift


def test_readiness_shift_single_gate_improvement_not_enough_when_others_fail() -> None:
    out = predict_readiness_shift(
        [
            {"gate_key": "binding_gate", "gate_before": "fail_or_hold", "gate_after": "pass", "delta": "improved"},
        ],
        [{"metric_key": "kd_nM", "simulated_value": 1.0}],
        readiness_before="not_ready",
        required_gate_keys=["binding_gate", "developability_gate"],
        failing_gate_keys_before=["binding_gate", "developability_gate"],
    )
    assert out["readiness_after"] == "not_ready"


def test_readiness_shift_stays_not_ready_when_multiple_gates_still_failing() -> None:
    out = predict_readiness_shift(
        [
            {"gate_key": "binding_gate", "gate_before": "fail_or_hold", "gate_after": "pass", "delta": "improved"},
            {"gate_key": "safety_gate", "gate_before": "fail_or_hold", "gate_after": "fail_or_hold", "delta": "none"},
        ],
        [{"metric_key": "kd_nM", "simulated_value": 1.0}],
        readiness_before="not_ready",
        required_gate_keys=["binding_gate", "safety_gate"],
        failing_gate_keys_before=["binding_gate", "safety_gate"],
    )
    assert out["readiness_after"] == "not_ready"


def test_readiness_shift_becomes_ready_when_all_required_gates_pass() -> None:
    out = predict_readiness_shift(
        [
            {"gate_key": "binding_gate", "gate_before": "fail_or_hold", "gate_after": "pass", "delta": "improved"},
            {"gate_key": "developability_gate", "gate_before": "fail_or_hold", "gate_after": "pass", "delta": "improved"},
        ],
        [{"metric_key": "kd_nM", "simulated_value": 1.0}],
        readiness_before="not_ready",
        required_gate_keys=["binding_gate", "developability_gate"],
        failing_gate_keys_before=["binding_gate", "developability_gate"],
    )
    assert out["readiness_after"] == "ready"
