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
    finally:
        db.close()
        eng.dispose()
