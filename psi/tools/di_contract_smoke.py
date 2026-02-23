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

from pathlib import Path

from psi.core.di.catalog import load_catalog
from psi.core.di.policy import canonical_policy_json, load_policy, sha256_hex_of_canonical_json
from psi.services.decisions import stable_json_dumps
from psi.services.di.selectors import ALLOWED_IGNORE_REASON_KEYS
from psi.services.di.runner import DI_SELECTION_SEMANTICS_VERSION
from psi.tools.di_snapshot_diff import compute_snapshot_diff_by_id


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


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

    if os.environ.get("PSI_DB_PATH"):
        # Respect explicit user override (but still run).
        db_path = os.environ["PSI_DB_PATH"]
    else:
        root = Path(tempfile.gettempdir()) / "psi_di_contract"
        root.mkdir(parents=True, exist_ok=True)
        db_path = str(root / "psi_di_contract.sqlite")
        os.environ["PSI_DB_PATH"] = db_path

    from psi.core.db import SessionLocal, ensure_schema
    from psi.core.models import Batch, Molecule, Program
    from psi.services.programs import create_program
    from psi.services.molecules import create_molecule, DuplicateMoleculeError
    from psi.services.batches import create_batch
    from psi.services.data_records import create_data_record
    from psi.services.measurements import upsert_measurements

    from psi.core.di.schema import DIInput
    from psi.services.di.runner import run_di
    from psi.services.di.verify import verify_snapshot

    ensure_schema()
    db = SessionLocal()

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

    # v1.2.9k: provenance.integrity must exist and be stable across deterministic reruns
    prov1 = (out1.get("output") or {}).get("provenance") or {}
    prov2 = (out2.get("output") or {}).get("provenance") or {}
    integ1 = prov1.get("integrity") if isinstance(prov1, dict) else None
    integ2 = prov2.get("integrity") if isinstance(prov2, dict) else None
    _assert(isinstance(integ1, dict), "provenance.integrity must exist and be a dict")
    _assert(isinstance(integ2, dict), "provenance.integrity must exist and be a dict")
    for k in ("snapshot_content_hash", "evidence_fingerprint"):
        _assert(bool(str(integ1.get(k) or "")), f"provenance.integrity.{k} must be non-empty")
        _assert(bool(str(integ2.get(k) or "")), f"provenance.integrity.{k} must be non-empty")
        _assert(str(integ1.get(k)) == str(integ2.get(k)), f"provenance.integrity.{k} must be stable across reruns")

    # v1.2.9h: snapshot diff tool must report no_change for deterministic reruns
    dr = compute_snapshot_diff_by_id(db=db, id1=int(out1.get("snapshot_id")), id2=int(out2.get("snapshot_id")))
    _assert(dr.drift_label == "no_change", "di_snapshot_diff must classify deterministic reruns as no_change")
    _assert(not (dr.changes or {}), "di_snapshot_diff changes must be empty for deterministic reruns")

    # v1.2.9n: anchored replay must match runner output for all compute-derived fingerprints after a clean run
    rep = verify_snapshot(db=db, snapshot_id=int(out1.get("snapshot_id")), debug=False)
    ar = (rep.get("anchored_replay") or {}) if isinstance(rep, dict) else {}
    _assert(bool(ar.get("available")), "anchored replay must be available for smoke snapshot")
    stored = (rep.get("stored") or {}) if isinstance(rep, dict) else {}
    replay = ((ar.get("replay") or {}) if isinstance(ar.get("replay"), dict) else {})

    for k in ("snapshot_content_hash", "evidence_fingerprint", "decision_output_hash_v2_effective", "semantic_fingerprint"):
        sv = str(stored.get(k) or "")
        rv = str(replay.get(k) or "")
        _assert(bool(sv) and bool(rv), f"stored + replay {k} must be non-empty")
        _assert(sv == rv, f"anchored replay {k} must equal stored {k}")


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
        test_policy_canonicalization_and_hash()
        test_policy_package_dual_hash_stability()
        test_catalog_hash_validation()
        test_policy_template_structure_present()
        test_selection_semantics_version_constant()
        test_policy_blocker_taxonomy_and_experiment_suggestions()
        test_ignore_reason_keys_allowed_set()
        test_stable_json_dumps()
        test_soe_v0_2_contract_snapshot_shape_and_determinism()
        test_cross_version_snapshot_content_hash_stability()
    except Exception as e:
        print(f"DI contract smoke FAILED: {e}")
        return 1

    print("DI contract smoke OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
