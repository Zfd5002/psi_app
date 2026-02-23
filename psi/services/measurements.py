from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from psi.core.measurement_schema import (
    ensure_data_measurements_table as _core_ensure_data_measurements_table,
    measurement_all_cols as _core_measurement_all_cols,
    measurement_cols as _core_measurement_cols,
    measurement_schema as _core_measurement_schema,
)


_NUM_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


def _to_obj(x: Any) -> Any:
    if x is None:
        return None
    if isinstance(x, (dict, list, int, float, bool)):
        return x
    if isinstance(x, str):
        s = x.strip()
        if not s:
            return None
        try:
            return json.loads(s)
        except Exception:
            return s
    return x


def _parse_numericish(v: Any) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """
    Returns (value_num, unit, comparator).
    comparator: '>' or '<' when present. unit: '%' if percent detected.
    """
    if v is None:
        return (None, None, None)

    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return (float(v), None, None)

    if not isinstance(v, str):
        return (None, None, None)

    s = v.strip()
    if not s:
        return (None, None, None)

    comparator = None
    if s[0] in (">", "<"):
        comparator = s[0]
        s = s[1:].strip()

    if s.startswith("~"):
        s = s[1:].strip()

    unit = None
    if s.endswith("%"):
        unit = "%"
        s = s[:-1].strip()

    s = s.replace(",", "")

    if _NUM_RE.match(s):
        try:
            return (float(s), unit, comparator)
        except Exception:
            return (None, unit, comparator)

    return (None, unit, comparator)


def extract_measurements(
    *,
    data_type: Optional[str],
    method: Optional[str],
    results_json: Any,
    params_json: Any = None,
) -> List[Dict[str, Any]]:
    """
    Conservative extraction: if results is a dict, attempt to parse scalar-ish values.
    """
    results = _to_obj(results_json)
    if not isinstance(results, dict):
        return []

    out: List[Dict[str, Any]] = []
    for k, v in results.items():
        name = str(k).strip()
        if not name:
            continue

        val_num, unit, comparator = _parse_numericish(v)

        val_text = None
        if isinstance(v, str) and v.strip():
            val_text = v.strip()
        elif val_num is None:
            continue

        out.append(
            {
                "name": name,
                "value_num": val_num,
                "value_text": val_text,
                "unit": unit,
                "comparator": comparator,
                "data_type": data_type,
                "method": method,
            }
        )
    return out


# ---- DB reflection helpers (no ORM model required) ----

# NOTE: These caches must be keyed per-DB/engine. Smoke tests intentionally create
# multiple temp DBs with different schemas in one process.
_COL_CACHE_BY_DB: Dict[str, Dict[str, Optional[str]]] = {}
_ALL_COLS_CACHE_BY_DB: Dict[str, set[str]] = {}
_COL_INFO_CACHE_BY_DB: Dict[str, Dict[str, Dict[str, Any]]] = {}


def _db_cache_key(db: Session) -> str:
    """Return a stable key for caches tied to a specific DB/engine."""
    bind = db.get_bind()
    try:
        return str(getattr(bind, "url", ""))
    except Exception:
        return repr(bind)



def _ensure_data_measurements_table(db: Session) -> None:
    """Back-compat wrapper; source of truth is psi.core.measurement_schema."""
    _core_ensure_data_measurements_table(db)


def _measurement_schema(db: Session) -> Dict[str, Dict[str, Any]]:
    """Back-compat wrapper; source of truth is psi.core.measurement_schema."""
    return _core_measurement_schema(db)


def _measurement_cols(db: Session) -> Dict[str, Optional[str]]:
    """Back-compat wrapper; source of truth is psi.core.measurement_schema."""
    out = _core_measurement_cols(db)
    # Maintain module-local caches for older call sites that rely on them.
    # (Core caches are keyed by DB URL, so this remains safe.)
    key = _db_cache_key(db)
    _COL_CACHE_BY_DB[key] = out
    _ALL_COLS_CACHE_BY_DB[key] = set(_core_measurement_all_cols(db))
    return out


def _all_measurement_cols(db: Session) -> set[str]:
    """Return the full set of column names for data_measurements."""
    key = _db_cache_key(db)
    if key not in _ALL_COLS_CACHE_BY_DB:
        _ALL_COLS_CACHE_BY_DB[key] = set(_core_measurement_all_cols(db))
    return _ALL_COLS_CACHE_BY_DB.get(key, set())


def _reset_measurement_reflection_cache() -> None:
    """Testing hook: clear reflection caches (safe no-op in production)."""
    _COL_CACHE_BY_DB.clear()
    _ALL_COLS_CACHE_BY_DB.clear()
    _COL_INFO_CACHE_BY_DB.clear()


def get_primary_measurement_for_record(
    db: Session,
    record_id: int,
    include_qc: bool = False,
) -> Optional[Dict[str, Any]]:
    """Return a single "headline" measurement row for a data record.

    - Always queries the DB (no relationship assumptions).
    - If an is_primary-like column exists, prefer rows where it is 1.
    - Otherwise choose deterministically via stable ordering.
    - Excludes QC-flagged rows unless include_qc=True (when qc columns exist).

    Returns a dict with stable keys (name/value_num/value_text/unit/comparator/qc_flag) when possible.
    """

    cols = _measurement_cols(db)
    all_cols = _all_measurement_cols(db)

    # Optional ordering columns
    created_col = None
    for cand in ("created_at", "updated_at", "timestamp", "ts"):
        if cand in all_cols:
            created_col = cand
            break

    where = [f"{cols['record_fk']}=:rid"]
    params: Dict[str, Any] = {"rid": record_id}

    qc_col = cols.get("qc_flag")
    if qc_col and not include_qc:
        # Treat NULL/0/'' as "not flagged"; anything else is flagged.
        where.append(f"({qc_col} IS NULL OR {qc_col}=0 OR {qc_col}='0' OR {qc_col}='')")

    order_parts: List[str] = []
    if cols.get("is_primary"):
        order_parts.append(f"{cols['is_primary']} DESC")
    if created_col:
        order_parts.append(f"{created_col} DESC")
    if cols.get("id"):
        order_parts.append(f"{cols['id']} DESC")
    # final deterministic tie-breaker
    order_parts.append(f"{cols['name']} ASC")

    q = text(
        f"SELECT * FROM data_measurements WHERE {' AND '.join(where)} ORDER BY {', '.join(order_parts)} LIMIT 1"
    )
    row = db.execute(q, params).mappings().first()
    if not row:
        return None

    def get(colkey: str) -> Any:
        col = cols.get(colkey)
        return row.get(col) if col else None

    return {
        "id": row.get("id") or row.get(cols.get("id")) if cols.get("id") else None,
        "record_id": record_id,
        "name": get("name"),
        "value_num": get("value_num"),
        "value_text": get("value_text"),
        "unit": get("unit"),
        "comparator": get("comparator"),
        "qc_flag": get("qc_flag"),
        "qc_note": get("qc_note"),
        "data_type": get("data_type"),
        "method": get("method"),

        # Optional provenance
        "producer": get("producer"),
        "producer_version": get("producer_version"),
        "source_path": get("source_path"),
        "run_id": get("run_id"),
        "produced_at": get("produced_at"),
        "notes": get("notes"),
    }
def list_measurements_for_record(db: Session, *, record_id: int) -> List[Dict[str, Any]]:
    """List raw extracted measurement rows for a DataRecord.

    This is intended for UI + QC review. It reflects the current measurement table schema.
    Ordering is deterministic.
    """
    _ensure_data_measurements_table(db)

    mcols = _measurement_cols(db)
    record_fk = mcols.get("record_fk") or "data_record_id"
    name_col = mcols.get("name") or "name"
    id_col = mcols.get("id") or "id"
    produced_at_col = mcols.get("produced_at")
    created_at_col = mcols.get("created_at") or mcols.get("updated_at")

    order_bits = [name_col]
    if produced_at_col:
        order_bits.append(produced_at_col)
    if created_at_col and created_at_col not in order_bits:
        order_bits.append(created_at_col)
    if id_col and id_col not in order_bits:
        order_bits.append(id_col)

    order_sql = ", ".join([f"{c} ASC" for c in order_bits if c])

    q = text(f"SELECT * FROM data_measurements WHERE {record_fk} = :rid ORDER BY {order_sql}")
    rows = db.execute(q, {"rid": int(record_id)}).mappings().all()
    return [dict(r) for r in rows]



def _has_primary(db: Session, record_id: int, cols: Dict[str, Optional[str]]) -> bool:
    if not cols.get("is_primary"):
        return False
    q = text(
        f"SELECT 1 FROM data_measurements WHERE {cols['record_fk']}=:rid AND {cols['is_primary']}=1 LIMIT 1"
    )
    return db.execute(q, {"rid": record_id}).first() is not None


def upsert_measurements(db: Session, *, record_id: int, measurements: List[Dict[str, Any]]) -> int:
    """
    SAFE upsert:
    - inserts missing rows
    - fills blanks only (won't overwrite existing numeric/text/unit/comparator)
    - sets first inserted row as primary if the column exists and no primary exists yet
    """
    if not measurements:
        return 0

    cols = _measurement_cols(db)
    schema = _measurement_schema(db)
    all_cols = set(schema.keys())
    wrote = 0
    primary_exists = _has_primary(db, record_id, cols)

    for m in measurements:
        name = (m.get("name") or "").strip()
        if not name:
            continue

        sel = text(
            f"SELECT * FROM data_measurements WHERE {cols['record_fk']}=:rid AND {cols['name']}=:name LIMIT 1"
        )
        row = db.execute(sel, {"rid": record_id, "name": name}).mappings().first()

        if row is None:
            insert_phys_cols: List[str] = []
            insert_vals: Dict[str, Any] = {}

            def add_phys(colname: str, bind: str, value: Any) -> None:
                if colname not in all_cols:
                    return
                if value is None:
                    return
                insert_phys_cols.append(colname)
                insert_vals[bind] = value

            # Required keys
            add_phys(cols["record_fk"], "rid", record_id)
            add_phys(cols["name"], "name", name)

            # Optional value payload
            add_phys(cols.get("value_num") or "", "value_num", m.get("value_num"))
            add_phys(cols.get("value_text") or "", "value_text", m.get("value_text"))
            add_phys(cols.get("unit") or "", "unit", m.get("unit"))
            add_phys(cols.get("comparator") or "", "comparator", m.get("comparator"))
            add_phys(cols.get("data_type") or "", "data_type", m.get("data_type"))
            add_phys(cols.get("method") or "", "method", m.get("method"))

            # Optional provenance payload (v1.2.3g; additive)
            add_phys(cols.get("producer") or "", "producer", m.get("producer"))
            add_phys(cols.get("producer_version") or "", "producer_version", m.get("producer_version"))
            add_phys(cols.get("source_path") or "", "source_path", m.get("source_path"))
            add_phys(cols.get("run_id") or "", "run_id", m.get("run_id"))
            add_phys(cols.get("produced_at") or "", "produced_at", m.get("produced_at"))
            add_phys(cols.get("notes") or "", "notes", m.get("notes"))

            # Back-compat: if is_primary exists and may be NOT NULL, always include it on INSERT.
            if cols.get("is_primary"):
                add_phys(cols["is_primary"], "is_primary", 1 if (not primary_exists) else 0)
                if not primary_exists:
                    primary_exists = True

            # Conservative required-default fill: satisfy NOT NULL columns with no defaults
            # using safe, pattern-based fallbacks only.
            from psi.core.utils import now_utc

            utcnow = now_utc()

            def _default_for_required(colname: str) -> Any:
                low = colname.lower()
                if low.startswith("is_") or low in ("primary", "is_primary", "is_outlier", "is_headline"):
                    return 0
                if low.endswith("_at") or low in ("created_at", "updated_at", "timestamp", "ts"):
                    return utcnow
                if low in ("qc_flag", "qc_status"):
                    return 0
                if low in ("qc_note", "qc_reason", "qc_message"):
                    return ""
                return None

            missing_required: List[str] = []
            for colname, info in schema.items():
                if colname in insert_phys_cols:
                    continue
                notnull = int(info.get("notnull") or 0)
                dflt = info.get("dflt_value")
                pk = int(info.get("pk") or 0)
                if pk:
                    continue
                if notnull and (dflt is None):
                    d = _default_for_required(colname)
                    if d is None:
                        missing_required.append(colname)
                        continue
                    # Use the physical column name as the bind key for required defaults
                    insert_phys_cols.append(colname)
                    insert_vals[colname] = d

            if missing_required:
                raise RuntimeError(
                    "data_measurements has required NOT NULL columns without defaults that PSI cannot safely auto-fill: "
                    + ", ".join(sorted(missing_required))
                    + f". Found columns: {sorted(all_cols)}"
                )

            # Self-check: columns and binds must match 1:1
            if len(insert_phys_cols) != len(insert_vals):
                raise RuntimeError(
                    f"measurement insert mismatch: {len(insert_phys_cols)} cols but {len(insert_vals)} binds. "
                    f"cols={insert_phys_cols} binds={sorted(insert_vals.keys())}"
                )

            col_sql = ", ".join(insert_phys_cols)
            val_sql = ", ".join([f":{b}" for b in insert_vals.keys()])
            ins = text(f"INSERT INTO data_measurements ({col_sql}) VALUES ({val_sql})")
            db.execute(ins, insert_vals)
            wrote += 1
            continue

        # SAFE fill-only updates
        updates = {}
        def fill(colkey: str, newval: Any):
            col = cols.get(colkey)
            if not col or newval is None:
                return
            cur = row.get(col)
            if cur is None or cur == "":
                updates[col] = newval

        fill("value_num", m.get("value_num"))
        fill("value_text", m.get("value_text"))
        fill("unit", m.get("unit"))
        fill("comparator", m.get("comparator"))

        # Optional provenance fill-only (do not overwrite)
        fill("producer", m.get("producer"))
        fill("producer_version", m.get("producer_version"))
        fill("source_path", m.get("source_path"))
        fill("run_id", m.get("run_id"))
        fill("produced_at", m.get("produced_at"))
        fill("notes", m.get("notes"))

        if updates and cols.get("id") and "id" in row:
            set_sql = ", ".join([f"{c}=:v_{i}" for i, c in enumerate(updates.keys())])
            params = {f"v_{i}": v for i, v in enumerate(updates.values())}
            params["mid"] = row["id"]
            upd = text(f"UPDATE data_measurements SET {set_sql} WHERE id=:mid")
            db.execute(upd, params)
            wrote += 1

    return wrote


def upsert_measurements_force(db: Session, *, record_id: int, measurements: List[Dict[str, Any]]) -> int:
    """
    FORCE upsert:
    - overwrites values for matching name
    - creates if missing
    """
    if not measurements:
        return 0

    cols = _measurement_cols(db)
    wrote = 0
    primary_exists = _has_primary(db, record_id, cols)

    for m in measurements:
        name = (m.get("name") or "").strip()
        if not name:
            continue

        sel = text(
            f"SELECT * FROM data_measurements WHERE {cols['record_fk']}=:rid AND {cols['name']}=:name LIMIT 1"
        )
        row = db.execute(sel, {"rid": record_id, "name": name}).mappings().first()

        if row is None:
            # Create then treat as overwrite (insert with values)
            wrote += upsert_measurements(db, record_id=record_id, measurements=[m])
            continue

        updates = {}
        def setv(colkey: str, newval: Any):
            col = cols.get(colkey)
            if col:
                updates[col] = newval

        setv("value_num", m.get("value_num"))
        setv("value_text", m.get("value_text"))
        setv("unit", m.get("unit"))
        setv("comparator", m.get("comparator"))
        if cols.get("id") and "id" in row and updates:
            set_sql = ", ".join([f"{c}=:v_{i}" for i, c in enumerate(updates.keys())])
            params = {f"v_{i}": v for i, v in enumerate(updates.values())}
            params["mid"] = row["id"]
            upd = text(f"UPDATE data_measurements SET {set_sql} WHERE id=:mid")
            db.execute(upd, params)
            wrote += 1

        # Ensure some primary exists if supported
        if cols.get("is_primary") and (not primary_exists):
            db.execute(
                text(f"UPDATE data_measurements SET {cols['is_primary']}=1 WHERE id=:mid"),
                {"mid": row["id"]},
            )
            primary_exists = True

    return wrote
