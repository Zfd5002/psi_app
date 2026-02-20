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
import re


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
    # Smoke test needs explicit export enablement.
    os.environ.setdefault("PSI_ENABLE_EXPORT", "1")

    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy import create_engine, text

    from psi.core.db import SessionLocal, ensure_schema
    from psi.core.models import Batch, Molecule, Program
    from psi.core.registry import DATA_SCHEMAS, REGISTRY
    from psi.services.batches import create_batch
    from psi.services.data_records import create_data_record
    from psi.services.measurements import get_primary_measurement_for_record, upsert_measurements
    from psi.services.molecules import DuplicateMoleculeError, create_molecule
    from psi.services.programs import create_program
    from psi.tools.export_measurements import export_csv
    from psi.services.export_wide import ExportWideOptions, export_wide_to_csv
    from psi.core.export_profiles import validate_profiles

    # --- Release guardrail ---
    from psi.web.app import create_app
    app = create_app()
    psi_version = app.state.templates.env.globals.get("PSI_VERSION")
    assert psi_version, "PSI_VERSION missing"
    # Patch notes must include current version (append-only discipline).
    root = Path(__file__).resolve().parents[2]
    pn = root / "PATCH_NOTES.md"
    assert pn.exists(), "PATCH_NOTES.md missing"
    pn_text = pn.read_text(encoding="utf-8")
    assert psi_version in pn_text, "PATCH_NOTES missing current version entry"

    # Stronger guardrail: ensure the latest PATCH_NOTES header matches PSI_VERSION.
    # Expected header format: "## YYYY-MM-DD — vX.Y.Z..."
    headers = re.findall(r"^##\s+\d{4}-\d{2}-\d{2}\s+—\s+(v[^\s]+)\s*$", pn_text, flags=re.M)
    assert headers, "PATCH_NOTES has no version headers"
    # PATCH_NOTES is maintained newest-first (top of file). The first matching header is the latest.
    latest = headers[0]
    assert (
        latest == psi_version
    ), f"PATCH_NOTES latest entry is {latest} but PSI_VERSION is {psi_version}"

    # --- Schema ---
    ensure_schema()

    # --- Registry sanity ---
    assert isinstance(REGISTRY, dict), "REGISTRY is not a dict"
    assert "domains_ordered" in REGISTRY, "REGISTRY missing domains_ordered"
    assert isinstance(DATA_SCHEMAS, dict) and DATA_SCHEMAS, "DATA_SCHEMAS empty"

    # --- Export profiles registry sanity ---
    validate_profiles()

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
    assert meas.get("value_num") is not None, "Numeric parsing failed"

    # --- Measurement insert compatibility matrix (no migrations) ---
    def _compat_db(path: Path, ddl: str) -> Session:
        if path.exists():
            path.unlink()
        eng = create_engine(f"sqlite:///{path}")
        with eng.begin() as conn:
            conn.execute(text(ddl))
        return sessionmaker(bind=eng)()

    tmp_root = Path(tempfile.gettempdir()) / "psi_smoke"

    # Variant A: older/alternate column names + extra NOT NULL flags
    s1 = _compat_db(
        tmp_root / "meas_compat_a.sqlite",
        """
        CREATE TABLE data_measurements (
            id INTEGER PRIMARY KEY,
            record_id INTEGER NOT NULL,
            metric_key TEXT NOT NULL,
            numeric_value REAL,
            text_value TEXT,
            unit TEXT,
            comparator TEXT,
            is_primary INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            is_extra_flag INTEGER NOT NULL
        );
        """,
    )
    # numeric-only
    upsert_measurements(
        s1,
        record_id=1,
        measurements=[{"name": "monomer_percent", "value_num": 98.0, "unit": "%"}],
    )
    # text-only
    upsert_measurements(
        s1,
        record_id=1,
        measurements=[{"name": "note", "value_text": "PASS"}],
    )
    pm1 = get_primary_measurement_for_record(s1, 1, include_qc=True)
    assert pm1 is not None, "Compat A: primary measurement missing"
    # Deterministic: first inserted becomes primary (is_primary exists)
    assert pm1.get("name") == "monomer_percent", "Compat A: primary resolution not deterministic"

    # Variant B: modern-ish names + different primary/timestamp column
    s2 = _compat_db(
        tmp_root / "meas_compat_b.sqlite",
        """
        CREATE TABLE data_measurements (
            id INTEGER PRIMARY KEY,
            data_record_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            value_num REAL,
            value_text TEXT,
            is_headline INTEGER NOT NULL,
            timestamp TEXT NOT NULL
        );
        """,
    )
    # Insert without explicitly setting a primary (service handles it)
    upsert_measurements(
        s2,
        record_id=42,
        measurements=[
            {"name": "b", "value_text": "Z"},
            {"name": "a", "value_text": "A"},
        ],
    )
    pm2 = get_primary_measurement_for_record(s2, 42, include_qc=True)
    assert pm2 is not None, "Compat B: primary measurement missing"
    # Deterministic: first inserted becomes primary when primary column exists
    assert pm2.get("name") == "b", "Compat B: primary resolution not deterministic"

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

    # --- Deterministic wide exporter sanity (default + profile) ---
    out_wide = Path(tempfile.gettempdir()) / "psi_smoke" / "export_wide_smoke.csv"
    export_wide_to_csv(db, out_path=str(out_wide), options=ExportWideOptions())
    with out_wide.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert "record_id" in header, "Wide export missing core column record_id"
        assert any(str(c).startswith("sec__monomer_pct") for c in header), "Wide export missing expected SEC column"

    out_wide_prof = Path(tempfile.gettempdir()) / "psi_smoke" / "export_wide_profile_smoke.csv"
    export_wide_to_csv(db, out_path=str(out_wide_prof), options=ExportWideOptions(profile="ML_core"))
    with out_wide_prof.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        # Profile should be a subset (still includes core)
        assert "record_id" in header, "Profile wide export missing core column record_id"
        assert "binding__kd_nM" in header or any("binding__kd_nM" == str(c) for c in header), "Profile wide export missing KD column"

    print("OK: smoke tests passed")


if __name__ == "__main__":
    main()
