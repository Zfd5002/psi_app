from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from psi.core.models import DecisionSnapshot
from psi.core.utils import stable_json_dumps


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _latest_di_snapshot(db: Session, *, molecule_id: int, as_of: datetime) -> dict[str, Any]:
    row = (
        db.query(DecisionSnapshot)
        .filter(DecisionSnapshot.molecule_id == int(molecule_id))
        .filter(DecisionSnapshot.created_at <= as_of)
        .order_by(DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc())
        .first()
    )
    if row is None:
        return {}
    try:
        out = json.loads(row.outputs_json or "{}")
    except Exception:
        out = {}
    return out if isinstance(out, dict) else {}


def build_template_ladder_report(
    db: Session,
    *,
    molecule_id: int,
    as_of: datetime,
) -> dict[str, Any]:
    base = Path(__file__).resolve().parents[1] / "core" / "di" / "catalogs"
    tcat = _load_json(base / "template_catalog_v0_1.json")
    pcat = _load_json(base / "template_prerequisites_v0_1.json")
    templates = tcat.get("templates") if isinstance(tcat.get("templates"), list) else []
    template_keys = sorted(
        [str((t or {}).get("template_key") or "") for t in templates if isinstance(t, dict) and str((t or {}).get("template_key") or "").strip()]
    )
    prereq_map = pcat.get("template_prerequisites") if isinstance(pcat.get("template_prerequisites"), dict) else {}
    out = _latest_di_snapshot(db, molecule_id=int(molecule_id), as_of=as_of)
    gates = out.get("gate_outcomes") if isinstance(out.get("gate_outcomes"), dict) else {}
    readiness = out.get("readiness") if isinstance(out.get("readiness"), dict) else {}
    decision_state = str(out.get("decision_state") or "")
    current_stage = "in_vivo_ready" if decision_state == "ready" else "pre_in_vivo"
    missing = []
    for tk in template_keys:
        reqs = prereq_map.get(tk) if isinstance(prereq_map.get(tk), list) else []
        missing_keys = []
        for rk in sorted(str(x) for x in reqs if str(x).strip()):
            status = str((gates.get(rk) or {}).get("status") or "").strip().lower()
            if status != "pass":
                missing_keys.append(rk)
        if missing_keys:
            missing.append({"template_key": tk, "missing_prerequisites": missing_keys})
    next_actions = []
    for row in missing:
        for mk in row.get("missing_prerequisites") or []:
            next_actions.append(f"satisfy_prerequisite:{row.get('template_key')}:{mk}")
    payload = {
        "schema_id": "template_ladder_report_v3",
        "schema_version": "v0.1",
        "header": {
            "molecule_id": int(molecule_id),
            "as_of": as_of.isoformat(),
            "decision_state": decision_state,
            "readiness_state": str(readiness.get("state") or ""),
        },
        "stage_table": {
            "stages": [{"stage_key": k, "current_version": str((next((t for t in templates if str((t or {}).get("template_key") or "") == k), {}) or {}).get("current_version") or "")} for k in template_keys],
            "current_stage": current_stage,
        },
        "missing_prerequisites_table": {"rows": missing},
        "next_actions_bullets": sorted(set(next_actions)),
    }
    return json.loads(stable_json_dumps(payload))


def render_template_ladder_report_html(*, report_payload: dict[str, Any]) -> str:
    tdir = Path(__file__).resolve().parents[1] / "web" / "templates" / "reports"
    env = Environment(
        loader=FileSystemLoader(str(tdir)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tpl = env.get_template("board_template_ladder_v3.html")
    return str(tpl.render(report=report_payload))

