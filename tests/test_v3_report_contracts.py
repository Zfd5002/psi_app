from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base, DecisionSnapshot, Molecule, Program
from psi.core.utils import stable_json_dumps
from psi.services.report_engine import (
    REPORT_TYPE_MOLECULE,
    REPORT_TYPE_MOLECULE_COMPARATIVE,
    REPORT_TYPE_PROGRAM,
    REPORT_TYPE_PROGRAM_COMPARATIVE,
    canonical_report_json,
    generate_molecule_comparative_report_v0,
    generate_molecule_report_v0,
    generate_program_comparative_report_v0,
    generate_program_report_v0,
    load_report_run_payload,
)
from psi.services.comparability import create_comparability_assessment
from psi.services.comparability import load_comparability_policy_latest
from psi.services.reports_v3 import get_v3_report_policy_pins


def _build_fixture_db():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    db = SessionTmp()
    p1 = Program(name="P1", description="", created_at=datetime(2026, 2, 26), updated_at=datetime(2026, 2, 26))
    p2 = Program(name="P2", description="", created_at=datetime(2026, 2, 26), updated_at=datetime(2026, 2, 26))
    db.add_all([p1, p2]); db.commit(); db.refresh(p1); db.refresh(p2)
    m1 = Molecule(program_id=int(p1.id), primary_id="M-1", title="Mol1", created_at=datetime(2026, 2, 26), updated_at=datetime(2026, 2, 26))
    m2 = Molecule(program_id=int(p2.id), primary_id="M-2", title="Mol2", created_at=datetime(2026, 2, 26), updated_at=datetime(2026, 2, 26))
    db.add_all([m1, m2]); db.commit(); db.refresh(m1); db.refresh(m2)
    for p, m, state, ts in (
        (p1, m1, "ready", datetime(2026, 2, 26, 1, 0, 0)),
        (p2, m2, "blocked", datetime(2026, 2, 26, 1, 5, 0)),
    ):
        db.add(
            DecisionSnapshot(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=None,
                decision_key="advance_to_in_vivo",
                rules_version="vX",
                engine_key="di",
                schema_version="di.snapshot.v0_4",
                inputs_json=stable_json_dumps({"engine_key": "di"}),
                outputs_json=stable_json_dumps(
                    {
                        "decision_state": state,
                        "readiness": {"state": state},
                        "gates": [],
                        "used_by_metric": (
                            {"ec50": [1001], "kd": [1002]}
                            if int(m.id) == int(m1.id)
                            else {"ic50": [2001]}
                        ),
                    }
                ),
                evidence_ids_json="[]",
                created_at=ts,
            )
        )
    db.commit()
    return eng, db, int(m1.id), int(m2.id), int(p1.id), int(p2.id)


def _required_sections(report_type: str) -> tuple[str, ...]:
    if report_type == REPORT_TYPE_MOLECULE:
        return (
            "identity_context",
            "stage_determination",
            "confidence_decomposition",
            "mechanistic_evidence_map",
            "risk_profile",
            "experimental_gaps",
            "scientific_summary",
            "drift_history",
            "reproducibility_appendix",
        )
    if report_type == REPORT_TYPE_PROGRAM:
        return (
            "metadata",
            "stage_determination",
            "molecule_overview_table",
            "cross_molecule_comparability",
            "risk_landscape",
            "decision_lineage",
            "next_best_experiments",
            "reproducibility_appendix",
        )
    if report_type == REPORT_TYPE_MOLECULE_COMPARATIVE:
        return (
            "metadata",
            "molecule_set",
            "stage_comparison",
            "confidence_comparison",
            "comparability_surface",
            "drift_comparison",
            "ranking_surface",
            "reproducibility_appendix",
        )
    return (
        "metadata",
        "program_set",
        "stage_comparison",
        "portfolio_posture_comparison",
        "comparability_surface",
        "ranking_surface",
        "resource_implications",
        "reproducibility_appendix",
    )


def test_v3_report_contract_sections_and_canonical_serialization_stability():
    eng, db, m1, m2, p1, p2 = _build_fixture_db()
    try:
        as_of = datetime(2026, 2, 26, 2, 0, 0)
        pins = {"report_policy": "v0"}
        r1 = generate_molecule_report_v0(db, molecule_id=m1, as_of=as_of, policy_pins=pins)
        r2 = generate_program_report_v0(db, program_id=p1, as_of=as_of, policy_pins=pins)
        r3 = generate_molecule_comparative_report_v0(db, molecule_ids=[m2, m1], as_of=as_of, policy_pins=pins)
        r4 = generate_program_comparative_report_v0(db, program_ids=[p2, p1], as_of=as_of, policy_pins=pins)
        p1a = load_report_run_payload(r1)
        p1b = load_report_run_payload(generate_molecule_report_v0(db, molecule_id=m1, as_of=as_of, policy_pins=pins))
        assert canonical_report_json(p1a) == canonical_report_json(p1b)
        assert p1a["metadata"]["report_fingerprint"] == p1b["metadata"]["report_fingerprint"]
        assert len(str(p1a["metadata"]["report_fingerprint"])) == 64
        latest_comp_version = str(load_comparability_policy_latest().get("policy_version") or "v0.1")
        for rt, payload in (
            (REPORT_TYPE_MOLECULE, p1a),
            (REPORT_TYPE_PROGRAM, load_report_run_payload(r2)),
            (REPORT_TYPE_MOLECULE_COMPARATIVE, load_report_run_payload(r3)),
            (REPORT_TYPE_PROGRAM_COMPARATIVE, load_report_run_payload(r4)),
        ):
            sections = payload.get("sections") if isinstance(payload, dict) else {}
            assert isinstance(sections, dict)
            expected = _required_sections(rt)
            assert tuple(sections.keys()) == tuple(sorted(expected))
            repro = sections.get("reproducibility_appendix") if isinstance(sections.get("reproducibility_appendix"), dict) else {}
            if rt == REPORT_TYPE_MOLECULE:
                assert repro.get("measurement_keys") == ["ec50", "kd"]
            if rt == REPORT_TYPE_PROGRAM:
                assert repro.get("measurement_keys") == ["ec50", "kd"]
            if rt in {REPORT_TYPE_MOLECULE_COMPARATIVE, REPORT_TYPE_PROGRAM_COMPARATIVE}:
                catalog_versions = repro.get("catalog_versions") if isinstance(repro.get("catalog_versions"), dict) else {}
                assert str(catalog_versions.get("comparability_policy") or "") == latest_comp_version
    finally:
        db.close()
        eng.dispose()


def test_molecule_report_uses_governance_comparability_determination_only() -> None:
    eng, db, m1, _m2, p1, _p2 = _build_fixture_db()
    try:
        as_of = datetime(2026, 2, 26, 2, 0, 0)
        create_comparability_assessment(
            db,
            left_scope_type="molecule",
            left_scope_id=m1,
            right_scope_type="molecule",
            right_scope_id=m1,
            status="comparable",
            rule_id="placeholder_not_assessed",
            cited_measurement_keys=["ec50", "kd"],
            cited_snapshot_ids=[1],
            as_of=as_of,
        )
        row = generate_molecule_report_v0(db, molecule_id=m1, as_of=as_of, policy_pins={"report_policy": "v0"})
        payload = load_report_run_payload(row)
        det = (
            payload.get("sections", {})
            .get("drift_history", {})
            .get("comparability_determination", {})
        )
        assert det.get("category") == "comparable_full"
        assert det.get("rule_id") != "policy_no_match"
        assert "comparable_partial" not in canonical_report_json(payload)
    finally:
        db.close()
        eng.dispose()


def test_molecule_comparative_ranking_marks_high_risk_only_when_present() -> None:
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    db = SessionTmp()
    try:
        p = Program(name="P", description="", created_at=datetime(2026, 2, 26), updated_at=datetime(2026, 2, 26))
        db.add(p)
        db.commit()
        db.refresh(p)
        m1 = Molecule(program_id=int(p.id), primary_id="M-1", title="Mol1", created_at=datetime(2026, 2, 26), updated_at=datetime(2026, 2, 26))
        m2 = Molecule(program_id=int(p.id), primary_id="M-2", title="Mol2", created_at=datetime(2026, 2, 26), updated_at=datetime(2026, 2, 26))
        db.add_all([m1, m2])
        db.commit()
        db.refresh(m1)
        db.refresh(m2)
        db.add(
            DecisionSnapshot(
                program_id=int(p.id),
                molecule_id=int(m1.id),
                batch_id=None,
                decision_key="advance_to_in_vivo",
                rules_version="vX",
                engine_key="di",
                schema_version="di.snapshot.v0_4",
                inputs_json=stable_json_dumps({"engine_key": "di"}),
                outputs_json=stable_json_dumps(
                    {
                        "decision_state": "ready",
                        "readiness": {"state": "ready"},
                        "gates": [],
                        "risk_flags_enriched": [{"key": "foo", "severity": "HIGH"}],
                    }
                ),
                evidence_ids_json="[]",
                created_at=datetime(2026, 2, 26, 1, 0, 0),
            )
        )
        db.add(
            DecisionSnapshot(
                program_id=int(p.id),
                molecule_id=int(m2.id),
                batch_id=None,
                decision_key="advance_to_in_vivo",
                rules_version="vX",
                engine_key="di",
                schema_version="di.snapshot.v0_4",
                inputs_json=stable_json_dumps({"engine_key": "di"}),
                outputs_json=stable_json_dumps(
                    {
                        "decision_state": "ready",
                        "readiness": {"state": "ready"},
                        "gates": [],
                        "risk_flags_enriched": [{"key": "bar", "severity": "low"}],
                    }
                ),
                evidence_ids_json="[]",
                created_at=datetime(2026, 2, 26, 1, 1, 0),
            )
        )
        db.commit()

        row = generate_molecule_comparative_report_v0(
            db,
            molecule_ids=[int(m1.id), int(m2.id)],
            as_of=datetime(2026, 2, 26, 2, 0, 0),
            policy_pins={"report_policy": "v0"},
        )
        payload = load_report_run_payload(row)
        entities = (
            payload.get("sections", {})
            .get("ranking_surface", {})
            .get("entities", [])
        )
        by_id = {int(e.get("entity_id")): e for e in entities if isinstance(e, dict) and e.get("entity_id") is not None}
        assert "high_severity_risk_present" in by_id[int(m1.id)].get("criteria_hits", [])
        assert "high_severity_risk_present" not in by_id[int(m2.id)].get("criteria_hits", [])
    finally:
        db.close()
        eng.dispose()


def test_molecule_comparative_report_policy_pins_use_latest_comparability_version() -> None:
    eng, db, m1, m2, _p1, _p2 = _build_fixture_db()
    try:
        latest = load_comparability_policy_latest()
        row = generate_molecule_comparative_report_v0(
            db,
            molecule_ids=[m1, m2],
            as_of=datetime(2026, 2, 26, 2, 0, 0),
            policy_pins=get_v3_report_policy_pins("molecule_comparative_report"),
        )
        payload = load_report_run_payload(row)
        pins = payload.get("metadata", {}).get("policy_pins", {})
        comp_pin = pins.get("comparability_policy") if isinstance(pins, dict) else {}
        assert str(comp_pin.get("policy_version") or "") == str(latest.get("policy_version") or "")
    finally:
        db.close()
        eng.dispose()
