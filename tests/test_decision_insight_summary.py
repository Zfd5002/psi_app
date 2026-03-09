from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DecisionSnapshot, Molecule, Program
from psi.services.decisions import get_snapshot_detail
from psi.web.ui_labels import humanize_key, humanize_path_token, humanize_state


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
    env.filters["humanize_key"] = humanize_key
    env.filters["humanize_state"] = humanize_state
    env.filters["humanize_path_token"] = humanize_path_token
    return env


def test_di_snapshot_detail_includes_insight_bundle_summary() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-di-insight", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-di-insight", title="MDI", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            snap = DecisionSnapshot(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=None,
                decision_key="advance_to_in_vivo",
                rules_version="v1",
                engine_key="di",
                schema_version="di.snapshot.v0_4",
                inputs_json=json.dumps({"schema_version": "di.snapshot.v0_4"}),
                outputs_json=json.dumps(
                    {
                        "decision_state": "not_ready",
                        "gates": [],
                        "gate_outcomes": {"G1": {"status": "fail", "missing": ["kd"], "failed_metrics": []}},
                        "blockers": [{"blocker_key": "missing_required_metric", "detail": {"gate": "G1", "missing": ["kd"]}}],
                    }
                ),
                evidence_ids_json="[]",
                created_at=now,
            )
            db.add(snap)
            db.commit()
            db.refresh(snap)

            ctx = get_snapshot_detail(db, int(snap.id))
            ib = ctx.get("di_insight_bundle") or {}
            assert ctx.get("is_di") is True
            assert str(ib.get("molecule_status") or "") == "not_ready"
            assert "Missing required evidence" in str(ib.get("decision_summary") or "")
        finally:
            db.close()
    finally:
        eng.dispose()


def test_di_snapshot_template_renders_evidence_breakdown_and_experiment_bridge() -> None:
    tpl = _env().get_template("decisions/_di_snapshot.html")
    html = tpl.render(
        request=SimpleNamespace(),
        snap=SimpleNamespace(id=9, program_id=4, molecule_id=7, decision_key="advance_to_in_vivo", created_at="2026-03-07"),
        output={"decision_state": "not_ready", "gate_outcomes": {}, "blockers": []},
        inputs={},
        di_insight_bundle={
            "decision_summary": "This molecule is blocked because SEC purity is below threshold.",
            "strongest_supporting_evidence": [{"metric_key": "kd_nM", "observed_value": 5.0}],
            "strongest_blocking_evidence": [{"metric_key": "monomer_pct", "required_threshold": "Monomer >= 85 %"}],
            "missing_evidence": [{"metric_key": "value_eu_ml"}],
            "recommended_experiments": [{"metric_key": "value_eu_ml", "suggested_assay": "Add endotoxin measurement"}],
        },
        di_snapshot_ui={},
        outcomes=[],
    )
    assert "Evidence Breakdown" in html
    assert "Decision to Experiment Bridge" in html
    assert "Strongest supporting evidence" in html
    assert "Create Suggested Experiment: value_eu_ml" in html
    assert "/data/new?program_id=4" in html
    assert "molecule_id=7" in html


def test_di_snapshot_template_bridge_requires_scope_ids() -> None:
    tpl = _env().get_template("decisions/_di_snapshot.html")
    html = tpl.render(
        request=SimpleNamespace(),
        snap=SimpleNamespace(id=9, program_id=None, molecule_id=None, decision_key="advance_to_in_vivo", created_at="2026-03-07"),
        output={"decision_state": "not_ready", "gate_outcomes": {}, "blockers": []},
        inputs={},
        di_insight_bundle={"missing_evidence": [{"metric_key": "kd_nM"}], "recommended_experiments": []},
        di_snapshot_ui={},
        outcomes=[],
    )
    assert "Bridge actions require both program_id and molecule_id" in html
