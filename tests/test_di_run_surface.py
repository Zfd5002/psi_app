from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from psi.core.models import Batch, Molecule, Program
from psi.services import development_progression as progression_svc
from psi.services.di import web as di_web
from psi.web.ui_labels import humanize_key, humanize_path_token, humanize_state


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
    env.filters["humanize_key"] = humanize_key
    env.filters["humanize_state"] = humanize_state
    env.filters["humanize_path_token"] = humanize_path_token
    return env


def test_di_run_context_defaults_to_canonical_progression(mkdb) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 9)
            p = Program(name="P-di", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-di", title="m", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            b = Batch(molecule_id=int(m.id), batch_id="B-di", title="b", created_at=now, updated_at=now)
            db.add(b)
            db.commit()

            ctx = di_web.build_di_run_context(db)
            assert ctx["selected_decision_key"] == progression_svc.canonical_decision_key()
            assert ctx["selected_decision_label"] == "Development Progression"
            assert ctx["canonical_chain_label"] == "Development Progression v1"
            assert str(ctx.get("selected_policy_path") or "").strip()
        finally:
            db.close()
    finally:
        eng.dispose()


def test_di_run_template_emphasizes_default_chain_and_advances_options() -> None:
    tpl = _env().get_template("di/run.html")
    html = tpl.render(
        error="",
        selected_scope_type="batch",
        selected_batch_id=1,
        selected_molecule_id=None,
        batches=[],
        molecules=[],
        decision_keys=["advance_to_in_vivo", "ready_for_scaleup_screen"],
        decision_key_labels={
            "advance_to_in_vivo": "Development Progression",
            "ready_for_scaleup_screen": "Scale-Up Readiness Screen",
        },
        selected_decision_key="advance_to_in_vivo",
        selected_decision_label="Development Progression",
        selected_policy_path="/tmp/pol.json",
        governance_policy_options=[],
        canonical_chain_label="Development Progression v1",
        heavy_compute_enabled=False,
        heavy_compute_banner="Heavy Compute: OFF",
    )
    assert "Run Development Assessment" in html
    assert "Default chain:" in html
    assert "Development Progression v1" in html
    assert "Advanced governance options" in html
