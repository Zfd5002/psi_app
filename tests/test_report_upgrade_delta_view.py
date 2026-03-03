from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base
from psi.services.reports_v3 import build_report_upgrade_delta_view
from psi.services.report_engine import generate_molecule_report_v0
from psi.web.ui_labels import humanize_key, humanize_path_token, humanize_state


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_upgrade_delta_view_rows_are_deterministically_ordered() -> None:
    from psi.core.models import Program, Molecule, DecisionSnapshot
    from psi.core.utils import stable_json_dumps

    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p = Program(name="P1", description="", created_at=datetime(2026, 2, 26), updated_at=datetime(2026, 2, 26))
            db.add(p)
            db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M1", title="Mol1", created_at=datetime(2026, 2, 26), updated_at=datetime(2026, 2, 26))
            db.add(m)
            db.commit(); db.refresh(m)
            db.add(
                DecisionSnapshot(
                    program_id=int(p.id), molecule_id=int(m.id), batch_id=None,
                    decision_key="advance_to_in_vivo", rules_version="vX", engine_key="di", schema_version="di.snapshot.v0_4",
                    inputs_json=stable_json_dumps({"engine_key": "di"}),
                    outputs_json=stable_json_dumps({"decision_state": "ready", "readiness": {"state": "ready"}, "gates": []}),
                    evidence_ids_json="[]", created_at=datetime(2026, 2, 26, 1, 0, 0),
                )
            )
            db.commit()
            r1 = generate_molecule_report_v0(db, molecule_id=int(m.id), as_of=datetime(2026, 2, 26, 2, 0, 0), policy_pins={"report_policy": "v0a"})
            r2 = generate_molecule_report_v0(db, molecule_id=int(m.id), as_of=datetime(2026, 2, 26, 2, 0, 0), policy_pins={"report_policy": "v0b"})
            out = build_report_upgrade_delta_view(db, base_report_run_id=int(r1.id), candidate_report_run_id=int(r2.id))
            changed_rows = out.get("change_table", {}).get("rows", [])
            keys = [str(r.get("key") or "") for r in changed_rows]
            assert keys == sorted(keys)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_upgrade_delta_board_template_renders_fragments() -> None:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
    env.filters["humanize_key"] = humanize_key
    env.filters["humanize_state"] = humanize_state
    env.filters["humanize_path_token"] = humanize_path_token
    tpl = env.get_template("reports/board_upgrade_delta_v3.html")
    html = tpl.render(
        report={
            "header": {"changed_key_count": 1, "base_report_run_id": 1, "candidate_report_run_id": 2},
            "executive_summary_bullets": {"categorical": ["Compared report runs 1 -> 2."]},
            "change_table": {"rows": [{"key": "pin:comparability_policy", "old": "v0.1", "new": "v0.2", "changed": True}]},
            "unchanged_table": {"rows": [{"key": "surface:ranking.enabled", "old": "false", "new": "false", "changed": False}]},
            "policy_pin_comparison": {"rows": [{"pin_key": "comparability_policy", "base_version": "v0.1", "candidate_version": "v0.2", "changed": True}]},
            "appendix": {"comparison_citations": {"base_report_run_id": 1, "candidate_report_run_id": 2}},
        }
    )
    assert "Upgrade Delta Header" in html
    assert "Change Table" in html
    assert "Unchanged" in html
    assert "Policy Pin Comparison" in html
