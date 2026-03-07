from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from psi.core.measurement_schema import measurement_cols


TREND_METRIC_KEYS = ("monomer_pct", "kd_nM", "value_eu_ml")


def build_molecule_trends(
    db: Session,
    *,
    molecule_id: int,
    metric_keys: tuple[str, ...] = TREND_METRIC_KEYS,
) -> dict[str, Any]:
    cols = measurement_cols(db)
    mk_col = str(cols["name"])
    val_col = str(cols["value_num"])
    rec_fk_col = str(cols["record_fk"])
    created_col = str(cols["created_at"] or "created_at")
    placeholders = ",".join([f":m{i}" for i in range(len(metric_keys))]) or "''"
    sql = text(
        f"""
        SELECT
          dm.id AS measurement_id,
          dm.{rec_fk_col} AS data_record_id,
          dm.{mk_col} AS metric_key,
          dm.{val_col} AS value_num,
          dr.batch_id AS batch_id,
          COALESCE(NULLIF(dr.run_date, ''), CAST(dm.{created_col} AS TEXT), CAST(dr.created_at AS TEXT), '') AS ts
        FROM data_measurements dm
        JOIN data_records dr ON dr.id = dm.{rec_fk_col}
        WHERE dr.molecule_id = :molecule_id
          AND dm.{mk_col} IN ({placeholders})
          AND dm.{val_col} IS NOT NULL
        ORDER BY ts ASC, dm.id ASC
        """
    )
    params = {"molecule_id": int(molecule_id)}
    params.update({f"m{i}": str(mk) for i, mk in enumerate(metric_keys)})
    rows = db.execute(sql, params).mappings().all()

    by_metric: dict[str, list[dict[str, Any]]] = {str(mk): [] for mk in metric_keys}
    for r in rows:
        mk = str(r.get("metric_key") or "")
        if mk not in by_metric:
            continue
        by_metric[mk].append(
            {
                "measurement_id": int(r.get("measurement_id") or 0),
                "data_record_id": int(r.get("data_record_id") or 0),
                "batch_id": int(r.get("batch_id")) if r.get("batch_id") is not None else None,
                "ts": str(r.get("ts") or ""),
                "value": float(r.get("value_num")),
            }
        )

    return {
        "metric_keys": [str(mk) for mk in metric_keys],
        "series": by_metric,
    }

