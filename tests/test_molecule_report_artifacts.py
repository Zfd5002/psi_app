from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base, Batch, DataRecord, File, FileLink, Molecule, Program
from psi.services.report_artifacts import assemble_molecule_report_artifacts
from psi.services.report_engine import generate_molecule_report_v0, load_report_run_payload
from psi.services.reports_v3 import _build_molecule_board_display


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


def _seed():
    eng, SessionTmp = _mkdb()
    db = SessionTmp()
    p = Program(name="P-art", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
    db.add(p)
    db.flush()
    m = Molecule(program_id=int(p.id), primary_id="M-art", title="Artifacts", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
    db.add(m)
    db.flush()
    b = Batch(molecule_id=int(m.id), batch_id="B-art", title="Batch", created_at=datetime(2026, 3, 3, 9), updated_at=datetime(2026, 3, 3, 9))
    db.add(b)
    db.flush()
    r1 = DataRecord(
        program_id=int(p.id),
        molecule_id=int(m.id),
        batch_id=int(b.id),
        domain="developability",
        data_type="sec_profile",
        method="sec_hplc",
        title="SEC profile",
        created_at=datetime(2026, 3, 3, 10, 0, 0),
        updated_at=datetime(2026, 3, 3, 10, 0, 0),
    )
    r2 = DataRecord(
        program_id=int(p.id),
        molecule_id=int(m.id),
        batch_id=int(b.id),
        domain="safety",
        data_type="endotoxin",
        method="lal",
        title="Endotoxin result",
        created_at=datetime(2026, 3, 3, 11, 0, 0),
        updated_at=datetime(2026, 3, 3, 11, 0, 0),
    )
    db.add_all([r1, r2])
    db.flush()
    f1 = File(stored_name="f1.bin", original_name="sec.csv", size_bytes=10, mime="text/csv", sha256="a" * 64, created_at=datetime(2026, 3, 3, 12, 0, 0))
    db.add(f1)
    db.flush()
    db.add(FileLink(file_id=int(f1.id), entity_type="DataRecord", entity_id=int(r1.id), label="SEC CSV", created_at=datetime(2026, 3, 3, 12, 0, 1)))
    db.commit()
    return eng, db, m


def test_molecule_report_persists_artifacts_section() -> None:
    eng, db, m = _seed()
    try:
        row = generate_molecule_report_v0(
            db,
            molecule_id=int(m.id),
            as_of=datetime(2026, 3, 3, 12, 30, 0),
            policy_pins={"report_policy": "v0"},
        )
        payload = load_report_run_payload(row)
        artifacts = payload.get("sections", {}).get("artifacts", {})
        assert str(artifacts.get("schema_version") or "") == "v1"
        assert isinstance(artifacts.get("items"), list)
        assert artifacts.get("items")
    finally:
        db.close()
        eng.dispose()


def test_artifacts_ordering_deterministic() -> None:
    eng, db, m = _seed()
    try:
        one = assemble_molecule_report_artifacts(db, molecule_id=int(m.id), as_of=datetime(2026, 3, 3, 12, 30, 0))
        two = assemble_molecule_report_artifacts(db, molecule_id=int(m.id), as_of=datetime(2026, 3, 3, 12, 30, 0))
        assert one == two
        items = one.get("items") if isinstance(one.get("items"), list) else []
        assert [str(i.get("artifact_type") or "") for i in items] == sorted(
            [str(i.get("artifact_type") or "") for i in items],
            key=lambda t: {"SEC": 0, "SDS_PAGE": 1, "ENDOTOXIN": 2, "OTHER": 3}.get(t, 3),
        )
    finally:
        db.close()
        eng.dispose()


def test_artifacts_render_no_db_query_at_view_time() -> None:
    eng, db, m = _seed()
    try:
        row = generate_molecule_report_v0(
            db,
            molecule_id=int(m.id),
            as_of=datetime(2026, 3, 3, 12, 30, 0),
            policy_pins={"report_policy": "v0"},
        )
        payload = load_report_run_payload(row)

        class NoQuerySession:
            def query(self, *_args, **_kwargs):
                raise AssertionError("view-time query not allowed")

        board = _build_molecule_board_display(
            NoQuerySession(),
            row=row,
            payload=payload,
            subject_ids=[int(m.id)],
            snapshot_coverage=[],
        )
        artifacts = board.get("artifacts") if isinstance(board.get("artifacts"), dict) else {}
        assert artifacts.get("items")
    finally:
        db.close()
        eng.dispose()


def test_artifacts_links_are_internal_and_stable() -> None:
    eng, db, m = _seed()
    try:
        out = assemble_molecule_report_artifacts(db, molecule_id=int(m.id), as_of=datetime(2026, 3, 3, 12, 30, 0))
        items = out.get("items") if isinstance(out.get("items"), list) else []
        assert items
        for item in items:
            links = item.get("links") if isinstance(item, dict) and isinstance(item.get("links"), list) else []
            assert links
            for link in links:
                url = str((link or {}).get("url") or "")
                assert url.startswith("/data/") or url.startswith("/files/")
    finally:
        db.close()
        eng.dispose()
