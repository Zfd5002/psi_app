from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from psi.core.measurement_schema import measurement_cols

_ARTIFACT_TYPE_ORDER = {
    "SEC": 0,
    "SDS_PAGE": 1,
    "ENDOTOXIN": 2,
    "OTHER": 3,
}


def _norm(v: object) -> str:
    return str(v or "").strip()


def _artifact_type_for_record(*, domain: str, data_type: str, method: str, title: str, metric_keys: list[str]) -> str:
    tokens = " ".join(
        [
            _norm(domain).lower(),
            _norm(data_type).lower(),
            _norm(method).lower(),
            _norm(title).lower(),
            " ".join(_norm(mk).lower() for mk in metric_keys),
        ]
    )
    if "sec" in tokens or "monomer" in tokens or "hmw" in tokens or "lmw" in tokens:
        return "SEC"
    if "sds" in tokens or "page" in tokens:
        return "SDS_PAGE"
    if "endotoxin" in tokens or "lal" in tokens:
        return "ENDOTOXIN"
    return "OTHER"


def _parse_dt(value: str) -> float:
    txt = _norm(value)
    if not txt:
        return 0.0
    try:
        return float(datetime.fromisoformat(txt).timestamp())
    except Exception:
        return 0.0


def assemble_molecule_report_artifacts(
    db: Session,
    *,
    molecule_id: int,
    as_of: datetime,
) -> dict[str, Any]:
    as_of_iso = as_of.isoformat()
    rows = (
        db.execute(
            text(
                """
                SELECT
                  dr.id AS data_record_id,
                  dr.batch_id AS batch_id,
                  dr.title AS title,
                  dr.domain AS domain,
                  dr.data_type AS data_type,
                  dr.method AS method,
                  dr.created_at AS created_at,
                  b.batch_id AS batch_label
                FROM data_records dr
                LEFT JOIN batches b ON b.id = dr.batch_id
                WHERE dr.molecule_id = :molecule_id
                  AND datetime(dr.created_at) <= datetime(:as_of)
                ORDER BY datetime(dr.created_at) DESC, dr.id DESC
                """
            ),
            {"molecule_id": int(molecule_id), "as_of": as_of_iso},
        )
        .mappings()
        .all()
    )
    if not rows:
        return {"schema_version": "v1", "as_of": as_of_iso, "items": []}

    record_ids = [int(r["data_record_id"]) for r in rows]
    metric_by_record: dict[int, list[str]] = {rid: [] for rid in record_ids}
    mcols = measurement_cols(db)
    rec_fk = mcols.get("record_fk")
    name_col = mcols.get("name")
    if rec_fk and name_col and record_ids:
        params = {f"r{i}": rid for i, rid in enumerate(record_ids)}
        in_clause = ", ".join(f":r{i}" for i in range(len(record_ids)))
        q = text(
            f"""
            SELECT {rec_fk} AS record_id, {name_col} AS metric_key, id
            FROM data_measurements
            WHERE {rec_fk} IN ({in_clause})
            ORDER BY {rec_fk} ASC, {name_col} ASC, id ASC
            """
        )
        mrows = db.execute(q, params).mappings().all()
        for mr in mrows:
            rid = int(mr["record_id"])
            mk = _norm(mr["metric_key"])
            if mk:
                metric_by_record.setdefault(rid, []).append(mk)
        for rid in list(metric_by_record.keys()):
            metric_by_record[rid] = sorted({str(x) for x in metric_by_record.get(rid, [])})

    file_links = (
        db.execute(
            text(
                """
                SELECT
                  fl.entity_id AS data_record_id,
                  fl.file_id AS file_id,
                  fl.label AS label
                FROM file_links fl
                WHERE fl.entity_type = 'DataRecord'
                  AND fl.entity_id IN ({in_clause})
                ORDER BY fl.entity_id ASC, fl.file_id DESC, fl.id DESC
                """.format(in_clause=", ".join(f":r{i}" for i in range(len(record_ids))))
            ),
            {f"r{i}": rid for i, rid in enumerate(record_ids)},
        )
        .mappings()
        .all()
    )
    files_by_record: dict[int, list[dict[str, Any]]] = {}
    for fl in file_links:
        rid = int(fl["data_record_id"])
        files_by_record.setdefault(rid, []).append(
            {
                "file_id": int(fl["file_id"]),
                "label": _norm(fl["label"]) or f"file:{int(fl['file_id'])}",
            }
        )

    items: list[dict[str, Any]] = []
    for r in rows:
        rid = int(r["data_record_id"])
        metric_keys = metric_by_record.get(rid, [])
        artifact_type = _artifact_type_for_record(
            domain=_norm(r["domain"]),
            data_type=_norm(r["data_type"]),
            method=_norm(r["method"]),
            title=_norm(r["title"]),
            metric_keys=metric_keys,
        )
        links = [{"label": "Data record", "url": f"/data/{rid}"}]
        for f in files_by_record.get(rid, []):
            links.append({"label": str(f["label"]), "url": f"/files/{int(f['file_id'])}/download"})
        links = sorted(
            links,
            key=lambda l: (
                0 if str(l.get("label") or "") == "Data record" else 1,
                str(l.get("url") or ""),
            ),
        )
        items.append(
            {
                "artifact_type": artifact_type,
                "batch_id": (int(r["batch_id"]) if r["batch_id"] is not None else None),
                "batch_label": _norm(r["batch_label"]) or None,
                "data_record_id": rid,
                "title": _norm(r["title"]) or f"Data record {rid}",
                "created_at": _norm(r["created_at"]),
                "links": links,
            }
        )

    items = sorted(
        items,
        key=lambda i: (
            int(_ARTIFACT_TYPE_ORDER.get(str(i.get("artifact_type") or "OTHER"), 3)),
            -_parse_dt(str(i.get("created_at") or "")),
            -int(i.get("data_record_id") or 0),
        ),
    )
    return {
        "schema_version": "v1",
        "as_of": as_of_iso,
        "items": items,
    }
