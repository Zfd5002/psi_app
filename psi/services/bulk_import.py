from __future__ import annotations

import csv
import io
from typing import Any

from sqlalchemy.orm import Session

from psi.core.models import Batch, Molecule


_METRIC_TO_ASSAY = {
    "monomer_pct": ("CMC", "CMC_Analytics", "SEC_HPLC"),
    "kd_nM": ("Biological", "Binding", "BLI"),
    "value_eu_ml": ("CMC", "CMC_Analytics", "Endotoxin"),
}


def _split_rows(pasted_text: str) -> list[list[str]]:
    text = str(pasted_text or "").strip()
    if not text:
        return []
    sample = text.splitlines()[0]
    delimiter = "\t" if "\t" in sample else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    return [list(row) for row in reader]


def parse_bulk_import_rows(pasted_text: str) -> list[dict[str, str]]:
    rows = _split_rows(pasted_text)
    if not rows:
        return []
    header = [str(x or "").strip().lower() for x in rows[0]]
    expected = ["molecule", "batch", "metric", "value", "unit"]
    if header != expected:
        raise ValueError("Header must be: molecule,batch,metric,value,unit (or tab-separated equivalent)")
    out: list[dict[str, str]] = []
    for idx, r in enumerate(rows[1:], start=2):
        padded = (r + ["", "", "", "", ""])[:5]
        row = {
            "row_num": str(idx),
            "molecule": str(padded[0] or "").strip(),
            "batch": str(padded[1] or "").strip(),
            "metric": str(padded[2] or "").strip(),
            "value": str(padded[3] or "").strip(),
            "unit": str(padded[4] or "").strip(),
        }
        if not any(row[k] for k in ("molecule", "batch", "metric", "value", "unit")):
            continue
        out.append(row)
    return out


def validate_bulk_import_rows(db: Session, *, parsed_rows: list[dict[str, str]]) -> dict[str, Any]:
    validated: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for row in parsed_rows:
        rn = int(row.get("row_num") or 0)
        molecule_key = str(row.get("molecule") or "")
        batch_key = str(row.get("batch") or "")
        metric_key = str(row.get("metric") or "")
        value_raw = str(row.get("value") or "")
        unit = str(row.get("unit") or "")

        mol = db.query(Molecule).filter(Molecule.primary_id == molecule_key).first()
        if not mol:
            errors.append({"row_num": rn, "error": f"Unknown molecule: {molecule_key}"})
            continue
        batch = (
            db.query(Batch)
            .filter(Batch.molecule_id == int(mol.id), Batch.batch_id == batch_key)
            .order_by(Batch.id.desc())
            .first()
        )
        if not batch:
            errors.append({"row_num": rn, "error": f"Unknown batch for molecule: {batch_key}"})
            continue
        try:
            value_num = float(value_raw)
        except Exception:
            errors.append({"row_num": rn, "error": f"Value is not numeric: {value_raw}"})
            continue

        domain, data_type, method = _METRIC_TO_ASSAY.get(metric_key, ("Other", "Other", metric_key or "Unknown"))
        validated.append(
            {
                "row_num": rn,
                "program_id": int(mol.program_id),
                "molecule_id": int(mol.id),
                "batch_id": int(batch.id),
                "batch_label": str(batch.batch_id or ""),
                "metric_key": metric_key,
                "value_num": value_num,
                "unit": unit,
                "domain": domain,
                "data_type": data_type,
                "method": method,
                "title": f"Bulk import {metric_key}",
            }
        )

    return {
        "validated_rows": sorted(validated, key=lambda x: (int(x["row_num"]), int(x["molecule_id"]), int(x["batch_id"]), str(x["metric_key"]))),
        "errors": sorted(errors, key=lambda x: (int(x["row_num"]), str(x["error"]))),
    }

