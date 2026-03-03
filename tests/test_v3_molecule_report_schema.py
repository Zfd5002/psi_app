from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base, Batch, DataRecord, DecisionSnapshot, Molecule, Program
from psi.core.utils import stable_json_dumps
from psi.services.report_engine import canonical_report_json, generate_molecule_report_v0, load_report_run_payload


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


def _seed_and_generate():
    eng, SessionTmp = _mkdb()
    db = SessionTmp()
    try:
        p = Program(name="P", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
        db.add(p)
        db.flush()
        m = Molecule(
            program_id=int(p.id),
            primary_id="M-15",
            title="Mol 15",
            created_at=datetime(2026, 3, 3),
            updated_at=datetime(2026, 3, 3),
        )
        db.add(m)
        db.flush()
        b = Batch(
            molecule_id=int(m.id),
            batch_id="M-15-001",
            title="Batch 1",
            created_at=datetime(2026, 3, 3, 9, 0, 0),
            updated_at=datetime(2026, 3, 3, 9, 0, 0),
        )
        db.add(b)
        db.flush()
        r = DataRecord(
            program_id=int(p.id),
            molecule_id=int(m.id),
            batch_id=int(b.id),
            domain="in_vitro",
            data_type="binding",
            method="spr",
            title="SPR run",
            notes="note-a",
            run_date="2026-03-03",
            created_at=datetime(2026, 3, 3, 10, 0, 0),
            updated_at=datetime(2026, 3, 3, 10, 0, 0),
        )
        db.add(r)
        db.flush()
        db.execute(
            text(
                """
                INSERT INTO data_measurements
                (data_record_id, metric_key, name, value_num, value_text, unit, qc_flag, ignore_for_model, created_at)
                VALUES
                (:rid, 'ec50', 'ec50', 12.3, NULL, 'nM', 'approved', 0, '2026-03-03T10:00:00'),
                (:rid, 'kd', 'kd', 4.2, NULL, 'nM', 'approved', 0, '2026-03-03T10:00:00')
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
                {
                    "decision_state": "ready",
                    "readiness": {"state": "ready"},
                    "gates": [
                        {"gate_key": "G1", "required_metrics": ["ec50", "kd"], "status": "pass"},
                    ],
                    "used_by_metric": {},
                }
            ),
            evidence_ids_json="[]",
            created_at=datetime(2026, 3, 3, 10, 5, 0),
        )
        db.add(snap)
        db.commit()
        row = generate_molecule_report_v0(
            db,
            molecule_id=int(m.id),
            as_of=datetime(2026, 3, 3, 11, 0, 0),
            policy_pins={"report_policy": "v0"},
        )
        payload = load_report_run_payload(row)
        return db, eng, int(m.id), row, payload
    except Exception:
        db.close()
        eng.dispose()
        raise


def test_molecule_report_fact_sheet_schema_v1_required_keys_present() -> None:
    db, eng, _mid, _row, payload = _seed_and_generate()
    try:
        sections = payload.get("sections") if isinstance(payload.get("sections"), dict) else {}
        fact = sections.get("fact_sheet") if isinstance(sections.get("fact_sheet"), dict) else {}
        assert str(fact.get("schema_version") or "") == "v1"
        assert isinstance(fact.get("meta"), dict)
        assert isinstance(fact.get("metrics_index"), dict)
        assert isinstance(fact.get("batch_registry"), list)
        assert isinstance(fact.get("metric_matrix"), dict)
        assert isinstance(fact.get("coverage_summary"), dict)
        best_batch = fact.get("best_batch") if isinstance(fact.get("best_batch"), dict) else {}
        assert set(best_batch.keys()) == {"status", "selection_method", "selected_batch_id", "trace"}
        assert str(best_batch.get("status") or "") == "computed"
        assert str(best_batch.get("selection_method") or "") == "coverage_score_v1"
        assert best_batch.get("selected_batch_id") is not None
        assert isinstance(best_batch.get("trace"), list)
        stability = fact.get("stability") if isinstance(fact.get("stability"), dict) else {}
        assert set(stability.keys()) == {"status", "method", "rationale"}
        assert str(stability.get("method") or "") == "coverage_only_v1"
        assert isinstance(stability.get("rationale"), list)
        metrics_index = fact.get("metrics_index") if isinstance(fact.get("metrics_index"), dict) else {}
        assert isinstance(metrics_index.get("template_ids_used"), list)
        assert isinstance(metrics_index.get("required_metric_keys"), list)
        assert "advance_to_in_vivo" in metrics_index.get("template_ids_used", [])
    finally:
        db.close()
        eng.dispose()


def test_molecule_report_fact_sheet_cell_uses_resolved_value_and_unit_not_n_cited() -> None:
    db, eng, _mid, _row, payload = _seed_and_generate()
    try:
        fact = payload.get("sections", {}).get("fact_sheet", {})
        matrix = fact.get("metric_matrix") if isinstance(fact.get("metric_matrix"), dict) else {}
        rows = matrix.get("rows") if isinstance(matrix.get("rows"), list) else []
        ec50 = next((r for r in rows if isinstance(r, dict) and str(r.get("metric_key") or "") == "ec50"), {})
        cells = ec50.get("cells") if isinstance(ec50.get("cells"), list) else []
        assert cells
        first = cells[0] if isinstance(cells[0], dict) else {}
        assert str(first.get("display") or "").startswith("12.3")
        assert "cited" not in str(first.get("display") or "").lower()
        assert first.get("measurement_id") is not None
        assert first.get("data_record_id") is not None
    finally:
        db.close()
        eng.dispose()


def test_payload_deterministic_on_repeat_generation() -> None:
    db, eng, mid, _row, p1 = _seed_and_generate()
    try:
        row2 = generate_molecule_report_v0(
            db,
            molecule_id=int(mid),
            as_of=datetime(2026, 3, 3, 11, 0, 0),
            policy_pins={"report_policy": "v0"},
        )
        p2 = load_report_run_payload(row2)
        assert canonical_report_json(p1) == canonical_report_json(p2)
    finally:
        db.close()
        eng.dispose()


def test_best_batch_tiebreak_deterministic() -> None:
    eng, SessionTmp = _mkdb()
    db = SessionTmp()
    try:
        p = Program(name="P", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
        db.add(p)
        db.flush()
        m = Molecule(
            program_id=int(p.id),
            primary_id="M-16",
            title="Mol 16",
            created_at=datetime(2026, 3, 3),
            updated_at=datetime(2026, 3, 3),
        )
        db.add(m)
        db.flush()
        b1 = Batch(molecule_id=int(m.id), batch_id="B1", title="Batch 1", created_at=datetime(2026, 3, 3, 9), updated_at=datetime(2026, 3, 3, 9))
        b2 = Batch(molecule_id=int(m.id), batch_id="B2", title="Batch 2", created_at=datetime(2026, 3, 3, 10), updated_at=datetime(2026, 3, 3, 10))
        db.add_all([b1, b2])
        db.flush()
        r1 = DataRecord(
            program_id=int(p.id), molecule_id=int(m.id), batch_id=int(b1.id), domain="d", data_type="t", method="m", title="R1", notes="n1",
            run_date="2026-03-03", created_at=datetime(2026, 3, 3, 11), updated_at=datetime(2026, 3, 3, 11),
        )
        r2 = DataRecord(
            program_id=int(p.id), molecule_id=int(m.id), batch_id=int(b2.id), domain="d", data_type="t", method="m", title="R2", notes="n2",
            run_date="2026-03-03", created_at=datetime(2026, 3, 3, 12), updated_at=datetime(2026, 3, 3, 12),
        )
        db.add_all([r1, r2])
        db.flush()
        db.execute(
            text(
                """
                INSERT INTO data_measurements
                (data_record_id, metric_key, name, value_num, value_text, unit, qc_flag, ignore_for_model, created_at)
                VALUES
                (:r1, 'ec50', 'ec50', 10.0, NULL, 'nM', 'approved', 0, '2026-03-03T11:00:00'),
                (:r2, 'ec50', 'ec50', 11.0, NULL, 'nM', 'approved', 0, '2026-03-03T12:00:00')
                """
            ),
            {"r1": int(r1.id), "r2": int(r2.id)},
        )
        snap = DecisionSnapshot(
            program_id=int(p.id),
            molecule_id=int(m.id),
            batch_id=int(b2.id),
            decision_key="advance_to_in_vivo",
            rules_version="v0",
            engine_key="di",
            schema_version="di.snapshot.v0_4",
            inputs_json=stable_json_dumps({"engine_key": "di"}),
            outputs_json=stable_json_dumps({"gates": [{"gate_key": "G1", "required_metrics": ["ec50"], "status": "pass"}]}),
            evidence_ids_json="[]",
            created_at=datetime(2026, 3, 3, 12, 5),
        )
        db.add(snap)
        db.commit()
        row = generate_molecule_report_v0(db, molecule_id=int(m.id), as_of=datetime(2026, 3, 3, 13), policy_pins={"report_policy": "v0"})
        payload = load_report_run_payload(row)
        fact = payload.get("sections", {}).get("fact_sheet", {})
        best = fact.get("best_batch") if isinstance(fact.get("best_batch"), dict) else {}
        assert str(best.get("selection_method") or "") == "coverage_score_v1"
        assert int(best.get("selected_batch_id") or 0) == int(b2.id)
    finally:
        db.close()
        eng.dispose()


def test_best_batch_trace_persisted_and_sorted() -> None:
    db, eng, _mid, _row, payload = _seed_and_generate()
    try:
        fact = payload.get("sections", {}).get("fact_sheet", {})
        best = fact.get("best_batch") if isinstance(fact.get("best_batch"), dict) else {}
        trace = best.get("trace") if isinstance(best.get("trace"), list) else []
        assert trace
        first = trace[0] if isinstance(trace[0], dict) else {}
        assert int(first.get("batch_id") or 0) == int(best.get("selected_batch_id") or 0)
        scores = [tuple((t or {}).get("score") or []) for t in trace if isinstance(t, dict)]
        assert scores == sorted(scores, reverse=True)
    finally:
        db.close()
        eng.dispose()


def test_stability_insufficient_with_one_batch() -> None:
    db, eng, _mid, _row, payload = _seed_and_generate()
    try:
        fact = payload.get("sections", {}).get("fact_sheet", {})
        stability = fact.get("stability") if isinstance(fact.get("stability"), dict) else {}
        assert str(stability.get("status") or "") == "insufficient_data"
        assert str(stability.get("method") or "") == "coverage_only_v1"
    finally:
        db.close()
        eng.dispose()


def test_stability_unstable_on_regression_threshold() -> None:
    eng, SessionTmp = _mkdb()
    db = SessionTmp()
    try:
        p = Program(name="P", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
        db.add(p)
        db.flush()
        m = Molecule(program_id=int(p.id), primary_id="M-17", title="Mol 17", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
        db.add(m)
        db.flush()
        b_old = Batch(molecule_id=int(m.id), batch_id="B-OLD", title="Old", created_at=datetime(2026, 3, 3, 8), updated_at=datetime(2026, 3, 3, 8))
        b_new = Batch(molecule_id=int(m.id), batch_id="B-NEW", title="New", created_at=datetime(2026, 3, 3, 12), updated_at=datetime(2026, 3, 3, 12))
        db.add_all([b_old, b_new])
        db.flush()
        r_old = DataRecord(
            program_id=int(p.id), molecule_id=int(m.id), batch_id=int(b_old.id), domain="d", data_type="t", method="m", title="Old rec", notes="n",
            run_date="2026-03-02", created_at=datetime(2026, 3, 3, 9), updated_at=datetime(2026, 3, 3, 9),
        )
        r_new = DataRecord(
            program_id=int(p.id), molecule_id=int(m.id), batch_id=int(b_new.id), domain="d", data_type="t", method="m", title="New rec", notes="n",
            run_date="2026-03-03", created_at=datetime(2026, 3, 3, 13), updated_at=datetime(2026, 3, 3, 13),
        )
        db.add_all([r_old, r_new])
        db.flush()
        db.execute(
            text(
                """
                INSERT INTO data_measurements
                (data_record_id, metric_key, name, value_num, value_text, unit, qc_flag, ignore_for_model, created_at)
                VALUES
                (:old_id, 'ec50', 'ec50', 1.1, NULL, 'nM', 'approved', 0, '2026-03-03T09:00:00'),
                (:old_id, 'kd', 'kd', 2.2, NULL, 'nM', 'approved', 0, '2026-03-03T09:00:00'),
                (:old_id, 'ic50', 'ic50', 3.3, NULL, 'nM', 'approved', 0, '2026-03-03T09:00:00'),
                (:new_id, 'ec50', 'ec50', 4.4, NULL, 'nM', 'approved', 0, '2026-03-03T13:00:00')
                """
            ),
            {"old_id": int(r_old.id), "new_id": int(r_new.id)},
        )
        snap = DecisionSnapshot(
            program_id=int(p.id),
            molecule_id=int(m.id),
            batch_id=int(b_old.id),
            decision_key="advance_to_in_vivo",
            rules_version="v0",
            engine_key="di",
            schema_version="di.snapshot.v0_4",
            inputs_json=stable_json_dumps({"engine_key": "di"}),
            outputs_json=stable_json_dumps({"gates": [{"gate_key": "G1", "required_metrics": ["ec50", "kd", "ic50"], "status": "pass"}]}),
            evidence_ids_json="[]",
            created_at=datetime(2026, 3, 3, 13, 5),
        )
        db.add(snap)
        db.commit()
        row = generate_molecule_report_v0(db, molecule_id=int(m.id), as_of=datetime(2026, 3, 3, 14), policy_pins={"report_policy": "v0"})
        payload = load_report_run_payload(row)
        stability = payload.get("sections", {}).get("fact_sheet", {}).get("stability", {})
        assert str(stability.get("status") or "") == "unstable"
    finally:
        db.close()
        eng.dispose()


def test_stability_not_snapshot_dependent() -> None:
    db, eng, mid, _row, _payload = _seed_and_generate()
    try:
        row_a = generate_molecule_report_v0(
            db,
            molecule_id=int(mid),
            as_of=datetime(2026, 3, 3, 11, 0, 0),
            policy_pins={"report_policy": "v0"},
        )
        payload_a = load_report_run_payload(row_a)
        db.execute(
            text(
                """
                UPDATE decision_snapshots
                SET outputs_json = :out
                WHERE molecule_id = :mid
                """
            ),
            {
                "mid": int(mid),
                "out": stable_json_dumps(
                    {
                        "decision_state": "not_ready",
                        "readiness": {"state": "not_ready"},
                        "gates": [{"gate_key": "G1", "required_metrics": ["ec50", "kd"], "status": "fail"}],
                    }
                ),
            },
        )
        db.commit()
        row_b = generate_molecule_report_v0(
            db,
            molecule_id=int(mid),
            as_of=datetime(2026, 3, 3, 11, 0, 0),
            policy_pins={"report_policy": "v0"},
        )
        payload_b = load_report_run_payload(row_b)
        s_a = payload_a.get("sections", {}).get("fact_sheet", {}).get("stability", {})
        s_b = payload_b.get("sections", {}).get("fact_sheet", {}).get("stability", {})
        assert s_a == s_b
    finally:
        db.close()
        eng.dispose()


def test_fact_sheet_cell_schema_invariants() -> None:
    db, eng, _mid, _row, payload = _seed_and_generate()
    try:
        fact = payload.get("sections", {}).get("fact_sheet", {})
        matrix = fact.get("metric_matrix") if isinstance(fact.get("metric_matrix"), dict) else {}
        rows = matrix.get("rows") if isinstance(matrix.get("rows"), list) else []
        assert rows
        for row in rows:
            assert isinstance(row, dict)
            assert "metric_key" in row
            cells = row.get("cells") if isinstance(row.get("cells"), list) else []
            assert cells
            for cell in cells:
                assert isinstance(cell, dict)
                for key in ("status", "display", "measurement_id", "data_record_id"):
                    assert key in cell
    finally:
        db.close()
        eng.dispose()


def test_fact_sheet_ordering_invariants() -> None:
    eng, SessionTmp = _mkdb()
    db = SessionTmp()
    try:
        p = Program(name="P", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
        db.add(p)
        db.flush()
        m = Molecule(program_id=int(p.id), primary_id="M-18", title="Mol 18", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
        db.add(m)
        db.flush()
        b1 = Batch(molecule_id=int(m.id), batch_id="B1", title="Batch 1", created_at=datetime(2026, 3, 3, 8), updated_at=datetime(2026, 3, 3, 8))
        b2 = Batch(molecule_id=int(m.id), batch_id="B2", title="Batch 2", created_at=datetime(2026, 3, 3, 10), updated_at=datetime(2026, 3, 3, 10))
        db.add_all([b1, b2])
        db.flush()
        r1 = DataRecord(
            program_id=int(p.id), molecule_id=int(m.id), batch_id=int(b1.id), domain="d", data_type="t", method="m", title="R1", notes="n1",
            run_date="2026-03-02", created_at=datetime(2026, 3, 3, 9), updated_at=datetime(2026, 3, 3, 9),
        )
        r2 = DataRecord(
            program_id=int(p.id), molecule_id=int(m.id), batch_id=int(b2.id), domain="d", data_type="t", method="m", title="R2", notes="n2",
            run_date="2026-03-03", created_at=datetime(2026, 3, 3, 11), updated_at=datetime(2026, 3, 3, 11),
        )
        db.add_all([r1, r2])
        db.flush()
        db.execute(
            text(
                """
                INSERT INTO data_measurements
                (data_record_id, metric_key, name, value_num, value_text, unit, qc_flag, ignore_for_model, created_at)
                VALUES
                (:r1, 'kd', 'kd', 3.1, NULL, 'nM', 'approved', 0, '2026-03-03T09:00:00'),
                (:r1, 'ec50', 'ec50', 2.1, NULL, 'nM', 'approved', 0, '2026-03-03T09:00:00'),
                (:r2, 'ec50', 'ec50', 1.1, NULL, 'nM', 'approved', 0, '2026-03-03T11:00:00')
                """
            ),
            {"r1": int(r1.id), "r2": int(r2.id)},
        )
        snap = DecisionSnapshot(
            program_id=int(p.id),
            molecule_id=int(m.id),
            batch_id=int(b2.id),
            decision_key="advance_to_in_vivo",
            rules_version="v0",
            engine_key="di",
            schema_version="di.snapshot.v0_4",
            inputs_json=stable_json_dumps({"engine_key": "di"}),
            outputs_json=stable_json_dumps({"gates": [{"gate_key": "G1", "required_metrics": ["ec50", "kd"], "status": "pass"}]}),
            evidence_ids_json="[]",
            created_at=datetime(2026, 3, 3, 11, 5),
        )
        db.add(snap)
        db.commit()
        row = generate_molecule_report_v0(db, molecule_id=int(m.id), as_of=datetime(2026, 3, 3, 12), policy_pins={"report_policy": "v0"})
        payload = load_report_run_payload(row)
        fact = payload.get("sections", {}).get("fact_sheet", {})
        batch_registry = fact.get("batch_registry") if isinstance(fact.get("batch_registry"), list) else []
        assert [int((r or {}).get("batch_id") or 0) for r in batch_registry] == [int(b2.id), int(b1.id)]
        metrics_index = fact.get("metrics_index") if isinstance(fact.get("metrics_index"), dict) else {}
        required = metrics_index.get("required_metric_keys") if isinstance(metrics_index.get("required_metric_keys"), list) else []
        assert required == sorted(required)
        best = fact.get("best_batch") if isinstance(fact.get("best_batch"), dict) else {}
        trace = best.get("trace") if isinstance(best.get("trace"), list) else []
        scores = [tuple((t or {}).get("score") or []) for t in trace if isinstance(t, dict)]
        assert scores == sorted(scores, reverse=True)
    finally:
        db.close()
        eng.dispose()
