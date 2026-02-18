"""PSI smoke test

Goals:
  - Idempotent: safe to run multiple times
  - Uses repo-aligned service APIs
  - Validates measurement parsing from a human string (e.g. "98%")
  - Performs a minimal export sanity check

Run:
  python -m psi.scripts.smoke_test
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _set_ephemeral_db_path() -> None:
    """Point PSI at a writable sqlite file for the duration of the smoke test.

    We do this *before* importing psi.core.db so the engine binds to the right path.
    """

    if os.environ.get("PSI_DB_PATH"):
        # Respect explicit user override.
        return

    root = Path(tempfile.gettempdir()) / "psi_smoke"
    root.mkdir(parents=True, exist_ok=True)
    os.environ["PSI_DB_PATH"] = str(root / "psi_smoke.sqlite")


def main() -> None:
    _set_ephemeral_db_path()

    from sqlalchemy.orm import Session

    from psi.core.db import SessionLocal, ensure_schema
    from psi.core.models import Batch, Molecule, Program
    from psi.core.registry import DATA_SCHEMAS, REGISTRY
    from psi.services.batches import create_batch
    from psi.services.data_records import create_data_record
    from psi.services.measurements import get_primary_measurement_for_record
    from psi.services.molecules import DuplicateMoleculeError, create_molecule
    from psi.services.programs import create_program
    from psi.tools.export_measurements import export_csv

    # --- Schema ---
    ensure_schema()

    # --- Registry sanity ---
    assert isinstance(REGISTRY, dict), "REGISTRY is not a dict"
    assert "domains_ordered" in REGISTRY, "REGISTRY missing domains_ordered"
    assert isinstance(DATA_SCHEMAS, dict) and DATA_SCHEMAS, "DATA_SCHEMAS empty"

    db: Session = SessionLocal()

    # --- Program ---
    p = db.query(Program).order_by(Program.id.asc()).first()
    if p is None:
        p = create_program(db, name="SMOKE", description="Smoke test program")

    # --- Molecule (structured creation) ---
    m = db.query(Molecule).filter(Molecule.program_id == p.id).order_by(Molecule.id.asc()).first()
    if m is None:
        # Small, valid AA sequences (not meant to be biologically meaningful).
        hc = "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISWNSGGSTYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYC"
        lc = "DIQMTQSPSSLSASVGDRVTITCRASSSVSYIHWFQQKPGKAPKLLIYAASTLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYC"
        try:
            m = create_molecule(
                db,
                program_id=p.id,
                primary_id="SMOKE-0001",
                title="Smoke test molecule",
                components={"HC1": hc, "LC1": lc},
            )
        except DuplicateMoleculeError:
            # In case the DB already has the same composition (idempotent behavior).
            m = db.query(Molecule).filter(Molecule.program_id == p.id).order_by(Molecule.id.asc()).first()
            assert m is not None, "Duplicate molecule error but no molecule found"

    # --- Batch (SEC requires batch_id) ---
    b = db.query(Batch).filter(Batch.molecule_id == m.id).order_by(Batch.id.asc()).first()
    if b is None:
        b = create_batch(db=db, molecule_id=m.id, title="Smoke batch", expression_notes="", purification_notes="")

    # --- Create SEC data record with numeric-like string (dict input) ---
    rec = create_data_record(
        db=db,
        program_id=p.id,
        molecule_id=m.id,
        batch_id=b.id,
        domain="CMC_Analytics",
        title="Smoke test SEC",
        data_type="SEC",
        method="SEC",
        results_json={"monomer_percent": "98%", "hmw_percent": "2%"},
        params_json={"column": "SEC-S200"},
    )

    # --- Ensure measurement parsed ---
    meas = get_primary_measurement_for_record(db, rec.id)
    assert meas is not None, "Primary measurement not created"
    assert meas.value_num is not None, "Numeric parsing failed"

    # --- Minimal export sanity check ---
    import csv

    out_csv = Path(tempfile.gettempdir()) / "psi_smoke" / "export_smoke.csv"
    export_csv(
        db,
        out_csv,
        program_id=p.id,
        molecule_id=m.id,
        data_type="SEC",
        include_qc=True,
        wide=True,
    )
    with out_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert any(str(c).startswith("primary_") for c in header), "Export missing primary_* columns"

    print("OK: smoke tests passed")


if __name__ == "__main__":
    main()
