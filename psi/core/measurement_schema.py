"""Canonical helpers for the data_measurements table.

This module centralizes:
  - ensuring the baseline data_measurements table exists (fresh DB support)
  - PRAGMA-based reflection of measurement columns across PSI versions
  - a stable column-name mapping used by both services and exporters

Keeping this logic in one place reduces drift between:
  - psi/services/measurements.py
  - psi/services/export_wide.py
  - psi/core/db.py ensure_schema() additive upgrades
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Set

from sqlalchemy import text
from sqlalchemy.orm import Session


# Caches keyed by DB engine URL (stable within a process)
_COL_MAP_CACHE_BY_DB: Dict[str, Dict[str, Optional[str]]] = {}
_ALL_COLS_CACHE_BY_DB: Dict[str, Set[str]] = {}
_COL_INFO_CACHE_BY_DB: Dict[str, Dict[str, Dict[str, Any]]] = {}


def _db_cache_key(db: Session) -> str:
    """Return a stable key for caches tied to a specific DB/engine."""
    bind = db.get_bind()
    try:
        return str(getattr(bind, "url", ""))
    except Exception:
        return repr(bind)


def ensure_data_measurements_table(db: Session) -> None:
    """Create a minimal data_measurements table if missing.

    PSI's ORM metadata does not always include this table, but multiple services
    expect it. This creates a compatible baseline schema for fresh DBs.

    NOTE: This is safe for existing DBs via CREATE TABLE IF NOT EXISTS.
    """
    db.execute(
        text(
            """
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
                ignore_for_model INTEGER,
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
            );
            """
        )
    )
    db.commit()


def measurement_schema(db: Session) -> Dict[str, Dict[str, Any]]:
    """Return PRAGMA table_info rows keyed by column name."""
    key = _db_cache_key(db)
    if key in _COL_INFO_CACHE_BY_DB:
        return _COL_INFO_CACHE_BY_DB[key]

    rows = db.execute(text("PRAGMA table_info(data_measurements)")).mappings().all()
    if not rows:
        ensure_data_measurements_table(db)
        rows = db.execute(text("PRAGMA table_info(data_measurements)")).mappings().all()

    info: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        info[str(r["name"])] = dict(r)
    _COL_INFO_CACHE_BY_DB[key] = info
    return info


def measurement_all_cols(db: Session) -> Set[str]:
    """Return the set of columns present on data_measurements."""
    key = _db_cache_key(db)
    if key in _ALL_COLS_CACHE_BY_DB:
        return _ALL_COLS_CACHE_BY_DB[key]
    cols = set(measurement_schema(db).keys())
    _ALL_COLS_CACHE_BY_DB[key] = set(cols)
    return cols


def measurement_cols(db: Session) -> Dict[str, Optional[str]]:
    """Detect column names in data_measurements so code works across PSI versions."""
    key = _db_cache_key(db)
    if key in _COL_MAP_CACHE_BY_DB:
        return _COL_MAP_CACHE_BY_DB[key]

    cols = measurement_all_cols(db)

    def pick(*names: str) -> Optional[str]:
        for n in names:
            if n in cols:
                return n
        return None

    out: Dict[str, Optional[str]] = {
        "id": pick("id"),
        "record_fk": pick("data_record_id", "record_id"),
        "name": pick("metric_key", "name", "key"),
        "value_num": pick("value_num", "numeric_value", "value"),
        "value_text": pick("value_text", "text_value", "raw_value"),
        "unit": pick("unit"),
        "comparator": pick("comparator", "op"),
        "is_primary": pick("is_primary", "primary", "is_headline"),
        "is_outlier": pick("is_outlier"),
        # timestamps
        "created_at": pick("created_at", "timestamp", "ts"),
        "updated_at": pick("updated_at"),
        # older QC columns (not the newer measurement_qc table)
        "qc_flag": pick("qc_flag", "qc_status"),
        "qc_note": pick("qc_note", "qc_reason", "qc_message"),
        # optional provenance columns
        "producer": pick("producer", "tool_name", "producer_name"),
        "producer_version": pick("producer_version", "tool_version"),
        "source_path": pick("source_path", "source_id", "extraction_path"),
        "run_id": pick("run_id"),
        "produced_at": pick("produced_at"),
        "notes": pick("notes"),
        # governance
        "ignore_for_model": pick("ignore_for_model"),
        # passthrough helpers (used by some legacy exports)
        "data_type": pick("data_type"),
        "method": pick("method"),
    }

    if not out["record_fk"] or not out["name"]:
        raise RuntimeError(
            f"data_measurements schema missing expected columns. Found: {sorted(cols)}"
        )

    _COL_MAP_CACHE_BY_DB[key] = out
    return out
