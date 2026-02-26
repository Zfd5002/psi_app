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
import io
import warnings
from contextlib import redirect_stderr

from datetime import datetime, timezone
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from psi.core.di.catalog import build_experiment_risk_flag_index, load_catalog
from psi.core.di.policy import canonical_policy_json, load_policy, sha256_hex_of_canonical_json
from psi.core.utils import stable_json_dumps
from psi.services import decisions as decisions_svc
from psi.services.di.compute import _build_scope_semantics, _normalize_ignored
from psi.services.di.eval import derive_gate_outcomes, derive_readiness, derive_shortlisting
from psi.services.di.risk_flags import derive_risk_flags_enriched
from psi.services.di.selectors import ALLOWED_IGNORE_REASON_KEYS
from psi.services.di.runner import DI_SELECTION_SEMANTICS_VERSION
from psi.services.di.sub_assessments import (
    baseline_risk_flags_from_used,
    comparability_qc_coherence_summary,
    decision_state_from_gate_statuses,
    material_readiness_rationale,
    mechanism_readiness_rationale,
    reproducibility_signal_from_soe,
)
from psi.services.di.templates.registry import list_template_keys_sorted, template_dependency_graph
from psi.services.di.util import value_functions_enforcement_reason


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


def _render_di_run_template_smoke(ctx: dict) -> str:
    repo_root = Path(__file__).resolve().parents[2]
    tpl_dir = repo_root / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(tpl_dir)))
    tmpl = env.get_template("di/run.html")
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


def test_value_functions_enforcement_reason_helper() -> None:
    _assert(
        value_functions_enforcement_reason(
            applicable=True,
            policy_flag_enabled=True,
            evaluator_version_expected="di.eval.v1",
            evaluator_version_actual="di.eval.v1",
        ) == "active",
        "enforcement reason should be active on exact evaluator version match",
    )
    _assert(
        value_functions_enforcement_reason(
            applicable=True,
            policy_flag_enabled=False,
            evaluator_version_expected="di.eval.v1",
            evaluator_version_actual="di.eval.v1",
        ) == "policy_flag_off",
        "enforcement reason should be policy_flag_off when template policy flag disabled",
    )
    _assert(
        value_functions_enforcement_reason(
            applicable=True,
            policy_flag_enabled=True,
            evaluator_version_expected="di.eval.v1",
            evaluator_version_actual="di.eval.v2",
        ) == "evaluator_version_mismatch",
        "enforcement reason should report evaluator_version_mismatch deterministically",
    )
    _assert(
        value_functions_enforcement_reason(
            applicable=False,
            policy_flag_enabled=True,
            evaluator_version_expected="di.eval.v1",
            evaluator_version_actual="di.eval.v1",
        ) == "not_applicable",
        "enforcement reason should be not_applicable when signal is not applicable",
    )


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


def test_experiment_catalog_v0_2_latest_loader_and_risk_mapping() -> None:
    from psi.core.di.catalog import load_experiment_catalog_latest, load_experiment_catalog_v0_2

    cat2 = load_experiment_catalog_v0_2()
    latest = load_experiment_catalog_latest()
    _assert(cat2.catalog_id == "experiment_catalog_v0_2", "experiment v0.2 catalog_id mismatch")
    _assert(cat2.catalog_version == "v0.2", "experiment v0.2 catalog_version mismatch")
    _assert(latest.catalog_version == "v0.2", "latest experiment catalog loader must select v0.2 deterministically")

    exps = cat2.catalog.get("experiments") if isinstance(cat2.catalog, dict) else []
    _assert(isinstance(exps, list) and bool(exps), "experiment catalog v0.2 experiments must be present")
    for i, e in enumerate(exps):
        _assert(isinstance(e, dict), f"experiment v0.2 experiments[{i}] must be object")
        rr = e.get("resolves_risk_flags")
        _assert(isinstance(rr, list), f"experiment v0.2 experiments[{i}].resolves_risk_flags must be list")
        _assert(all(isinstance(x, str) and x for x in rr), f"experiment v0.2 experiments[{i}].resolves_risk_flags values must be non-empty strings")
        _assert(rr == sorted(set(rr)), f"experiment v0.2 experiments[{i}].resolves_risk_flags must be sorted duplicate-free")

    idx1 = build_experiment_risk_flag_index(catalog=cat2.catalog)
    idx2 = build_experiment_risk_flag_index(catalog=json.loads(cat2.canonical_json))
    _assert(idx1 == idx2, "risk-flag index builder must be deterministic for canonical-equivalent catalog content")
    for rf, eks in sorted(idx1.items()):
        _assert(isinstance(rf, str) and rf, "risk-flag index keys must be non-empty strings")
        _assert(eks == sorted(set(eks)), f"risk-flag index values for {rf} must be sorted duplicate-free")


def test_policy_template_structure_present() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    pol_path = repo_root / "psi" / "core" / "di" / "policies" / "advance_to_in_vivo_v0_1.json"
    pol = load_policy(pol_path)

    ts = (pol.package or {}).get("template_structure")
    _assert(isinstance(ts, dict), "template_structure must be present in policy package")

    for k in ("context_knobs", "gate_categories", "risk_flag_categories", "blocker_taxonomy"):
        _assert(k in ts, f"template_structure.{k} missing")
        _assert(isinstance(ts.get(k), list), f"template_structure.{k} must be a list")


def test_policy_risk_flag_severity_tiers_present_and_cover_expected_flags() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    pol_dir = repo_root / "psi" / "core" / "di" / "policies"
    allowed = {"high", "medium", "moderate", "low"}
    common_expected = {
        "context_missing",
        "coverage_gap",
        "interpretation_gap",
        "method_incomparable",
        "missing_required_metric",
        "outlier_present",
        "qc_uncertainty",
        "threshold_violation",
    }
    advance_extra = {"internalization_sensitive_binding_gap"}

    for p in sorted(pol_dir.glob("*.json")):
        pol = load_policy(p)
        pkg = pol.package if isinstance(pol.package, dict) else {}
        ts = pkg.get("template_structure") if isinstance(pkg.get("template_structure"), dict) else {}
        tiers = ts.get("risk_flag_severity_tiers") if isinstance(ts.get("risk_flag_severity_tiers"), dict) else {}
        _assert(bool(tiers), f"{p.name}: template_structure.risk_flag_severity_tiers must be present")
        body_tiers = (pol.policy_body or {}).get("risk_flag_severity_tiers") if isinstance(pol.policy_body, dict) else {}
        if str(pol.template_key or "").startswith("advance_to_in_vivo.") or str(pol.template_key or "") == "ready_for_scaleup_screen.v0_1":
            _assert(isinstance(body_tiers, dict) and bool(body_tiers), f"{p.name}: policy_body.risk_flag_severity_tiers must be present (w108 governance surface)")
            _assert(dict(body_tiers) == dict(tiers), f"{p.name}: policy_body risk_flag_severity_tiers must match template_structure copy")
        keys = [str(k) for k in tiers.keys()]
        _assert(keys == sorted(keys), f"{p.name}: severity tier keys must be stably sorted in file order")
        for k, v in sorted(tiers.items()):
            _assert(isinstance(k, str) and k, f"{p.name}: severity tier key must be non-empty string")
            _assert(str(v) in allowed, f"{p.name}: severity tier for {k} must be one of {sorted(allowed)}")
        expected = set(common_expected)
        if str(pol.template_key or "").startswith("advance_to_in_vivo."):
            expected |= advance_extra
        missing = sorted([k for k in expected if k not in tiers])
        _assert(not missing, f"{p.name}: missing risk flag severity tiers for {missing}")


def test_risk_flag_enrichment_uses_policy_severity_tiers_deterministically() -> None:
    pol_pkg = {
        "template_structure": {
            "risk_flag_severity_tiers": {
                "custom_flag": "low",
                "outlier_present": "moderate",
            }
        }
    }
    pol_body = {
        "gates": {},
        "risk_flag_severity_tiers": {
            "custom_flag": "high",
            "outlier_present": "moderate",
        },
    }
    risk_flags = [{"risk_flag": "outlier_present"}, {"risk_flag": "custom_flag"}]
    out1 = derive_risk_flags_enriched(
        risk_flags=risk_flags,
        used_by_metric={},
        policy_body=pol_body,
        policy_package=pol_pkg,
    )
    out2 = derive_risk_flags_enriched(
        risk_flags=list(reversed(risk_flags)),
        used_by_metric={},
        policy_body=pol_body,
        policy_package=pol_pkg,
    )
    _assert(stable_json_dumps(out1) == stable_json_dumps(out2), "risk flag enrichment must be deterministic independent of input order")
    sev_by_key = {str((x or {}).get("key") or ""): str((x or {}).get("severity") or "") for x in out1 if isinstance(x, dict)}
    _assert(sev_by_key.get("custom_flag") == "high", "policy_body severity tiers must take precedence over template_structure copy")
    _assert(
        sev_by_key.get("outlier_present") in {"moderate", "medium"},
        "policy severity tiers must preserve/normalize outlier_present severity deterministically",
    )


def test_risk_flag_enrichment_unknown_key_defaults_to_unspecified_neutral() -> None:
    out = derive_risk_flags_enriched(
        risk_flags=[{"risk_flag": "unknown_new_flag"}],
        used_by_metric={},
        policy_body={"gates": {}, "risk_flag_severity_tiers": {}},
        policy_package=None,
    )
    _assert(len(out) == 1, "unknown risk flag should still be emitted")
    _assert(str((out[0] or {}).get("severity") or "") == "unspecified", "unknown risk flag severity fallback must be unspecified (neutral)")


def test_di_snapshot_ui_risk_flag_severity_rendering_deterministic() -> None:
    ctx = {
        "snap": {"decision_key": "advance_to_in_vivo", "id": 1},
        "output": {
            "decision_state": "ready",
            "risk_flags_enriched": [
                {"key": "qc_uncertainty", "severity": "moderate"},
                {"key": "interpretation_gap", "severity": "high"},
            ],
        },
        "inputs": {},
        "di_snapshot_ui": {"gate_outcomes_ordered": [], "outcomes_ordered": [], "error_block": {"present": False}},
    }
    html1 = _render_di_snapshot_template_smoke(ctx)
    html2 = _render_di_snapshot_template_smoke(ctx)
    _assert(html1 == html2, "DI snapshot UI render must be deterministic for identical context")
    _assert("severity=moderate" in html1 and "severity=high" in html1, "DI snapshot UI should render risk severity tiers distinctly")


def test_di_run_view_toggle_ui_is_localstorage_only() -> None:
    ctx = {
        "error": None,
        "heavy_compute_enabled": False,
        "heavy_compute_banner": "Heavy Compute: OFF (default). Does not affect DI snapshot hashes.",
        "selected_scope_type": "batch",
        "decision_keys": ["advance_to_in_vivo"],
        "selected_decision_key": "advance_to_in_vivo",
        "policies": [{"path": "/tmp/policy.json", "decision_key": "advance_to_in_vivo", "policy_version": "v0.3", "policy_name": "advance_to_in_vivo"}],
        "selected_policy_path": "/tmp/policy.json",
        "batches": [],
        "molecules": [],
        "selected_batch_id": None,
        "selected_molecule_id": None,
    }
    html = _render_di_run_template_smoke(ctx)
    _assert("psi.di.run.view_mode" in html, "DI run page should persist view toggle in localStorage")
    _assert("name=\"decision_key\"" in html and "name=\"policy_path\"" in html and "name=\"qc_mode\"" in html, "DI run toggle UI must not remove DI form inputs")
    _assert("does not change DI inputs, outputs, or snapshot hashes" in html, "DI run governance note should state hash/input isolation")
    _assert("Heavy Compute: OFF (default). Does not affect DI snapshot hashes." in html, "heavy compute banner should render deterministically on DI run page")
    _assert(html.count("data-di-panel=\"scientist\"") == 1 and html.count("data-di-panel=\"governance\"") == 1, "view panels should remain deterministic and separate from shared heavy compute banner")


def test_heavy_compute_banner_text_shared_helper_deterministic() -> None:
    from psi.services.di.util import heavy_compute_banner_text

    off = heavy_compute_banner_text(enabled=False)
    on = heavy_compute_banner_text(enabled=True)
    _assert(off == "Heavy Compute: OFF (default, PSI_HEAVY_COMPUTE=0). Does not affect DI snapshot hashes.", "heavy compute OFF banner text mismatch")
    _assert(on == "Heavy Compute: ON (PSI_HEAVY_COMPUTE=1). Does not affect DI snapshot hashes.", "heavy compute ON banner text mismatch")


def test_drift_plain_english_translation_deterministic() -> None:
    from psi.services.decisions import _drift_plain_english_from_output

    out = {"drift_type": "EVIDENCE_ONLY"}
    t1 = _drift_plain_english_from_output(out)
    t2 = _drift_plain_english_from_output({"drift_type": "EVIDENCE_ONLY"})
    _assert(t1 == t2 == "Evidence changed, but policy semantics did not change.", "drift translation must be deterministic and stable")


def test_di_web_latest_policy_selection_prefers_forward_immutable_forks() -> None:
    from psi.services.di.web import latest_policy_for_decision

    adv = latest_policy_for_decision("advance_to_in_vivo") or {}
    scale = latest_policy_for_decision("ready_for_scaleup_screen") or {}
    _assert(str(adv.get("policy_version") or "") == "v0.5", "advance_to_in_vivo latest policy should resolve to immutable forward fork v0.5")
    _assert(str(scale.get("policy_version") or "") == "v0.2", "ready_for_scaleup_screen latest policy should resolve to immutable forward fork v0.2")


def test_policy_immutability_manifest_matches_policy_files() -> None:
    from psi.tools.policy_immutability_check import validate_policy_immutability

    report = validate_policy_immutability()
    _assert(bool(report.get("ok")), f"policy immutability manifest mismatch: {stable_json_dumps(report)}")


def test_policy_registry_manifest_matches_package_hashes() -> None:
    from pathlib import Path
    from psi.core.di.policy import load_policy

    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = repo_root / "psi" / "core" / "di" / "policy_registry_manifest.json"
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = raw.get("entries") if isinstance(raw, dict) else None
    _assert(isinstance(entries, list) and bool(entries), "policy registry manifest entries must be present")
    paths = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        rel = str(e.get("path") or "").strip()
        fn = str(e.get("filename") or "").strip()
        paths.append(rel or f"psi/core/di/policies/{fn}")
    _assert(paths == sorted(paths), "policy registry manifest entries must be path-sorted")
    for e in entries:
        _assert(isinstance(e, dict), "policy registry manifest entry must be object")
        rel = str(e.get("path") or "").strip()
        fn = str(e.get("filename") or "")
        _assert(fn, "policy registry manifest filename required")
        pol_path = (repo_root / rel) if rel else (repo_root / "psi" / "core" / "di" / "policies" / fn)
        _assert(pol_path.is_file(), f"policy registry manifest path missing: {pol_path}")
        pol = load_policy(pol_path)
        _assert(str(e.get("policy_version") or "") == str(pol.version or ""), f"{fn}: policy_version mismatch in registry manifest")
        _assert(str(e.get("policy_package_hash") or "") == str(pol.policy_package_hash or ""), f"{fn}: policy_package_hash mismatch in registry manifest")


def test_policy_strict_versioned_path_resolution() -> None:
    from pathlib import Path
    from psi.core.di.policy import resolve_versioned_policy_path

    pdir = Path(__file__).resolve().parents[2] / "psi" / "core" / "di" / "policies"
    p = resolve_versioned_policy_path(policy_dir=pdir, policy_name="advance_to_in_vivo", policy_version="v0.5")
    _assert(p.name == "advance_to_in_vivo_v0_5.json", "strict policy resolver should map v0.5 to exact filename")


def test_policy_registry_contains_forward_default_policy_hashes() -> None:
    from pathlib import Path
    from psi.core.di.policy import load_policy

    root = Path(__file__).resolve().parents[2] / "psi"
    manifest = json.loads((root / "core" / "di" / "policy_registry_manifest.json").read_text(encoding="utf-8"))
    entries = manifest.get("entries") if isinstance(manifest, dict) else []
    hashes = {str((e or {}).get("policy_package_hash") or "") for e in entries if isinstance(e, dict)}
    adv = load_policy(root / "core" / "di" / "policies" / "advance_to_in_vivo_v0_5.json")
    scale = load_policy(root / "core" / "di" / "policies" / "ready_for_scaleup_screen_v0_2.json")
    _assert(str(adv.policy_package_hash) in hashes, "policy registry manifest must include advance_to_in_vivo_v0_5 package hash")
    _assert(str(scale.policy_package_hash) in hashes, "policy registry manifest must include ready_for_scaleup_screen_v0_2 package hash")


def test_policy_hash_audit_report_deterministic() -> None:
    from psi.tools.policy_hash_audit import build_policy_hash_audit_report

    r1 = build_policy_hash_audit_report(snapshot_limit=5)
    r2 = build_policy_hash_audit_report(snapshot_limit=5)
    _assert(stable_json_dumps(r1) == stable_json_dumps(r2), "policy hash audit report must be deterministic for fixed DB")


def test_risk_flag_enrichment_ordering_stable_with_medium_and_legacy_moderate() -> None:
    pol_body = {
        "gates": {},
        "risk_flag_severity_tiers": {
            "z_low": "low",
            "a_high": "high",
            "m_med": "medium",
            "b_mod": "moderate",
        },
    }
    inp = [
        {"risk_flag": "z_low"},
        {"risk_flag": "m_med"},
        {"risk_flag": "a_high"},
        {"risk_flag": "b_mod"},
    ]
    out1 = derive_risk_flags_enriched(risk_flags=inp, used_by_metric={}, policy_body=pol_body, policy_package=None)
    out2 = derive_risk_flags_enriched(risk_flags=list(reversed(inp)), used_by_metric={}, policy_body=pol_body, policy_package=None)
    _assert(stable_json_dumps(out1) == stable_json_dumps(out2), "risk flag enrichment ordering must be deterministic with medium/moderate vocabulary mix")
    keys = [str((x or {}).get("key") or "") for x in out1]
    _assert(keys == ["a_high", "b_mod", "m_med", "z_low"], f"unexpected risk flag deterministic ordering: {keys}")


def test_policy_blocker_suggestions_mapping_key_order_stable() -> None:
    from pathlib import Path
    from psi.core.di.policy import load_policy

    pdir = Path(__file__).resolve().parents[2] / "psi" / "core" / "di" / "policies"
    for p in sorted(pdir.glob("*.json")):
        pol = load_policy(p)
        body = pol.policy_body if isinstance(pol.policy_body, dict) else {}
        sugg = body.get("blocker_suggestions")
        if not isinstance(sugg, dict):
            continue
        keys = [str(k) for k in sugg.keys()]
        _assert(keys == sorted(keys), f"{p.name}: blocker_suggestions keys must be stably sorted in file order")


def test_policy_gate_lists_no_duplicates_and_stable_file_order() -> None:
    from pathlib import Path
    from psi.core.di.policy import load_policy

    pdir = Path(__file__).resolve().parents[2] / "psi" / "core" / "di" / "policies"
    for p in sorted(pdir.glob('*.json')):
        pol = load_policy(p)
        body = pol.policy_body if isinstance(pol.policy_body, dict) else {}
        for key in ("gate_order", "required_gate_keys"):
            vals = body.get(key)
            if not isinstance(vals, list):
                continue
            norm = [str(x) for x in vals]
            _assert(len(norm) == len(set(norm)), f"{p.name}: {key} must be duplicate-free")
            _assert(norm == [str(x) for x in vals], f"{p.name}: {key} order must be stable on repeated read")


def test_policy_freeze_sidecar_covers_legacy_policy_files_without_mutating_json() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "psi" / "core" / "di"
    sidecar = json.loads((root / "policy_metadata_freeze.json").read_text(encoding="utf-8"))
    policies = sidecar.get("policies") if isinstance(sidecar, dict) else None
    _assert(isinstance(policies, list) and bool(policies), "policy freeze sidecar must contain policy entries")
    notice = str(sidecar.get("freeze_notice") or "")
    _assert("IMMUTABLE" in notice and "SNAPSHOT REFERENCED" in notice, "policy freeze sidecar notice text mismatch")
    covered = sorted(str((p or {}).get("filename") or "") for p in policies if isinstance(p, dict) and bool((p or {}).get("immutable")))
    expected = sorted([
        "advance_to_in_vivo_v0_1.json",
        "advance_to_in_vivo_v0_2.json",
        "advance_to_in_vivo_v0_3.json",
        "advance_to_in_vivo_v0_4.json",
        "ready_for_scaleup_screen_v0_1.json",
    ])
    _assert(covered == expected, f"policy freeze sidecar legacy coverage mismatch: {covered}")


def test_forward_policy_forks_use_medium_vocabulary_and_no_legacy_moderate() -> None:
    from pathlib import Path

    pdir = Path(__file__).resolve().parents[2] / "psi" / "core" / "di" / "policies"
    targets = [
        pdir / "advance_to_in_vivo_v0_5.json",
        pdir / "ready_for_scaleup_screen_v0_2.json",
    ]
    for p in targets:
        txt = p.read_text(encoding="utf-8")
        _assert('"medium"' in txt, f"{p.name}: expected forward medium severity vocabulary")
        _assert('"moderate"' not in txt, f"{p.name}: legacy moderate vocabulary must not appear in forward fork")


def test_progress_policy_catalog_v0_1_loads_and_validates() -> None:
    from psi.core.di.catalog import load_progress_policy_latest, load_progress_policy_v0_1, load_progress_policy_v0_2

    pol = load_progress_policy_v0_1()
    _assert(pol.policy_id == "progress_policy_v0_1", "progress policy id mismatch")
    _assert(pol.policy_version == "v0.1", "progress policy version mismatch")
    body = pol.policy if isinstance(pol.policy, dict) else {}
    early = body.get("early_milestones") if isinstance(body.get("early_milestones"), dict) else {}
    di_m = body.get("di_milestones") if isinstance(body.get("di_milestones"), dict) else {}
    _assert(bool(early), "progress policy early_milestones must be present")
    _assert(bool(di_m), "progress policy di_milestones must be present")
    _assert(early.get("expression_present") == ["expr_yield_mgL"], "progress policy must include expression_present milestone mapping")
    _assert(early.get("purification_present") == ["purity_percent"], "progress policy must include purification_present milestone mapping")
    for mk, vals in sorted(early.items()):
        _assert(isinstance(vals, list), f"early milestone {mk} must be list")
        _assert(all(isinstance(x, str) and x for x in vals), f"early milestone {mk} values must be non-empty strings")
        _assert(len(vals) == len(set(vals)), f"early milestone {mk} list must be duplicate-free")
    for mk, tv in sorted(di_m.items()):
        _assert(isinstance(tv, str) and tv, f"di milestone {mk} must map to non-empty template key")

    pol_v2 = load_progress_policy_v0_2()
    body_v2 = pol_v2.policy if isinstance(pol_v2.policy, dict) else {}
    di_v2 = body_v2.get("di_milestones") if isinstance(body_v2.get("di_milestones"), dict) else {}
    _assert(di_v2.get("in_vivo_ready") == "advance_to_in_vivo.v0_5", "progress policy v0_2 should reference current in_vivo template")
    _assert(di_v2.get("scaleup_ready") == "ready_for_scaleup_screen.v0_2", "progress policy v0_2 should reference current scaleup template")

    latest_1 = load_progress_policy_latest()
    latest_2 = load_progress_policy_latest()
    _assert(latest_1.source_name == latest_2.source_name == "progress_policy_v0_2.json", "progress policy latest loader must deterministically select v0_2")
    _assert(latest_1.policy_hash == latest_2.policy_hash, "progress policy latest loader hash must be deterministic")


def test_shortlisting_policy_catalog_v0_1_weights_schema_and_values() -> None:
    p = Path(__file__).resolve().parents[2] / "psi" / "core" / "di" / "catalogs" / "shortlisting_policy_v0_1.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    _assert(str(raw.get("policy_id") or "") == "shortlisting_policy_v0_1", "shortlisting policy id mismatch")
    _assert(str(raw.get("policy_version") or "") == "v0.1", "shortlisting policy version mismatch")
    rw = raw.get("ranking_weights") if isinstance(raw.get("ranking_weights"), dict) else {}
    _assert(set(rw.keys()) == {"batch_scope", "molecule_scope"}, "shortlisting policy ranking_weights scopes mismatch")
    batch = rw.get("batch_scope") if isinstance(rw.get("batch_scope"), dict) else {}
    mol = rw.get("molecule_scope") if isinstance(rw.get("molecule_scope"), dict) else {}
    _assert(list(batch.keys()) == sorted(batch.keys()), "shortlisting policy batch_scope keys must be sorted")
    _assert(list(mol.keys()) == sorted(mol.keys()), "shortlisting policy molecule_scope keys must be sorted")
    allowed_batch = {"decision_state_pro", "decision_state_con", "blockers_count", "comparability_high_severity", "metrics_present", "metrics_missing", "warnings_count"}
    allowed_mol = {"metrics_sourced_count", "used_metric_count", "ignored_count", "warning_count"}
    _assert(set(batch.keys()) == allowed_batch, "shortlisting policy batch_scope allowed keys mismatch")
    _assert(set(mol.keys()) == allowed_mol, "shortlisting policy molecule_scope allowed keys mismatch")
    for k, v in sorted(batch.items()):
        _assert(isinstance(v, (int, float)), f"shortlisting policy batch weight {k} must be numeric")
    for k, v in sorted(mol.items()):
        _assert(isinstance(v, (int, float)), f"shortlisting policy molecule weight {k} must be numeric")


def test_progress_policy_metric_keys_are_representable_in_measurement_registry() -> None:
    from psi.core.di.catalog import load_progress_policy_latest, load_progress_policy_v0_1
    from psi.core import registry as core_registry

    registry_field_keys: set[str] = set()
    schemas = core_registry.DATA_SCHEMAS if isinstance(getattr(core_registry, "DATA_SCHEMAS", None), dict) else {}
    for dt_key in sorted(schemas.keys()):
        methods = schemas.get(dt_key) if isinstance(schemas.get(dt_key), dict) else {}
        for method_key in sorted(methods.keys()):
            method = methods.get(method_key) if isinstance(methods.get(method_key), dict) else {}
            for fld_key in ("params_fields", "results_fields"):
                fields = method.get(fld_key) if isinstance(method.get(fld_key), list) else []
                for fld in fields:
                    if not isinstance(fld, dict):
                        continue
                    k = str(fld.get("key") or "").strip()
                    if k:
                        registry_field_keys.add(k)

    missing: list[str] = []
    for pol in (load_progress_policy_v0_1(), load_progress_policy_latest()):
        body = pol.policy if isinstance(pol.policy, dict) else {}
        early = body.get("early_milestones") if isinstance(body.get("early_milestones"), dict) else {}
        for milestone_key in sorted(early.keys()):
            vals = early.get(milestone_key) if isinstance(early.get(milestone_key), list) else []
            for mk in sorted(str(x) for x in vals if str(x).strip()):
                if mk not in registry_field_keys:
                    missing.append(mk)

    _assert(not missing, f"progress policy metric keys must be representable in measurement registry fields: {sorted(set(missing))}")


def test_template_prerequisites_catalog_v0_1_loads_and_validates() -> None:
    from pathlib import Path

    from psi.core.di.catalog import (
        load_progress_policy_latest,
        load_progress_policy_v0_1,
        load_template_prerequisites,
        load_template_prerequisites_latest,
        load_template_prerequisites_v0_1,
    )

    pol = load_template_prerequisites_v0_1()
    body = pol.policy if isinstance(pol.policy, dict) else {}
    mappings = body.get("template_prerequisites") if isinstance(body.get("template_prerequisites"), dict) else {}
    _assert(bool(mappings), "template prerequisites mapping must be present")
    for tk, deps in sorted(mappings.items()):
        _assert(isinstance(tk, str) and tk, "template prerequisite key must be non-empty string")
        _assert(isinstance(deps, list), f"template_prerequisites[{tk}] must be list")
        _assert(all(isinstance(x, str) and x for x in deps), f"template_prerequisites[{tk}] values must be non-empty strings")
        _assert(len(deps) == len(set(deps)), f"template_prerequisites[{tk}] must be duplicate-free")

    # Deterministic latest-loader selection (future-proof for additive catalog versions).
    latest_1 = load_template_prerequisites_latest()
    latest_2 = load_template_prerequisites_latest()
    _assert(latest_1.source_name == latest_2.source_name, "template prerequisites latest loader must be deterministic")
    _assert(latest_1.policy_hash == latest_2.policy_hash, "template prerequisites latest loader hash must be deterministic")

    cat_dir = Path(__file__).resolve().parents[2] / "psi" / "core" / "di" / "catalogs"
    v02_path = cat_dir / "template_prerequisites_v0_2.json"
    if v02_path.exists():
        pol_v02 = load_template_prerequisites(v02_path)
        body_v02 = pol_v02.policy if isinstance(pol_v02.policy, dict) else {}
        mappings_v02 = body_v02.get("template_prerequisites") if isinstance(body_v02.get("template_prerequisites"), dict) else {}
        _assert(bool(mappings_v02), "template_prerequisites_v0_2 must include non-empty template_prerequisites")
        _assert(latest_1.source_name == "template_prerequisites_v0_2.json", "latest loader must prefer highest template prerequisites catalog version")
        mappings_for_coverage = mappings_v02
    else:
        mappings_for_coverage = mappings

    # Molecule header milestone coverage audit: both baseline and latest progress policies must be catalog-covered.
    for prog in (load_progress_policy_v0_1(), load_progress_policy_latest()):
        prog_body = prog.policy if isinstance(prog.policy, dict) else {}
        di_m = prog_body.get("di_milestones") if isinstance(prog_body.get("di_milestones"), dict) else {}
        for milestone_key, template_key in sorted(di_m.items()):
            _assert(
                str(template_key) in mappings_for_coverage,
                f"template prerequisites catalog must cover progress policy DI milestone {milestone_key} -> {template_key}",
            )


def test_confidence_policy_catalog_loads_and_latest_loader_is_deterministic() -> None:
    from psi.core.di.catalog import (
        load_confidence_policy_latest,
        load_confidence_policy_v0_1,
        load_confidence_policy_v0_2,
        load_confidence_policy_v0_3,
    )

    pol_v1 = load_confidence_policy_v0_1()
    body_v1 = pol_v1.policy if isinstance(pol_v1.policy, dict) else {}
    _assert(str(body_v1.get("policy_id") or "") == "confidence_policy_v0_1", "confidence policy v0_1 id mismatch")

    pol_v2 = load_confidence_policy_v0_2()
    body_v2 = pol_v2.policy if isinstance(pol_v2.policy, dict) else {}
    _assert(str(body_v2.get("policy_id") or "") == "confidence_policy_v0_2", "confidence policy v0_2 id mismatch")
    comp_order = body_v2.get("component_order") if isinstance(body_v2.get("component_order"), list) else []
    scalar_rules = body_v2.get("scalar_rules") if isinstance(body_v2.get("scalar_rules"), dict) else {}
    component_rules = body_v2.get("component_rules") if isinstance(body_v2.get("component_rules"), dict) else {}
    _assert(comp_order == ["qc_quality", "reproducibility", "comparability", "interpretability"], "confidence policy component_order mismatch")
    for k in ("high_concern_escalates_to", "medium_concerns_amber_min", "unknown_when_assessed_count_is_zero"):
        _assert(k in scalar_rules, f"confidence policy scalar_rules missing key: {k}")
    for ck in comp_order:
        rv = component_rules.get(ck) if isinstance(component_rules.get(ck), dict) else {}
        _assert(bool(str(rv.get("label") or "")), f"confidence policy component_rules.{ck}.label must be present")

    pol_v3 = load_confidence_policy_v0_3()
    body_v3 = pol_v3.policy if isinstance(pol_v3.policy, dict) else {}
    _assert(str(body_v3.get("policy_id") or "") == "confidence_policy_v0_3", "confidence policy v0_3 id mismatch")
    mta = body_v3.get("multi_template_aggregation") if isinstance(body_v3.get("multi_template_aggregation"), dict) else {}
    _assert(str(mta.get("strategy") or "") != "", "confidence policy v0_3 multi_template_aggregation.strategy must be present")
    _assert(bool(mta.get("weighted_scoring")) is False, "confidence policy v0_3 must explicitly keep weighted_scoring=false")

    l1 = load_confidence_policy_latest()
    l2 = load_confidence_policy_latest()
    _assert(l1.source_name == l2.source_name == "confidence_policy_v0_3.json", "confidence policy latest loader must deterministically select v0_3")
    _assert(l1.policy_hash == l2.policy_hash, "confidence policy latest loader hash must be deterministic")


def test_confidence_policy_catalog_non_weighted_language_and_keys() -> None:
    base = Path(__file__).resolve().parents[2] / "psi" / "core" / "di" / "catalogs"
    for name in ("confidence_policy_v0_2.json", "confidence_policy_v0_3.json"):
        txt = (base / name).read_text(encoding="utf-8").lower()
        if name == "confidence_policy_v0_3.json":
            _assert('"weighted_scoring": false' in txt, "confidence policy v0_3 must explicitly record weighted_scoring=false")
            txt_for_weight_check = txt.replace('"weighted_scoring": false', '')
        else:
            txt_for_weight_check = txt
        _assert("weight" not in txt_for_weight_check, f"{name}: confidence policy catalog must not introduce weighted scoring fields")
        _assert("average" not in txt, f"{name}: confidence policy catalog must not introduce averaging fields")
        _assert("\"component_rules\"" in txt and "\"scalar_rules\"" in txt, f"{name}: confidence policy catalog must include component_rules and scalar_rules")
    txt_v3 = (base / "confidence_policy_v0_3.json").read_text(encoding="utf-8").lower()
    _assert("\"multi_template_aggregation\"" in txt_v3, "confidence policy v0_3 must make multi-template aggregation strategy policy-visible")


def test_molecule_header_confidence_model_non_weighted_neutral_missing() -> None:
    from psi.services.molecules import _build_confidence_model

    cm = _build_confidence_model(
        latest_di_row={"_out": {}},
        risk_severity_counts={"high": 0, "medium": 0, "low": 0, "unspecified": 0},
    )
    comps = cm.get("components") if isinstance(cm, dict) else []
    _assert(isinstance(comps, list) and len(comps) == 4, "confidence model should emit 4 deterministic components")
    comp_keys = [str((c or {}).get("key") or "") for c in comps if isinstance(c, dict)]
    _assert(
        comp_keys == ["qc_quality", "reproducibility", "comparability", "interpretability"],
        f"confidence component order must be deterministic and fixed; got {comp_keys}",
    )
    _assert(
        str(cm.get("scalar_state") or "") == "green",
        "missing evidence components must remain neutral (not negative) when no concerns are present",
    )
    _assert(
        "no weights" in str(cm.get("rule_text") or "").lower(),
        "confidence rule text must explicitly state non-weighted counting",
    )


def test_molecule_header_prerequisite_blocker_sorting_deterministic() -> None:
    from psi.services.molecules import _sorted_prerequisite_blockers_for_advisory

    inp = [
        {"template_key": "z.template", "status": "missing", "latest_snapshot_id": None},
        {"template_key": "a.template", "status": "failed", "latest_snapshot_id": 42},
        {"template_key": "a.template", "status": "missing", "latest_snapshot_id": None},
    ]
    out1 = _sorted_prerequisite_blockers_for_advisory(inp)
    out2 = _sorted_prerequisite_blockers_for_advisory(list(reversed(inp)))
    keys1 = [
        (str(x.get("template_key") or ""), str(x.get("status") or ""), int(x.get("latest_snapshot_id") or 0))
        for x in out1
        if isinstance(x, dict)
    ]
    keys2 = [
        (str(x.get("template_key") or ""), str(x.get("status") or ""), int(x.get("latest_snapshot_id") or 0))
        for x in out2
        if isinstance(x, dict)
    ]
    _assert(keys1 == keys2, "prerequisite blocker sorting must be deterministic irrespective of input order")
    _assert(keys1 == [("a.template", "failed", 42), ("a.template", "missing", 0), ("z.template", "missing", 0)], f"unexpected blocker sort order: {keys1}")


def test_molecule_header_risk_items_deterministic_and_neutral_unknown() -> None:
    from psi.services.molecules import _build_header_risk_items

    row = {
        "_out": {
            "risk_flags_enriched": [
                {"key": "z_flag", "severity": "low"},
                {"key": "a_flag", "severity": "high"},
                {"key": "m_flag", "severity": "moderate"},
                {"key": "u_flag", "severity": "mystery"},
            ]
        }
    }
    items1 = _build_header_risk_items(latest_di_row=row)
    items2 = _build_header_risk_items(
        latest_di_row={"_out": {"risk_flags_enriched": list(reversed((row.get("_out") or {}).get("risk_flags_enriched") or []))}}
    )
    _assert(stable_json_dumps(items1) == stable_json_dumps(items2), "molecule header risk items must be deterministic irrespective of input order")
    keys = [str((x or {}).get("key") or "") for x in items1 if isinstance(x, dict)]
    _assert(keys == ["a_flag", "m_flag", "z_flag", "u_flag"], f"unexpected header risk item order: {keys}")
    by_key = {str((x or {}).get("key") or ""): (x or {}) for x in items1 if isinstance(x, dict)}
    _assert(str((by_key.get("m_flag") or {}).get("severity") or "") == "medium", "moderate severity should normalize to medium for header display")
    _assert(str((by_key.get("u_flag") or {}).get("severity") or "") == "unspecified", "unknown severity should render as neutral unspecified")
    _assert(bool((by_key.get("u_flag") or {}).get("severity_neutral")) is True, "unknown severity must be neutral in header display")


def test_progress_stage_advisory_selection_is_deterministic() -> None:
    from psi.services.molecules import _build_progress_stage_advisory

    advisories = [
        {"milestone_key": "di_b", "blocked_by_text": "Blocked by prerequisites: z.template (missing)"},
        {"milestone_key": "di_a", "blocked_by_text": "Blocked by prerequisites: a.template (failed, latest snapshot #7)"},
    ]
    out = _build_progress_stage_advisory(prereq_advisories=sorted(advisories, key=lambda a: str(a.get("milestone_key") or "")))
    _assert(isinstance(out, dict), "stage advisory should be emitted when prerequisite advisories exist")
    _assert(str((out or {}).get("milestone_key") or "") == "di_a", "stage advisory should select deterministic first blocked DI milestone")
    items = (out or {}).get("blocked_by_items")
    _assert(isinstance(items, list) and len(items) == 2, "stage advisory should carry all blocker advisories deterministically")
    _assert([str((x or {}).get('milestone_key') or '') for x in items] == ["di_a", "di_b"], "stage advisory blocker list order mismatch")
    _assert(
        " | " in str((out or {}).get("blocked_by_text") or ""),
        "stage advisory should aggregate all blocker texts deterministically",
    )


def test_progress_hover_text_policy_key_ordering_and_explainability() -> None:
    from psi.services.molecules import _build_progress_hover_text

    txt = _build_progress_hover_text(
        milestones=[
            {"key": "b_key", "satisfied": False},
            {"key": "a_key", "satisfied": True},
            {"key": "c_key", "satisfied": True},
        ]
    )
    _assert("satisfied=a_key,c_key" in txt, "progress hover text must include satisfied milestone keys in stable milestone order")
    _assert("not_yet=b_key" in txt, "progress hover text must include missing milestone keys")


def test_molecule_header_confidence_scaffold_no_snapshot_all_neutral() -> None:
    from psi.services.molecules import _build_confidence_model

    cm = _build_confidence_model(latest_di_row=None, risk_severity_counts={"high": 0, "medium": 0, "low": 0, "unspecified": 0})
    comps = cm.get("components") if isinstance(cm, dict) else []
    _assert(isinstance(comps, list) and len(comps) == 4, "confidence scaffold must include 4 components")
    states = [str((c or {}).get("state") or "") for c in comps if isinstance(c, dict)]
    _assert(states == ["not_assessed", "not_assessed", "not_assessed", "not_assessed"], f"no-snapshot scaffold must be neutral not_assessed; got {states}")
    labels = [str((c or {}).get("name") or "") for c in comps if isinstance(c, dict)]
    _assert(labels == ["QC Quality", "Reproducibility", "Comparability", "Interpretability"], f"unexpected scaffold labels: {labels}")


def test_confidence_component_derivation_missing_evidence_neutral() -> None:
    from psi.services.molecules import _derive_confidence_components

    comps = _derive_confidence_components(
        latest_di_row={"_out": {"gates": []}},
        risk_severity_counts={"high": 0, "medium": 0, "low": 0, "unspecified": 0},
    )
    by_key = {str((c or {}).get("key") or ""): (c or {}) for c in comps if isinstance(c, dict)}
    _assert(str((by_key.get("qc_quality") or {}).get("state") or "") == "not_assessed", "missing QC evidence should be neutral")
    _assert(str((by_key.get("reproducibility") or {}).get("state") or "") == "not_assessed", "missing reproducibility evidence should be neutral")
    _assert(str((by_key.get("comparability") or {}).get("state") or "") == "not_assessed", "missing comparability evidence should be neutral")
    _assert(str((by_key.get("interpretability") or {}).get("state") or "") == "good", "no risk flags should yield good interpretability (not a penalty)")


def test_confidence_component_derivation_deterministic_from_existing_artifacts() -> None:
    from psi.services.molecules import _derive_confidence_components

    row1 = {
        "_out": {
            "gates": [
                {"gate_key": "G3_endotoxin", "status": "pass"},
                {"gate_key": "G2_purity_integrity", "status": "pass"},
            ],
            "drift_type": "INCOMPARABLE",
        }
    }
    row2 = {
        "_out": {
            "gates": list(reversed((row1.get("_out") or {}).get("gates") or [])),
            "drift_type": "INCOMPARABLE",
        }
    }
    risk_counts = {"high": 1, "medium": 0, "low": 0, "unspecified": 0}
    c1 = _derive_confidence_components(latest_di_row=row1, risk_severity_counts=risk_counts)
    c2 = _derive_confidence_components(latest_di_row=row2, risk_severity_counts=risk_counts)
    _assert(stable_json_dumps(c1) == stable_json_dumps(c2), "confidence component derivation must be deterministic")


def test_interpretability_detail_items_ordering_deterministic() -> None:
    from psi.services.molecules import _build_confidence_model

    cm = _build_confidence_model(
        latest_di_row={"_out": {"gates": []}},
        risk_severity_counts={"low": 2, "high": 1, "unspecified": 3, "medium": 4},
    )
    comps = cm.get("components") if isinstance(cm, dict) else []
    interp = next((c for c in comps if isinstance(c, dict) and str(c.get("key") or "") == "interpretability"), {})
    items = interp.get("detail_items") if isinstance(interp, dict) else []
    seq = [
        (str((x or {}).get("severity") or ""), int((x or {}).get("count") or 0))
        for x in (items or [])
        if isinstance(x, dict)
    ]
    _assert(seq == [("high", 1), ("medium", 4), ("low", 2), ("unspecified", 3)], f"interpretability detail items must use deterministic tier ordering; got {seq}")


def test_confidence_scalar_non_weighted_counting_rules() -> None:
    from psi.services.molecules import _derive_confidence_scalar_from_components

    s1 = _derive_confidence_scalar_from_components(
        components=[
            {"key": "interpretability", "state": "concern", "severity": "high"},
            {"key": "qc_quality", "state": "good"},
        ]
    )
    _assert(s1[0] == "amber", "any high-severity concern should produce amber under v0.1 scalar rule")

    s2 = _derive_confidence_scalar_from_components(
        components=[
            {"key": "interpretability", "state": "concern", "severity": "medium"},
            {"key": "comparability", "state": "concern", "severity": "medium"},
            {"key": "qc_quality", "state": "good"},
        ]
    )
    _assert(s2[0] == "amber", "two medium concerns should produce amber under v0.1 scalar rule")

    s3 = _derive_confidence_scalar_from_components(
        components=[
            {"key": "interpretability", "state": "concern", "severity": "low"},
            {"key": "comparability", "state": "not_assessed"},
            {"key": "qc_quality", "state": "good"},
        ]
    )
    _assert(s3[0] == "green", "low-severity concerns alone should not escalate beyond green in count-only rule")


def test_confidence_scalar_surface_rejects_weighting_language() -> None:
    from psi.services.molecules import _build_confidence_model

    cm = _build_confidence_model(latest_di_row={"_out": {}}, risk_severity_counts={"high": 0, "medium": 0, "low": 0, "unspecified": 0})
    txt = str(cm.get("rule_text") or "").lower()
    _assert("weight" in txt, "rule text must explicitly state no weights")
    _assert("average" not in txt, "rule text must not mention averaging")
    _assert("score" not in txt, "rule text must not imply hidden scoring")


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
    qc1 = comparability_qc_coherence_summary(comparability={"summary": {"high_severity_count": 1, "total_flags": 3}})
    qc2 = comparability_qc_coherence_summary(comparability={"summary": {"total_flags": 3, "high_severity_count": 1}})
    _assert(stable_json_dumps(qc1) == stable_json_dumps(qc2), "comparability sub-assessment helper must be deterministic")
    rep1 = reproducibility_signal_from_soe(
        required_metric_keys=["monomer_pct", "hmw_pct"],
        evidence_summary=[
            {"metric_key": "hmw_pct", "total_count": 2, "usable_count": 2},
            {"metric_key": "monomer_pct", "total_count": 1, "usable_count": 1},
        ],
    )
    rep2 = reproducibility_signal_from_soe(
        required_metric_keys=["hmw_pct", "monomer_pct"],
        evidence_summary=[
            {"metric_key": "monomer_pct", "total_count": 1, "usable_count": 1},
            {"metric_key": "hmw_pct", "total_count": 2, "usable_count": 2},
        ],
    )
    _assert(stable_json_dumps(rep1) == stable_json_dumps(rep2), "reproducibility sub-assessment helper must be deterministic")
    mat1 = material_readiness_rationale(status="pass", use_thresholds=True)
    mat2 = material_readiness_rationale(status="pass", use_thresholds=True)
    _assert(mat1 == mat2, "material readiness helper must be deterministic")


def test_sub_assessment_reproducibility_helper_key_shape_stable() -> None:
    rep = reproducibility_signal_from_soe(
        required_metric_keys=["m2", "m1"],
        evidence_summary=[
            {"metric_key": "m1", "total_count": 2, "usable_count": 2},
            {"metric_key": "m2", "total_count": 1, "usable_count": 1},
        ],
    )
    _assert(isinstance(rep, dict), "reproducibility sub-assessment helper must return dict")
    _assert(
        list(rep.keys()) == [
            "status",
            "required_metric_count",
            "positive_required_metric_count",
            "all_required_metrics_positive",
            "metrics",
        ],
        f"reproducibility helper key order/shape changed unexpectedly: {list(rep.keys())}",
    )
    rows = rep.get("metrics") if isinstance(rep.get("metrics"), list) else []
    _assert([str((r or {}).get("metric_key") or "") for r in rows] == ["m1", "m2"], "reproducibility helper metrics must remain stably sorted")
    _assert(
        material_readiness_rationale(status="fail", use_thresholds=False) == "Missing or out-of-range material readiness metrics.",
        "material readiness helper should return stable failure rationale",
    )
    mech1 = mechanism_readiness_rationale(gate_key="G4_functional", status="pass", use_thresholds=False)
    mech2 = mechanism_readiness_rationale(gate_key="G4_functional", status="pass", use_thresholds=False)
    _assert(mech1 == mech2, "mechanism readiness helper must be deterministic")
    _assert(
        mechanism_readiness_rationale(gate_key="G5_internalization_if_kd_present", status="fail", use_thresholds=False)
        == "kd_nM present but internalization evidence missing.",
        "mechanism readiness helper should return stable internalization rationale",
    )


def test_outcome_label_validation_helpers_deterministic() -> None:
    label_types = list(decisions_svc.OUTCOME_LABEL_TYPES)
    verdicts = list(decisions_svc.DI_REVIEW_VERDICTS)
    a = decisions_svc.validate_outcome_label_submission(label_type="correct", note="  ok  ", outcome_label_types=label_types)
    b = decisions_svc.validate_outcome_label_submission(label_type="correct", note="ok", outcome_label_types=label_types)
    _assert(stable_json_dumps(a) == stable_json_dumps(b), "outcome label validation should normalize deterministically")
    _assert(a.get("label_type") == "correct" and a.get("note") == "ok", "outcome label validation should preserve allowed key and normalized note")
    try:
        decisions_svc.validate_outcome_label_submission(label_type="other", note="", outcome_label_types=label_types)
        raise AssertionError("expected note-required validation error")
    except ValueError as e:
        _assert(str(e) == "Note required for this label type", "note-required validation message must be stable")
    review = decisions_svc.validate_di_review_submission(verdict="useful", rationale="  stable  ", di_review_verdicts=verdicts)
    _assert(isinstance(review, dict) and review.get("di_review_verdict") == "useful" and review.get("di_review_rationale") == "stable", "di review validation must normalize deterministically")
    try:
        decisions_svc.validate_di_review_submission(verdict="unknown", rationale="x", di_review_verdicts=verdicts)
        raise AssertionError("expected invalid verdict validation error")
    except ValueError as e:
        _assert(str(e) == "Invalid DI review verdict", "invalid verdict validation message must be stable")


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


def test_nbe_uses_catalog_risk_mapping_only() -> None:
    from psi.services.di import nbe as nbe_mod

    _assert(not hasattr(nbe_mod, "_RISK_FLAG_TO_EXPERIMENT_KEYS"), "nbe must not retain hardcoded risk-flag mapping constant")

    suggestions, recommended = nbe_mod.build_experiment_suggestions(
        blockers=[],
        risk_flags=[{"risk_flag": "aggregated_purity_interpretation_gap"}],
        catalog_id="experiment_catalog_v0_2",
        catalog_version="v0.2",
        allow_recommended_list=True,
    )
    keys = suggestions.get("risk_flag:aggregated_purity_interpretation_gap") or []
    _assert(bool(keys), "v0.2 catalog risk mapping should provide at least one experiment for aggregated_purity_interpretation_gap")
    suggestions2, _ = nbe_mod.build_experiment_suggestions(
        blockers=[],
        risk_flags=[{"risk_flag": "aggregated_purity_interpretation_gap"}],
        catalog_id="experiment_catalog_v0_2",
        catalog_version="v0.2",
        allow_recommended_list=True,
    )
    _assert(
        stable_json_dumps(suggestions) == stable_json_dumps(suggestions2),
        "risk-flag-driven suggestions must be deterministic across reruns",
    )
    rec_keys = [str((r or {}).get("experiment_key") or "") for r in (recommended or []) if isinstance(r, dict)]
    _assert(len(rec_keys) == len(set(rec_keys)), "recommended experiments must be deduplicated")

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
    _assert(
        "value_functions_enforcement_reason" in (out1.get("output") or {}),
        "new snapshots with output extensions must include value_functions_enforcement_reason",
    )
    _assert(
        str((out1.get("output") or {}).get("value_functions_enforcement_reason") or "")
        in {"active", "policy_flag_off", "evaluator_version_mismatch", "not_applicable"},
        "value_functions_enforcement_reason must use allowed deterministic enum values",
    )

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
    sev_rank = {"high": 0, "medium": 1, "moderate": 1, "low": 2}
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


def test_di_error_output_top_level_key_parity() -> None:
    """Representative success vs error top-level parity (read-only on existing DB)."""
    from types import SimpleNamespace

    from psi.core.db import SessionLocal
    from psi.core.models import DecisionSnapshot
    from psi.core.di.schema import DIInput
    from psi.services.di.runner import _build_di_error_output, _complete_di_error_output_contract_parity

    db = SessionLocal()
    try:
        snap = None
        success_inputs = {}
        for cand in (
            db.query(DecisionSnapshot)
            .filter(DecisionSnapshot.engine_key == "di")
            .order_by(DecisionSnapshot.id.desc())
            .all()
        ):
            try:
                cand_inputs = json.loads(cand.inputs_json or "{}")
            except Exception:
                cand_inputs = {}
            if not isinstance(cand_inputs, dict):
                continue
            ext = cand_inputs.get("output_extensions")
            if not isinstance(ext, list):
                continue
            ext_vals = {str(x) for x in ext}
            if "error_output_parity_v2_0a" not in ext_vals:
                continue
            snap = cand
            success_inputs = cand_inputs
            break

        _assert(snap is not None, "need at least one parity-gated DI snapshot for error parity smoke")
        try:
            success_out = json.loads(snap.outputs_json or "{}")
        except Exception:
            success_out = {}
        _assert(isinstance(success_out, dict) and bool(success_out), "representative success output must parse as non-empty dict")
        _assert(isinstance(success_inputs, dict) and bool(success_inputs), "representative success inputs must parse as non-empty dict")

        di_input = DIInput(
            decision_key=str(getattr(snap, "decision_key", "") or "advance_to_in_vivo"),
            scope_type="batch",
            scope_id=int(getattr(snap, "batch_id", None) or 1),
            as_of_ts=None,
            qc_mode="model_safe",
            context={},
        )
        pol_stub = SimpleNamespace(
            policy_id=str(success_inputs.get("policy_id") or "stub.policy"),
            name=str(success_inputs.get("policy_name") or "stub"),
            version=str(success_inputs.get("policy_version") or "v0.4"),
            schema_version=str(success_inputs.get("policy_schema_version") or "di.policy_package.v0_1"),
            policy_semantics_hash=str(success_inputs.get("policy_semantics_hash") or ("0" * 64)),
            policy_package_hash=str(success_inputs.get("policy_package_hash") or ("1" * 64)),
            source_name=str(success_inputs.get("policy_source") or "stub.json"),
            changelog=[],
            template_key=str(success_inputs.get("template_key") or ""),
        )
        err = _build_di_error_output(
            di_input=di_input,
            pol=pol_stub,
            evaluator_version="di.template.stub.v0",
            warning_kind="contract_smoke",
            warning_detail={"reason": "parity_test"},
            blocker_key="contract_smoke",
            blocker_detail={"reason": "parity_test"},
            risk_flag="contract_smoke",
            risk_note="contract smoke parity",
            risk_enriched_key="contract_smoke",
            risk_enriched_explanation="contract smoke parity",
            readiness_blocker_key="contract_smoke",
            readiness_blocker_explanation="contract smoke parity",
            readiness_blocking_reason="contract smoke parity",
        )
        err = _complete_di_error_output_contract_parity(
            out=err,
            di_input=di_input,
            pol=pol_stub,
            inputs_obj={
                "output_extensions": list(success_inputs.get("output_extensions") or []),
                "evaluator_version": str(success_inputs.get("evaluator_version") or ""),
            },
        )

        success_keys = set(str(k) for k in success_out.keys())
        err_keys = set(str(k) for k in err.keys())
        missing = sorted([k for k in success_keys if k not in err_keys])
        _assert(not missing, f"error output missing top-level keys from representative success output: {missing}")

        for k in [
            "metric_evaluations",
            "recommended_experiments",
            "comparability",
            "confidence_degradation",
            "why_evidence",
            "drift_type",
            "state_transition",
            "value_functions_enforced",
            "value_functions_enforcement_reason",
        ]:
            _assert(k in err_keys, f"error output parity must include top-level key: {k}")

        ext_vals = {str(x) for x in (success_inputs.get("output_extensions") or [])}
        if "value_functions_enforced_v0_1" in ext_vals:
            _assert(
                "value_functions_enforcement_reason" in success_keys,
                "gated success output must include value_functions_enforcement_reason",
            )
            _assert(
                "value_functions_enforcement_reason" in err_keys,
                "gated error output must include value_functions_enforcement_reason",
            )
    finally:
        db.close()


def test_di_error_output_parity_extension_gating_v03_vs_v04() -> None:
    from types import SimpleNamespace

    from psi.core.di.schema import DIInput
    from psi.services.di.runner import _build_di_error_output, _complete_di_error_output_contract_parity

    di_input = DIInput(
        decision_key="advance_to_in_vivo",
        scope_type="batch",
        scope_id=1,
        as_of_ts=None,
        qc_mode="model_safe",
        context={},
    )

    def _mk_pol(version: str) -> Any:
        return SimpleNamespace(
            policy_id="stub.policy",
            name="stub",
            version=version,
            schema_version="di.policy_package.v0_1",
            policy_semantics_hash="0" * 64,
            policy_package_hash="1" * 64,
            source_name="stub.json",
            changelog=[],
            template_key="advance_to_in_vivo.v0_1",
        )

    def _mk_err(version: str) -> dict[str, Any]:
        err = _build_di_error_output(
            di_input=di_input,
            pol=_mk_pol(version),
            evaluator_version="di.template.stub.v0",
            warning_kind="contract_smoke",
            warning_detail={"reason": "parity_gating"},
            blocker_key="contract_smoke",
            blocker_detail={"reason": "parity_gating"},
            risk_flag="contract_smoke",
            risk_note="contract smoke parity gating",
            risk_enriched_key="contract_smoke",
            risk_enriched_explanation="contract smoke parity gating",
            readiness_blocker_key="contract_smoke",
            readiness_blocker_explanation="contract smoke parity gating",
            readiness_blocking_reason="contract smoke parity gating",
        )
        return _complete_di_error_output_contract_parity(
            out=err,
            di_input=di_input,
            pol=_mk_pol(version),
            # omit evaluator_version intentionally to exercise fallback behavior (w75 hardening)
            inputs_obj={"output_extensions": ["value_functions_enforced_v0_1", "error_output_parity_v2_0a"]},
        )

    err_v03 = _mk_err("v0.3")
    err_v04 = _mk_err("v0.4")

    for k in (
        "metric_evaluations",
        "recommended_experiments",
        "comparability",
        "confidence_degradation",
        "why_evidence",
        "drift_type",
        "state_transition",
        "shortlisting",
        "value_functions_enforced",
        "value_functions_enforcement_reason",
    ):
        _assert(k in err_v03 and k in err_v04, f"error parity common field missing: {k}")

    for k in ("scope_semantics", "context_evaluation", "template_dependency_graph"):
        _assert(k not in err_v03, f"v0.3 error parity should not emit v0.4-only field: {k}")
        _assert(k in err_v04, f"v0.4 error parity should emit v0.4-only field: {k}")


def test_error_output_field_surface_guard_against_happy_path_drift() -> None:
    # Explicit alias/intent lock for x20: if happy-path adds new top-level fields,
    # the representative parity test above should fail unless error projection is updated.
    test_di_error_output_top_level_key_parity()


def test_di_error_output_parity_multiple_error_factories_defaults() -> None:
    from types import SimpleNamespace

    from psi.core.di.schema import DIInput
    from psi.services.di.runner import (
        _complete_di_error_output_contract_parity,
        _policy_schema_mismatch_output,
        _unsupported_template_output,
    )

    di_input = DIInput(
        decision_key="advance_to_in_vivo",
        scope_type="batch",
        scope_id=1,
        as_of_ts=None,
        qc_mode="model_safe",
        context={},
    )
    pol = SimpleNamespace(
        policy_id="stub.policy",
        name="stub",
        version="v0.4",
        schema_version="di.policy_package.v0_1",
        policy_semantics_hash="0" * 64,
        policy_package_hash="1" * 64,
        source_name="stub.json",
        changelog=[],
        template_key="advance_to_in_vivo.v0_1",
    )
    inputs_obj = {
        "output_extensions": ["value_functions_enforced_v0_1", "error_output_parity_v2_0a"],
        "evaluator_version": "di.template.stub.v0",
    }
    err_schema = _complete_di_error_output_contract_parity(
        out=_policy_schema_mismatch_output(di_input=di_input, pol=pol, mismatch="unknown_policy_schema_version", evaluator_version="di.template.stub.v0"),
        di_input=di_input,
        pol=pol,
        inputs_obj=dict(inputs_obj),
    )
    err_template = _complete_di_error_output_contract_parity(
        out=_unsupported_template_output(di_input=di_input, pol=pol, reason="unknown_template", evaluator_version="di.template.stub.v0"),
        di_input=di_input,
        pol=pol,
        inputs_obj=dict(inputs_obj),
    )
    for tag, err in (("policy_schema_mismatch", err_schema), ("unsupported_template", err_template)):
        _assert(isinstance(err.get("metric_evaluations"), dict), f"{tag}: metric_evaluations parity default must be dict")
        _assert(isinstance(err.get("recommended_experiments"), list), f"{tag}: recommended_experiments parity default must be list")
        _assert(err.get("shortlisting") is None, f"{tag}: shortlisting parity default must be null")
        _assert(err.get("scope_semantics") is None, f"{tag}: scope_semantics parity default must be null")
        _assert(str(err.get("drift_type") or "") == "NO_CHANGE", f"{tag}: drift_type parity default mismatch")
        _assert(
            str(err.get("value_functions_enforcement_reason") or "") in {"active", "policy_flag_off", "evaluator_version_mismatch", "not_applicable"},
            f"{tag}: value_functions_enforcement_reason must be valid enum",
        )


def test_outcome_dataset_export_deterministic() -> None:
    from psi.core.db import get_db
    from psi.tools.export_outcome_dataset import build_outcome_dataset_rows, write_outcome_dataset_jsonl

    p1 = Path(tempfile.mkdtemp(prefix="psi_outcome_export1_", dir=tempfile.gettempdir())) / "outcome.jsonl"
    p2 = Path(tempfile.mkdtemp(prefix="psi_outcome_export2_", dir=tempfile.gettempdir())) / "outcome.jsonl"
    try:
        with get_db(None, ensure=False) as db:
            rows1 = build_outcome_dataset_rows(db=db, engine_key_filter="di")
            rows2 = build_outcome_dataset_rows(db=db, engine_key_filter="di")
        _assert(stable_json_dumps(rows1) == stable_json_dumps(rows2), "outcome dataset rows must be deterministic for fixed DB")
        write_outcome_dataset_jsonl(rows=rows1, out_path=p1)
        write_outcome_dataset_jsonl(rows=rows2, out_path=p2)
        _assert(p1.read_text(encoding="utf-8") == p2.read_text(encoding="utf-8"), "outcome dataset JSONL output must be deterministic")
    finally:
        shutil.rmtree(str(p1.parent), ignore_errors=True)
        shutil.rmtree(str(p2.parent), ignore_errors=True)


def test_outcome_dataset_export_hash_field_enrichment_from_stored_snapshot_fields() -> None:
    from psi.tools.export_outcome_dataset import _extract_snapshot_hash_fields

    out = {
        "policy": {"hash": "sem_from_policy_hash", "policy_package_hash": "pkg_from_policy"},
        "provenance": {
            "policy_ref": {"policy_semantics_hash": "sem_from_policy_ref", "policy_package_hash": "pkg_from_policy_ref"},
            "integrity": {"evidence_fingerprint": "ev_from_integrity"},
            "inputs_fingerprint": {"evidence_fingerprint": "ev_from_inputs_fp"},
        },
    }
    inp = {"policy_hash": "sem_from_input_legacy"}
    fields = _extract_snapshot_hash_fields(inp=inp, out=out)
    _assert(str(fields.get("policy_semantics_hash") or "") == "sem_from_policy_ref", "export enrichment should prefer stored provenance.policy_ref semantics hash before legacy policy.hash")
    _assert(str(fields.get("policy_package_hash") or "") == "pkg_from_policy", "export enrichment should use stored package hash deterministically")
    _assert(str(fields.get("evidence_fingerprint") or "") == "ev_from_integrity", "export enrichment should prefer stored provenance.integrity evidence fingerprint")


def test_label_outcome_cli_outcome_event_date_parser_deterministic() -> None:
    from psi.tools import label_outcome as label_outcome_cli

    dt = label_outcome_cli._parse_outcome_event_date("2026-02-26T12:34:56Z")
    _assert(getattr(dt, "isoformat", lambda: "")() == "2026-02-26T12:34:56", "outcome_event_date parser should normalize Z timestamps to naive UTC deterministically")

    err = io.StringIO()
    try:
        with redirect_stderr(err):
            label_outcome_cli._parse_outcome_event_date("not-a-date")
        _assert(False, "invalid outcome_event_date should raise SystemExit")
    except SystemExit as exc:
        _assert(int(getattr(exc, "code", 0) or 0) == 1, "invalid outcome_event_date should exit with code 1")
    _assert(
        err.getvalue().strip() == "--outcome-event-date must be ISO8601 (e.g. 2026-02-26 or 2026-02-26T12:00:00Z)",
        "invalid outcome_event_date message must remain deterministic",
    )


def test_molecule_composition_hash_stability_after_helper_split() -> None:
    from psi.services.molecule_sequences import composition_sha256 as seq_comp_hash
    from psi.services.molecules import composition_sha256 as mol_comp_hash

    payload = {"HC1": "CHAIN001", "HC2": "CHAIN001", "LC1": "CHAIN002", "LC2": "CHAIN002"}
    h1 = seq_comp_hash(payload)
    h2 = mol_comp_hash(dict(reversed(list(payload.items()))))
    _assert(h1 == h2, "composition hash helper split must preserve canonical hash behavior")
    _assert(h1 == "d4ac4888670245b6feac67421f49d0e3cfbb1d38d1a46f94f56b83e65faea569", "composition hash digest changed unexpectedly")


def test_yaml_engine_deprecation_warning_emits_only_on_use() -> None:
    from psi.core import decision_engine as de

    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always", DeprecationWarning)
        de.run_decision(
            rules={"decisions": {"d": {"min_domain_scores": {}}}, "domains": {}, "hard_stops": [], "presence_threshold": 2},
            decision_key="d",
            evidence_rows=[],
        )
    msgs = [str(getattr(w, "message", "")) for w in rec]
    _assert(any("YAML DI engine is deprecated" in m for m in msgs), "legacy YAML run_decision should emit deprecation warning on use")


def test_replay_policy_compat_catalog_loads_and_is_deterministic() -> None:
    from psi.core.di.catalog import load_replay_policy_compat_latest

    c1 = load_replay_policy_compat_latest()
    c2 = load_replay_policy_compat_latest()
    _assert(c1.source_name == c2.source_name == "replay_policy_compat_v0_1.json", "replay policy compat latest loader must be deterministic")
    _assert(c1.catalog_hash == c2.catalog_hash, "replay policy compat latest loader hash must be deterministic")
    policies = c1.catalog.get("policies") if isinstance(c1.catalog, dict) else None
    _assert(isinstance(policies, list), "replay policy compat catalog policies must be a list")


def test_verify_snapshot_policy_resolution_metadata_default_strict() -> None:
    from psi.core.db import get_db
    from psi.core.models import DecisionSnapshot
    from psi.services.di.verify import verify_snapshot

    with get_db(None, ensure=False) as db:
        snap = (
            db.query(DecisionSnapshot)
            .order_by(DecisionSnapshot.id.desc())
            .first()
        )
        if snap is None:
            return
        rep = verify_snapshot(db=db, snapshot_id=int(snap.id), debug=False)
    pr = rep.get("policy_resolution") if isinstance(rep, dict) else {}
    _assert(isinstance(pr, dict), "verify_snapshot report must include policy_resolution metadata")
    _assert(bool(pr.get("compat_fallback_enabled")) is False, "verify_snapshot default must keep compat fallback disabled")
    _assert(bool(pr.get("compat_fallback_used")) is False, "verify_snapshot default strict path must not use compat fallback")


def test_compute_finalize_integrity_helper_deterministic() -> None:
    from psi.core.di.schema import EvidenceRef
    from psi.services.di.compute import _finalize_integrity

    out1 = {"provenance": {"integrity": {"evidence_fingerprint": "seed"}}}
    out2 = {"provenance": {"integrity": {"evidence_fingerprint": "seed"}}}
    inputs_obj = {"decision_key": "advance_to_in_vivo", "scope_type": "batch", "scope_id": 1}
    used = {
        "hmw_pct": EvidenceRef(
            measurement_id=10,
            data_record_id=20,
            metric_key="hmw_pct",
            metric_key_source="canonical",
            value_num=1.0,
            value_text=None,
            value_bool=None,
            unit="%",
            comparator=None,
            qc_status="approved",
            qc_flag_raw=None,
            qc_source="measurement_qc",
            is_primary=True,
            is_outlier=False,
            produced_at=None,
            created_at="2026-02-26T00:00:00",
        )
    }
    _finalize_integrity(out=out1, inputs_obj=dict(inputs_obj), used_by_metric=used)
    _finalize_integrity(out=out2, inputs_obj=dict(inputs_obj), used_by_metric=used)
    i1 = (((out1.get("provenance") or {}).get("integrity")) if isinstance(out1.get("provenance"), dict) else {})
    i2 = (((out2.get("provenance") or {}).get("integrity")) if isinstance(out2.get("provenance"), dict) else {})
    for k in ("snapshot_content_hash", "decision_output_hash", "decision_output_hash_v2"):
        _assert(bool(str((i1 or {}).get(k) or "")), f"_finalize_integrity must populate {k}")
    _assert(i1 == i2, "_finalize_integrity helper output must be deterministic for identical inputs")

def main() -> int:
    try:
        global _SMOKE_SET_BASELINE_CUTOFF
        if "PSI_DI_BASELINE_CUTOFF_ISO" not in os.environ:
            os.environ["PSI_DI_BASELINE_CUTOFF_ISO"] = datetime.now(timezone.utc).isoformat()
            _SMOKE_SET_BASELINE_CUTOFF = True
        test_policy_canonicalization_and_hash()
        test_value_functions_enforcement_reason_helper()
        test_policy_package_dual_hash_stability()
        test_catalog_hash_validation()
        test_experiment_catalog_v0_2_latest_loader_and_risk_mapping()
        test_policy_template_structure_present()
        test_policy_risk_flag_severity_tiers_present_and_cover_expected_flags()
        test_risk_flag_enrichment_uses_policy_severity_tiers_deterministically()
        test_risk_flag_enrichment_unknown_key_defaults_to_unspecified_neutral()
        test_progress_policy_catalog_v0_1_loads_and_validates()
        test_progress_policy_metric_keys_are_representable_in_measurement_registry()
        test_shortlisting_policy_catalog_v0_1_weights_schema_and_values()
        test_template_prerequisites_catalog_v0_1_loads_and_validates()
        test_confidence_policy_catalog_loads_and_latest_loader_is_deterministic()
        test_confidence_policy_catalog_non_weighted_language_and_keys()
        test_molecule_header_confidence_model_non_weighted_neutral_missing()
        test_molecule_header_prerequisite_blocker_sorting_deterministic()
        test_molecule_header_risk_items_deterministic_and_neutral_unknown()
        test_progress_hover_text_policy_key_ordering_and_explainability()
        test_molecule_header_confidence_scaffold_no_snapshot_all_neutral()
        test_confidence_component_derivation_missing_evidence_neutral()
        test_confidence_component_derivation_deterministic_from_existing_artifacts()
        test_interpretability_detail_items_ordering_deterministic()
        test_confidence_scalar_non_weighted_counting_rules()
        test_confidence_scalar_surface_rejects_weighting_language()
        test_selection_semantics_version_constant()
        test_policy_authoritative_required_gate_keys()
        test_context_knob_branching_gate_outcomes_deterministic()
        test_shortlisting_refusal_v04_extensions_deterministic()
        test_tie_break_dimensions_v04_complete_and_deterministic()
        test_scope_semantics_v04_deterministic()
        test_template_registry_and_dependency_graph_deterministic()
        test_shared_sub_assessments_pure_helpers()
        test_sub_assessment_reproducibility_helper_key_shape_stable()
        test_outcome_label_validation_helpers_deterministic()
        test_shortlisting_reproducibility_from_soe_evidence_summary()
        test_policy_blocker_taxonomy_and_experiment_suggestions()
        test_nbe_uses_catalog_risk_mapping_only()
        test_di_snapshot_ui_risk_flag_severity_rendering_deterministic()
        test_di_run_view_toggle_ui_is_localstorage_only()
        test_drift_plain_english_translation_deterministic()
        test_di_web_latest_policy_selection_prefers_forward_immutable_forks()
        test_policy_immutability_manifest_matches_policy_files()
        test_policy_registry_manifest_matches_package_hashes()
        test_policy_strict_versioned_path_resolution()
        test_policy_registry_contains_forward_default_policy_hashes()
        test_policy_hash_audit_report_deterministic()
        test_risk_flag_enrichment_ordering_stable_with_medium_and_legacy_moderate()
        test_policy_blocker_suggestions_mapping_key_order_stable()
        test_policy_gate_lists_no_duplicates_and_stable_file_order()
        test_policy_freeze_sidecar_covers_legacy_policy_files_without_mutating_json()
        test_forward_policy_forks_use_medium_vocabulary_and_no_legacy_moderate()
        test_ignore_reason_keys_allowed_set()
        test_stable_json_dumps()
        test_normalize_ignored_schema_compat()
        test_soe_v0_2_contract_snapshot_shape_and_determinism()
        test_molecule_scope_determinism()
        test_baseline_cutoff_prevents_walk()
        test_cross_version_snapshot_content_hash_stability()
        test_di_error_output_top_level_key_parity()
        test_di_error_output_parity_extension_gating_v03_vs_v04()
        test_error_output_field_surface_guard_against_happy_path_drift()
        test_di_error_output_parity_multiple_error_factories_defaults()
        test_outcome_dataset_export_deterministic()
        test_outcome_dataset_export_hash_field_enrichment_from_stored_snapshot_fields()
        test_label_outcome_cli_outcome_event_date_parser_deterministic()
        test_molecule_composition_hash_stability_after_helper_split()
        test_yaml_engine_deprecation_warning_emits_only_on_use()
        test_replay_policy_compat_catalog_loads_and_is_deterministic()
        test_verify_snapshot_policy_resolution_metadata_default_strict()
        test_compute_finalize_integrity_helper_deterministic()
    except Exception as e:
        print(f"DI contract smoke FAILED: {e}")
        return 1

    print("DI contract smoke OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
