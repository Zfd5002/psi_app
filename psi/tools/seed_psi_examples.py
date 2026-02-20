#!/usr/bin/env python3
"""
Seed PSI_EXAMPLES dataset into an existing PSI database.

Design goals:
- Safe by default (no deletion; idempotent-ish).
- Uses PSI services to ensure chain registry + measurement extraction are exercised.
- Adds QC events on extracted measurements when specified in fixture.

Usage (from repo root, with venv active):
  python -m psi.tools.seed_psi_examples --db ./psi.sqlite
or
  PSI_DB_PATH=./psi.sqlite python -m psi.tools.seed_psi_examples

Notes:
- If the program or molecules already exist, the seeder will skip creating duplicates.
- DataRecords are de-duped by (batch_id, title) for this dataset.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import text

from psi.core.db import ensure_schema, SessionLocal
from psi.core.models import Program, Molecule, Batch, DataRecord
from psi.services.molecules import create_molecule, DuplicateMoleculeError
from psi.services.batches import create_batch
from psi.services.data_records import create_data_record
from psi.services.measurements import list_measurements_for_record
from psi.services.qc import append_qc_event


DEFAULT_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "psi_examples_fixture.json"


def _load_fixture(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _get_program(db, name: str) -> Optional[Program]:
    return db.query(Program).filter(Program.name == name).first()


def _get_molecule_by_primary_id(db, program_id: int, primary_id: str) -> Optional[Molecule]:
    return db.query(Molecule).filter(Molecule.program_id == program_id, Molecule.primary_id == primary_id).first()


def _get_batch_by_code(db, molecule_id: int, batch_code: str) -> Optional[Batch]:
    return db.query(Batch).filter(Batch.molecule_id == molecule_id, Batch.batch_id == batch_code).first()


def _record_exists(db, batch_db_id: int, title: str) -> bool:
    return (
        db.query(DataRecord)
        .filter(DataRecord.batch_id == batch_db_id, DataRecord.title == title)
        .first()
        is not None
    )


def _apply_qc_for_record(db, record_id: int, qc_spec: Dict[str, Any], actor: str) -> int:
    """qc_spec: { measurement_name: {action, ignore_policy?, note?, ignore_reason_code?, ignore_note?} }"""
    if not qc_spec:
        return 0
    meas = list_measurements_for_record(db, record_id=record_id)
    by_name = {}
    for m in meas:
        n = (m.get("name") or "").strip()
        if n:
            by_name[n] = m
    applied = 0
    for name, ev in (qc_spec or {}).items():
        if name not in by_name:
            continue
        mid = int(by_name[name].get("id"))
        action = (ev.get("action") or "note")
        append_qc_event(
            db,
            measurement_id=mid,
            record_id=record_id,
            metric_key=name,
            action=action,
            actor=actor,
            note=ev.get("note"),
            ignore_policy=ev.get("ignore_policy"),
            ignore_reason_code=ev.get("ignore_reason_code"),
            ignore_note=ev.get("ignore_note"),
        )
        applied += 1
    db.commit()
    return applied


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", default=str(DEFAULT_FIXTURE), help="Path to psi_examples_fixture.json")
    ap.add_argument("--db", default=None, help="SQLite DB path (overrides PSI_DB_PATH for this run)")
    ap.add_argument("--actor", default="psi_examples_seed", help="QC actor name")
    args = ap.parse_args()

    if args.db:
        os.environ["PSI_DB_PATH"] = args.db

    # Ensure schema exists (creates tables + any missing columns, and data_measurements baseline).
    ensure_schema()

    db = SessionLocal()
    fx = _load_fixture(Path(args.fixture))

    prog_name = fx["program"]["name"]
    prog_desc = fx["program"].get("description")

    p = _get_program(db, prog_name)
    if p is None:
        p = Program(name=prog_name, description=prog_desc)
        db.add(p)
        db.commit()
        db.refresh(p)
        print(f"Created program {prog_name} (id={p.id})")
    else:
        # keep description if empty
        if (not p.description) and prog_desc:
            p.description = prog_desc
            db.add(p)
            db.commit()
        print(f"Using existing program {prog_name} (id={p.id})")

    created_m = 0
    created_b = 0
    created_r = 0
    qc_events = 0

    for m in fx.get("molecules", []):
        primary_id = m["primary_id"]
        existing = _get_molecule_by_primary_id(db, p.id, primary_id)
        if existing is None:
            try:
                existing = create_molecule(
                    db,
                    program_id=p.id,
                    primary_id=primary_id,
                    title=m.get("title") or "",
                    description_user=m.get("description_user"),
                    molecule_format="IgG",
                    heavy_compute_enabled=0,
                    components=m.get("components") or None,
                    background_tasks=None,
                )
                created_m += 1
                print(f"Created molecule {primary_id} (id={existing.id})")
            except DuplicateMoleculeError as e:
                # If composition duplicates, fall back to locating by hash.
                print(f"Skip molecule {primary_id}: duplicate composition (existing id={e.existing_molecule_id})")
                existing = db.get(Molecule, e.existing_molecule_id)
        else:
            print(f"Using existing molecule {primary_id} (id={existing.id})")

        if existing is None:
            continue

        for b in m.get("batches", []):
            # Create batch code deterministically by using PSI's next_batch_id allocator.
            # We cannot predict the batch_id string ahead of time, so we dedupe by title+cro notes.
            # Strategy: if a batch with the same title already exists under molecule, reuse it.
            bt_title = (b.get("title") or "").strip()
            found = (
                db.query(Batch)
                .filter(Batch.molecule_id == existing.id, Batch.title == bt_title)
                .order_by(Batch.created_at.asc())
                .first()
            )
            if found is None:
                found = create_batch(
                    db,
                    molecule_id=existing.id,
                    title=bt_title,
                    expression_notes=b.get("expression_notes") or "",
                    purification_notes=b.get("purification_notes") or "",
                )
                created_b += 1
                print(f"  Created batch {found.batch_id} ({bt_title})")
            else:
                print(f"  Using existing batch {found.batch_id} ({bt_title})")

            for r in b.get("records", []):
                title = (r.get("title") or "").strip()
                if _record_exists(db, found.id, title):
                    continue
                rec = create_data_record(
                    db,
                    program_id=p.id,
                    molecule_id=existing.id,
                    batch_id=found.id,
                    domain=r.get("domain") or "",
                    data_type=r.get("data_type") or "",
                    method=r.get("method") or "",
                    title=title,
                    notes=(r.get("notes") or "").strip() or "[PSI_EXAMPLES]",
                    run_date=(r.get("run_date") or "").strip(),
                    params_json=r.get("params") or {},
                    results_json=r.get("results") or {},
                    uploads=None,
                    storage=None,
                    reason="PSI_EXAMPLES seed",
                )
                created_r += 1
                qc_spec = r.get("qc") or {}
                qc_events += _apply_qc_for_record(db, rec.id, qc_spec, actor=args.actor)

    # A tiny sanity query: how many rows in data_measurements now?
    n_meas = db.execute(text("SELECT COUNT(1) AS n FROM data_measurements")).mappings().first()["n"]

    print("")
    print("Done.")
    print(f"  molecules created: {created_m}")
    print(f"  batches created:   {created_b}")
    print(f"  records created:   {created_r}")
    print(f"  qc events applied: {qc_events}")
    print(f"  measurements rows: {n_meas}")


if __name__ == "__main__":
    main()
