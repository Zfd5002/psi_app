from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base, Molecule, Program, ReportRun
from psi.services.report_engine import canonical_report_json
from psi.services.reports_v3 import build_report_identity_summary
from psi.services.reports_v3 import get_report_run_detail
from psi.web.routers.reports import report_options_molecules, report_options_programs


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_identity_summary_derivation_for_all_report_types_is_deterministic() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p1 = Program(name="Program A", created_at=datetime(2026, 2, 26, 0, 0, 0), updated_at=datetime(2026, 2, 26, 0, 0, 0))
            p2 = Program(name="Program B", created_at=datetime(2026, 2, 26, 0, 0, 0), updated_at=datetime(2026, 2, 26, 0, 0, 0))
            db.add_all([p1, p2])
            db.flush()
            m1 = Molecule(program_id=int(p1.id), primary_id="M1", title="Mol 1", created_at=datetime(2026, 2, 26, 0, 0, 0), updated_at=datetime(2026, 2, 26, 0, 0, 0))
            m2 = Molecule(program_id=int(p1.id), primary_id="M2", title="Mol 2", created_at=datetime(2026, 2, 26, 0, 0, 0), updated_at=datetime(2026, 2, 26, 0, 0, 0))
            db.add_all([m1, m2])
            db.commit()

            molecule_payload = {
                "sections": {
                    "identity_context": {
                        "primary_id": "M1",
                        "title": "Mol 1",
                        "program_id": int(p1.id),
                        "snapshot_id": 11,
                    }
                }
            }
            program_payload = {"sections": {"metadata": {"program_id": int(p1.id)}}}
            mol_comp_payload = {
                "sections": {
                    "molecule_set": {
                        "rows": [
                            {"molecule_id": int(m1.id), "primary_id": "M1", "title": "Mol 1"},
                            {"molecule_id": int(m2.id), "primary_id": "M2", "title": "Mol 2"},
                        ]
                    }
                }
            }
            prog_comp_payload = {
                "sections": {
                    "program_set": {
                        "rows": [
                            {"program_id": int(p1.id), "molecule_count": 2},
                            {"program_id": int(p2.id), "molecule_count": 0},
                        ]
                    }
                }
            }

            s1 = build_report_identity_summary(
                db,
                report_type="molecule_report",
                payload=molecule_payload,
                subject_ids=[int(m1.id)],
                snapshot_coverage=[11],
            )
            s2 = build_report_identity_summary(
                db,
                report_type="program_report",
                payload=program_payload,
                subject_ids=[int(p1.id)],
                snapshot_coverage=[],
            )
            s3 = build_report_identity_summary(
                db,
                report_type="molecule_comparative_report",
                payload=mol_comp_payload,
                subject_ids=[int(m1.id), int(m2.id)],
                snapshot_coverage=[],
            )
            s4 = build_report_identity_summary(
                db,
                report_type="program_comparative_report",
                payload=prog_comp_payload,
                subject_ids=[int(p1.id), int(p2.id)],
                snapshot_coverage=[],
            )
            assert s1 == "M1 (Mol 1) · program_id=1 · snapshot_id=11"
            assert s2 == "Program A (program_id=1)"
            assert s3 == "M1 (Mol 1), M2 (Mol 2)"
            assert s4 == "Program A (program_id=1), Program B (program_id=2)"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_report_option_endpoints_are_stable_and_filtered() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p2 = Program(name="P2", created_at=datetime(2026, 2, 26, 0, 0, 0), updated_at=datetime(2026, 2, 26, 0, 0, 0))
            p1 = Program(name="P1", created_at=datetime(2026, 2, 26, 0, 0, 0), updated_at=datetime(2026, 2, 26, 0, 0, 0))
            db.add_all([p2, p1])
            db.flush()
            db.add_all(
                [
                    Molecule(program_id=int(p1.id), primary_id="B", title="T2", created_at=datetime(2026, 2, 26, 0, 0, 0), updated_at=datetime(2026, 2, 26, 0, 0, 0)),
                    Molecule(program_id=int(p1.id), primary_id="A", title="T1", created_at=datetime(2026, 2, 26, 0, 0, 0), updated_at=datetime(2026, 2, 26, 0, 0, 0)),
                    Molecule(program_id=int(p2.id), primary_id="C", title="T3", created_at=datetime(2026, 2, 26, 0, 0, 0), updated_at=datetime(2026, 2, 26, 0, 0, 0)),
                ]
            )
            db.commit()

            programs = report_options_programs(db=db)
            assert [x["id"] for x in programs] == [int(p2.id), int(p1.id)]

            molecules = report_options_molecules(program_id=int(p1.id), db=db)
            assert [x["primary_id"] for x in molecules] == ["A", "B"]
            assert all(int(x["program_id"]) == int(p1.id) for x in molecules)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_report_detail_exposes_canonical_measurement_citation_mapping() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p = Program(name="Program A", created_at=datetime(2026, 2, 26, 0, 0, 0), updated_at=datetime(2026, 2, 26, 0, 0, 0))
            db.add(p)
            db.flush()
            m = Molecule(program_id=int(p.id), primary_id="M1", title="Mol 1", created_at=datetime(2026, 2, 26, 0, 0, 0), updated_at=datetime(2026, 2, 26, 0, 0, 0))
            db.add(m)
            db.flush()
            payload = {
                "metadata": {
                    "report_type": "molecule_report",
                    "subject_ids": [int(m.id)],
                    "as_of": "2026-02-26T00:00:00",
                    "policy_pins": {},
                    "snapshot_coverage": [],
                },
                "sections": {
                    "identity_context": {"molecule_id": int(m.id), "primary_id": "M1", "title": "Mol 1"},
                    "fact_sheet": {},
                    "artifacts": {},
                    "reproducibility_appendix": {},
                    "comparability_surface": {
                        "assessments": [
                            {"cited_measurement_keys": ["hmw_percent", "hmw_pct"], "cited_snapshot_ids": []}
                        ]
                    },
                },
            }
            row = ReportRun(
                report_type="molecule_report",
                subject_ids_json=canonical_report_json([int(m.id)]),
                as_of=datetime(2026, 2, 26, 0, 0, 0),
                policy_pins_json=canonical_report_json({}),
                snapshot_coverage_json=canonical_report_json([]),
                payload_json=canonical_report_json(payload),
                created_at=datetime(2026, 2, 26, 0, 0, 0),
            )
            db.add(row)
            db.commit()
            db.refresh(row)

            ctx = get_report_run_detail(db, int(row.id))
            assert ctx["measurement_key_citations"] == ["hmw_pct", "hmw_percent"]
            assert ctx["measurement_key_citations_display"] == ["hmw_pct"]
            assert ctx["measurement_key_citation_map"] == [
                {"raw_key": "hmw_pct", "canonical_key": "hmw_pct"},
                {"raw_key": "hmw_percent", "canonical_key": "hmw_pct"},
            ]
        finally:
            db.close()
    finally:
        eng.dispose()
