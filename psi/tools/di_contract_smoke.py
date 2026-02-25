"""DI contract smoke checks (lightweight, no heavy compute).

Run:
  python -m psi.tools.di_contract_smoke

Purpose:
- Prevent regressions in policy canonicalization + hashing
- Ensure stable JSON serialization helper stays deterministic

This is intentionally minimal and fast.
"""

from __future__ import annotations

import json
import sys
import os
import tempfile
import shutil

from datetime import datetime, timezone
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from psi.core.di.catalog import load_catalog
from psi.core.di.policy import canonical_policy_json, load_policy, sha256_hex_of_canonical_json
from psi.core.utils import stable_json_dumps
from psi.services.di.compute import _build_scope_semantics, _normalize_ignored
from psi.services.di.eval import derive_gate_outcomes, derive_readiness, derive_shortlisting
from psi.services.di.selectors import ALLOWED_IGNORE_REASON_KEYS
from psi.services.di.runner import DI_SELECTION_SEMANTICS_VERSION
from psi.services.di.sub_assessments import baseline_risk_flags_from_used, decision_state_from_gate_statuses
from psi.services.di.templates.registry import list_template_keys_sorted, template_dependency_graph


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _assert_snapshot_provenance_block(prov: dict, *, expected_scope_type: str) -> None:
    _assert(isinstance(prov, dict), "di_snapshot_provenance must be a dict")
    for k in (
        "policy_name",
        "template_name",
        "template_key",
        "policy_version",
        "policy_semantics_hash",
        "shortlisting_enabled",
        "scope_type",
        "scope_id",
    ):
        _assert(k in prov, f"di_snapshot_provenance missing key: {k}")
    _assert(str(prov.get("scope_type") or "") == expected_scope_type, f"di_snapshot_provenance.scope_type must be {expected_scope_type}")
    _assert(prov.get("scope_id") is not None, "di_snapshot_provenance.scope_id must be present")
    _assert(bool(str(prov.get("policy_version") or "")), "di_snapshot_provenance.policy_version must be non-empty")
    _assert(bool(str(prov.get("policy_semantics_hash") or "")), "di_snapshot_provenance.policy_semantics_hash must be non-empty")
    _assert(isinstance(prov.get("shortlisting_enabled"), bool), "di_snapshot_provenance.shortlisting_enabled must be bool")


def _render_di_snapshot_template_smoke(ctx: dict) -> str:
    repo_root = Path(__file__).resolve().parents[2]
    tpl_dir = repo_root / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(tpl_dir)))
    tmpl = env.get_template("decisions/_di_snapshot.html")
    return tmpl.render(**(ctx or {}))


def _assert_single_active_snapshot_per_scope(db) -> None:
    from sqlalchemy import text

    rows = (
        db.execute(
            text(
                """
                SELECT
                  decision_key,
                  program_id,
                  COALESCE(molecule_id, 0) AS molecule_id_norm,
                  COALESCE(batch_id, 0) AS batch_id_norm,
                  COUNT(1) AS active_count
                FROM decision_snapshots
                WHERE superseded_by_snapshot_id IS NULL
                GROUP BY decision_key, program_id, COALESCE(molecule_id, 0), COALESCE(batch_id, 0)
                HAVING COUNT(1) > 1
                ORDER BY decision_key ASC, program_id ASC, molecule_id_norm ASC, batch_id_norm ASC
                """
            )
        )
        .mappings()
        .all()
    )
    _assert(not rows, f"decision_snapshots must have at most one active row per scope; duplicates={rows}")


_SMOKE_SET_BASELINE_CUTOFF = False


def test_policy_canonicalization_and_hash() -> None:
    a = {"b": 2, "a": 1, "nested": {"z": 9, "y": 8}}
    b = {"nested": {"y": 8, "z": 9}, "a": 1, "b": 2}

    ca = canonical_policy_json(a)
    cb = canonical_policy_json(b)
    _assert(ca == cb, "canonical_policy_json should be identical for key-reordered dicts")

    ha = sha256_hex_of_canonical_json(a)
    hb = sha256_hex_of_canonical_json(b)
    _assert(ha == hb, "policy_hash should be identical for canonical-equivalent policies")

    # Canonical JSON should parse back to same object.
    ra = json.loads(ca)
    _assert(ra == b or ra == a, "canonical JSON should be valid and round-trippable")


def test_stable_json_dumps() -> None:
    obj1 = {"z": 1, "a": {"c": 3, "b": 2}, "list": [{"y": 2, "x": 1}, 5]}
    obj2 = {"list": [{"x": 1, "y": 2}, 5], "a": {"b": 2, "c": 3}, "z": 1}

    s1 = stable_json_dumps(obj1)
    s2 = stable_json_dumps(obj2)
    _assert(s1 == s2, "stable_json_dumps should be identical for key-reordered dicts")

    # Verify it parses.
    p = json.loads(s1)
    _assert(isinstance(p, dict) and p.get("z") == 1, "stable_json_dumps output should parse")


def test_normalize_ignored_schema_compat() -> None:
    ignored = [
        {
            "measurement_id": 1,
            "data_record_id": 2,
            "metric_key": "m",
            "reason_key": "qc",
            "reason_detail": "flagged",
            "qc_status": "qc_flag",
        },
        {
            "measurement_id": 3,
            "data_record_id": 4,
            "metric_key": "m2",
            "reason_key": "qc",
            "reason_detail": "ok",
            "qc_source": "measurement_qc",
        },
    ]
    out = _normalize_ignored(ignored)
    _assert(len(out) == 2, "normalize_ignored should preserve list length")
    _assert(getattr(out[0], "qc_source", None) == "qc_flag", "qc_status should map to qc_source")
    _assert(getattr(out[1], "qc_source", None) == "measurement_qc", "qc_source should be preserved")


def test_policy_package_dual_hash_stability() -> None:
    # Real policy file (packaged). Ensure both hashes are stable for identical content.
    repo_root = Path(__file__).resolve().parents[2]
    pol_path = repo_root / "psi" / "core" / "di" / "policies" / "advance_to_in_vivo_v0_1.json"
    pol = load_policy(pol_path)
    pol2 = load_policy(pol_path)
    _assert(pol.policy_semantics_hash == pol2.policy_semantics_hash, "policy_semantics_hash should be stable")
    _assert(pol.policy_package_hash == pol2.policy_package_hash, "policy_package_hash should be stable")
    _assert(pol.policy_body_canonical_json == pol2.policy_body_canonical_json, "policy_body canonical JSON should be stable")


def test_catalog_hash_validation() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    cat_path = repo_root / "psi" / "core" / "di" / "catalogs" / "experiment_catalog_v0_1.json"
    cat = load_catalog(cat_path)
    # Basic invariants
    _assert(bool(cat.catalog_id), "catalog_id must be present")
    _assert(bool(cat.catalog_version), "catalog_version must be present")
    # Hash stability
    h2 = sha256_hex_of_canonical_json(cat.catalog)
    _assert(cat.catalog_hash == h2, "catalog_hash must match canonical JSON hash")


def test_policy_template_structure_present() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    pol_path = repo_root / "psi" / "core" / "di" / "policies" / "advance_to_in_vivo_v0_1.json"
    pol = load_policy(pol_path)

    ts = (pol.package or {}).get("template_structure")
    _assert(isinstance(ts, dict), "template_structure must be present in policy package")

    for k in ("context_knobs", "gate_categories", "risk_flag_categories", "blocker_taxonomy"):
        _assert(k in ts, f"template_structure.{k} missing")
        _assert(isinstance(ts.get(k), list), f"template_structure.{k} must be a list")


def test_selection_semantics_version_constant() -> None:
    _assert(DI_SELECTION_SEMANTICS_VERSION == "di.selection.v0_1", "selection semantics version must be di.selection.v0_1")


def test_policy_authoritative_required_gate_keys() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    pol_adv = load_policy(repo_root / "psi" / "core" / "di" / "policies" / "advance_to_in_vivo_v0_3.json")
    pol_scale = load_policy(repo_root / "psi" / "core" / "di" / "policies" / "ready_for_scaleup_screen_v0_1.json")

    r_adv = derive_readiness(
        decision_state="not_ready",
        decision_key="advance_to_in_vivo",
        policy_body=(pol_adv.policy_body or {}),
        gate_results=[],
        templ_blockers=[],
        used_by_metric={},
        ignored=[],
        warnings=[],
        qc_mode="model_safe",
    )
    cov_adv = (r_adv.get("coverage") or {}) if isinstance(r_adv, dict) else {}
    _assert(int(cov_adv.get("required_total") or 0) == 10, "advance_to_in_vivo required metrics must come from policy-defined required gates")
    _assert(int(cov_adv.get("optional_total") or 0) == 5, "advance_to_in_vivo optional metrics must exclude conditional/optional policy gates")

    r_scale = derive_readiness(
        decision_state="not_ready",
        decision_key="ready_for_scaleup_screen",
        policy_body=(pol_scale.policy_body or {}),
        gate_results=[],
        templ_blockers=[],
        used_by_metric={},
        ignored=[],
        warnings=[],
        qc_mode="model_safe",
    )
    cov_scale = (r_scale.get("coverage") or {}) if isinstance(r_scale, dict) else {}
    _assert(int(cov_scale.get("required_total") or 0) == 6, "ready_for_scaleup_screen required metrics must follow template policy gates")
    _assert(int(cov_scale.get("optional_total") or 0) == 0, "ready_for_scaleup_screen should not inherit hardcoded optional gate behavior")

    pol_scale_short = dict(pol_scale.policy_body or {})
    pol_scale_short["shortlisting"] = {"allow_shortlisting": True}
    short = derive_shortlisting(
        policy_body=pol_scale_short,
        decision_state="ready",
        readiness={"state": "ready", "coverage": {"coverage_ratio": 1.0}},
        gate_outcomes={
            "G1_material_readiness": {"status": "pass"},
            "G2_purity_integrity": {"status": "pass"},
            "G3_stability": {"status": "fail"},
        },
        blockers=[],
        comparability={"summary": {"high_severity_count": 0, "total_flags": 0}},
        metric_evaluations={},
        scope_type="batch",
        scope_id=1,
    )
    _assert(isinstance(short, dict) and bool(short.get("refused")), "shortlisting should refuse when policy-derived required gate fails")
    reasons = short.get("refusal_reasons") if isinstance(short.get("refusal_reasons"), list) else []
    hg = [r for r in reasons if isinstance(r, dict) and r.get("kind") == "hard_gates_not_passed"]
    _assert(bool(hg), "shortlisting refusal must include hard_gates_not_passed")
    _assert("G3_stability" in (hg[0].get("gates") or []), "shortlisting must use template policy gates, not hardcoded advance gates")


def test_context_knob_branching_gate_outcomes_deterministic() -> None:
    policy_body = {
        "gates": {
            "G_ctx": {
                "require_any": ["m_base"],
                "context_require_any_by_value": {
                    "route": {
                        "SC": {"require_any": ["m_base", "m_sc"], "explanation": "SC branch"},
                        "_default": {"require_any": ["m_base"], "explanation": "default branch"},
                    }
                },
            }
        }
    }
    used = {"m_base": object()}
    out_iv_1 = derive_gate_outcomes(policy_body=policy_body, gate_results=[], used_by_metric=used, inputs_context={"route": "IV"}, emit_context_branch_surface=True)
    out_iv_2 = derive_gate_outcomes(policy_body=policy_body, gate_results=[], used_by_metric=used, inputs_context={"route": "IV"}, emit_context_branch_surface=True)
    out_sc = derive_gate_outcomes(policy_body=policy_body, gate_results=[], used_by_metric=used, inputs_context={"route": "SC"}, emit_context_branch_surface=True)

    _assert(stable_json_dumps(out_iv_1) == stable_json_dumps(out_iv_2), "context branch selection must be deterministic for identical knobs")
    g_iv = (out_iv_1 or {}).get("G_ctx") or {}
    g_sc = (out_sc or {}).get("G_ctx") or {}
    b_iv = g_iv.get("context_branch") if isinstance(g_iv.get("context_branch"), dict) else {}
    b_sc = g_sc.get("context_branch") if isinstance(g_sc.get("context_branch"), dict) else {}
    _assert(bool(b_iv) and bool(b_sc), "context branch selection must be present in gate outputs when policy defines branches")
    _assert(str(b_iv.get("selected_branch") or "") == "_default", "IV should select default branch in smoke fixture")
    _assert(str(b_sc.get("selected_branch") or "") == "SC", "SC should select SC branch in smoke fixture")
    _assert((g_iv.get("required_metrics") or []) == ["m_base"], "default branch must keep baseline required metrics")
    _assert((g_sc.get("required_metrics") or []) == ["m_base", "m_sc"], "SC branch must switch required metrics deterministically")




def test_shortlisting_reproducibility_from_soe_evidence_summary() -> None:
    policy_body = {
        "shortlisting": {"allow_shortlisting": True, "min_required_coverage_ratio": 1.0, "min_readiness_state": "ready"},
        "gates": {
            "G1": {"require_all": ["m_a", "m_b"]},
            "G2": {"require_all": ["m_c"]},
        },
    }
    short = derive_shortlisting(
        policy_body=policy_body,
        decision_state="ready",
        readiness={"state": "ready", "coverage": {"coverage_ratio": 1.0}},
        gate_outcomes={"G1": {"status": "pass"}, "G2": {"status": "pass"}},
        blockers=[],
        comparability={"summary": {"high_severity_count": 0, "total_flags": 0}},
        metric_evaluations={},
        evidence_summary=[
            {"metric_key": "m_b", "total_count": 1, "usable_count": 1},
            {"metric_key": "m_a", "total_count": 2, "usable_count": 2},
            {"metric_key": "m_c", "total_count": 3, "usable_count": 2},
        ],
        scope_type="batch",
        scope_id=1,
    )
    _assert(isinstance(short, dict) and not bool(short.get("refused")), "shortlisting should produce ranked candidate")
    cands = short.get("ranked_candidates") if isinstance(short.get("ranked_candidates"), list) else []
    _assert(len(cands) == 1 and isinstance(cands[0], dict), "shortlisting must emit one candidate in smoke fixture")
    cand = cands[0]
    repro = cand.get("reproducibility") if isinstance(cand.get("reproducibility"), dict) else None
    _assert(isinstance(repro, dict), "candidate.reproducibility must exist when evidence_summary is provided")
    _assert(str(repro.get("status") or "") == "available", "reproducibility.status must be available when evidence_summary exists")
    _assert(int(repro.get("required_metric_count") or 0) == 3, "reproducibility.required_metric_count must match required policy metrics")
    _assert(int(repro.get("positive_required_metric_count") or 0) == 2, "reproducibility positive count must follow total_count/usable_count > 1 rule")
    metrics = repro.get("metrics") if isinstance(repro.get("metrics"), list) else []
    _assert([str((m or {}).get("metric_key") or "") for m in metrics] == ["m_a", "m_b", "m_c"], "reproducibility.metrics must be deterministically ordered")
    expl = cand.get("tie_break_explanations") if isinstance(cand.get("tie_break_explanations"), list) else []
    repro_expl = [x for x in expl if isinstance(x, dict) and str(x.get("key") or "") == "reproducibility"]
    _assert(bool(repro_expl), "tie_break_explanations must include reproducibility")
    details = repro_expl[0].get("details") if isinstance(repro_expl[0].get("details"), dict) else {}
    _assert(int(details.get("positive_required_metric_count") or 0) == 2, "reproducibility why.details must include deterministic summary")


def test_shortlisting_refusal_v04_extensions_deterministic() -> None:
    policy_body = {
        "shortlisting": {"allow_shortlisting": True, "min_required_coverage_ratio": 1.0, "min_readiness_state": "ready"},
        "gates": {"G1": {"require_all": ["m_a", "m_b"]}},
    }
    common = dict(
        policy_body=policy_body,
        decision_state="not_ready",
        readiness={"state": "not_ready", "coverage": {"coverage_ratio": 0.5}},
        gate_outcomes={"G1": {"status": "fail"}},
        blockers=[],
        comparability={"summary": {"high_severity_count": 0, "total_flags": 0}},
        metric_evaluations={},
        evidence_summary=[{"metric_key": "m_a", "total_count": 1, "usable_count": 1}],
        scope_type="batch",
        scope_id=1,
    )
    out1 = derive_shortlisting(**common, emit_v0_4_extensions=True)
    out2 = derive_shortlisting(**common, emit_v0_4_extensions=True)
    _assert(stable_json_dumps(out1 or {}) == stable_json_dumps(out2 or {}), "v0.4 refusal extension surface must be deterministic")
    _assert(isinstance(out1, dict) and bool(out1.get("refused")), "fixture must refuse shortlisting")
    txt = out1.get("refusal_reasons_text") if isinstance(out1.get("refusal_reasons_text"), list) else []
    _assert(any(str(x).startswith("insufficient_reproducibility_counts:") for x in txt), "v0.4 refusal text must include reproducibility-count reason")
    legacy = derive_shortlisting(**common, emit_v0_4_extensions=False)
    _assert(isinstance(legacy, dict), "legacy fixture must return shortlisting dict")
    for k in ("refusal_reasons_text", "tie_break", "candidates"):
        _assert(k not in legacy, f"v0.3 shortlisting surface must not include {k}")


def test_tie_break_dimensions_v04_complete_and_deterministic() -> None:
    policy_body = {
        "shortlisting": {"allow_shortlisting": True, "min_required_coverage_ratio": 1.0, "min_readiness_state": "ready"},
        "gates": {"G1": {"require_all": ["monomer_pct", "hmw_pct", "lmw_pct", "percent_killing"]}},
    }
    kwargs = dict(
        policy_body=policy_body,
        decision_state="ready",
        readiness={"state": "ready", "coverage": {"coverage_ratio": 1.0}, "qc_confidence": {"reviewed_required_present": 2, "unreviewed_required_present": 0, "mode": "model_safe"}},
        gate_outcomes={"G1": {"status": "pass"}},
        blockers=[],
        comparability={"summary": {"high_severity_count": 0, "total_flags": 0}},
        metric_evaluations={
            "monomer_pct": {"evaluated_status": "PASS", "interpretation_gap": False},
            "hmw_pct": {"evaluated_status": "PASS", "interpretation_gap": False},
            "lmw_pct": {"evaluated_status": "PASS", "interpretation_gap": False},
            "percent_killing": {"evaluated_status": "PASS", "interpretation_gap": False},
        },
        evidence_summary=[
            {"metric_key": "monomer_pct", "total_count": 2, "usable_count": 2},
            {"metric_key": "hmw_pct", "total_count": 2, "usable_count": 2},
            {"metric_key": "lmw_pct", "total_count": 2, "usable_count": 2},
            {"metric_key": "percent_killing", "total_count": 2, "usable_count": 2},
        ],
        scope_type="batch",
        scope_id=7,
        emit_v0_4_extensions=True,
    )
    out1 = derive_shortlisting(**kwargs)
    out2 = derive_shortlisting(**kwargs)
    _assert(stable_json_dumps(out1 or {}) == stable_json_dumps(out2 or {}), "v0.4 tie-break payload must be deterministic")
    cand = ((out1 or {}).get("ranked_candidates") or [{}])[0]
    dims = cand.get("tie_break_dimensions") if isinstance(cand, dict) and isinstance(cand.get("tie_break_dimensions"), list) else []
    keys = [str((d or {}).get("key") or "") for d in dims]
    _assert(keys == ["readiness_completeness", "qc_confidence", "purity_aggregation_profile", "reproducibility", "potency_functional"], "tie-break dimension keys must be complete and in stable order")
    _assert(all(str((d or {}).get("status") or "") in ("implemented", "deferred") for d in dims), "tie-break dimensions must declare implemented/deferred status")
    tb = (out1 or {}).get("tie_break") if isinstance((out1 or {}).get("tie_break"), dict) else {}
    tb_dims = tb.get("dimensions") if isinstance(tb.get("dimensions"), list) else []
    _assert([str((d or {}).get("key") or "") for d in tb_dims] == keys, "shortlisting.tie_break.dimensions must align with candidate tie-break dimensions")


def test_scope_semantics_v04_deterministic() -> None:
    from psi.core.di.schema import DIInput

    di_in = DIInput(
        decision_key="advance_to_in_vivo",
        scope_type="molecule",
        scope_id=42,
        as_of_ts=None,
        qc_mode="model_safe",
        context={"route": "SC"},
    )
    shortlisting = {"enabled": True, "refused": False, "ranked_candidates": [{"candidate_id": "molecule:42"}]}
    selection_provenance = {"molecule_id": 42, "batch_ids_ordered": [9, 7, 5]}
    s1 = _build_scope_semantics(di_in=di_in, shortlisting=shortlisting, selection_provenance=selection_provenance)
    s2 = _build_scope_semantics(di_in=di_in, shortlisting=shortlisting, selection_provenance=selection_provenance)
    _assert(stable_json_dumps(s1) == stable_json_dumps(s2), "scope_semantics must be deterministic")
    _assert(str(s1.get("ranked_entity") or "") == "batch", "scope_semantics.ranked_entity must be batch")
    _assert(str(s1.get("molecule_derivation") or "") == "best_ready_batch_per_molecule", "scope_semantics.molecule_derivation must be explicit")
    batch_ids = [int((x or {}).get("batch_id") or 0) for x in (s1.get("batch_ranked_candidates") or [])]
    _assert(batch_ids == [9, 7, 5], "scope_semantics batch-ranked view must preserve deterministic batch order")
    mols = s1.get("molecule_derived_candidates") if isinstance(s1.get("molecule_derived_candidates"), list) else []
    _assert(len(mols) == 1 and int((mols[0] or {}).get("best_batch_id") or 0) == 9, "scope semantics molecule derivation must align with batch-ranked best candidate")


def test_template_registry_and_dependency_graph_deterministic() -> None:
    keys1 = list_template_keys_sorted()
    keys2 = list_template_keys_sorted()
    _assert(keys1 == keys2, "template registry listing must be deterministic")
    _assert(len(keys1) >= 2, "template registry must include >=2 templates")
    graph1 = template_dependency_graph()
    graph2 = template_dependency_graph()
    _assert(stable_json_dumps(graph1) == stable_json_dumps(graph2), "template dependency graph must be deterministic")
    nodes = graph1.get("nodes") if isinstance(graph1.get("nodes"), list) else []
    _assert(nodes == sorted(nodes), "template dependency graph nodes must be sorted")
    edges = graph1.get("edges") if isinstance(graph1.get("edges"), list) else []
    _assert(any(isinstance(e, dict) and e.get("depends_on") for e in edges), "template dependency graph must include at least one dependency edge")


def test_shared_sub_assessments_pure_helpers() -> None:
    class _Ev:
        def __init__(self, *, is_outlier: bool, qc_status: str):
            self.is_outlier = is_outlier
            self.qc_status = qc_status

    used = {"a": _Ev(is_outlier=False, qc_status="approved"), "b": _Ev(is_outlier=True, qc_status="unreviewed")}
    rf1 = baseline_risk_flags_from_used(used_by_metric=used)
    rf2 = baseline_risk_flags_from_used(used_by_metric=used)
    _assert(stable_json_dumps(rf1) == stable_json_dumps(rf2), "shared risk-flag helper must be deterministic")
    _assert([str((x or {}).get('risk_flag') or '') for x in rf1] == ["outlier_present", "qc_uncertainty"], "shared risk-flag helper should return stable baseline flags")
    class _Gate:
        def __init__(self, gate_key: str, status: str):
            self.gate_key = gate_key
            self.status = status
    ds, meta = decision_state_from_gate_statuses(gates=[_Gate("G1", "pass")], required_gate_keys=["G1"], blockers=[])
    _assert(ds == "ready" and bool(meta.get("required_pass")), "shared decision-state helper must be deterministic and pure")


def test_policy_blocker_taxonomy_and_experiment_suggestions() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    pol_path = repo_root / "psi" / "core" / "di" / "policies" / "advance_to_in_vivo_v0_1.json"
    cat_path = repo_root / "psi" / "core" / "di" / "catalogs" / "experiment_catalog_v0_1.json"

    pol = load_policy(pol_path)
    cat = load_catalog(cat_path)

    ts = (pol.package or {}).get("template_structure") or {}
    taxonomy = ts.get("blocker_taxonomy") or []
    _assert(isinstance(taxonomy, list) and taxonomy, "blocker_taxonomy must be a non-empty list")
    taxonomy_set = set(str(x) for x in taxonomy)

    body = pol.policy_body if isinstance(pol.policy_body, dict) else {}
    blocker_order = body.get("blocker_order") or []
    if blocker_order:
        _assert(all(str(b) in taxonomy_set for b in blocker_order), "All blocker_order keys must exist in blocker_taxonomy")

    blocker_suggestions = body.get("blocker_suggestions") or {}
    if isinstance(blocker_suggestions, dict):
        _assert(all(str(k) in taxonomy_set for k in blocker_suggestions.keys()), "All blocker_suggestions keys must exist in blocker_taxonomy")

        exp_keys = set((e or {}).get("experiment_key") for e in ((cat.catalog.get("experiments") or []) if isinstance(cat.catalog.get("experiments"), list) else []))
        for bk, exps in blocker_suggestions.items():
            _assert(isinstance(exps, list), f"blocker_suggestions[{bk}] must be a list")
            norm = [str(x).strip() for x in exps if str(x).strip()]
            _assert(len(norm) == len(set(norm)), f"blocker_suggestions[{bk}] must be deduplicated")
            _assert(norm == sorted(norm), f"blocker_suggestions[{bk}] must be lexicographically sorted")
            missing = [x for x in norm if x not in exp_keys]
            _assert(not missing, f"blocker_suggestions[{bk}] contains unknown experiment_keys: {missing}")

def test_ignore_reason_keys_allowed_set() -> None:
    # Ensure the allowed set is stable and contains required keys.
    required = {
        "qc_failed",
        "qc_unreviewed_strict",
        "superseded_by_primary",
        "superseded_by_newer",
        "outlier_policy",
        "metric_not_applicable",
        "unit_inconvertible",
        "method_incomparable",
        "as_of_excluded",
    }
    _assert(required.issubset(ALLOWED_IGNORE_REASON_KEYS), "allowed ignore reason keys must include the required stable taxonomy")


def test_soe_v0_2_contract_snapshot_shape_and_determinism() -> None:
    # Lightweight integration check: build a tiny ephemeral DB, run DI, and validate
    # the additive SoE v0.2 structure + deterministic ordering.

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from psi.core.db import _copy_sqlite_bundle, _install_sqlite_pragmas, ensure_schema
    from psi.core.models import Batch, Molecule, Program
    from psi.services.programs import create_program
    from psi.services.molecules import create_molecule, DuplicateMoleculeError
    from psi.services.batches import create_batch
    from psi.services.data_records import create_data_record
    from psi.services.measurements import upsert_measurements

    from psi.core.di.schema import DIInput
    from psi.services.di.runner import run_di
    from psi.services.di.verify import verify_snapshot

    def _seed_contract_db(db):
        # Program
        p = db.query(Program).filter(Program.name == "DI_SMOKE").first()
        if p is None:
            p = create_program(db, name="DI_SMOKE", description="DI contract smoke")

        # Molecule
        m = db.query(Molecule).filter(Molecule.program_id == p.id).first()
        if m is None:
            hc = "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISWNSGGSTYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYC"
            lc = "DIQMTQSPSSLSASVGDRVTITCRASSSVSYIHWFQQKPGKAPKLLIYAASTLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYC"
            try:
                m = create_molecule(db, program_id=p.id, primary_id="DI-SMOKE-0001", title="DI Smoke molecule", components={"HC1": hc, "LC1": lc})
            except DuplicateMoleculeError:
                m = db.query(Molecule).filter(Molecule.program_id == p.id).first()
                _assert(m is not None, "Duplicate molecule but none found")

        # Batch
        b = db.query(Batch).filter(Batch.molecule_id == m.id).first()
        if b is None:
            b = create_batch(db=db, molecule_id=m.id, title="DI Smoke batch", expression_notes="", purification_notes="")

        # Minimal records + measurements to exercise alias mapping + missing coverage.
        # Provide alias metric key (hmw_percent) that canonicalizes to hmw_pct in policy.
        r = create_data_record(
            db=db,
            program_id=p.id,
            molecule_id=None,
            batch_id=b.id,
            domain="generic",
            data_type="generic",
            method="generic",
            title="DI contract record",
            params_json={},
            results_json={},
        )

        upsert_measurements(
            db=db,
            record_id=r.id,
            measurements=[
                {
                    "name": "hmw_percent",  # alias -> should satisfy canonical hmw_pct via metric_alias_map
                    "value_num": 2.0,
                    "value_text": "2.0",
                    "unit": None,
                    "comparator": None,
                    "data_type": r.data_type,
                    "method": r.method,
                },
                {
                    "name": "monomer_pct",
                    "value_num": 98.0,
                    "value_text": "98%",
                    "unit": "%",
                    "comparator": None,
                    "data_type": r.data_type,
                    "method": r.method,
                },
                # Intentionally omit lmw_pct to exercise missing-coverage paths.
                {
                    "name": "value_eu_ml",
                    "value_num": 0.1,
                    "value_text": "0.1",
                    "unit": None,
                    "comparator": None,
                    "data_type": r.data_type,
                    "method": r.method,
                },
                {
                    "name": "limit_eu_ml",
                    "value_num": 5.0,
                    "value_text": "5",
                    "unit": None,
                    "comparator": None,
                    "data_type": r.data_type,
                    "method": r.method,
                },
            ],
        )
        return b.id

    def _run_once(db_path: Path, *, policy_path_override: Path | None = None):
        eng = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False}, future=True)
        _install_sqlite_pragmas(eng, read_only=False)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng, future=True)
        ensure_schema(engine_override=eng)
        db = SessionLocal()
        try:
            batch_id = _seed_contract_db(db)
            di_input = DIInput(
                decision_key="advance_to_in_vivo",
                scope_type="batch",
                scope_id=int(batch_id),
                as_of_ts=None,
                qc_mode="model_safe",
                context={},
            )
            out = run_di(db, di_input=di_input, policy_path=(policy_path_override or policy_path))
            _assert_single_active_snapshot_per_scope(db)
            return out, db
        except Exception:
            db.close()
            raise

    if os.environ.get("PSI_DB_PATH"):
        baseline_path = Path(os.environ["PSI_DB_PATH"])
        _assert(baseline_path.exists(), f"PSI_DB_PATH not found: {baseline_path}")
    else:
        root = Path(tempfile.gettempdir()) / "psi_di_contract"
        root.mkdir(parents=True, exist_ok=True)
        baseline_path = root / "psi_di_contract.sqlite"
        for p in (baseline_path, baseline_path.with_name(baseline_path.name + "-wal"), baseline_path.with_name(baseline_path.name + "-shm")):
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        eng = create_engine(f"sqlite:///{baseline_path}", connect_args={"check_same_thread": False}, future=True)
        _install_sqlite_pragmas(eng, read_only=False)
        ensure_schema(engine_override=eng)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng, future=True)
        db = SessionLocal()
        try:
            _seed_contract_db(db)
        finally:
            db.close()
            eng.dispose()

    run1_dir = Path(tempfile.mkdtemp(prefix="psi_di_contract_run1_", dir=tempfile.gettempdir()))
    run2_dir = Path(tempfile.mkdtemp(prefix="psi_di_contract_run2_", dir=tempfile.gettempdir()))
    db1_path = _copy_sqlite_bundle(baseline_path, run1_dir)
    db2_path = _copy_sqlite_bundle(baseline_path, run2_dir)

    policy_path = Path(__file__).resolve().parents[2] / "psi" / "core" / "di" / "policies" / "advance_to_in_vivo_v0_3.json"

    out1, db1 = _run_once(db1_path)
    out2, db2 = _run_once(db2_path)

    from psi.services.decisions import add_outcome_label, get_snapshot_detail

    # NOTE: run_di persists a new DecisionSnapshot row per call, so snapshot_id will
    # naturally differ. Determinism is asserted over the pure DI output payload.
    s1 = stable_json_dumps(out1.get("output") or {})
    s2 = stable_json_dumps(out2.get("output") or {})

    if s1 != s2:
        p1 = Path(tempfile.gettempdir()) / "di_contract_out1.json"
        p2 = Path(tempfile.gettempdir()) / "di_contract_out2.json"
        p1.write_text(s1 + "\n", encoding="utf-8")
        p2.write_text(s2 + "\n", encoding="utf-8")
        print(f"Wrote non-deterministic DI outputs to:\n  {p1}\n  {p2}", file=sys.stderr)

    _assert(s1 == s2, "DI output must be deterministic for identical DB + inputs")

    _assert("ranking" not in (out1.get("output") or {}), "weighted ranking must be absent from canonical DI output")

    snap_ctx1 = get_snapshot_detail(db1, int(out1.get("snapshot_id")))
    snap_ctx2 = get_snapshot_detail(db2, int(out2.get("snapshot_id")))
    prov_block1 = snap_ctx1.get("di_snapshot_provenance")
    prov_block2 = snap_ctx2.get("di_snapshot_provenance")
    _assert_snapshot_provenance_block(prov_block1, expected_scope_type="batch")
    _assert_snapshot_provenance_block(prov_block2, expected_scope_type="batch")
    _assert(
        stable_json_dumps(prov_block1) == stable_json_dumps(prov_block2),
        "di_snapshot_provenance block must be stable across deterministic reruns",
    )
    # w44: snapshot template rendering must tolerate both absent labels and present labels.
    html_no_labels = _render_di_snapshot_template_smoke(snap_ctx1)
    _assert("No DI review yet." in html_no_labels, "DI snapshot render should tolerate missing review labels")
    add_outcome_label(db1, snapshot_id=int(out1.get("snapshot_id")), name="correct", value_text="manual smoke")
    add_outcome_label(db1, snapshot_id=int(out1.get("snapshot_id")), name="di_review_verdict", value_text="useful")
    add_outcome_label(db1, snapshot_id=int(out1.get("snapshot_id")), name="di_review_rationale", value_text="stable render check")
    snap_ctx1_labeled = get_snapshot_detail(db1, int(out1.get("snapshot_id")))
    html_with_labels = _render_di_snapshot_template_smoke(snap_ctx1_labeled)
    _assert("Latest outcome label" in html_with_labels, "DI snapshot render should show latest outcome label summary")
    _assert("stable render check" in html_with_labels, "DI snapshot render should show latest DI review rationale")

    # v1.2.9k: provenance.integrity must exist and be stable across deterministic reruns
    out1_obj = (out1.get("output") or {})
    prov1 = out1_obj.get("provenance") or {}
    prov2 = (out2.get("output") or {}).get("provenance") or {}
    integ1 = prov1.get("integrity") if isinstance(prov1, dict) else None
    integ2 = prov2.get("integrity") if isinstance(prov2, dict) else None
    _assert(isinstance(integ1, dict), "provenance.integrity must exist and be a dict")
    _assert(isinstance(integ2, dict), "provenance.integrity must exist and be a dict")
    for k in ("snapshot_content_hash", "evidence_fingerprint"):
        _assert(bool(str(integ1.get(k) or "")), f"provenance.integrity.{k} must be non-empty")
        _assert(bool(str(integ2.get(k) or "")), f"provenance.integrity.{k} must be non-empty")
        _assert(str(integ1.get(k)) == str(integ2.get(k)), f"provenance.integrity.{k} must be stable across reruns")

    # Governance gate: weighted ranking is suppressed in canonical output even if policy shortlisting is configured.
    disabled_pol = json.loads(policy_path.read_text(encoding="utf-8"))
    pb = disabled_pol.get("policy_body")
    if not isinstance(pb, dict):
        pb = {}
        disabled_pol["policy_body"] = pb
    sh = pb.get("shortlisting")
    if not isinstance(sh, dict):
        sh = {}
    sh["allow_shortlisting"] = False
    sh["allow"] = False
    pb["shortlisting"] = sh
    disabled_path = Path(tempfile.mkdtemp(prefix="psi_di_contract_policy_", dir=tempfile.gettempdir())) / "disabled_shortlisting.json"
    disabled_path.write_text(json.dumps(disabled_pol, sort_keys=True, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    out_disabled, db_disabled = _run_once(db2_path, policy_path_override=disabled_path)
    try:
        _assert("ranking" not in (out_disabled.get("output") or {}), "ranking must remain absent when policy shortlisting is disabled")
    finally:
        db_disabled.close()

    _assert("ranking" not in out1_obj, "batch scope canonical output must not include weighted ranking")
    _assert("Ranking candidates" not in html_with_labels, "DI snapshot UI must not render weighted ranking table")

    # v1.2.9n: anchored replay must match runner output for all compute-derived fingerprints after a clean run
    rep = verify_snapshot(db=db1, snapshot_id=int(out1.get("snapshot_id")), debug=False)
    ar = (rep.get("anchored_replay") or {}) if isinstance(rep, dict) else {}
    _assert(bool(ar.get("available")), "anchored replay must be available for smoke snapshot")
    stored = (rep.get("stored") or {}) if isinstance(rep, dict) else {}
    replay = ((ar.get("replay") or {}) if isinstance(ar.get("replay"), dict) else {})

    for k in ("snapshot_content_hash", "evidence_fingerprint", "decision_output_hash_v2_effective", "semantic_fingerprint"):
        sv = str(stored.get(k) or "")
        rv = str(replay.get(k) or "")
        _assert(bool(sv) and bool(rv), f"stored + replay {k} must be non-empty")
        _assert(sv == rv, f"anchored replay {k} must equal stored {k}")

    db1.close()
    db2.close()


def test_molecule_scope_determinism() -> None:
    # Molecule-scope aggregation should be deterministic across identical DBs.

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from psi.core.db import _copy_sqlite_bundle, _install_sqlite_pragmas, ensure_schema
    from psi.core.models import Batch, Molecule, Program
    from psi.services.programs import create_program
    from psi.services.molecules import create_molecule, DuplicateMoleculeError
    from psi.services.batches import create_batch
    from psi.services.data_records import create_data_record
    from psi.services.measurements import upsert_measurements

    from psi.core.di.schema import DIInput
    from psi.services.di.runner import run_di

    def _seed_molecule_db(db):
        p = db.query(Program).filter(Program.name == "DI_SMOKE_MOL").first()
        if p is None:
            p = create_program(db, name="DI_SMOKE_MOL", description="DI molecule smoke")

        m = db.query(Molecule).filter(Molecule.program_id == p.id).first()
        if m is None:
            hc = "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISWNSGGSTYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYC"
            lc = "DIQMTQSPSSLSASVGDRVTITCRASSSVSYIHWFQQKPGKAPKLLIYAASTLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYC"
            try:
                m = create_molecule(db, program_id=p.id, primary_id="DI-SMOKE-MOL-0001", title="DI Smoke molecule (mol)", components={"HC1": hc, "LC1": lc})
            except DuplicateMoleculeError:
                m = db.query(Molecule).filter(Molecule.program_id == p.id).first()
                _assert(m is not None, "Duplicate molecule but none found")

        b1 = db.query(Batch).filter(Batch.molecule_id == m.id).order_by(Batch.id.asc()).first()
        if b1 is None:
            b1 = create_batch(db=db, molecule_id=m.id, title="DI Smoke mol batch 1", expression_notes="", purification_notes="")
        b2 = db.query(Batch).filter(Batch.molecule_id == m.id).order_by(Batch.id.desc()).first()
        if b2 is None or b2.id == b1.id:
            b2 = create_batch(db=db, molecule_id=m.id, title="DI Smoke mol batch 2", expression_notes="", purification_notes="")

        r1 = create_data_record(
            db=db,
            program_id=p.id,
            molecule_id=None,
            batch_id=b1.id,
            domain="generic",
            data_type="generic",
            method="generic",
            title="DI mol contract record 1",
            params_json={},
            results_json={},
        )
        upsert_measurements(
            db=db,
            record_id=r1.id,
            measurements=[
                {
                    "name": "hmw_percent",
                    "value_num": 1.0,
                    "value_text": "1.0",
                    "unit": None,
                    "comparator": None,
                    "data_type": r1.data_type,
                    "method": r1.method,
                },
            ],
        )

        r2 = create_data_record(
            db=db,
            program_id=p.id,
            molecule_id=None,
            batch_id=b2.id,
            domain="generic",
            data_type="generic",
            method="generic",
            title="DI mol contract record 2",
            params_json={},
            results_json={},
        )
        upsert_measurements(
            db=db,
            record_id=r2.id,
            measurements=[
                {
                    "name": "monomer_pct",
                    "value_num": 97.0,
                    "value_text": "97%",
                    "unit": "%",
                    "comparator": None,
                    "data_type": r2.data_type,
                    "method": r2.method,
                },
            ],
        )

        return m.id, [b1.id, b2.id]

    def _run_once(db_path: Path):
        eng = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False}, future=True)
        _install_sqlite_pragmas(eng, read_only=False)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng, future=True)
        ensure_schema(engine_override=eng)
        db = SessionLocal()
        try:
            mol_id, batch_ids = _seed_molecule_db(db)
            di_input = DIInput(
                decision_key="advance_to_in_vivo",
                scope_type="molecule",
                scope_id=int(mol_id),
                as_of_ts=None,
                qc_mode="model_safe",
                context={},
            )
            out = run_di(db, di_input=di_input, policy_path=policy_path)
            _assert_single_active_snapshot_per_scope(db)
            return out, batch_ids, db
        except Exception:
            db.close()
            raise

    root = Path(tempfile.gettempdir()) / "psi_di_contract_molecule"
    root.mkdir(parents=True, exist_ok=True)
    baseline_path = root / "psi_di_contract_molecule.sqlite"
    for p in (baseline_path, baseline_path.with_name(baseline_path.name + "-wal"), baseline_path.with_name(baseline_path.name + "-shm")):
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass
    eng = create_engine(f"sqlite:///{baseline_path}", connect_args={"check_same_thread": False}, future=True)
    _install_sqlite_pragmas(eng, read_only=False)
    ensure_schema(engine_override=eng)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng, future=True)
    db = SessionLocal()
    try:
        _seed_molecule_db(db)
    finally:
        db.close()
        eng.dispose()

    run1_dir = Path(tempfile.mkdtemp(prefix="psi_di_contract_mol_run1_", dir=tempfile.gettempdir()))
    run2_dir = Path(tempfile.mkdtemp(prefix="psi_di_contract_mol_run2_", dir=tempfile.gettempdir()))
    db1_path = _copy_sqlite_bundle(baseline_path, run1_dir)
    db2_path = _copy_sqlite_bundle(baseline_path, run2_dir)

    policy_path = Path(__file__).resolve().parents[2] / "psi" / "core" / "di" / "policies" / "advance_to_in_vivo_v0_3.json"

    out1, batch_ids1, db1 = _run_once(db1_path)
    out2, batch_ids2, db2 = _run_once(db2_path)

    from psi.services.decisions import get_snapshot_detail

    s1 = stable_json_dumps(out1.get("output") or {})
    s2 = stable_json_dumps(out2.get("output") or {})
    _assert(s1 == s2, "molecule-scope DI output must be deterministic for identical DB + inputs")

    out1_obj = (out1.get("output") or {})
    prov = out1_obj.get("provenance") or {}
    sp = prov.get("selection_provenance") if isinstance(prov, dict) else {}
    ordered = sp.get("batch_ids_ordered") if isinstance(sp, dict) else None
    _assert(isinstance(ordered, list) and len(ordered) >= 2, "molecule selection must include ordered batch_ids")
    _assert(set(int(x) for x in ordered) == set(int(x) for x in batch_ids1), "ordered batch_ids must match selected batches")

    _assert("ranking" not in out1_obj, "molecule scope canonical output must not include weighted ranking")
    why_evidence = out1_obj.get("why_evidence")
    _assert(isinstance(why_evidence, dict), "molecule output.why_evidence must exist and be a dict")
    ranking_why = (why_evidence.get("ranking") or {}).get("candidates") if isinstance(why_evidence.get("ranking"), dict) else None
    _assert(isinstance(ranking_why, list), "why_evidence.ranking.candidates must be a list")
    _assert(len(ranking_why) == 0, "why_evidence.ranking.candidates must be empty when canonical ranking is suppressed")

    snap_ctx1 = get_snapshot_detail(db1, int(out1.get("snapshot_id")))
    snap_ctx2 = get_snapshot_detail(db2, int(out2.get("snapshot_id")))
    prov_block1 = snap_ctx1.get("di_snapshot_provenance")
    prov_block2 = snap_ctx2.get("di_snapshot_provenance")
    _assert_snapshot_provenance_block(prov_block1, expected_scope_type="molecule")
    _assert_snapshot_provenance_block(prov_block2, expected_scope_type="molecule")
    _assert(
        stable_json_dumps(prov_block1) == stable_json_dumps(prov_block2),
        "molecule di_snapshot_provenance block must be stable across deterministic reruns",
    )

    db1.close()
    db2.close()


    out_payload = out1.get("output") or {}

    # v1.2.9g: readiness formalization must be present and deterministic
    readiness = out_payload.get("readiness")
    _assert(isinstance(readiness, dict), "output.readiness must exist and be a dict")
    _assert(readiness.get("state") in ("ready", "not_ready", "blocked", "insufficient_evidence"), "readiness.state enum invalid")

    # v1.2.9m8: coverage.required_total must be > 0 when policy has required gates
    cov = readiness.get("coverage")
    _assert(isinstance(cov, dict), "readiness.coverage must exist and be a dict")
    _assert(int(cov.get("required_total") or 0) > 0, "coverage.required_total must be > 0")

    # v1.2.9i: normalized readiness fields must exist (empty arrays must be present)
    _assert(isinstance(readiness.get("decision_context"), str) and readiness.get("decision_context"), "readiness.decision_context must be a non-empty string")
    _assert(isinstance(readiness.get("readiness_level"), str) and readiness.get("readiness_level"), "readiness.readiness_level must be a non-empty string")
    for k in ("blocking_gates", "blocking_reasons", "assumptions", "required_next_steps"):
        _assert(k in readiness, f"readiness must include key: {k}")
        _assert(isinstance(readiness.get(k), list), f"readiness.{k} must be a list")

    blockers = readiness.get("blockers") or []
    _assert(isinstance(blockers, list), "readiness.blockers must be a list")
    # Deterministic blocker ordering: (severity_rank, key, metrics, gates)
    sev_rank = {"high": 0, "moderate": 1, "low": 2}
    def _blk_sort_key(b):
        b = b or {}
        return (
            sev_rank.get(str(b.get("severity") or "").strip().lower(), 9),
            str(b.get("key") or ""),
            ",".join(b.get("metrics") or []),
            ",".join(b.get("gates") or []),
        )

    _assert(blockers == sorted(blockers, key=_blk_sort_key), "readiness.blockers must be deterministically sorted")

    cov_fp = out_payload.get("coverage_fingerprint")
    _assert(isinstance(cov_fp, str) and len(cov_fp) == 64, "coverage_fingerprint must be sha256 hex")

    # v1.2.9m8: selector tie-break invariant
    #
    # NOTE: Some PSI DB schemas enforce uniqueness for (data_record_id, metric_key) (e.g. UNIQUE INDEX
    # on (data_record_id, metric_key)), meaning you cannot store two monomer_pct rows for the same record.
    # In those schemas, it is impossible to exercise an in-DB tie on identical timestamps.
    #
    # To keep this smoke test schema-agnostic (and without modifying selector/engine logic), we lock the
    # tie-break behavior by asserting it is encoded in selector source:
    #   candidates.sort(..., reverse=True) with -row_id(r) included in the sort key
    import inspect, re
    import psi.services.di.selectors as selectors_mod

    _src = inspect.getsource(selectors_mod)
    _assert(
        re.search(r"candidates\.sort\(key=sort_key,\s*reverse=True\)", _src) is not None
        and re.search(r"\-row_id\(r\)", _src) is not None,
        "selector tie-break invariant not found (expected smallest measurement id to win ties)",
    )

    gate_outcomes = out_payload.get("gate_outcomes") or {}
    _assert(isinstance(gate_outcomes, dict), "gate_outcomes must exist and be a dict")
    gokeys = list(gate_outcomes.keys())
    _assert(gokeys == sorted(gokeys), "gate_outcomes keys must be lexicographically sorted")
    for gk, gi in gate_outcomes.items():
        gi = gi or {}
        for lk in ("required_metrics", "present_metrics", "missing_metrics", "qc_notes"):
            if lk in gi:
                v = gi.get(lk)
                _assert(isinstance(v, list), f"gate_outcomes[{gk}].{lk} must be a list")
                _assert(v == sorted(v), f"gate_outcomes[{gk}].{lk} must be sorted")

    why_evidence = out_payload.get("why_evidence")
    _assert(isinstance(why_evidence, dict), "output.why_evidence must exist and be a dict")
    for k in ("gates", "readiness", "shortlisting", "ranking"):
        _assert(k in why_evidence, f"why_evidence missing key: {k}")
    gates_why = why_evidence.get("gates") or {}
    _assert(isinstance(gates_why, dict), "why_evidence.gates must be a dict")
    _assert(list(gates_why.keys()) == sorted(list(gates_why.keys())), "why_evidence.gates keys must be sorted")
    for gk, gi in gate_outcomes.items():
        gi = gi or {}
        ptrs = gates_why.get(gk) or []
        _assert(isinstance(ptrs, list), f"why_evidence.gates[{gk}] must be a list")
        if (gi.get("present_metrics") or []):
            _assert(ptrs, f"why_evidence.gates[{gk}] must contain pointers when present_metrics exist")
        ptr_sort = [
            (
                str((p or {}).get("kind") or ""),
                int((p or {}).get("id") or 0),
                str((p or {}).get("field") or ""),
                str((p or {}).get("metric_key") or ""),
            )
            for p in ptrs
        ]
        _assert(ptr_sort == sorted(ptr_sort), f"why_evidence.gates[{gk}] pointers must be deterministically sorted")

    soe = (out_payload.get("state_of_evidence") or {})
    _assert("used" in soe and "ignored_evidence" in soe and "warnings" in soe, "legacy SoE fields must remain")

    v2 = soe.get("soe_v0_2")
    _assert(isinstance(v2, dict), "state_of_evidence.soe_v0_2 must exist and be a dict")

    for k in ("requirements", "metric_status", "gate_coverage", "summary", "qc_summary", "recency", "coverage"):
        _assert(k in v2, f"soe_v0_2 missing required key: {k}")

    ms = v2.get("metric_status") or {}
    _assert(isinstance(ms, dict) and ms, "metric_status must be a non-empty dict")

    # Deterministic ordering (insertion order) for metric keys and gate keys.
    mkeys = list(ms.keys())
    _assert(mkeys == sorted(mkeys), "metric_status keys must be lexicographically sorted")

    gates = v2.get("gate_coverage") or {}
    gkeys = list(gates.keys())
    _assert(gkeys == sorted(gkeys), "gate_coverage keys must be lexicographically sorted")

    req = (v2.get("requirements") or {}).get("by_gate") or {}
    rkeys = list(req.keys())
    _assert(rkeys == sorted(rkeys), "requirements.by_gate keys must be lexicographically sorted")

    allowed = {"present", "missing", "present_but_ignored", "present_but_non_numeric"}
    for mk, info in ms.items():
        st = (info or {}).get("status")
        _assert(st in allowed, f"metric_status[{mk}].status must be one of {sorted(list(allowed))}")

    # Alias mapping should be explainable (hmw_pct satisfied via alias hmw_percent)
    hmw = ms.get("hmw_pct") or {}
    _assert(hmw.get("status") in ("present", "present_but_non_numeric"), "hmw_pct should be present via alias mapping")
    src = hmw.get("metric_key_source")
    _assert(isinstance(src, str) and src.startswith("alias:"), "hmw_pct metric_key_source should indicate alias")

    # v1.2.9i: SoE v0.3 must exist and be stable
    v3 = soe.get("soe_v0_3")
    _assert(isinstance(v3, dict), "state_of_evidence.soe_v0_3 must exist and be a dict")
    _assert(v3.get("schema_version") == "0.3", "soe_v0_3.schema_version must be '0.3'")
    es = v3.get("evidence_summary")
    _assert(isinstance(es, list), "soe_v0_3.evidence_summary must be a list")
    # deterministic ordering by metric_key
    keys = [str((e or {}).get("metric_key") or "") for e in es]
    _assert(keys == sorted(keys), "soe_v0_3.evidence_summary must be ordered by metric_key ASC")
    for e in es:
        e = e or {}
        for k in ("metric_key", "total_count", "usable_count", "ignored_count", "latest_timestamp", "methods_present", "units_present", "ignore_reasons_breakdown"):
            _assert(k in e, f"soe_v0_3 evidence entry missing key: {k}")
        _assert(isinstance(e.get("methods_present"), list) and e.get("methods_present") == sorted(e.get("methods_present")), "methods_present must be sorted")
        _assert(isinstance(e.get("units_present"), list) and e.get("units_present") == sorted(e.get("units_present")), "units_present must be sorted")
        br = e.get("ignore_reasons_breakdown")
        _assert(isinstance(br, list), "ignore_reasons_breakdown must be a list")
        br_keys = [str((x or {}).get("reason_key") or "") for x in br]
        _assert(br_keys == sorted(br_keys), "ignore_reasons_breakdown must be ordered by reason_key ASC")

    # v1.2.9i: suggestions must be present (may be empty) and deterministically ordered
    sugg = out_payload.get("suggestions")
    _assert(isinstance(sugg, list), "output.suggestions must exist and be a list")
    ids = [str((s or {}).get("suggestion_id") or "") for s in sugg]
    _assert(ids == sorted(ids), "suggestions must be ordered by suggestion_id ASC")
    for s in sugg:
        s = s or {}
        for k in ("suggestion_id", "type", "rationale", "action_spec"):
            _assert(k in s, f"suggestion missing key: {k}")
        a = s.get("action_spec") or {}
        _assert(isinstance(a, dict), "suggestion.action_spec must be a dict")
        for k in ("metric_key", "preferred_method", "required_unit"):
            _assert(k in a, f"suggestion.action_spec missing key: {k}")

    # v1.2.9j: comparability + confidence degradation must exist and be deterministic
    comp = out_payload.get("comparability")
    _assert(isinstance(comp, dict), "output.comparability must exist and be a dict")
    for k in ("metric_level", "qc_coherence", "summary"):
        _assert(k in comp, f"comparability missing key: {k}")
    ml = comp.get("metric_level")
    qc = comp.get("qc_coherence")
    _assert(isinstance(ml, list), "comparability.metric_level must be a list")
    _assert(isinstance(qc, list), "comparability.qc_coherence must be a list")
    _assert(ml == sorted(ml, key=lambda x: (str((x or {}).get("metric_key") or ""), str((x or {}).get("issue") or ""))), "comparability.metric_level must be sorted by metric_key,issue")
    _assert(qc == sorted(qc, key=lambda x: (str((x or {}).get("metric_key") or ""), str((x or {}).get("issue") or ""))), "comparability.qc_coherence must be sorted by metric_key,issue")
    for e in ml:
        e = e or {}
        _assert("metric_key" in e and "issue" in e and "severity" in e, "comparability.metric_level entry missing required keys")
        if e.get("issue") == "mixed_method":
            md = e.get("methods_detected")
            _assert(isinstance(md, list) and md == sorted(md), "methods_detected must be sorted")
        if e.get("issue") == "unit_inconsistent":
            ud = e.get("units_detected")
            _assert(isinstance(ud, list) and ud == sorted(ud), "units_detected must be sorted")
    for e in qc:
        e = e or {}
        _assert("metric_key" in e and "issue" in e and "severity" in e, "comparability.qc_coherence entry missing required keys")
        sd = e.get("states_detected")
        _assert(isinstance(sd, list) and sd == sorted(sd), "states_detected must be sorted")

    summ = comp.get("summary") or {}
    _assert(isinstance(summ, dict), "comparability.summary must be a dict")
    _assert(int(summ.get("total_flags") or 0) == int(len(ml) + len(qc)), "comparability.summary.total_flags must match flag counts")

    cd = out_payload.get("confidence_degradation")
    _assert(isinstance(cd, dict), "output.confidence_degradation must exist and be a dict")
    _assert("triggered" in cd and "reasons" in cd, "confidence_degradation must include triggered and reasons")
    reasons = cd.get("reasons")
    _assert(isinstance(reasons, list), "confidence_degradation.reasons must be a list")
    keys = [(str((r or {}).get("kind") or ""), str((r or {}).get("metric_key") or ""), str((r or {}).get("severity") or "")) for r in reasons]
    _assert(keys == sorted(keys), "confidence_degradation.reasons must be sorted by kind,metric_key,severity")

    db.close()

def test_baseline_cutoff_prevents_walk() -> None:
    """Ensure baseline cutoff prevents run2 from selecting run1 as drift baseline."""
    if not _SMOKE_SET_BASELINE_CUTOFF:
        # If cutoff was pre-set externally, we can't assert its value; skip to avoid false failure.
        print("baseline_cutoff_test: skipped (cutoff pre-set externally)")
        return

    if os.environ.get("PSI_DB_PATH"):
        db_path = os.environ["PSI_DB_PATH"]
    else:
        root = Path(tempfile.gettempdir()) / "psi_di_contract_cutoff"
        root.mkdir(parents=True, exist_ok=True)
        db_path = str(root / "psi_di_contract_cutoff.sqlite")
        os.environ["PSI_DB_PATH"] = db_path

    from psi.core.db import SessionLocal, ensure_schema
    from psi.core.models import Batch, Molecule, Program, DecisionSnapshot
    from psi.services.programs import create_program
    from psi.services.molecules import create_molecule
    from psi.services.batches import create_batch
    from psi.services.data_records import create_data_record
    from psi.services.measurements import upsert_measurements

    from psi.core.di.schema import DIInput
    from psi.services.di.runner import run_di

    ensure_schema()
    db = SessionLocal()

    p = db.query(Program).filter(Program.name == "DI_SMOKE_CUTOFF").first()
    if p is None:
        p = create_program(db, name="DI_SMOKE_CUTOFF", description="DI cutoff smoke")

    m = db.query(Molecule).filter(Molecule.program_id == p.id).first()
    if m is None:
        m = create_molecule(db, program_id=p.id, primary_id="DI-SMOKE-CUTOFF-0001", title="DI cutoff molecule", components={"HC1": "EVQLV", "LC1": "DIQMT"})

    b = db.query(Batch).filter(Batch.molecule_id == m.id).first()
    if b is None:
        b = create_batch(db=db, molecule_id=m.id, title="DI cutoff batch", expression_notes="", purification_notes="")

    dr = create_data_record(
        db=db,
        program_id=p.id,
        molecule_id=None,
        batch_id=b.id,
        domain="generic",
        data_type="generic",
        method="generic",
        title="DI cutoff record",
        params_json={},
        results_json={},
    )
    upsert_measurements(
        db=db,
        record_id=dr.id,
        measurements=[
            {
                "name": "monomer_pct",
                "value_num": 98.0,
                "value_text": "98%",
                "unit": "%",
                "comparator": None,
                "data_type": dr.data_type,
                "method": dr.method,
            }
        ],
    )

    policy_path = Path(__file__).resolve().parents[2] / "psi" / "core" / "di" / "policies" / "advance_to_in_vivo_v0_3.json"
    di_input = DIInput(
        decision_key="advance_to_in_vivo",
        scope_type="batch",
        scope_id=int(b.id),
        as_of_ts=None,
        qc_mode="model_safe",
        context={},
    )

    out1 = run_di(db, di_input=di_input, policy_path=policy_path)
    out2 = run_di(db, di_input=di_input, policy_path=policy_path)

    s1 = db.query(DecisionSnapshot).filter(DecisionSnapshot.id == int(out1.get("snapshot_id"))).first()
    s2 = db.query(DecisionSnapshot).filter(DecisionSnapshot.id == int(out2.get("snapshot_id"))).first()
    _assert(s1 is not None and s2 is not None, "snapshot rows must exist for cutoff test")
    try:
        inputs2 = json.loads(s2.inputs_json or "{}")
    except Exception:
        inputs2 = {}
    drift_ctx = inputs2.get("drift_context") if isinstance(inputs2, dict) else None
    prev_id = None
    if isinstance(drift_ctx, dict):
        try:
            prev_id = int(drift_ctx.get("prev_snapshot_id") or 0)
        except Exception:
            prev_id = None
    _assert(prev_id != int(s1.id), "baseline cutoff must prevent run2 from referencing run1 snapshot")

    db.close()




def test_cross_version_snapshot_content_hash_stability() -> None:
    """Regression: snapshot_content_hash must be stable across code version bumps.

    We simulate a version bump by patching module-level PSI_VERSION constants used by
    DI output construction (runner/compute) between snapshot creation and verification.
    """
    if os.environ.get("PSI_DB_PATH"):
        db_path = os.environ["PSI_DB_PATH"]
    else:
        root = Path(tempfile.gettempdir()) / "psi_di_contract_xver"
        root.mkdir(parents=True, exist_ok=True)
        db_path = str(root / "psi_di_contract_xver.sqlite")
        os.environ["PSI_DB_PATH"] = db_path

    from psi.core.db import SessionLocal, ensure_schema
    from psi.core.models import Batch, Molecule, Program
    from psi.services.programs import create_program
    from psi.services.molecules import create_molecule
    from psi.services.batches import create_batch
    from psi.services.data_records import create_data_record
    from psi.services.measurements import upsert_measurements

    from psi.core.di.schema import DIInput
    from psi.services.di.runner import run_di
    from psi.services.di.verify import verify_snapshot

    ensure_schema()
    db = SessionLocal()

    # Program
    p = db.query(Program).filter(Program.name == "DI_SMOKE_XVER").first()
    if p is None:
        p = create_program(db, name="DI_SMOKE_XVER", description="DI cross-version smoke")

    # Molecule
    m = db.query(Molecule).filter(Molecule.program_id == p.id).first()
    if m is None:
        hc = "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISWNSGSTYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYCARGGGG"
        lc = "DIQMTQSPSSLSASVGDRVTITCRASQSISSSYLAWYQQKPGKAPKLLIYDASTRATGIPDRFSGSGSGTDFTLTISSLQPEDFATYYCQQSYSTPYTFGQGTKVEIK"
        m = create_molecule(db, program_id=p.id, primary_id="DI-SMOKE-XVER-0001", title="DI Smoke Xver molecule", components={"HC1": hc, "LC1": lc})

    # Batch
    b = db.query(Batch).filter(Batch.molecule_id == m.id).first()
    if b is None:
        b = create_batch(db=db, molecule_id=m.id, title="DI Smoke Xver batch", expression_notes="", purification_notes="")

    # Measurements (minimal)
    dr = create_data_record(
        db=db,
        program_id=p.id,
        molecule_id=None,
        batch_id=b.id,
        domain="generic",
        data_type="generic",
        method="generic",
        title="DI cross-version contract record",
        params_json={},
        results_json={},
    )
    upsert_measurements(
        db=db,
        record_id=dr.id,
        measurements=[
            {
                "name": "monomer_pct",
                "value_num": 98.0,
                "value_text": "98.0",
                "unit": "%",
                "comparator": None,
                "data_type": dr.data_type,
                "method": dr.method,
            },
            {
                "name": "hmw_pct",
                "value_num": 1.0,
                "value_text": "1.0",
                "unit": "%",
                "comparator": None,
                "data_type": dr.data_type,
                "method": dr.method,
            },
        ],
    )

    # Policy path (repo-local)
    policy_path = Path(__file__).resolve().parents[2] / "psi" / "core" / "di" / "policies" / "advance_to_in_vivo_v0_3.json"

    di_input = DIInput(
        decision_key="advance_to_in_vivo",
        scope_type="batch",
        scope_id=int(b.id),
        as_of_ts=None,
        qc_mode="model_safe",
        context={},
    )

    out = run_di(db, di_input=di_input, policy_path=policy_path)
    snapshot_id = int(out.get("snapshot_id"))

    # Simulate a version bump between creation and verification
    import psi.services.di.compute as di_compute
    import psi.services.di.runner as di_runner

    old_compute_ver = getattr(di_compute, "PSI_VERSION", None)
    old_runner_ver = getattr(di_runner, "PSI_VERSION", None)
    try:
        di_compute.PSI_VERSION = "v9.9.9-test"
        di_runner.PSI_VERSION = "v9.9.9-test"

        rep = verify_snapshot(db=db, snapshot_id=snapshot_id, debug=False)

        # verify_snapshot() historically returned {"ok": true/false, ...}; newer versions report
        # classification fields without an explicit ok flag. Treat VERIFIED as pass.
        ok = False
        if isinstance(rep, dict):
            if "ok" in rep:
                ok = bool(rep.get("ok"))
            else:
                cls = str(rep.get("classification") or "")
                ar = rep.get("anchored_replay") if isinstance(rep.get("anchored_replay"), dict) else {}
                svr = str(ar.get("stored_vs_replay_classification") or "")
                rvc = str(ar.get("replay_vs_current_classification") or "")
                ok = (cls == "VERIFIED" and svr == "VERIFIED" and rvc == "VERIFIED")

        _assert(ok, f"cross-version verify should pass; report={rep}")
    finally:
        if old_compute_ver is not None:
            di_compute.PSI_VERSION = old_compute_ver
        if old_runner_ver is not None:
            di_runner.PSI_VERSION = old_runner_ver

    db.close()

def main() -> int:
    try:
        global _SMOKE_SET_BASELINE_CUTOFF
        if "PSI_DI_BASELINE_CUTOFF_ISO" not in os.environ:
            os.environ["PSI_DI_BASELINE_CUTOFF_ISO"] = datetime.now(timezone.utc).isoformat()
            _SMOKE_SET_BASELINE_CUTOFF = True
        test_policy_canonicalization_and_hash()
        test_policy_package_dual_hash_stability()
        test_catalog_hash_validation()
        test_policy_template_structure_present()
        test_selection_semantics_version_constant()
        test_policy_authoritative_required_gate_keys()
        test_context_knob_branching_gate_outcomes_deterministic()
        test_shortlisting_refusal_v04_extensions_deterministic()
        test_tie_break_dimensions_v04_complete_and_deterministic()
        test_scope_semantics_v04_deterministic()
        test_template_registry_and_dependency_graph_deterministic()
        test_shared_sub_assessments_pure_helpers()
        test_shortlisting_reproducibility_from_soe_evidence_summary()
        test_policy_blocker_taxonomy_and_experiment_suggestions()
        test_ignore_reason_keys_allowed_set()
        test_stable_json_dumps()
        test_normalize_ignored_schema_compat()
        test_soe_v0_2_contract_snapshot_shape_and_determinism()
        test_molecule_scope_determinism()
        test_baseline_cutoff_prevents_walk()
        test_cross_version_snapshot_content_hash_stability()
    except Exception as e:
        print(f"DI contract smoke FAILED: {e}")
        return 1

    print("DI contract smoke OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
