from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from contextlib import contextmanager
from pathlib import Path

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


def test_molecule_sequence_analysis_route_renders_surface(mkdb, dummy_templates, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            _p, m = _seed_scope(db)
            monkeypatch.setattr(molecules_router, "get_templates", lambda _request: dummy_templates)
            resp = molecules_router.molecule_sequence_analysis(
                molecule_id=int(m.id),
                request=SimpleNamespace(query_params={}),
                db=db,
            )
            assert resp.context["surface"]["surface_key"] == "molecule_sequence_analysis"
            assert int(resp.context["molecule"].id) == int(m.id)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_experiment_result_rows_one_row_per_data_record(monkeypatch) -> None:
    fake_record = SimpleNamespace(
        id=11,
        title="Binding run",
        run_date="2026-03-10",
        data_type="BINDING",
        method="SPR",
        primary_result_text="",
    )
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
        lambda _db, record_id: (
            [
                {"metric_key": "kd_nM", "value_num": 3.2, "unit": "nM"},
                {"metric_key": "kon", "value_num": 9.1e4, "unit": "1/Ms"},
                {"metric_key": "koff", "value_num": 0.008, "unit": "1/s"},
                {"metric_key": "chi2", "value_num": 1.2, "unit": ""},
                {"metric_key": "conclusion", "value_text": "pass", "unit": ""},
            ]
            if int(record_id) == 11
            else []
        ),
    )
    rows = molecules_router._build_experiment_result_rows(SimpleNamespace(), [fake_panel], [])
    assert len(rows) == 1
    row = rows[0]
    assert int(row.get("record_id") or 0) == 11
    assert row.get("result") == "pass"
    # Summary capped and deterministic: core binding metrics are preferred over fit diagnostics.
    summary = str(row.get("summary") or "")
    assert summary.count(";") <= 2
    assert "KD 3.2 nM" in summary
    assert "Kon 91,000 M^-1 s^-1" in summary
    assert "Koff 0.008 s^-1" in summary
    assert "Chi2" not in summary


def test_experiment_result_rows_uses_batched_measurement_lookup_when_available(monkeypatch) -> None:
    rec_a = SimpleNamespace(
        id=901,
        title="A",
        run_date="2026-03-10",
        data_type="BINDING",
        method="SPR",
        primary_result_text="",
    )
    rec_b = SimpleNamespace(
        id=902,
        title="B",
        run_date="2026-03-09",
        data_type="BINDING",
        method="SPR",
        primary_result_text="",
    )
    panel = {
        "batch": SimpleNamespace(id=7, batch_id="M-SPLIT-001"),
        "batch_label": "M-SPLIT-001",
        "assays": {"Binding": {"cond-1": {"runs": [{"record": rec_a}, {"record": rec_b}]}}},
    }
    seen: list[list[int]] = []

    def _batched(_db, *, record_ids):
        ids = sorted(int(x) for x in record_ids)
        seen.append(ids)
        return {
            901: [{"metric_key": "kd_nM", "value_num": 1.1, "unit": "nM"}],
            902: [{"metric_key": "kd_nM", "value_num": 2.2, "unit": "nM"}],
        }

    def _single_should_not_run(*_args, **_kwargs):
        raise AssertionError("single-record lookup should not run when batched lookup is available")

    monkeypatch.setattr(molecules_router, "list_measurements_for_record_ids", _batched)
    monkeypatch.setattr(molecules_router, "list_measurements_for_record", _single_should_not_run)
    rows = molecules_router._build_experiment_result_rows(SimpleNamespace(), [panel], [])
    assert seen == [[901, 902]]
    assert len(rows) == 2


def test_experiment_result_rows_sort_by_group_then_run_date_desc_then_record_id_desc(monkeypatch) -> None:
    r_expr = SimpleNamespace(
        id=101,
        title="Expr",
        run_date="2026-03-09",
        data_type="EXPRESSION",
        method="TRANSIENT_HEK",
        primary_result_text="",
    )
    r_sec_old = SimpleNamespace(
        id=102,
        title="SEC old",
        run_date="2026-03-08",
        data_type="SEC",
        method="SEC",
        primary_result_text="",
    )
    r_sec_new = SimpleNamespace(
        id=103,
        title="SEC new",
        run_date="2026-03-10",
        data_type="SEC",
        method="SEC",
        primary_result_text="",
    )
    r_bind = SimpleNamespace(
        id=104,
        title="Bind",
        run_date="2026-03-10",
        data_type="BINDING",
        method="SPR",
        primary_result_text="",
    )

    panel = {
        "batch": SimpleNamespace(id=7, batch_id="M-SPLIT-001"),
        "batch_label": "M-SPLIT-001",
        "assays": {
            "A": {
                "c1": {"runs": [{"record": r_bind}, {"record": r_sec_old}, {"record": r_sec_new}, {"record": r_expr}]}
            }
        },
    }
    monkeypatch.setattr(
        molecules_router,
        "list_measurements_for_record",
        lambda _db, record_id: [{"metric_key": "conclusion", "value_text": "pass"}] if int(record_id) == 104 else [],
    )
    rows = molecules_router._build_experiment_result_rows(SimpleNamespace(), [panel], [])
    assert [int(r.get("record_id") or 0) for r in rows] == [101, 103, 102, 104]


def test_experiment_result_rows_result_fallback_chain(monkeypatch) -> None:
    rec_a = SimpleNamespace(id=201, title="A", run_date="2026-03-10", data_type="ENDOTOXIN", method="LAL", primary_result_text="pass")
    rec_b = SimpleNamespace(id=202, title="B", run_date="2026-03-10", data_type="ENDOTOXIN", method="LAL", primary_result_text="borderline")
    rec_c = SimpleNamespace(id=203, title="C", run_date="2026-03-10", data_type="ENDOTOXIN", method="LAL", primary_result_text="Looks FAIL in review")
    panel = {
        "batch": SimpleNamespace(id=7, batch_id="M-SPLIT-001"),
        "batch_label": "M-SPLIT-001",
        "assays": {"E": {"c1": {"runs": [{"record": rec_a}, {"record": rec_b}, {"record": rec_c}]}}},
    }

    def _rows(_db, record_id):
        rid = int(record_id)
        if rid == 201:
            return [{"metric_key": "conclusion", "value_text": "pass"}]
        if rid == 202:
            return [{"metric_key": "pass_fail", "value_text": "borderline"}]
        return []

    monkeypatch.setattr(molecules_router, "list_measurements_for_record", _rows)
    rows = molecules_router._build_experiment_result_rows(SimpleNamespace(), [panel], [])
    by_id = {int(r.get("record_id") or 0): r for r in rows}
    assert by_id[201]["result"] == "pass"
    assert by_id[202]["result"] == "borderline"
    assert by_id[203]["result"] == "fail"


def test_experiment_result_rows_no_placeholders_when_no_runs(monkeypatch) -> None:
    monkeypatch.setattr(molecules_router, "list_measurements_for_record", lambda _db, record_id: [])
    rows = molecules_router._build_experiment_result_rows(SimpleNamespace(), [], [])
    assert rows == []


def test_experiment_summary_uses_unit_fallback_when_measurement_unit_missing(monkeypatch) -> None:
    rec = SimpleNamespace(
        id=301,
        title="Binding fallback units",
        run_date="2026-03-10",
        data_type="BINDING",
        method="SPR",
        primary_result_text="",
    )
    panel = {
        "batch": SimpleNamespace(id=7, batch_id="M-SPLIT-001"),
        "batch_label": "M-SPLIT-001",
        "assays": {"B": {"c1": {"runs": [{"record": rec}]}}},
    }
    monkeypatch.setattr(
        molecules_router,
        "list_measurements_for_record",
        lambda _db, record_id: (
            [
                {"metric_key": "kd_nM", "value_num": 140.0, "unit": ""},
                {"metric_key": "kon", "value_num": 82000.0, "unit": ""},
                {"metric_key": "koff", "value_num": 0.011, "unit": ""},
            ]
            if int(record_id) == 301
            else []
        ),
    )
    rows = molecules_router._build_experiment_result_rows(SimpleNamespace(), [panel], [])
    summary = str(rows[0].get("summary") or "")
    assert "KD 140 nM" in summary
    assert "Kon 82,000 M^-1 s^-1" in summary
    assert "Koff 0.011 s^-1" in summary


def test_experiment_summary_omits_unit_cleanly_when_unavailable(monkeypatch) -> None:
    rec = SimpleNamespace(
        id=302,
        title="Custom metric no unit",
        run_date="2026-03-10",
        data_type="IN_SILICO",
        method="DEVELOPABILITY_SCORE",
        primary_result_text="",
    )
    panel = {
        "batch": SimpleNamespace(id=7, batch_id="M-SPLIT-001"),
        "batch_label": "M-SPLIT-001",
        "assays": {"C": {"c1": {"runs": [{"record": rec}]}}},
    }
    monkeypatch.setattr(
        molecules_router,
        "list_measurements_for_record",
        lambda _db, record_id: [{"metric_key": "custom_signal", "value_num": 12.3, "unit": ""}] if int(record_id) == 302 else [],
    )
    rows = molecules_router._build_experiment_result_rows(SimpleNamespace(), [panel], [])
    summary = str(rows[0].get("summary") or "")
    assert "Custom Signal 12.3" in summary
    assert "None" not in summary


def test_results_template_column_order_is_experiment_centric() -> None:
    tpl = (Path(__file__).resolve().parents[1] / "psi" / "web" / "templates" / "molecules" / "results.html").read_text(encoding="utf-8")
    assert "<th>Run Date</th><th>Batch</th><th>Experiment</th><th>Summary</th><th>Result</th><th>Record</th>" in tpl
    assert '<table class="table mini results-experiment-table">' in tpl
    assert '<col class="col-run-date" />' in tpl
    assert '<col class="col-summary" />' in tpl


def test_molecule_best_batch_summary_rows_metric_order_and_best_direction(monkeypatch) -> None:
    r1 = SimpleNamespace(id=401, run_date="2026-03-01")
    r2 = SimpleNamespace(id=402, run_date="2026-03-10")
    r3 = SimpleNamespace(id=403, run_date="2026-03-10")
    panel = {
        "batch": SimpleNamespace(id=7, batch_id="B-001"),
        "batch_label": "B-001",
        "assays": {"A": {"c1": {"runs": [{"record": r1}, {"record": r2}, {"record": r3}]}}},
    }

    def _rows(_db, record_id):
        rid = int(record_id)
        if rid == 401:
            return [
                {"metric_key": "titer_mg_l", "value_num": 100, "unit": "mg/L"},
                {"metric_key": "total_yield_mg", "value_num": 10, "unit": "mg"},
                {"metric_key": "hmw_pct", "value_num": 4.0, "unit": "%"},
                {"metric_key": "kd_nM", "value_num": 9.0, "unit": "nM"},
            ]
        if rid == 402:
            return [
                {"metric_key": "titer_mg_l", "value_num": 200, "unit": "mg/L"},
                {"metric_key": "total_yield_mg", "value_num": 12, "unit": "mg"},
                {"metric_key": "hmw_pct", "value_num": 2.5, "unit": "%"},
                {"metric_key": "kd_nM", "value_num": 3.5, "unit": "nM"},
            ]
        if rid == 403:
            return [
                {"metric_key": "titer_mg_l", "value_num": 200, "unit": "mg/L"},
                {"metric_key": "total_yield_mg", "value_num": 16, "unit": "mg"},
                {"metric_key": "hmw_pct", "value_num": 2.5, "unit": "%"},
                {"metric_key": "kd_nM", "value_num": 3.5, "unit": "nM"},
            ]
        return []

    monkeypatch.setattr(molecules_router, "list_measurements_for_record", _rows)
    rows = molecules_router._best_batch_summary_rows(SimpleNamespace(), [panel], [])
    labels = [str(r.get("metric_label") or "") for r in rows]
    assert labels == ["Expression titer", "Total yield", "HMW %", "Binding KD"]
    by_label = {str(r.get("metric_label") or ""): r for r in rows}
    assert by_label["Expression titer"]["experiment"] == "Expression"
    assert by_label["Total yield"]["experiment"] == "Expression"
    assert by_label["HMW %"]["experiment"] == "SEC"
    assert by_label["Binding KD"]["experiment"] == "SPR"
    assert by_label["Expression titer"]["best_display"] == "200 mg/L"
    assert by_label["Expression titer"]["average_display"] == "166.7 mg/L"
    assert by_label["Expression titer"]["best_date"] == "2026-03-10"
    assert by_label["Total yield"]["best_display"] == "16 mg"
    assert by_label["HMW %"]["best_display"] == "2.5 %"
    assert by_label["Binding KD"]["best_display"] == "3.5 nM"


def test_molecule_best_batch_summary_rows_skips_incompatible_units_and_non_numeric(monkeypatch) -> None:
    r1 = SimpleNamespace(id=501, run_date="2026-03-01")
    r2 = SimpleNamespace(id=502, run_date="2026-03-02")
    panel = {
        "batch": SimpleNamespace(id=7, batch_id="B-001"),
        "batch_label": "B-001",
        "assays": {"A": {"c1": {"runs": [{"record": r1}, {"record": r2}]}}},
    }

    def _rows(_db, record_id):
        rid = int(record_id)
        if rid == 501:
            return [{"metric_key": "endotoxin_eu_ml", "value_num": 0.9, "unit": "EU/mL"}]
        if rid == 502:
            return [{"metric_key": "endotoxin_eu_ml", "value_text": "n/a", "unit": "EU/mg"}]
        return []

    monkeypatch.setattr(molecules_router, "list_measurements_for_record", _rows)
    rows = molecules_router._best_batch_summary_rows(SimpleNamespace(), [panel], [])
    assert len(rows) == 1
    row = rows[0]
    assert row["metric_label"] == "Endotoxin"
    assert row["best_display"] == "0.9 EU/mL"
    assert row["average_display"] == "0.9 EU/mL"


def test_molecule_detail_template_contains_best_batch_summary_columns() -> None:
    tpl = (Path(__file__).resolve().parents[1] / "psi" / "web" / "templates" / "molecules" / "detail.html").read_text(encoding="utf-8")
    assert "<h2 style=\"margin-top:0;\">Best Batch-Derived Summary</h2>" in tpl
    assert "<th>Metric</th><th>Experiment</th><th>Best</th><th>Average</th><th>Best Batch</th><th>Best Date</th>" in tpl


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
