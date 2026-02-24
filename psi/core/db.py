from __future__ import annotations

from contextlib import contextmanager
import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import bindparam, create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = os.environ.get("PSI_DB_PATH", str(BASE_DIR / "psi.sqlite"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

def _looks_like_readonly_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "readonly" in msg
        or "read-only" in msg
        or "attempt to write a readonly database" in msg
        or "disk i/o error" in msg
    )


def _stat_sqlite_bundle(src_db: Path) -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    for p in (
        src_db,
        src_db.with_name(src_db.name + "-wal"),
        src_db.with_name(src_db.name + "-shm"),
    ):
        try:
            st = p.stat()
        except FileNotFoundError:
            continue
        out[str(p)] = (int(st.st_size), int(st.st_mtime_ns))
    return out


def _copy_sqlite_bundle(src_db: Path, dst_dir: Path) -> Path:
    dst_db = dst_dir / src_db.name
    shutil.copy2(src_db, dst_db)
    wal = src_db.with_name(src_db.name + "-wal")
    shm = src_db.with_name(src_db.name + "-shm")
    if wal.exists():
        shutil.copy2(wal, dst_dir / wal.name)
    if shm.exists():
        shutil.copy2(shm, dst_dir / shm.name)
    return dst_db


def _install_sqlite_pragmas(eng: Engine, *, read_only: bool) -> None:
    """Register a SQLite PRAGMA setup hook on *eng*."""
    if eng.url.get_backend_name() != "sqlite":
        return

    @event.listens_for(eng, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            if read_only:
                try:
                    cursor.execute("PRAGMA query_only=1")
                except Exception:
                    pass
                try:
                    cursor.execute("PRAGMA busy_timeout=5000")
                except Exception:
                    pass
                return
            try:
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.fetchone()  # Consume the result row; required to clear cursor state.
            except Exception:
                pass  # WAL failed (filesystem type, directory permissions, etc.); non-fatal.
            try:
                cursor.execute("PRAGMA synchronous=NORMAL")
            except Exception:
                pass
            try:
                cursor.execute("PRAGMA busy_timeout=5000")
            except Exception:
                pass
        finally:
            cursor.close()


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
_install_sqlite_pragmas(engine, read_only=False)

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
            # v1.2.9q: snapshot supersession governance.
            "is_superseded": "INTEGER",
            "superseded_by_snapshot_id": "INTEGER",
            "superseded_at": "TEXT",
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
            existing = {r[1] for r in conn.execute(text("PRAGMA table_info(" + table + ")")).fetchall()}
            for col, coltype in cols.items():
                if col not in existing:
                    conn.execute(text("ALTER TABLE " + table + " ADD COLUMN " + col + " " + coltype))


    # v1.2.9q: backfill snapshot supersession metadata (deterministic).
    # Goal: ensure at most one ACTIVE snapshot per scope (decision_key, program_id, molecule_id, batch_id).
    # ACTIVE is defined as is_superseded == 0 (NULL treated as 0 for legacy rows).
    with eng.begin() as conn:
        try:
            cols = {r[1] for r in conn.execute(text("PRAGMA table_info(decision_snapshots)")).fetchall()}
        except Exception:
            cols = set()

        if "is_superseded" in cols:
            # v1.2.9s: Safe backfill — never do a blanket NULL->0 conversion while the
            # unique index already exists.  The old approach (SET all NULL to 0, then dedup)
            # fires the unique constraint on every startup after the first because the index
            # persists but the blanket update runs before dedup.
            #
            # Correct order:
            #   1. Treat NULL as "candidate active".  Combine NULLs + existing 0-rows.
            #   2. For each scope, keep the single newest row as the winner.
            #   3. Mark all losers is_superseded=1 FIRST (this can never violate uniqueness).
            #   4. Then set the winner to 0 if it was NULL (now guaranteed: at most one per scope).
            #
            # This is idempotent: if all rows are already 0 or 1 and at most one active
            # per scope, all queries return empty result sets and no UPDATEs fire.

            # Fast after first run: null_count becomes 0 and subsequent startups only do cheap counts.
            # Early-exit: nothing to do if there are no NULL rows.
            null_count = conn.execute(
                text("SELECT COUNT(*) FROM decision_snapshots WHERE is_superseded IS NULL")
            ).scalar()

            if null_count and null_count > 0:
                # Step 1: Find every scope that has any NULL or 0 (candidate-active) rows.
                groups = conn.execute(
                    text(
                        '''
                        SELECT
                          decision_key,
                          program_id,
                          COALESCE(molecule_id, 0) AS mol_id0,
                          COALESCE(batch_id, 0) AS batch_id0
                        FROM decision_snapshots
                        WHERE is_superseded IS NULL OR is_superseded = 0
                        GROUP BY decision_key, program_id,
                                 COALESCE(molecule_id, 0), COALESCE(batch_id, 0)
                        '''
                    )
                ).fetchall()

                for g in groups:
                    dk, pid, mol0, bat0 = g
                    # Fetch all candidate-active rows for this scope, newest first.
                    rows = conn.execute(
                        text(
                            '''
                            SELECT id
                            FROM decision_snapshots
                            WHERE decision_key = :dk
                              AND program_id = :pid
                              AND COALESCE(molecule_id, 0) = :mol0
                              AND COALESCE(batch_id, 0) = :bat0
                              AND (is_superseded IS NULL OR is_superseded = 0)
                            ORDER BY created_at DESC, id DESC
                            '''
                        ),
                        {"dk": dk, "pid": pid, "mol0": mol0, "bat0": bat0},
                    ).fetchall()

                    if not rows:
                        continue

                    keep_id = int(rows[0][0])
                    loser_ids = [int(r[0]) for r in rows[1:]]

                    # Step 2: Mark all losers superseded BEFORE touching the winner.
                    # This can never violate the unique index because we are only
                    # setting rows to 1 (removing them from the active set).
                    if loser_ids:
                        q = text(
                            '''
                            UPDATE decision_snapshots
                            SET
                              is_superseded = 1,
                              superseded_at = CURRENT_TIMESTAMP,
                              superseded_by_snapshot_id = :keep_id
                            WHERE id IN :ids
                            '''
                        ).bindparams(bindparam("ids", expanding=True))
                        conn.execute(q, {"keep_id": keep_id, "ids": list(loser_ids)})

                # Step 3: Set remaining NULLs (the winners) to 0.
                # At this point each scope has at most one NULL row, so this
                # conversion is safe even with the unique index in place.
                conn.execute(
                    text("UPDATE decision_snapshots SET is_superseded=0 WHERE is_superseded IS NULL")
                )

    # v1.2.0: required indexes (additive; SQLite-friendly)
    with eng.connect() as conn:
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_sequence_entities_chain_id ON sequence_entities(chain_id)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_molecules_composition_sha256 ON molecules(composition_sha256)"))

        # v1.2.9q: snapshot supersession indexes + single-ACTIVE constraint (additive).
        # Note: uses COALESCE to treat NULL scope IDs as 0 so uniqueness is enforced under SQLite UNIQUE semantics.
        try:
            cols = {r[1] for r in conn.execute(text("PRAGMA table_info(decision_snapshots)")).fetchall()}
        except Exception:
            cols = set()

        if "is_superseded" in cols:
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_decision_snapshots_one_active_per_scope "
                "ON decision_snapshots(decision_key, program_id, COALESCE(molecule_id,0), COALESCE(batch_id,0)) "
                "WHERE is_superseded = 0"
            ))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_decision_snapshots_superseded_by ON decision_snapshots(superseded_by_snapshot_id)"))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_decision_snapshots_scope_superseded_by "
                "ON decision_snapshots(decision_key, program_id, COALESCE(molecule_id,0), COALESCE(batch_id,0), superseded_by_snapshot_id)"
            ))

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

    tmp_dir = None
    if db_path:
        p = Path(db_path).expanduser().resolve()
        eng = create_engine(
            f"sqlite:///{p}",
            connect_args={"check_same_thread": False},
            future=True,
        )
        _install_sqlite_pragmas(eng, read_only=(ensure is False))
        if ensure:
            ensure_schema(engine_override=eng)
        SessionTmp = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=eng,
            future=True,
            expire_on_commit=False,
        )
        db = SessionTmp()
        if not ensure:
            try:
                db.execute(text("SELECT id FROM decision_snapshots LIMIT 1")).fetchall()
            except OperationalError as e:
                if not _looks_like_readonly_error(e):
                    raise
                db.close()
                tmp_dir = tempfile.TemporaryDirectory(prefix="psi_ro_db_")
                tmp_path = None
                for _ in range(3):
                    before = _stat_sqlite_bundle(p)
                    tmp_path = _copy_sqlite_bundle(p, Path(tmp_dir.name))
                    after = _stat_sqlite_bundle(p)
                    if before == after:
                        break
                eng = create_engine(
                    f"sqlite:///{tmp_path}",
                    connect_args={"check_same_thread": False},
                    future=True,
                )
                _install_sqlite_pragmas(eng, read_only=True)
                SessionTmp = sessionmaker(
                    autocommit=False,
                    autoflush=False,
                    bind=eng,
                    future=True,
                    expire_on_commit=False,
                )
                db = SessionTmp()
                db.execute(text("SELECT id FROM decision_snapshots LIMIT 1")).fetchall()
    else:
        if ensure:
            ensure_schema()
        db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
        if tmp_dir is not None:
            tmp_dir.cleanup()
