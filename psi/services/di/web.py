from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from psi.core.di.policy import load_policy
from psi.core.models import Batch, Molecule
from psi.services.di.templates.registry import DECISION_KEY_TO_TEMPLATE_KEY
from psi.services.di.util import heavy_compute_banner_text, is_heavy_compute_enabled


def _policy_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "core" / "di" / "policies"


def _parse_version(v: str) -> Tuple[int, ...]:
    s = str(v or "").strip().lower()
    if s.startswith("v"):
        s = s[1:]
    parts = [p for p in s.split(".") if p]
    out: List[int] = []
    for p in parts:
        try:
            out.append(int(p))
        except Exception:
            out.append(0)
    return tuple(out or [0])


def list_di_policies() -> List[Dict[str, Any]]:
    policies: List[Dict[str, Any]] = []
    pdir = _policy_dir()
    if not pdir.exists():
        return policies

    for path in sorted(pdir.glob("*.json")):
        pol = load_policy(path)
        decision_key = str(pol.decision_key or "").strip()
        if decision_key not in DECISION_KEY_TO_TEMPLATE_KEY:
            continue
        policies.append(
            {
                "decision_key": decision_key,
                "template_key": str(pol.template_key or ""),
                "policy_version": str(pol.version or ""),
                "policy_name": str(pol.name or ""),
                "policy_id": str(pol.policy_id or ""),
                "path": str(path),
                "version_tuple": _parse_version(str(pol.version or "")),
            }
        )

    policies.sort(key=lambda p: (p["decision_key"], tuple(-x for x in p["version_tuple"]), p["policy_version"], p["path"]))
    return policies


def latest_policy_for_decision(decision_key: str) -> Dict[str, Any] | None:
    dk = str(decision_key or "").strip()
    opts = [p for p in list_di_policies() if p["decision_key"] == dk]
    if not opts:
        return None
    return opts[0]


def build_di_run_context(
    db: Session,
    *,
    decision_key: str | None = None,
    batch_id: int | None = None,
    molecule_id: int | None = None,
    scope_type: str | None = None,
) -> Dict[str, Any]:
    decision_keys = sorted(DECISION_KEY_TO_TEMPLATE_KEY.keys())
    dk = str(decision_key or "").strip() or (decision_keys[0] if decision_keys else "")
    selected_scope_type = str(scope_type or "").strip().lower()
    if selected_scope_type not in ("batch", "molecule"):
        selected_scope_type = "batch" if batch_id else ("molecule" if molecule_id else "batch")
    policies = list_di_policies()
    selected_policy = latest_policy_for_decision(dk)
    # w52: context-aware policy v0.4 is opt-in; keep default UI selection pinned to v0.3.
    if dk == "advance_to_in_vivo":
        stable_default = next((p for p in policies if p["decision_key"] == dk and p["policy_version"] == "v0.3"), None)
        if stable_default is not None:
            selected_policy = stable_default
    selected_policy_path = selected_policy["path"] if selected_policy else ""

    q = db.query(Batch)
    if molecule_id:
        q = q.filter(Batch.molecule_id == int(molecule_id))
    batches = q.order_by(Batch.created_at.desc(), Batch.id.desc()).all()
    molecules = db.query(Molecule).order_by(Molecule.created_at.desc(), Molecule.id.desc()).all()

    heavy_compute_enabled = is_heavy_compute_enabled()
    return {
        "selected_scope_type": selected_scope_type,
        "decision_keys": decision_keys,
        "policies": policies,
        "selected_decision_key": dk,
        "selected_policy_path": selected_policy_path,
        "batches": batches,
        "molecules": molecules,
        "selected_batch_id": int(batch_id) if batch_id else None,
        "selected_molecule_id": int(molecule_id) if molecule_id else None,
        "heavy_compute_enabled": bool(heavy_compute_enabled),
        "heavy_compute_banner": heavy_compute_banner_text(enabled=heavy_compute_enabled),
    }


def resolve_policy_path_for_run(*, decision_key: str, policy_path: str) -> Path:
    dk = str(decision_key or "").strip()
    p = str(policy_path or "").strip()
    if not dk or not p:
        raise ValueError("Decision key and policy are required")

    allowed = [x["path"] for x in list_di_policies() if x["decision_key"] == dk]
    if p not in allowed:
        raise ValueError("Invalid policy selection")
    return Path(p)
