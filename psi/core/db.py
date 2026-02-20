from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = os.environ.get("PSI_DB_PATH", str(BASE_DIR / "psi.sqlite"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def ensure_schema(*, engine_override: Optional[Engine] = None) -> None:
    """Lightweight migration: create missing tables and add missing columns.

    This avoids Alembic while remaining backwards-compatible.
    """
    from .models import Base  # local import to avoid circular

    eng = engine_override or engine

    # Create missing tables
    Base.metadata.create_all(bind=eng)

    # Ensure data_measurements exists for fresh DBs (measurement services depend on it).
    # Historically this table has been managed outside ORM metadata, so we create it explicitly.
    with eng.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS data_measurements (
                id INTEGER PRIMARY KEY,
                data_record_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                value_num REAL,
                value_text TEXT,
                unit TEXT,
                comparator TEXT,
                is_primary INTEGER,
                is_outlier INTEGER,
                created_at TEXT,
                updated_at TEXT,
                qc_flag TEXT,
                qc_note TEXT,
                data_type TEXT,
                method TEXT,
                producer TEXT,
                producer_version TEXT,
                source_path TEXT,
                run_id TEXT,
                produced_at TEXT,
                notes TEXT
                ,ignore_for_model INTEGER NOT NULL DEFAULT 0
            );
        """))


    # Add missing columns if model evolved (best-effort).
    # For SQLite, we can check PRAGMA table_info and ALTER TABLE ADD COLUMN.
    model_columns = {
        "programs": {
            "id": "INTEGER",
            "name": "TEXT",
            "description": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        },
        "molecules": {
            "id": "INTEGER",
            "program_id": "INTEGER",
            "primary_id": "TEXT",
            "composition_sha256": "TEXT",
            "title": "TEXT",
            "description": "TEXT",
            "molecule_format": "TEXT",
            "description_auto": "TEXT",
            "description_user": "TEXT",
            "heavy_compute_enabled": "INTEGER",
            "sequences": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        },
        "molecule_components": {
            "id": "INTEGER",
            "molecule_id": "INTEGER",
            "role": "TEXT",
            "fasta": "TEXT",
            "sha256": "TEXT",
            "sequence_entity_id": "INTEGER",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        },
        "sequence_entities": {
            "id": "INTEGER",
            "sha256": "TEXT",
            "chain_id": "TEXT",
            "sequence_norm": "TEXT",
            "type_hint": "TEXT",
            "notes": "TEXT",
            "length": "INTEGER",
            "alphabet": "TEXT",
            "created_at": "TEXT",
        },
        "domain_instances": {
            "id": "INTEGER",
            "molecule_id": "INTEGER",
            "component_id": "INTEGER",
            "domain_type": "TEXT",
            "start_idx": "INTEGER",
            "end_idx": "INTEGER",
            "domain_sequence_id": "INTEGER",
            "source": "TEXT",
            "method": "TEXT",
            "tool_name": "TEXT",
            "tool_version": "TEXT",
            "settings_hash": "TEXT",
            "status": "TEXT",
            "warnings_json": "TEXT",
            "error": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        },
        "domain_artifacts": {
            "id": "INTEGER",
            "sequence_id": "INTEGER",
            "artifact_type": "TEXT",
            "domain_type": "TEXT",
            "tool_name": "TEXT",
            "tool_version": "TEXT",
            "settings_hash": "TEXT",
            "status": "TEXT",
            "result_json": "TEXT",
            "error": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        },
        "property_run_events": {
            "id": "INTEGER",
            "run_id": "INTEGER",
            "molecule_id": "INTEGER",
            "timestamp": "TEXT",
            "step": "TEXT",
            "level": "TEXT",
            "message": "TEXT",
            "payload_json": "TEXT",
        },
        "property_runs": {
            "id": "INTEGER",
            "molecule_id": "INTEGER",
            "input_hash": "TEXT",
            "trigger_reason": "TEXT",
            "compute_tier": "TEXT",
            "status": "TEXT",
            "error": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        },
        "property_values": {
            "id": "INTEGER",
            "run_id": "INTEGER",
            "molecule_id": "INTEGER",
            "property_key": "TEXT",
            "label": "TEXT",
            "value_json": "TEXT",
            "tier": "TEXT",
            "created_at": "TEXT",
        },
        "batches": {
            "id": "INTEGER",
            "molecule_id": "INTEGER",
            "batch_id": "TEXT",
            "title": "TEXT",
            "expression_notes": "TEXT",
            "purification_notes": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        },
        "data_records": {
            "id": "INTEGER",
            "program_id": "INTEGER",
            "molecule_id": "INTEGER",
            "batch_id": "INTEGER",
            "domain": "TEXT",
            "data_type": "TEXT",
            "method": "TEXT",
            "title": "TEXT",
            "notes": "TEXT",
            "params_json": "TEXT",
            "results_json": "TEXT",
            "primary_result_text": "TEXT",
            "raw_inputs_json": "TEXT",
            "derived_outputs_json": "TEXT",
            "is_included": "INTEGER",
            "excluded_reason": "TEXT",
            "run_date": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        },

        # v1.2.3g: per-measurement provenance (optional legacy table; additive columns only)
        # NOTE: data_measurements is managed by PRAGMA-driven services in PSI and may pre-exist
        # in older DBs. We only ALTER if the table exists.
        "data_measurements": {
            "producer": "TEXT",
            "producer_version": "TEXT",
            "source_path": "TEXT",
            "run_id": "TEXT",
            "produced_at": "TEXT",
            "notes": "TEXT",
            "ignore_for_model": "INTEGER NOT NULL DEFAULT 0",
        },
        "evidence": {
            "id": "INTEGER",
            "program_id": "INTEGER",
            "molecule_id": "INTEGER",
            "batch_id": "INTEGER",
            "domain": "TEXT",
            "evidence_type": "TEXT",
            "strength": "INTEGER",
            "summary": "TEXT",
            "details": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        },
        "evidence_citations": {
            "id": "INTEGER",
            "evidence_id": "INTEGER",
            "data_record_id": "INTEGER",
            "created_at": "TEXT",
        },
        "files": {
            "id": "INTEGER",
            "stored_name": "TEXT",
            "original_name": "TEXT",
            "size_bytes": "INTEGER",
            "mime": "TEXT",
            "sha256": "TEXT",
            # v1.2.6: provenance foundation (all optional)
            "source_kind": "TEXT",
            "source_path": "TEXT",
            "collected_at": "TEXT",
            "imported_at": "TEXT",
            "instrument": "TEXT",
            "operator": "TEXT",
            "run_id": "TEXT",
            "tags_json": "TEXT",
            "notes": "TEXT",
            "created_at": "TEXT",
        },
        "file_links": {
            "id": "INTEGER",
            "file_id": "INTEGER",
            "entity_type": "TEXT",
            "entity_id": "INTEGER",
            # v1.2.6: typed linkage
            "role": "TEXT",
            "label": "TEXT",
            "created_at": "TEXT",
        },
        "audit_events": {
            "id": "INTEGER",
            "entity_type": "TEXT",
            "entity_id": "INTEGER",
            "action": "TEXT",
            "timestamp": "TEXT",
            "actor": "TEXT",
            "before_json": "TEXT",
            "after_json": "TEXT",
            "diff_json": "TEXT",
            "reason": "TEXT",
        },
        "decision_snapshots": {
            "id": "INTEGER",
            "program_id": "INTEGER",
            "molecule_id": "INTEGER",
            "batch_id": "INTEGER",
            "decision_key": "TEXT",
            "rules_version": "TEXT",
            # v1.2.9b: schema discrimination for DI snapshots.
            "engine_key": "TEXT",
            "schema_version": "TEXT",
            "inputs_json": "TEXT",
            "outputs_json": "TEXT",
            "evidence_ids_json": "TEXT",
            "as_of_ts": "TEXT",
            "notes": "TEXT",
            "created_at": "TEXT",
        },
    }

    # Additive column evolution: only ALTER tables that actually exist.
    # This keeps ensure_schema tolerant of optional legacy tables that may exist
    # in some DBs but are not part of SQLAlchemy Base metadata.
    def _table_exists(conn, table: str) -> bool:
        r = conn.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:t LIMIT 1"),
            {"t": table},
        ).first()
        return r is not None

    with eng.begin() as conn:
        for table, cols in model_columns.items():
            if not _table_exists(conn, table):
                continue
            existing = {r[1] for r in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()}
            for col, coltype in cols.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}"))

    # v1.2.0: required indexes (additive; SQLite-friendly)
    with eng.connect() as conn:
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_sequence_entities_chain_id ON sequence_entities(chain_id)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_molecules_composition_sha256 ON molecules(composition_sha256)"))

        # v1.2.6: file registry indexes (additive)
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_files_sha256 ON files(sha256)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_file_links_entity ON file_links(entity_type, entity_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_file_links_role ON file_links(role)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_file_deriv_parent ON file_derivations(parent_file_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_file_deriv_child ON file_derivations(child_file_id)"))
        conn.commit()


@contextmanager
def get_db(db_path: Optional[str] = None, *, ensure: bool = True) -> Iterator[Session]:
    """Context-managed DB session for CLIs.

    Web routes use a FastAPI dependency in :mod:`psi.web.deps`.
    This helper is for scripts that must respect an explicit `--db` path.

    When `db_path` is provided we create an isolated engine/sessionmaker for that
    SQLite file without mutating the module globals (engine/SessionLocal).
    """

    if db_path:
        p = Path(db_path).expanduser().resolve()
        eng = create_engine(
            f"sqlite:///{p}",
            connect_args={"check_same_thread": False},
            future=True,
        )
        if ensure:
            ensure_schema(engine_override=eng)
        SessionTmp = sessionmaker(autocommit=False, autoflush=False, bind=eng, future=True)
        db = SessionTmp()
    else:
        if ensure:
            ensure_schema()
        db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
