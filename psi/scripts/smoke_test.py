from __future__ import annotations

import importlib
import os
import tempfile


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "psi_smoke.sqlite")
        os.environ["PSI_DB_PATH"] = db_path

        # Reload db module so engine picks up env var
        import psi.core.db as dbmod

        importlib.reload(dbmod)
        from psi.core.db import SessionLocal, ensure_schema
        from psi.core.decision_engine import load_rules, run_decision
        from psi.core.registry import REGISTRY
        from psi.core.models import Evidence, Molecule, Program
        from psi.services.batches import create_batch
        from psi.services.molecules import create_molecule
        from psi.services.programs import create_program

        # 1) ensure_schema runs safely (idempotent)
        ensure_schema()
        ensure_schema()

        # 2) registry loads
        assert isinstance(REGISTRY, dict) and "domains" in REGISTRY, "Registry missing domains"

        # 3) basic CRUD + batch auto-increment
        with SessionLocal() as s:
            p = create_program(s, name="Smoke Program")
            m = create_molecule(s, program_id=p.id, primary_id="TCB-001")
            b1 = create_batch(s, molecule_id=m.id)
            b2 = create_batch(s, molecule_id=m.id)
            assert b1.batch_id.endswith("-001"), f"Unexpected first batch id: {b1.batch_id}"
            assert b2.batch_id.endswith("-002"), f"Unexpected second batch id: {b2.batch_id}"

        # 4) decision engine determinism
        rules_path = os.path.join(os.path.dirname(__file__), "..", "..", "psi_rules", "psirules-0.1.0.yml")
        rules = load_rules(rules_path)
        decision_keys = list(rules.get("decisions", {}).keys())
        if decision_keys:
            k = decision_keys[0]
            ev = [
                Evidence(
                    id=123,
                    program_id=1,
                    molecule_id=None,
                    batch_id=None,
                    domain="biological",
                    evidence_type=rules["domains"].get("biological", {}).get("evidence_types", [{}])[0] if rules.get("domains") else "",
                    strength=3,
                    summary="test",
                )
            ]
            out1 = run_decision(rules, k, ev)
            out2 = run_decision(rules, k, ev)
            assert out1 == out2, "Decision output is not deterministic"

    print("OK: smoke tests passed")


if __name__ == "__main__":
    main()
