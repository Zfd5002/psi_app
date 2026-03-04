from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base, Batch, DataRecord, DecisionSnapshot, Molecule, Program
from psi.core.utils import stable_json_dumps
from psi.services.report_engine import generate_molecule_report_v0, load_report_run_payload
from psi.services.reports_v3 import _build_molecule_board_display, build_molecule_board_display_from_payload


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    with eng.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS data_measurements (
                    id INTEGER PRIMARY KEY,
                    data_record_id INTEGER NOT NULL,
                    metric_key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    value_num REAL,
                    value_text TEXT,
                    unit TEXT,
                    qc_flag TEXT,
                    ignore_for_model INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT
                )
                """
            )
        )
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def _seed_report():
    eng, SessionTmp = _mkdb()
    db = SessionTmp()
    p = Program(name="P", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
    db.add(p)
    db.flush()
    m = Molecule(program_id=int(p.id), primary_id="M-1", title="Mol", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
    db.add(m)
    db.flush()
    b = Batch(molecule_id=int(m.id), batch_id="B1", title="Batch 1", created_at=datetime(2026, 3, 3, 9), updated_at=datetime(2026, 3, 3, 9))
    db.add(b)
    db.flush()
    r = DataRecord(
        program_id=int(p.id),
        molecule_id=int(m.id),
        batch_id=int(b.id),
        domain="d",
        data_type="t",
        method="m",
        title="R",
        notes="frozen note",
        run_date="2026-03-03",
        created_at=datetime(2026, 3, 3, 10),
        updated_at=datetime(2026, 3, 3, 10),
    )
    db.add(r)
    db.flush()
    db.execute(
        text(
            """
            INSERT INTO data_measurements
            (data_record_id, metric_key, name, value_num, unit, qc_flag, ignore_for_model, created_at)
            VALUES (:rid, 'ec50', 'ec50', 9.1, 'nM', 'approved', 0, '2026-03-03T10:00:00')
            """
        ),
        {"rid": int(r.id)},
    )
    snap = DecisionSnapshot(
        program_id=int(p.id),
        molecule_id=int(m.id),
        batch_id=int(b.id),
        decision_key="advance_to_in_vivo",
        rules_version="v0",
        engine_key="di",
        schema_version="di.snapshot.v0_4",
        inputs_json=stable_json_dumps({"engine_key": "di"}),
        outputs_json=stable_json_dumps(
            {"decision_state": "ready", "readiness": {"state": "ready"}, "gates": [{"gate_key": "G1", "required_metrics": ["ec50"], "status": "pass"}]}
        ),
        evidence_ids_json="[]",
        created_at=datetime(2026, 3, 3, 10, 5),
    )
    db.add(snap)
    db.commit()
    row = generate_molecule_report_v0(
        db,
        molecule_id=int(m.id),
        as_of=datetime(2026, 3, 3, 11),
        policy_pins={"report_policy": "v0"},
    )
    payload = load_report_run_payload(row)
    return db, eng, row, payload


def test_fact_sheet_no_db_query_at_view_time() -> None:
    db, eng, row, payload = _seed_report()
    try:
        class NoQuerySession:
            def query(self, *_args, **_kwargs):
                raise AssertionError("view-time query not allowed")

        out = build_molecule_board_display_from_payload(row=row, payload=payload)
        assert isinstance(out, dict)
        # Ensure wrapper path used by report detail does not query.
        out2 = _build_molecule_board_display(
            NoQuerySession(),
            row=row,
            payload=payload,
            subject_ids=[1],
            snapshot_coverage=[],
        )
        assert out2.get("fact_sheet", {}).get("metric_rows") is not None
        assert "gate_summary" not in out2
    finally:
        db.close()
        eng.dispose()


def test_fact_sheet_notes_are_frozen_from_payload_not_live_db() -> None:
    db, eng, row, payload = _seed_report()
    try:
        # mutate source record after report creation
        db.execute(text("UPDATE data_records SET notes='mutated note' WHERE id = 1"))
        db.commit()
        out = build_molecule_board_display_from_payload(row=row, payload=payload)
        notes = out.get("scientist_notes") if isinstance(out.get("scientist_notes"), list) else []
        rendered = " | ".join(str((n or {}).get("body") or "") for n in notes if isinstance(n, dict))
        assert "frozen note" in rendered
        assert "mutated note" not in rendered
    finally:
        db.close()
        eng.dispose()


def test_report_does_not_persist_di_gate_sections_in_evidence_only_mode() -> None:
    db, eng, row, payload = _seed_report()
    try:
        fact = payload.get("sections", {}).get("fact_sheet", {})
        gates = fact.get("gates_v1", None) if isinstance(fact, dict) else None
        assert gates is None
    finally:
        db.close()
        eng.dispose()


def test_report_gate_render_no_db_query_at_view_time() -> None:
    db, eng, row, payload = _seed_report()
    try:
        class NoQuerySession:
            def query(self, *_args, **_kwargs):
                raise AssertionError("view-time query not allowed")

        out = _build_molecule_board_display(
            NoQuerySession(),
            row=row,
            payload=payload,
            subject_ids=[1],
            snapshot_coverage=[],
        )
        assert "gate_summary" not in out
    finally:
        db.close()
        eng.dispose()
