from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from contextlib import contextmanager

from fastapi import BackgroundTasks

from psi.core.models import DomainInstance, Molecule, MoleculeComponent, Program
from psi.web.routers import molecules as molecules_router
from psi.services import molecules as molecules_svc


def _seed_scope(db):
    now = datetime(2026, 3, 10)
    p = Program(name="P-molecule-split", created_at=now, updated_at=now)
    db.add(p)
    db.commit()
    db.refresh(p)
    m = Molecule(program_id=int(p.id), primary_id="M-SPLIT", title="split", created_at=now, updated_at=now)
    db.add(m)
    db.commit()
    db.refresh(m)
    return p, m


def _seed_component(db, *, molecule_id: int) -> MoleculeComponent:
    now = datetime(2026, 3, 10)
    c = MoleculeComponent(
        molecule_id=int(molecule_id),
        role="HC1",
        fasta="EVQLVESGGGLVQPGGSLRLSCAASGFTF",
        sha256="x",
        created_at=now,
        updated_at=now,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_molecule_results_route_renders_surface(mkdb, dummy_templates, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            _p, m = _seed_scope(db)
            monkeypatch.setattr(molecules_router, "get_templates", lambda _request: dummy_templates)
            resp = molecules_router.molecule_results(
                molecule_id=int(m.id),
                request=SimpleNamespace(query_params={}),
                db=db,
            )
            assert resp.context["surface"]["surface_key"] == "molecule_results"
            assert int(resp.context["molecule"].id) == int(m.id)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_molecule_sequence_route_renders_surface(mkdb, dummy_templates, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            _p, m = _seed_scope(db)
            monkeypatch.setattr(molecules_router, "get_templates", lambda _request: dummy_templates)
            resp = molecules_router.molecule_sequence(
                molecule_id=int(m.id),
                request=SimpleNamespace(query_params={}),
                db=db,
            )
            assert resp.context["surface"]["surface_key"] == "molecule_sequence"
            assert int(resp.context["molecule"].id) == int(m.id)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_molecule_governance_route_renders_surface(mkdb, dummy_templates, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            _p, m = _seed_scope(db)
            monkeypatch.setattr(molecules_router, "get_templates", lambda _request: dummy_templates)
            resp = molecules_router.molecule_governance(
                molecule_id=int(m.id),
                request=SimpleNamespace(query_params={}),
                db=db,
            )
            assert resp.context["surface"]["surface_key"] == "molecule_governance"
            assert int(resp.context["molecule"].id) == int(m.id)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_flatten_result_value_rows_prefers_extracted_measurements(monkeypatch) -> None:
    fake_record = SimpleNamespace(id=11, title="Binding run", run_date="2026-03-10")
    fake_panel = {
        "batch": SimpleNamespace(id=7, batch_id="M-SPLIT-001"),
        "batch_label": "M-SPLIT-001",
        "assays": {
            "Binding": {
                "cond-1": {
                    "runs": [
                        {
                            "record": fake_record,
                            "summary": {"kind": "Binding", "kd_nM": 9.1},
                        }
                    ]
                }
            }
        },
    }

    monkeypatch.setattr(
        molecules_router,
        "list_measurements_for_record",
        lambda _db, record_id: [{"metric_key": "kd_nM", "value_num": 3.2, "unit": "nM"}] if int(record_id) == 11 else [],
    )
    fake_unassigned_record = SimpleNamespace(id=12, title="Molecule-level run", run_date="2026-03-11")
    fake_unassigned = [{"record": fake_unassigned_record, "summary": {"kind": "Expression"}}]

    rows = molecules_router._flatten_result_value_rows(SimpleNamespace(), [fake_panel], fake_unassigned)
    assert rows
    assert any(
        (r.get("metric") == "kd_nM" and r.get("value") == "3.2" and r.get("units") == "nM")
        for r in rows
    )
    assert any((r.get("record_id") == 12 and r.get("batch_label") == "Unassigned") for r in rows)


def test_recompute_domains_redirects_back_to_sequence_when_requested(mkdb) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            _p, m = _seed_scope(db)
            resp = molecules_router.recompute_domains(
                molecule_id=int(m.id),
                background_tasks=BackgroundTasks(),
                return_to=f"/molecules/{int(m.id)}/sequence#sequence-viewer",
                db=db,
            )
            assert resp.status_code == 303
            assert (
                resp.headers.get("location")
                == f"/molecules/{int(m.id)}/sequence?domains_status=started#sequence-viewer"
            )
        finally:
            db.close()
    finally:
        eng.dispose()


def test_recompute_domains_background_uses_writable_session(mkdb, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            _p, m = _seed_scope(db)
            seen: dict[str, object] = {"ensure": None, "called": False}

            @contextmanager
            def fake_db_ctx(_db_path, ensure=False):
                seen["ensure"] = ensure
                yield SimpleNamespace()

            def fake_extract(_session, _molecule_id):
                seen["called"] = True

            monkeypatch.setattr(molecules_router, "get_db_ctx", fake_db_ctx)
            monkeypatch.setattr(molecules_router, "extract_domains_for_molecule", fake_extract)
            bg = BackgroundTasks()
            resp = molecules_router.recompute_domains(
                molecule_id=int(m.id),
                background_tasks=bg,
                return_to=f"/molecules/{int(m.id)}/sequence#sequence-viewer",
                db=db,
            )
            assert resp.status_code == 303
            assert len(bg.tasks) == 1
            t = bg.tasks[0]
            t.func(*t.args, **t.kwargs)
            assert seen["ensure"] is True
            assert seen["called"] is True
        finally:
            db.close()
    finally:
        eng.dispose()


def test_run_numbering_redirects_back_to_sequence_when_requested(mkdb) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            _p, m = _seed_scope(db)
            resp = molecules_router.run_numbering(
                molecule_id=int(m.id),
                background_tasks=BackgroundTasks(),
                scheme="kabat",
                return_to=f"/molecules/{int(m.id)}/sequence#sequence-viewer",
                db=db,
            )
            assert resp.status_code == 303
            assert (
                resp.headers.get("location")
                == f"/molecules/{int(m.id)}/sequence?scheme=kabat&numbering_status=no_domains#sequence-viewer"
            )
        finally:
            db.close()
    finally:
        eng.dispose()


def test_run_numbering_redirects_missing_dependencies_when_domains_present(mkdb, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            _p, m = _seed_scope(db)
            c = _seed_component(db, molecule_id=int(m.id))
            now = datetime(2026, 3, 10)
            db.add(
                DomainInstance(
                    molecule_id=int(m.id),
                    component_id=int(c.id),
                    domain_type="VH",
                    start_idx=0,
                    end_idx=10,
                    domain_sequence_id=None,
                    source="auto",
                    method="test",
                    status="success",
                    created_at=now,
                    updated_at=now,
                )
            )
            db.commit()
            monkeypatch.setattr(
                molecules_router,
                "numbering_dependency_status",
                lambda: {
                    "ok": False,
                    "missing": ["abnumber", "anarci"],
                    "components": {
                        "abnumber": {"available": False, "version": None, "error": "ImportError: missing"},
                        "anarci": {"available": False, "version": None, "error": "ImportError: missing"},
                        "biopython": {"available": True, "version": "1.83", "error": None},
                    },
                },
            )
            bg = BackgroundTasks()
            resp = molecules_router.run_numbering(
                molecule_id=int(m.id),
                background_tasks=bg,
                scheme="kabat",
                return_to=f"/molecules/{int(m.id)}/sequence#sequence-viewer",
                db=db,
            )
            assert resp.status_code == 303
            assert (
                resp.headers.get("location")
                == f"/molecules/{int(m.id)}/sequence?scheme=kabat&numbering_status=missing_dependencies&numbering_missing=abnumber%2Canarci#sequence-viewer"
            )
            assert len(bg.tasks) == 0
        finally:
            db.close()
    finally:
        eng.dispose()


def test_run_numbering_starts_when_domains_and_dependency_present(mkdb, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            _p, m = _seed_scope(db)
            c = _seed_component(db, molecule_id=int(m.id))
            now = datetime(2026, 3, 10)
            db.add(
                DomainInstance(
                    molecule_id=int(m.id),
                    component_id=int(c.id),
                    domain_type="VH",
                    start_idx=0,
                    end_idx=10,
                    domain_sequence_id=None,
                    source="auto",
                    method="test",
                    status="success",
                    created_at=now,
                    updated_at=now,
                )
            )
            db.commit()
            monkeypatch.setattr(
                molecules_router,
                "numbering_dependency_status",
                lambda: {
                    "ok": True,
                    "missing": [],
                    "components": {
                        "abnumber": {"available": True, "version": "0.4.4", "error": None},
                        "anarci": {"available": True, "version": "1.3", "error": None},
                        "biopython": {"available": True, "version": "1.83", "error": None},
                    },
                },
            )
            bg = BackgroundTasks()
            resp = molecules_router.run_numbering(
                molecule_id=int(m.id),
                background_tasks=bg,
                scheme="kabat",
                return_to=f"/molecules/{int(m.id)}/sequence#sequence-viewer",
                db=db,
            )
            assert resp.status_code == 303
            assert (
                resp.headers.get("location")
                == f"/molecules/{int(m.id)}/sequence?scheme=kabat&numbering_status=started#sequence-viewer"
            )
            assert len(bg.tasks) == 1
        finally:
            db.close()
    finally:
        eng.dispose()


def test_run_numbering_background_uses_writable_session(mkdb, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            _p, m = _seed_scope(db)
            c = _seed_component(db, molecule_id=int(m.id))
            now = datetime(2026, 3, 10)
            db.add(
                DomainInstance(
                    molecule_id=int(m.id),
                    component_id=int(c.id),
                    domain_type="VH",
                    start_idx=0,
                    end_idx=10,
                    domain_sequence_id=None,
                    source="auto",
                    method="test",
                    status="success",
                    created_at=now,
                    updated_at=now,
                )
            )
            db.commit()
            seen: dict[str, object] = {"ensure": None, "called": False}

            @contextmanager
            def fake_db_ctx(_db_path, ensure=False):
                seen["ensure"] = ensure
                yield SimpleNamespace()

            def fake_trigger(*_args, **_kwargs):
                seen["called"] = True
                return []

            monkeypatch.setattr(
                molecules_router,
                "numbering_dependency_status",
                lambda: {
                    "ok": True,
                    "missing": [],
                    "components": {
                        "abnumber": {"available": True, "version": "0.4.4", "error": None},
                        "anarci": {"available": True, "version": "1.3", "error": None},
                        "biopython": {"available": True, "version": "1.83", "error": None},
                    },
                },
            )
            monkeypatch.setattr(molecules_router, "get_db_ctx", fake_db_ctx)
            monkeypatch.setattr(molecules_router, "trigger_numbering_for_molecule", fake_trigger)
            bg = BackgroundTasks()
            resp = molecules_router.run_numbering(
                molecule_id=int(m.id),
                background_tasks=bg,
                scheme="kabat",
                return_to=f"/molecules/{int(m.id)}/sequence#sequence-viewer",
                db=db,
            )
            assert resp.status_code == 303
            assert len(bg.tasks) == 1
            t = bg.tasks[0]
            t.func(*t.args, **t.kwargs)
            assert seen["ensure"] is True
            assert seen["called"] is True
        finally:
            db.close()
    finally:
        eng.dispose()


def test_background_domain_extraction_uses_writable_session(monkeypatch) -> None:
    seen: dict[str, object] = {"ensure": None, "called": False}

    @contextmanager
    def fake_get_db(_db_path, ensure=False):
        seen["ensure"] = ensure
        yield SimpleNamespace()

    def fake_extract(_db, _molecule_id):
        seen["called"] = True

    monkeypatch.setattr(molecules_svc, "get_db", fake_get_db)
    monkeypatch.setattr(molecules_svc, "extract_domains_for_molecule", fake_extract)
    molecules_svc._background_domain_extraction(123, "/tmp/test.sqlite")
    assert seen["ensure"] is True
    assert seen["called"] is True


def test_background_compute_uses_writable_session(monkeypatch) -> None:
    seen: dict[str, object] = {"ensure": None, "called": False}

    @contextmanager
    def fake_get_db(_db_path, ensure=False):
        seen["ensure"] = ensure
        yield SimpleNamespace(get=lambda *_args, **_kwargs: SimpleNamespace(heavy_compute_enabled=0))

    def fake_run(_db, **_kwargs):
        seen["called"] = True

    monkeypatch.setattr(molecules_svc, "get_db", fake_get_db)
    monkeypatch.setattr(molecules_svc, "run_computed_properties", fake_run)
    molecules_svc._background_compute(123, "manual_recompute", "/tmp/test.sqlite")
    assert seen["ensure"] is True
    assert seen["called"] is True
