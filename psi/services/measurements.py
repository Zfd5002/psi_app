from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session


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

_COL_CACHE: Optional[Dict[str, Optional[str]]] = None
_ALL_COLS_CACHE: Optional[set[str]] = None


def _measurement_cols(db: Session) -> Dict[str, Optional[str]]:
    """
    Detect column names in data_measurements so this code works across PSI versions.
    """
    global _COL_CACHE
    if _COL_CACHE is not None:
        return _COL_CACHE

    rows = db.execute(text("PRAGMA table_info(data_measurements)")).mappings().all()
    cols = {r["name"] for r in rows}
    global _ALL_COLS_CACHE
    _ALL_COLS_CACHE = set(cols)

    def pick(*names: str) -> Optional[str]:
        for n in names:
            if n in cols:
                return n
        return None

    _COL_CACHE = {
        "id": pick("id"),
        "record_fk": pick("data_record_id", "record_id"),
        "name": pick("name", "key"),
        "value_num": pick("value_num", "numeric_value", "value"),
        "value_text": pick("value_text", "text_value", "raw_value"),
        "unit": pick("unit"),
        "comparator": pick("comparator", "op"),
        "is_primary": pick("is_primary", "primary", "is_headline"),
        "qc_flag": pick("qc_flag", "qc_status"),
        "qc_note": pick("qc_note", "qc_reason", "qc_message"),
        "data_type": pick("data_type"),
        "method": pick("method"),
    }

    if not _COL_CACHE["record_fk"] or not _COL_CACHE["name"]:
        raise RuntimeError(
            f"data_measurements schema missing expected columns. Found: {sorted(cols)}"
        )

    return _COL_CACHE


def _all_measurement_cols(db: Session) -> set[str]:
    """Return the full set of column names for data_measurements."""
    global _ALL_COLS_CACHE
    if _ALL_COLS_CACHE is None:
        _measurement_cols(db)
    return _ALL_COLS_CACHE or set()


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
    }


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
            insert_cols = [cols["record_fk"], cols["name"]]
            insert_vals = {"rid": record_id, "name": name}

            def add(colkey: str, val: Any):
                col = cols.get(colkey)
                if col and val is not None:
                    insert_cols.append(col)
                    insert_vals[colkey] = val

            add("value_num", m.get("value_num"))
            add("value_text", m.get("value_text"))
            add("unit", m.get("unit"))
            add("comparator", m.get("comparator"))
            add("data_type", m.get("data_type"))
            add("method", m.get("method"))

            if cols.get("is_primary") and (not primary_exists):
                insert_cols.append(cols["is_primary"])
                insert_vals["is_primary"] = 1
                primary_exists = True

            col_sql = ", ".join(insert_cols)
            val_sql = ", ".join(
                [
                    ":rid" if c == cols["record_fk"] else (":name" if c == cols["name"] else f":{k}")
                    for c, k in zip(insert_cols, ["rid","name"] + [ck for ck in insert_vals.keys() if ck not in ("rid","name")])
                ]
            )
            # Build val_sql explicitly to match insert_cols
            bind_map = {cols["record_fk"]: "rid", cols["name"]: "name"}
            binds = []
            for c in insert_cols:
                if c in bind_map:
                    binds.append(f":{bind_map[c]}")
                elif c == cols.get("is_primary"):
                    binds.append(":is_primary")
                else:
                    # find which key holds this value
                    for k, v in insert_vals.items():
                        if cols.get(k) == c:
                            binds.append(f":{k}")
                            break
            val_sql = ", ".join(binds)

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
