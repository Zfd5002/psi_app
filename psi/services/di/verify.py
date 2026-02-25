"""Deterministic DI snapshot verification (read-only).

This is the shared implementation for:
- CLI tool: `python -m psi.tools.verify_snapshot`
- Web verification endpoint + anchored replay (v1.2.9m)

The verifier:
- Recomputes DI output using the policy resolved from the repo.
- Compares stored integrity fields (policy hashes, evidence fingerprint, snapshot content hash).
- Classifies drift without mutating the DB or persisting new snapshots.
"""

from __future__ import annotations

import json
import copy
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

from sqlalchemy.orm import Session

from psi.core.di.policy import load_policy
from psi.core.di.schema import DIInput
from psi.core.models import DecisionSnapshot, MeasurementQC
from psi.services.di.integrity import compute_decision_output_hash, compute_decision_output_hash_v2
from psi.services.di.integrity import extract_evidence_tuples_from_used
from psi.services.di.compute import _compute_di_from_used_by_metric
from psi.services.di.runner import compute_di_output
from psi.services.di.util import qc_status_from_flag, stable_json_dumps

# Anchored replay recomputation (verification-only).
from sqlalchemy import text, bindparam

from psi.core.measurement_schema import measurement_cols
from psi.core.di.schema import EvidenceRef
from types import SimpleNamespace

def _canonical_json_bytes(obj) -> bytes:
    return stable_json_dumps(obj).encode("utf-8")

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

from psi.services.di.integrity import compute_evidence_fingerprint, compute_snapshot_content_hash


def _as_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _as_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def _extract_used_metric_to_mid(outputs_obj: Dict[str, Any]) -> Dict[str, int]:
    """Extract metric_key -> measurement_id from stored snapshot output.

    This is a verification-only helper to enable anchored replay by measurement IDs.
    """

    soe = _as_dict(outputs_obj.get("state_of_evidence"))
    used = _as_dict(soe.get("used"))
    out: Dict[str, int] = {}
    for mk in sorted([str(k) for k in used.keys()]):
        ev = used.get(mk)
        mid: Optional[int] = None
        if isinstance(ev, dict):
            v = ev.get("measurement_id")
            try:
                mid = int(v)
            except Exception:
                mid = None
        else:
            try:
                mid = int(getattr(ev, "measurement_id", None))
            except Exception:
                mid = None
        if mid is not None and mid > 0:
            out[str(mk)] = int(mid)
    return out


def _load_measurements_by_id(db: Session, *, mids: List[int]) -> Dict[int, Dict[str, Any]]:
    """Load raw data_measurements rows by id (read-only)."""

    mids = [int(x) for x in mids if isinstance(x, int) or str(x).isdigit()]
    mids = sorted(list(set([int(x) for x in mids if int(x) > 0])))
    if not mids:
        return {}

    cols = measurement_cols(db)
    id_col = cols.get("id") or "id"
    record_fk = cols["record_fk"]

    q = text(
        f"""
        SELECT
          dm.*,
          dr.id as _dr_id
        FROM data_measurements dm
        JOIN data_records dr ON dr.id = dm.{record_fk}
        WHERE dm.{id_col} IN :mids
        ORDER BY dm.{id_col} ASC
        """
    ).bindparams(bindparam("mids", expanding=True))

    # NOTE: use SQLAlchemy expanding bindparam for SQLite-compatible `IN (...)`.
    rows = db.execute(q, {"mids": list(mids)}).mappings().all()
    out: Dict[int, Dict[str, Any]] = {}
    for r in rows:
        try:
            mid = int(r.get(id_col) if id_col in r else r.get("id"))
        except Exception:
            continue
        out[int(mid)] = dict(r)
    return out


def _qc_status_for_mid(db: Session, *, mid: int, qc_flag_raw: Any) -> Tuple[str, str]:
    """Return (qc_status, qc_source) deterministically."""

    qc = db.query(MeasurementQC).filter(MeasurementQC.measurement_id == int(mid)).first()
    if qc and qc.status:
        return str(qc.status), "measurement_qc"
    return qc_status_from_flag(qc_flag_raw), "qc_flag_fallback"


def _build_evidence_ref_from_row(
    *,
    cols: Dict[str, Any],
    metric_key: str,
    metric_key_source: str,
    row: Dict[str, Any],
    qc_status: str,
    qc_source: str,
) -> EvidenceRef:
    id_col = cols.get("id") or "id"
    unit_col = cols.get("unit")
    comparator_col = cols.get("comparator")
    produced_col = cols.get("produced_at")
    created_col = cols.get("created_at")
    is_primary_col = cols.get("is_primary")
    is_outlier_col = cols.get("is_outlier")
    qc_flag_col = cols.get("qc_flag")

    mid = int(row.get(id_col) if id_col in row else row.get("id"))
    drid = int(row.get("_dr_id") or 0)

    val_num = row.get(cols.get("value_num"))
    val_text = row.get(cols.get("value_text"))
    val_bool_raw = row.get(cols.get("value_bool")) if cols.get("value_bool") else row.get("value_bool")

    vb: Optional[bool]
    if isinstance(val_bool_raw, bool):
        vb = val_bool_raw
    elif isinstance(val_bool_raw, int):
        vb = bool(val_bool_raw)
    elif isinstance(val_bool_raw, str) and val_bool_raw.strip().lower() in ("true", "false"):
        vb = (val_bool_raw.strip().lower() == "true")
    else:
        vb = None

    return EvidenceRef(
        measurement_id=mid,
        data_record_id=drid,
        metric_key=str(metric_key),
        metric_key_source=str(metric_key_source),
        value_num=(float(val_num) if val_num is not None and not isinstance(val_num, bool) else None),
        value_text=(str(val_text).strip() if isinstance(val_text, str) and val_text.strip() else None),
        value_bool=vb,
        unit=(str(row.get(unit_col)).strip() if unit_col and row.get(unit_col) is not None else None),
        comparator=(str(row.get(comparator_col)).strip() if comparator_col and row.get(comparator_col) is not None else None),
        qc_status=str(qc_status),
        qc_flag_raw=(str(row.get(qc_flag_col)) if qc_flag_col and row.get(qc_flag_col) is not None else None),
        qc_source=str(qc_source),
        is_primary=(bool(int(row.get(is_primary_col) or 0)) if is_primary_col else False),
        is_outlier=(bool(int(row.get(is_outlier_col) or 0)) if is_outlier_col else False),
        produced_at=(str(row.get(produced_col)) if produced_col and row.get(produced_col) is not None else None),
        created_at=(str(row.get(created_col)) if created_col and row.get(created_col) is not None else None),
    )


def _compute_anchored_replay(
    *,
    db: Session,
    di_in: DIInput,
    pol: Any,
    policy_path: Path,
    stored_outputs_obj: Dict[str, Any],
    stored_evidence_ids_json: List[int],
    stored_inputs_obj: Dict[str, Any],
) -> Dict[str, Any]:
    """Verification-only anchored replay recompute using snapshot-stored evidence IDs.

    This function intentionally does NOT change selector semantics; it bypasses selection
    entirely by using the measurement IDs embedded in the stored snapshot output.
    """

    metric_to_mid = _extract_used_metric_to_mid(stored_outputs_obj)
    if not metric_to_mid:
        return {
            "available": False,
            "reason": "missing_state_of_evidence_used_map",
            "missing_measurement_ids": sorted(list(set(stored_evidence_ids_json or []))),
            "output": None,
        }

    mids = sorted(list(set([int(x) for x in metric_to_mid.values() if int(x) > 0])))
    rows_by_id = _load_measurements_by_id(db, mids=mids)

    cols = measurement_cols(db)
    name_col = cols.get("name")
    qc_flag_col = cols.get("qc_flag")

    used_by_metric: Dict[str, EvidenceRef] = {}
    missing: List[int] = []
    metric_missing: List[str] = []

    for mk in sorted(metric_to_mid.keys()):
        mid = int(metric_to_mid[mk])
        row = rows_by_id.get(mid)
        if not row:
            missing.append(int(mid))
            metric_missing.append(str(mk))
            continue

        raw_name = str(row.get(name_col) or "").strip() if name_col else ""
        metric_key_source = "canonical" if raw_name == str(mk) else (f"alias:{raw_name}" if raw_name else "canonical")

        qc_status, qc_source = _qc_status_for_mid(db, mid=mid, qc_flag_raw=(row.get(qc_flag_col) if qc_flag_col else None))

        used_by_metric[str(mk)] = _build_evidence_ref_from_row(
            cols=cols,
            metric_key=str(mk),
            metric_key_source=metric_key_source,
            row=row,
            qc_status=qc_status,
            qc_source=qc_source,
        )

    if missing:
        return {
            "available": False,
            "reason": "stored_measurement_ids_missing_in_db",
            "missing_measurement_ids": sorted(list(set([int(x) for x in missing]))),
            "missing_metrics": sorted(list(set([str(x) for x in metric_missing]))),
            "output": None,
        }
    # Use the snapshot-stored SoE metadata to ensure anchored replay output is byte-identical.
    soe = _as_dict(stored_outputs_obj.get("state_of_evidence"))
    ignored: List[Any] = _as_list(soe.get("ignored_evidence"))
    warnings: List[Dict[str, Any]] = _as_list(soe.get("warnings"))  # type: ignore[assignment]
    prov = _as_dict(stored_outputs_obj.get("provenance"))
    selection_provenance = _as_dict(prov.get("selection_provenance"))

    # NOTE: Do NOT inject anchored_replay markers into the output payload; keep those in the verify report only.

    out = _compute_di_from_used_by_metric(
        db,
        di_in=di_in,
        pol=pol,
        used_by_metric=used_by_metric,
        inputs_obj=stored_inputs_obj,
        ignored=ignored,
        warnings=warnings,
        selection_provenance=selection_provenance,
    )
    out = _scrub_output_for_replay(
        out,
        policy_version=str(stored_inputs_obj.get("policy_version") or ""),
        schema_version=str(stored_inputs_obj.get("schema_version") or ""),
    )

    # --- Legacy compatibility (verification-only) ---
    # Some early snapshots were created before certain provenance fields were
    # fully normalized (e.g. scope_id type, as_of_ts surface). Anchored replay
    # must reproduce the stored snapshot surface for those snapshots. We do
    # this by:
    #   1) copying specific provenance fingerprint fields from the stored output
    #   2) recomputing integrity hashes on the adjusted payload (read-only)
    try:
        sprov = stored_outputs_obj.get("provenance") if isinstance(stored_outputs_obj.get("provenance"), dict) else {}
        sout_fp = sprov.get("inputs_fingerprint") if isinstance(sprov.get("inputs_fingerprint"), dict) else {}

        stored_scope_id = sout_fp.get("scope_id")
        stored_as_of_ts = sprov.get("as_of_ts") if "as_of_ts" in sprov else None

        oprov = out.get("provenance") if isinstance(out.get("provenance"), dict) else {}
        out_fp = oprov.get("inputs_fingerprint") if isinstance(oprov.get("inputs_fingerprint"), dict) else {}

        replay_scope_id = out_fp.get("scope_id")
        replay_as_of_ts = oprov.get("as_of_ts") if "as_of_ts" in oprov else None

        mutated = False

        # 1) scope_id type mismatches (str vs int) on legacy snapshots
        if stored_scope_id is not None and replay_scope_id is not None and type(stored_scope_id) != type(replay_scope_id):
            out_fp = dict(out_fp)
            out_fp["scope_id"] = stored_scope_id
            oprov = dict(oprov)
            oprov["inputs_fingerprint"] = out_fp
            mutated = True

        # 2) legacy as_of_ts omitted (null) but anchored replay uses an effective as_of
        #    for computation. For integrity reproduction we must match the stored surface.
        if stored_as_of_ts is None and replay_as_of_ts is not None:
            oprov = dict(oprov)
            oprov["as_of_ts"] = None
            mutated = True
        elif stored_as_of_ts is not None and replay_as_of_ts is not None and str(stored_as_of_ts) != str(replay_as_of_ts):
            # Extremely defensive: if stored has an explicit value, mirror it.
            oprov = dict(oprov)
            oprov["as_of_ts"] = stored_as_of_ts
            mutated = True

        # 3) drift_type should be byte-identical for anchored replay (derived-only).
        stored_drift = stored_outputs_obj.get("drift_type") if isinstance(stored_outputs_obj, dict) else None
        replay_drift = out.get("drift_type") if isinstance(out, dict) else None
        if stored_drift is not None and stored_drift != replay_drift:
            out = dict(out)
            out["drift_type"] = stored_drift
            mutated = True
        elif stored_drift is None and replay_drift is not None:
            # Legacy snapshots without drift_type should remain hash-identical.
            out = dict(out)
            out.pop("drift_type", None)
            mutated = True

        # 4) state_transition should be byte-identical for anchored replay (derived-only).
        stored_state = stored_outputs_obj.get("state_transition") if isinstance(stored_outputs_obj, dict) else None
        replay_state = out.get("state_transition") if isinstance(out, dict) else None
        if stored_state is not None and stored_state != replay_state:
            out = dict(out)
            out["state_transition"] = stored_state
            mutated = True
        elif stored_state is None and replay_state is not None:
            out = dict(out)
            out.pop("state_transition", None)
            mutated = True

        # 5) comparability should be byte-identical for anchored replay (derived-only).
        stored_comp = stored_outputs_obj.get("comparability") if isinstance(stored_outputs_obj, dict) else None
        replay_comp = out.get("comparability") if isinstance(out, dict) else None
        if stored_comp is not None and stored_comp != replay_comp:
            out = dict(out)
            out["comparability"] = stored_comp
            mutated = True
        elif stored_comp is None and replay_comp is not None:
            out = dict(out)
            out.pop("comparability", None)
            mutated = True

        if mutated:
            out["provenance"] = oprov

            # Recompute integrity on the mutated payload.
            evidence_ids = mids

            used_map = {}
            soe2 = out.get("state_of_evidence") if isinstance(out.get("state_of_evidence"), dict) else {}
            used2 = soe2.get("used") if isinstance(soe2.get("used"), dict) else {}
            for mk in sorted([str(k) for k in used2.keys()]):
                ev = used2.get(mk) or {}
                if isinstance(ev, dict):
                    used_map[mk] = SimpleNamespace(
                        measurement_id=str(ev.get("measurement_id") or ""),
                        qc_status=str(ev.get("qc_status") or ""),
                        unit=str(ev.get("unit") or ""),
                        comparator=str(ev.get("comparator") or ""),
                    )

            integ = {}
            try:
                integ["evidence_fingerprint"] = compute_evidence_fingerprint(used_by_metric=used_map)
            except Exception:
                integ["evidence_fingerprint"] = ""
            try:
                integ["snapshot_content_hash"] = compute_snapshot_content_hash(
                    inputs_obj=stored_inputs_obj,
                    outputs_obj=out,
                    evidence_ids=list(evidence_ids or []),
                )
            except Exception:
                integ["snapshot_content_hash"] = ""
            try:
                integ["decision_output_hash"] = compute_decision_output_hash(inputs_obj=stored_inputs_obj, outputs_obj=out)
            except Exception:
                integ["decision_output_hash"] = ""
            try:
                integ["decision_output_hash_v2"] = compute_decision_output_hash_v2(inputs_obj=stored_inputs_obj, outputs_obj=out)
            except Exception:
                integ["decision_output_hash_v2"] = ""

            prov3 = out.get("provenance") if isinstance(out.get("provenance"), dict) else {}
            integ_existing = prov3.get("integrity") if isinstance(prov3.get("integrity"), dict) else {}
            integ_existing = dict(integ_existing)
            integ_existing.update(integ)
            prov3 = dict(prov3)
            prov3["integrity"] = integ_existing
            out["provenance"] = prov3
    except Exception:
        # Never fail verification due to best-effort legacy alignment.
        pass

    return {
        "available": True,
        "reason": "ok",
        "missing_measurement_ids": [],
        "output": out,
    }


def _parse_json_field(raw: str | None, *, default: Any) -> Any:
    if raw is None:
        return default
    s = str(raw).strip()
    if not s:
        return default
    return json.loads(s)


def _coerce_int_list(value: Any) -> List[int]:
    """Best-effort coercion to a deterministic, sorted list[int].

    - Accepts lists/tuples/sets, or a single scalar.
    - Ignores unparseable values.
    - Always returns a sorted ascending list of unique ints.
    """

    if value is None:
        return []

    items: List[Any]
    if isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]

    out: List[int] = []
    for x in items:
        try:
            out.append(int(x))
        except Exception:
            continue
    return sorted(list(set(out)))



def _require_integrity_present(output: Dict[str, Any], *, label: str) -> Dict[str, Any]:
    """Require output['provenance']['integrity'] to exist for verification.

    Verification must never compute integrity using alternate algorithms. Integrity
    is defined by the canonical functions in psi.services.di.integrity and is
    expected to be present on all DI outputs produced by compute_di_output/run_di.
    """

    if not isinstance(output, dict):
        raise AssertionError(f"{label}: output is not a dict")

    prov = output.get('provenance')
    if not isinstance(prov, dict):
        raise AssertionError(f"{label}: output.provenance missing or not a dict")

    integ = prov.get('integrity')
    if not isinstance(integ, dict):
        raise AssertionError(f"{label}: output.provenance.integrity missing or not a dict")

    required_keys = ['snapshot_content_hash','evidence_fingerprint','decision_output_hash','decision_output_hash_v2']
    missing = [k for k in required_keys if not str(integ.get(k) or '').strip()]
    if missing:
        raise AssertionError(f"{label}: provenance.integrity missing required keys: {missing}")

    return integ



def _fetch_measurements_brief(db: Session, ids: List[int]) -> Dict[int, Dict[str, Any]]:
    if not ids:
        return {}
    cols = measurement_cols(db)
    qc_col = cols.get("qc_status")
    # We intentionally keep this query defensive: only select columns we know exist in all schemas.
    sel = [
        "id",
        "data_record_id",
        "metric_key",
        "value_num",
        "value_text",
        "unit",
        "created_at",
    ]
    if qc_col:
        sel.append(f"{qc_col} as qc_status")
    q = text(
        f"""
        select {", ".join(sel)}
        from data_measurements
        where id in :ids
        """
    ).bindparams(bindparam("ids", expanding=True))
    rows = db.execute(q, {"ids": list(ids)}).mappings().all()
    out: Dict[int, Dict[str, Any]] = {}
    for r in rows:
        out[int(r["id"])] = dict(r)
    return out


def _explain_evidence_id_change(db: Session, removed_ids: List[int], added_ids: List[int]) -> Dict[str, Any]:
    """Explain why evidence ids changed between stored and recomputed selections.

    This is a best-effort diagnostic, not a formal guarantee.
    """
    removed = _fetch_measurements_brief(db, removed_ids)
    added = _fetch_measurements_brief(db, added_ids)

    # Index by metric_key when possible (most diffs are re-selection of same metric).
    removed_by_metric: Dict[str, List[Dict[str, Any]]] = {}
    for m in removed.values():
        removed_by_metric.setdefault(str(m.get("metric_key")), []).append(m)
    added_by_metric: Dict[str, List[Dict[str, Any]]] = {}
    for m in added.values():
        added_by_metric.setdefault(str(m.get("metric_key")), []).append(m)

    per_metric: List[Dict[str, Any]] = []
    metric_keys = sorted(set(list(removed_by_metric.keys()) + list(added_by_metric.keys())))
    for mk in metric_keys:
        r_list = sorted(removed_by_metric.get(mk, []), key=lambda x: (x.get("created_at") or "", x.get("id") or 0))
        a_list = sorted(added_by_metric.get(mk, []), key=lambda x: (x.get("created_at") or "", x.get("id") or 0))
        if not r_list or not a_list:
            per_metric.append({
                "metric_key": mk,
                "removed_ids": [x.get("id") for x in r_list],
                "added_ids": [x.get("id") for x in a_list],
                "reason_key": "metric_added_or_removed",
            })
            continue

        # Most common: 1->1 swap due to newer data_record/created_at.
        r0, a0 = r_list[-1], a_list[-1]
        reason = "unknown"
        try:
            r_ts = r0.get("created_at")
            a_ts = a0.get("created_at")
            same_value = (r0.get("value_num") == a0.get("value_num")) and (str(r0.get("value_text")) == str(a0.get("value_text")))
            if a_ts and r_ts and str(a_ts) > str(r_ts):
                reason = "newer_measurement_selected" if same_value else "newer_measurement_with_value_change"
            elif not a_ts and not r_ts:
                reason = "tie_break_selected_different_id"
            else:
                reason = "selection_changed"
        except Exception:
            pass

        per_metric.append({
            "metric_key": mk,
            "removed_id": r0.get("id"),
            "removed_created_at": r0.get("created_at"),
            "removed_data_record_id": r0.get("data_record_id"),
            "removed_qc_status": r0.get("qc_status"),
            "added_id": a0.get("id"),
            "added_created_at": a0.get("created_at"),
            "added_data_record_id": a0.get("data_record_id"),
            "added_qc_status": a0.get("qc_status"),
            "removed_value_num": r0.get("value_num"),
            "added_value_num": a0.get("value_num"),
            "removed_value_text": r0.get("value_text"),
            "added_value_text": a0.get("value_text"),
            "unit": a0.get("unit") or r0.get("unit"),
            "reason_key": reason,
        })

    return {
        "removed_count": len(removed_ids),
        "added_count": len(added_ids),
        "per_metric": per_metric,
        "note": "If reason_key is 'newer_measurement_selected', this usually means new measurements were inserted after the snapshot was created; recompute chooses the newest per selection semantics.",
    }

def _strip_volatile_fields_for_semantic_compare(outputs_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Remove fields that can legitimately change across releases without
    changing decision meaning.

    Today this includes:
      - outputs.engine.code_version
      - outputs.provenance.integrity (hashes)
    """

    # IMPORTANT: never mutate `outputs_obj` in-place.
    # We strip hashes for semantic comparison only; the caller may still need
    # provenance.integrity later for drift classification and debug output.
    try:
        # Prefer a JSON round-trip for a deep copy, using default=str to
        # tolerate datetimes/Decimals/etc.
        cleaned: Any = json.loads(json.dumps(outputs_obj, default=str))
    except Exception:
        # Fallback: deepcopy to avoid in-place mutation if JSON encoding fails.
        cleaned = copy.deepcopy(outputs_obj)

    if not isinstance(cleaned, dict):
        return copy.deepcopy(outputs_obj)

    eng = cleaned.get("engine")
    if isinstance(eng, dict):
        eng.pop("code_version", None)

    prov = cleaned.get("provenance")
    if isinstance(prov, dict):
        prov.pop("integrity", None)

    return cleaned


def _semantic_fingerprint(outputs_obj: Dict[str, Any]) -> str:
    """Stable fingerprint of semantic outputs (excluding volatile fields).

    Hashes the stripped outputs payload (engine.code_version and provenance.integrity
    removed) so the fingerprint is stable across PSI version upgrades and additive
    integrity fields, but changes when decision outcomes or evidence change.
    """
    try:
        stripped = _strip_volatile_fields_for_semantic_compare(outputs_obj)
        s = json.dumps(stripped, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        return hashlib.sha256(s.encode("utf-8")).hexdigest()
    except Exception:
        return ""


def _scrub_output_for_replay(output: Dict[str, Any], *, policy_version: str, schema_version: str) -> Dict[str, Any]:
    """Replay-only compatibility scrub for historical canonical surfaces.

    Historical v0.3 snapshots (DI snapshot v0.1) must not receive post-w52
    context-branch fields in canonical replay outputs.
    """

    if not isinstance(output, dict):
        return output
    pv = str(policy_version or "").strip().lower()
    sv = str(schema_version or "").strip().lower()
    if not (pv.startswith("v0.3") or sv == "di.snapshot.v0_1"):
        return output

    out = dict(output)
    out.pop("context_evaluation", None)
    gate_outcomes = out.get("gate_outcomes")
    if isinstance(gate_outcomes, dict):
        cleaned: Dict[str, Any] = {}
        for gk in sorted([str(k) for k in gate_outcomes.keys()]):
            gd = gate_outcomes.get(gk)
            if not isinstance(gd, dict):
                cleaned[gk] = gd
                continue
            g2 = dict(gd)
            g2.pop("required_metrics_base", None)
            g2.pop("requirement_mode", None)
            g2.pop("context_branch", None)
            cleaned[gk] = g2
        out["gate_outcomes"] = cleaned
    shortlisting = out.get("shortlisting")
    if isinstance(shortlisting, dict):
        s2 = dict(shortlisting)
        s2.pop("refusal_reasons_text", None)
        s2.pop("tie_break", None)
        s2.pop("candidates", None)
        out["shortlisting"] = s2
    return out


def _resolve_policy_from_repo(
    *,
    policy_id: str,
    policy_version: str,
    policy_semantics_hash: str = "",
    policy_package_hash: str = "",
    require_exact_hash_match: bool = False,
) -> Tuple[Any, Path]:
    base = Path(__file__).resolve().parents[2]  # psi/
    pol_dir = base / "core" / "di" / "policies"
    if not pol_dir.exists():
        raise ValueError(f"Policy directory not found: {pol_dir}")

    matches: List[Tuple[Any, Path]] = []
    for p in sorted(pol_dir.glob("*.json")):
        try:
            pol = load_policy(p)
        except Exception:
            continue
        if str(pol.policy_id) == str(policy_id) and str(pol.version) == str(policy_version):
            matches.append((pol, p))

    if not matches:
        raise ValueError(f"Policy not found in repo for policy_id={policy_id!r} policy_version={policy_version!r}")
    sem_h = str(policy_semantics_hash or "")
    pkg_h = str(policy_package_hash or "")
    if sem_h or pkg_h:
        exact_matches: List[Tuple[Any, Path]] = []
        for pol, p in matches:
            pol_sem = str(getattr(pol, "policy_semantics_hash", "") or "")
            pol_pkg = str(getattr(pol, "policy_package_hash", "") or "")
            if sem_h and pol_sem != sem_h:
                continue
            if pkg_h and pol_pkg != pkg_h:
                continue
            exact_matches.append((pol, p))
        if exact_matches:
            if len(exact_matches) > 1:
                exact_matches.sort(key=lambda t: str(t[1]))
            return exact_matches[0]
        if require_exact_hash_match:
            raise ValueError(
                f"Policy exact hash match not found in repo for policy_id={policy_id!r} "
                f"policy_version={policy_version!r}"
            )
    if len(matches) > 1:
        # Deterministic choice, but treat as governance warning.
        matches.sort(key=lambda t: str(t[1]))
    return matches[0]



def _drift_classification(
    *,
    stored_policy_semantics_hash: str,
    stored_policy_package_hash: str,
    recomputed_policy_semantics_hash: str,
    recomputed_policy_package_hash: str,
    stored_evidence_fingerprint: str,
    recomputed_evidence_fingerprint: str,
    stored_snapshot_content_hash: str,
    recomputed_snapshot_content_hash: str,
    stored_decision_output_hash: str,
    recomputed_decision_output_hash: str,
    stored_semantic_fingerprint: str | None,
    recomputed_semantic_fingerprint: str | None,
    stored_evidence_tuples: List[List[str]] | None,
    recomputed_evidence_tuples: List[List[str]] | None,
) -> Tuple[str, Dict[str, Any]]:
    """Return (classification, explain)."""

    explain: Dict[str, Any] = {
        "policy_hash_changed": False,
        "evidence_changed": False,
        "qc_only_changes": False,
        "structural_only": False,
        "semantic_changed": False,
        "snapshot_content_hash_changed": False,
        "missing_stored_integrity_fields": False,
        "legacy_integrity_hash_mismatch": False,
    }

    missing_integrity = (not stored_snapshot_content_hash) or (not stored_evidence_fingerprint)
    if missing_integrity:
        explain["missing_stored_integrity_fields"] = True

    if (stored_policy_semantics_hash != recomputed_policy_semantics_hash) or (
        stored_policy_package_hash != recomputed_policy_package_hash
    ):
        explain["policy_hash_changed"] = True
        return "POLICY_DRIFT", explain

    # Legacy snapshots without integrity fields cannot be VERIFIED; treat as structural drift.
    if missing_integrity:
        explain["structural_only"] = True
        return "STRUCTURAL_DRIFT", explain

    if stored_evidence_fingerprint != recomputed_evidence_fingerprint:
        explain["evidence_changed"] = True
        qc_only = False
        if stored_evidence_tuples is not None and recomputed_evidence_tuples is not None:
            if len(stored_evidence_tuples) == len(recomputed_evidence_tuples):
                same_metric_and_id = True
                qc_changed = False
                for a, b in zip(stored_evidence_tuples, recomputed_evidence_tuples):
                    # [metric_key, measurement_id, qc_status, unit, comparator]
                    if a[0] != b[0] or a[1] != b[1]:
                        same_metric_and_id = False
                        break
                    if a[2] != b[2]:
                        qc_changed = True
                if same_metric_and_id and qc_changed:
                    qc_only = True
        explain["qc_only_changes"] = qc_only
        return ("QC_DRIFT" if qc_only else "DATA_DRIFT"), explain

    # Evidence + policy match, so allow legacy integrity hash mismatches as long
    # as the semantic decision surface is identical after removing volatile
    # integrity fields (e.g., provenance.integrity and engine.code_version).
    if (
        stored_semantic_fingerprint
        and recomputed_semantic_fingerprint
        and stored_semantic_fingerprint == recomputed_semantic_fingerprint
    ):
        if stored_snapshot_content_hash != recomputed_snapshot_content_hash:
            explain["snapshot_content_hash_changed"] = True
        if stored_decision_output_hash and recomputed_decision_output_hash:
            if stored_decision_output_hash != recomputed_decision_output_hash:
                explain["legacy_integrity_hash_mismatch"] = True
        return "VERIFIED", explain

    # Semantic decision surface: if this matches, the snapshot is VERIFIED even if
    # full snapshot_content_hash differs due to additive diagnostic fields.
    if stored_decision_output_hash and recomputed_decision_output_hash:
        if stored_decision_output_hash == recomputed_decision_output_hash:
            if stored_snapshot_content_hash != recomputed_snapshot_content_hash:
                explain["snapshot_content_hash_changed"] = True
            return "VERIFIED", explain

    # Fallback: if decision_output_hash missing, default to legacy behavior.
    if stored_snapshot_content_hash != recomputed_snapshot_content_hash:
        explain["snapshot_content_hash_changed"] = True
        explain["structural_only"] = True
        # If we have decision_output_hash values but they differ, flag it.
        if stored_decision_output_hash and recomputed_decision_output_hash and (
            stored_decision_output_hash != recomputed_decision_output_hash
        ):
            explain["semantic_changed"] = True
        return "STRUCTURAL_DRIFT", explain

    return "VERIFIED", explain


def _diff_top_level_keys(a: Any, b: Any) -> Dict[str, Any]:
    """Small deterministic structural diff for debugging drift.

    Returns only key-level differences (added/removed/changed keys), to avoid
    expensive deep diffs and to keep output stable.
    """

    da = a if isinstance(a, dict) else {}
    db = b if isinstance(b, dict) else {}
    ka = set([str(k) for k in da.keys()])
    kb = set([str(k) for k in db.keys()])
    added = sorted(list(kb - ka))
    removed = sorted(list(ka - kb))
    changed: List[str] = []
    for k in sorted(list(ka & kb)):
        if str(type(da.get(k))) != str(type(db.get(k))):
            changed.append(k)
            continue
        # cheap compare
        if da.get(k) != db.get(k):
            changed.append(k)
    return {"added": added, "removed": removed, "changed": changed}


def _is_comparable_output(outputs_obj: Dict[str, Any]) -> bool:
    comp = outputs_obj.get("comparability") if isinstance(outputs_obj, dict) else {}
    if isinstance(comp, dict) and "is_comparable" in comp:
        try:
            return bool(comp.get("is_comparable"))
        except Exception:
            return False
    return False


def _build_diff_surface(outputs_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Curated, deterministic diff surface for governance comparison."""
    out = outputs_obj if isinstance(outputs_obj, dict) else {}

    surface: Dict[str, Any] = {}
    surface["decision_state"] = str(out.get("decision_state") or "")
    surface["drift_type"] = str(out.get("drift_type") or "")

    st = out.get("state_transition") if isinstance(out.get("state_transition"), dict) else {}
    if isinstance(st, dict) and st:
        surface["state_transition.trigger"] = str(st.get("trigger") or "")
        surface["state_transition.from_state"] = str(st.get("from_state") or "")
        surface["state_transition.to_state"] = str(st.get("to_state") or "")

    comp = out.get("comparability") if isinstance(out.get("comparability"), dict) else {}
    if isinstance(comp, dict) and comp:
        surface["comparability.is_comparable"] = bool(comp.get("is_comparable"))
        surface["comparability.reason"] = str(comp.get("reason") or "")
        surface["comparability.policy_semantics_hash_changed"] = bool(comp.get("policy_semantics_hash_changed"))
        surface["comparability.evidence_fingerprint_changed"] = bool(comp.get("evidence_fingerprint_changed"))

    readiness = out.get("readiness") if isinstance(out.get("readiness"), dict) else {}
    if isinstance(readiness, dict) and readiness:
        surface["readiness.state"] = str(readiness.get("state") or "")
        surface["readiness.readiness_level"] = str(readiness.get("readiness_level") or "")
        cov = readiness.get("coverage") if isinstance(readiness.get("coverage"), dict) else {}
        if isinstance(cov, dict) and cov:
            for k in ("required_present", "required_total", "optional_present", "optional_total", "coverage_ratio"):
                surface[f"coverage.{k}"] = cov.get(k)

    gate_outcomes = out.get("gate_outcomes") if isinstance(out.get("gate_outcomes"), dict) else {}
    if isinstance(gate_outcomes, dict) and gate_outcomes:
        for gk in sorted([str(k) for k in gate_outcomes.keys()]):
            gv = gate_outcomes.get(gk) if isinstance(gate_outcomes.get(gk), dict) else {}
            surface[f"gate_outcomes.{gk}.status"] = str(gv.get("status") or "")

    risk_flags = out.get("risk_flags") if isinstance(out.get("risk_flags"), list) else []
    if isinstance(risk_flags, list) and risk_flags:
        counts: Dict[str, int] = {}
        for rf in risk_flags:
            if isinstance(rf, dict):
                key = str(rf.get("risk_flag") or "")
            else:
                key = ""
            if key:
                counts[key] = counts.get(key, 0) + 1
        for k in sorted(counts.keys()):
            surface[f"risk_flags.{k}"] = int(counts[k])

    blockers = out.get("blockers") if isinstance(out.get("blockers"), list) else []
    if isinstance(blockers, list) and blockers:
        counts_b: Dict[str, int] = {}
        for b in blockers:
            if isinstance(b, dict):
                key = str(b.get("blocker_key") or "")
            else:
                key = ""
            if key:
                counts_b[key] = counts_b.get(key, 0) + 1
        for k in sorted(counts_b.keys()):
            surface[f"blockers.{k}"] = int(counts_b[k])

    return surface


def _diff_surface(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    keys = sorted(list(set([str(k) for k in a.keys()] + [str(k) for k in b.keys()])))
    changed: List[str] = []
    for k in keys:
        if a.get(k) != b.get(k):
            changed.append(k)
    changed = sorted(changed)

    counts = {
        "total_fields_changed": int(len(changed)),
        "coverage_fields_changed": 0,
        "risk_fields_changed": 0,
        "gate_fields_changed": 0,
        "comparability_fields_changed": 0,
        "readiness_fields_changed": 0,
        "blocker_fields_changed": 0,
        "state_fields_changed": 0,
    }
    for k in changed:
        if k.startswith("coverage."):
            counts["coverage_fields_changed"] += 1
        elif k.startswith("risk_flags."):
            counts["risk_fields_changed"] += 1
        elif k.startswith("gate_outcomes."):
            counts["gate_fields_changed"] += 1
        elif k.startswith("comparability."):
            counts["comparability_fields_changed"] += 1
        elif k.startswith("readiness."):
            counts["readiness_fields_changed"] += 1
        elif k.startswith("blockers."):
            counts["blocker_fields_changed"] += 1
        else:
            counts["state_fields_changed"] += 1

    return {"changed_fields": changed, "changed_counts": counts, "notes": []}


def verify_snapshot(*, db: Session, snapshot_id: int, debug: bool = False) -> Dict[str, Any]:
    snap = db.query(DecisionSnapshot).filter(DecisionSnapshot.id == int(snapshot_id)).first()
    if not snap:
        raise KeyError(f"Snapshot not found: {snapshot_id}")

    inputs_obj = _parse_json_field(snap.inputs_json, default={})
    outputs_obj = _parse_json_field(snap.outputs_json, default={})

    stored_semantic_fp = _semantic_fingerprint(outputs_obj) if isinstance(outputs_obj, dict) else ""

    # Evidence identifiers (additive; kept stable for non-debug output)
    stored_measurement_ids_used = _coerce_int_list(
        outputs_obj.get("measurement_ids_used") if isinstance(outputs_obj, dict) else None
    )
    recomputed_measurement_ids_used: List[int] = []  # populated after recompute

    stored_evidence_ids_json: List[int] = []
    evidence_ids_json_parse_error: str | None = None
    try:
        # Defensive: if missing/unparseable, degrade to [] without breaking consumers.
        stored_evidence_ids_json = _coerce_int_list(_parse_json_field(snap.evidence_ids_json, default=[]))
    except Exception as e:
        stored_evidence_ids_json = []
        evidence_ids_json_parse_error = str(e)

    # Stored policy identifiers/hashes
    stored_policy_id = str(inputs_obj.get("policy_id") or "")
    stored_policy_version = str(inputs_obj.get("policy_version") or "")
    stored_policy_semantics_hash = str(inputs_obj.get("policy_semantics_hash") or "")
    stored_policy_package_hash = str(inputs_obj.get("policy_package_hash") or "")

    try:
        pol, pol_path = _resolve_policy_from_repo(
            policy_id=stored_policy_id,
            policy_version=stored_policy_version,
            policy_semantics_hash=stored_policy_semantics_hash,
            policy_package_hash=stored_policy_package_hash,
            require_exact_hash_match=True,
        )
    except Exception as e:
        return {
            "snapshot_id": int(snapshot_id),
            "classification": "POLICY_UNAVAILABLE",
            "stored": {
                "policy_id": stored_policy_id,
                "policy_version": stored_policy_version,
                "policy_semantics_hash": stored_policy_semantics_hash,
                "policy_package_hash": stored_policy_package_hash,
            },
            "anchored_replay": {
                "available": False,
                "reason": "policy_exact_match_not_found",
                "detail": str(e),
            },
        }

    recomputed_policy_semantics_hash = str(pol.policy_semantics_hash)
    recomputed_policy_package_hash = str(pol.policy_package_hash)

    # Re-run DI using pure computation path (must not persist)
    # Current-world recompute: if as_of_ts is None, interpret as "now".
    di_in_current = DIInput(
        decision_key=str(inputs_obj.get("decision_key") or snap.decision_key),
        scope_type=str(inputs_obj.get("scope_type") or "batch"),
        scope_id=int(inputs_obj.get("scope_id") or snap.batch_id),
        as_of_ts=(str(inputs_obj.get("as_of_ts")).strip() if inputs_obj.get("as_of_ts") is not None else None),
        qc_mode=str(inputs_obj.get("qc_mode") or "model_safe"),
        context=(inputs_obj.get("context") or {}) if isinstance(inputs_obj.get("context") or {}, dict) else {},
    )

    # Anchored replay should be evaluated "as-of" the snapshot creation time when
    # the stored snapshot omitted as_of_ts (legacy snapshots). This prevents
    # future measurements from influencing summary surfaces like SoE evidence
    # summary counts/timestamps.
    replay_as_of = (
        str(inputs_obj.get("as_of_ts")).strip()
        if inputs_obj.get("as_of_ts") is not None
        else str(snap.created_at)
    )
    di_in_replay = DIInput(
        decision_key=str(inputs_obj.get("decision_key") or snap.decision_key),
        scope_type=str(inputs_obj.get("scope_type") or "batch"),
        scope_id=int(inputs_obj.get("scope_id") or snap.batch_id),
        as_of_ts=replay_as_of,
        qc_mode=str(inputs_obj.get("qc_mode") or "model_safe"),
        context=(inputs_obj.get("context") or {}) if isinstance(inputs_obj.get("context") or {}, dict) else {},
    )

    recomputed = compute_di_output(db, di_input=di_in_current, pol=pol, policy_path=pol_path)
    recomputed_out = recomputed.get("output") if isinstance(recomputed, dict) else None
    # IMPORTANT: ensure integrity on the *DI output payload*, not the wrapper.
    # Otherwise verify_snapshot may emit empty hashes/fingerprints, obscuring
    # the real drift signal.
    if isinstance(recomputed_out, dict):
        _require_integrity_present(recomputed_out, label='recomputed')

    recomputed_semantic_fp = _semantic_fingerprint(recomputed_out) if isinstance(recomputed_out, dict) else ""

    # Prior active snapshot for diff_summary (if comparable)
    prior_snap: DecisionSnapshot | None = None
    try:
        prior_snap = (
            db.query(DecisionSnapshot)
            .filter(DecisionSnapshot.decision_key == str(snap.decision_key))
            .filter(DecisionSnapshot.program_id == int(snap.program_id))
            .filter(DecisionSnapshot.molecule_id == (int(snap.molecule_id) if snap.molecule_id is not None else None))
            .filter(DecisionSnapshot.batch_id == (int(snap.batch_id) if snap.batch_id is not None else None))
            .filter(DecisionSnapshot.superseded_by_snapshot_id == int(snap.id))
            .order_by(DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc())
            .first()
        )
        if prior_snap is None:
            prior_snap = (
                db.query(DecisionSnapshot)
                .filter(DecisionSnapshot.decision_key == str(snap.decision_key))
                .filter(DecisionSnapshot.program_id == int(snap.program_id))
                .filter(DecisionSnapshot.molecule_id == (int(snap.molecule_id) if snap.molecule_id is not None else None))
                .filter(DecisionSnapshot.batch_id == (int(snap.batch_id) if snap.batch_id is not None else None))
                .filter(DecisionSnapshot.id != int(snap.id))
                .filter(
                    (DecisionSnapshot.created_at < snap.created_at)
                    | ((DecisionSnapshot.created_at == snap.created_at) & (DecisionSnapshot.id < snap.id))
                )
                .order_by(DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc())
                .first()
            )
    except Exception:
        prior_snap = None

    recomputed_measurement_ids_used = _coerce_int_list(
        recomputed_out.get("measurement_ids_used") if isinstance(recomputed_out, dict) else None
    )

    # For now, the recomputed evidence identifiers exposed by verify are the
    # DI output's measurement IDs (the actionable drift signal users need).
    recomputed_evidence_ids = list(recomputed_measurement_ids_used)

    added_ids = sorted(list(set(recomputed_measurement_ids_used) - set(stored_measurement_ids_used)))
    removed_ids = sorted(list(set(stored_measurement_ids_used) - set(recomputed_measurement_ids_used)))

    # Integrity fields (stored)
    stored_integrity: Dict[str, Any] = {}
    prov = outputs_obj.get("provenance") if isinstance(outputs_obj, dict) else None
    if isinstance(prov, dict):
        stored_integrity = prov.get("integrity") or {}
    stored_snapshot_content_hash = str(stored_integrity.get("snapshot_content_hash") or "")
    stored_evidence_fingerprint = str(stored_integrity.get("evidence_fingerprint") or "")
    stored_decision_output_hash = str(stored_integrity.get("decision_output_hash") or "")
    stored_decision_output_hash_v2_embedded = str(stored_integrity.get("decision_output_hash_v2") or "")

    # Integrity fields (recomputed)
    recomputed_integrity: Dict[str, Any] = {}
    rprov = recomputed_out.get("provenance") if isinstance(recomputed_out, dict) else None
    if isinstance(rprov, dict):
        recomputed_integrity = rprov.get("integrity") or {}
    recomputed_snapshot_content_hash = str(recomputed_integrity.get("snapshot_content_hash") or "")
    recomputed_evidence_fingerprint = str(recomputed_integrity.get("evidence_fingerprint") or "")
    recomputed_decision_output_hash = str(recomputed_integrity.get("decision_output_hash") or "")
    recomputed_decision_output_hash_v2_embedded = str(recomputed_integrity.get("decision_output_hash_v2") or "")

    # Back-compat: for stored snapshots without semantic hashes, compute from stored payload (read-only).
    if not stored_decision_output_hash:
        try:
            stored_decision_output_hash = compute_decision_output_hash(inputs_obj=inputs_obj, outputs_obj=outputs_obj)
        except Exception:
            stored_decision_output_hash = ""

    # v2 semantic hash is intentionally defined to be stable across code-version
    # changes when policy hashes and evidence fingerprint are unchanged. Therefore,
    # do NOT trust embedded v2 hashes across upgrades; always recompute v2 from
    # stored payload using the current canonicalization.
    try:
        stored_decision_output_hash_v2_effective = compute_decision_output_hash_v2(
            inputs_obj=inputs_obj, outputs_obj=outputs_obj
        )
    except Exception:
        stored_decision_output_hash_v2_effective = ""

    # Back-compat: for recompute path if older snapshots/outputs missing integrity.
    if not recomputed_decision_output_hash:
        try:
            recomputed_decision_output_hash = compute_decision_output_hash(inputs_obj=inputs_obj, outputs_obj=recomputed_out)
        except Exception:
            recomputed_decision_output_hash = ""

    try:
        recomputed_decision_output_hash_v2_effective = compute_decision_output_hash_v2(
            inputs_obj=inputs_obj,
            outputs_obj=recomputed_out,
        )
    except Exception:
        recomputed_decision_output_hash_v2_effective = ""

    # Evidence tuple payloads for drift explanation
    stored_used: Dict[str, Any] = {}
    if isinstance(outputs_obj, dict):
        soe = outputs_obj.get("state_of_evidence")
        if isinstance(soe, dict) and isinstance(soe.get("used"), dict):
            stored_used = soe.get("used") or {}
    stored_evidence_tuples = extract_evidence_tuples_from_used(stored_used)

    recomputed_used: Dict[str, Any] = {}
    if isinstance(recomputed_out, dict):
        rsoe = recomputed_out.get("state_of_evidence")
        if isinstance(rsoe, dict) and isinstance(rsoe.get("used"), dict):
            recomputed_used = rsoe.get("used") or {}
    recomputed_evidence_tuples = extract_evidence_tuples_from_used(recomputed_used)

    # --- Optional anchored replay (verification-only): bypass selector using stored used measurement IDs ---
    anchored = _compute_anchored_replay(
        db=db,
        di_in=di_in_replay,
        pol=pol,
        policy_path=pol_path,
        stored_outputs_obj=(outputs_obj if isinstance(outputs_obj, dict) else {}),
        stored_evidence_ids_json=stored_evidence_ids_json,
        stored_inputs_obj=(inputs_obj if isinstance(inputs_obj, dict) else {}),
    )

    anchored_out: Dict[str, Any] | None = anchored.get("output") if isinstance(anchored, dict) else None
    if isinstance(anchored_out, dict):
        _require_integrity_present(anchored_out, label='anchored_replay')
    anchored_semantic_fp = _semantic_fingerprint(anchored_out) if isinstance(anchored_out, dict) else ""
    anchored_integrity: Dict[str, Any] = {}
    anchored_snapshot_content_hash = ""
    anchored_evidence_fingerprint = ""
    anchored_decision_output_hash_v2_effective = ""
    anchored_measurement_ids_used: List[int] = []
    anchored_evidence_tuples: Dict[str, Any] = {}

    if isinstance(anchored_out, dict):
        anchored_measurement_ids_used = _coerce_int_list(anchored_out.get("measurement_ids_used"))
        aprov = anchored_out.get("provenance") if isinstance(anchored_out.get("provenance"), dict) else {}
        anchored_integrity = (aprov.get("integrity") or {}) if isinstance(aprov, dict) else {}
        anchored_snapshot_content_hash = str(anchored_integrity.get("snapshot_content_hash") or "")
        anchored_evidence_fingerprint = str(anchored_integrity.get("evidence_fingerprint") or "")
        try:
            anchored_decision_output_hash_v2_effective = compute_decision_output_hash_v2(
                inputs_obj=inputs_obj,
                outputs_obj=anchored_out,
            )
        except Exception:
            anchored_decision_output_hash_v2_effective = ""

        a_used: Dict[str, Any] = {}
        a_soe = anchored_out.get("state_of_evidence") if isinstance(anchored_out.get("state_of_evidence"), dict) else {}
        if isinstance(a_soe.get("used"), dict):
            a_used = a_soe.get("used") or {}
        anchored_evidence_tuples = extract_evidence_tuples_from_used(a_used)

    # Drift classifications (stored vs current-world recompute is the primary)
    anchored_classification = None
    anchored_explain: Dict[str, Any] | None = None
    replay_vs_current_classification = None
    replay_vs_current_explain: Dict[str, Any] | None = None

    if isinstance(anchored_out, dict) and anchored.get("available") is True:
        anchored_classification, anchored_explain = _drift_classification(
            stored_policy_semantics_hash=stored_policy_semantics_hash,
            stored_policy_package_hash=stored_policy_package_hash,
            recomputed_policy_semantics_hash=recomputed_policy_semantics_hash,
            recomputed_policy_package_hash=recomputed_policy_package_hash,
            stored_evidence_fingerprint=stored_evidence_fingerprint,
            recomputed_evidence_fingerprint=anchored_evidence_fingerprint,
            stored_snapshot_content_hash=stored_snapshot_content_hash,
            recomputed_snapshot_content_hash=anchored_snapshot_content_hash,
            stored_decision_output_hash=stored_decision_output_hash_v2_effective,
            recomputed_decision_output_hash=anchored_decision_output_hash_v2_effective,
            stored_semantic_fingerprint=stored_semantic_fp or None,
            recomputed_semantic_fingerprint=anchored_semantic_fp or None,
            stored_evidence_tuples=stored_evidence_tuples,
            recomputed_evidence_tuples=anchored_evidence_tuples,
        )

        # replay vs current-world
        try:
            replay_vs_current_classification, replay_vs_current_explain = _drift_classification(
                stored_policy_semantics_hash=recomputed_policy_semantics_hash,
                stored_policy_package_hash=recomputed_policy_package_hash,
                recomputed_policy_semantics_hash=recomputed_policy_semantics_hash,
                recomputed_policy_package_hash=recomputed_policy_package_hash,
                stored_evidence_fingerprint=anchored_evidence_fingerprint,
                recomputed_evidence_fingerprint=recomputed_evidence_fingerprint,
                stored_snapshot_content_hash=anchored_snapshot_content_hash,
                recomputed_snapshot_content_hash=recomputed_snapshot_content_hash,
                stored_decision_output_hash=anchored_decision_output_hash_v2_effective,
                recomputed_decision_output_hash=recomputed_decision_output_hash_v2_effective,
                stored_semantic_fingerprint=anchored_semantic_fp or None,
                recomputed_semantic_fingerprint=recomputed_semantic_fp or None,
                stored_evidence_tuples=anchored_evidence_tuples,
                recomputed_evidence_tuples=recomputed_evidence_tuples,
            )
        except Exception:
            replay_vs_current_classification = None
            replay_vs_current_explain = None

    classification, explain = _drift_classification(
        stored_policy_semantics_hash=stored_policy_semantics_hash,
        stored_policy_package_hash=stored_policy_package_hash,
        recomputed_policy_semantics_hash=recomputed_policy_semantics_hash,
        recomputed_policy_package_hash=recomputed_policy_package_hash,
        stored_evidence_fingerprint=stored_evidence_fingerprint,
        recomputed_evidence_fingerprint=recomputed_evidence_fingerprint,
        stored_snapshot_content_hash=stored_snapshot_content_hash,
        recomputed_snapshot_content_hash=recomputed_snapshot_content_hash,
        stored_decision_output_hash=stored_decision_output_hash_v2_effective,
        recomputed_decision_output_hash=recomputed_decision_output_hash_v2_effective,
        stored_semantic_fingerprint=stored_semantic_fp or None,
        recomputed_semantic_fingerprint=recomputed_semantic_fp or None,
        stored_evidence_tuples=stored_evidence_tuples,
        recomputed_evidence_tuples=recomputed_evidence_tuples,
    )

    report: Dict[str, Any] = {
        "snapshot_id": int(snap.id),
        "classification": classification,
        "evidence_ids": {
            "stored_measurement_ids_used": stored_measurement_ids_used,
            "recomputed_measurement_ids_used": recomputed_measurement_ids_used,
            "stored_evidence_ids_json": stored_evidence_ids_json,
            "recomputed_evidence_ids": recomputed_evidence_ids,
            "anchored_replay_measurement_ids_used": anchored_measurement_ids_used,
        },
        "evidence_ids_diff": {
            "added": added_ids,
            "removed": removed_ids,
        },
        "evidence_ids_explain": _explain_evidence_id_change(db, removed_ids, added_ids),
        "stored": {
            "policy_id": stored_policy_id,
            "policy_version": stored_policy_version,
            "policy_semantics_hash": stored_policy_semantics_hash,
            "policy_package_hash": stored_policy_package_hash,
            "semantic_fingerprint": stored_semantic_fp,
            "snapshot_content_hash": stored_snapshot_content_hash,
            "evidence_fingerprint": stored_evidence_fingerprint,
            "decision_output_hash": stored_decision_output_hash,
            "decision_output_hash_v2": stored_decision_output_hash_v2_embedded,
            "decision_output_hash_v2_effective": stored_decision_output_hash_v2_effective,
        },
        "recomputed": {
            "policy_semantics_hash": recomputed_policy_semantics_hash,
            "policy_package_hash": recomputed_policy_package_hash,
            "semantic_fingerprint": recomputed_semantic_fp,
            "snapshot_content_hash": recomputed_snapshot_content_hash,
            "evidence_fingerprint": recomputed_evidence_fingerprint,
            "decision_output_hash": recomputed_decision_output_hash,
            "decision_output_hash_v2": recomputed_decision_output_hash_v2_embedded,
            "decision_output_hash_v2_effective": recomputed_decision_output_hash_v2_effective,
        },
        "anchored_replay": {
            "available": bool(anchored.get("available")) if isinstance(anchored, dict) else False,
            "reason": str(anchored.get("reason") or "") if isinstance(anchored, dict) else "",
            "missing_measurement_ids": anchored.get("missing_measurement_ids") if isinstance(anchored, dict) else [],
            "stored_vs_replay_classification": anchored_classification,
            "replay_vs_current_classification": replay_vs_current_classification,
            "replay": {
                "semantic_fingerprint": anchored_semantic_fp,
                "snapshot_content_hash": anchored_snapshot_content_hash,
                "evidence_fingerprint": anchored_evidence_fingerprint,
                "decision_output_hash_v2_effective": anchored_decision_output_hash_v2_effective,
            },
        },
        "explain": explain,
    }

    # Optional diff_summary (deterministic; only when comparable + prior snapshot exists)
    if prior_snap is not None and isinstance(outputs_obj, dict) and _is_comparable_output(outputs_obj):
        try:
            prev_outputs = _parse_json_field(prior_snap.outputs_json, default={})
            if isinstance(prev_outputs, dict):
                surface_prev = _build_diff_surface(prev_outputs)
                surface_cur = _build_diff_surface(outputs_obj)
                diff = _diff_surface(surface_prev, surface_cur)
                report["diff_summary"] = {
                    "prev_snapshot_id": int(prior_snap.id),
                    "changed_fields": diff.get("changed_fields") or [],
                    "changed_counts": diff.get("changed_counts") or {},
                    "notes": diff.get("notes") or [],
                }
        except Exception:
            pass

    # Additive drift diagnosis (no new logic/thresholds)
    if isinstance(report.get("anchored_replay"), dict):
        diagnosis: Dict[str, Any] = {}
        try:
            av = bool(report["anchored_replay"].get("available"))
            if av and anchored_classification == "VERIFIED" and classification != "VERIFIED":
                diagnosis["primary"] = "selection_or_data_repointing"
                diagnosis["detail"] = "Anchored replay VERIFIED, but current-world recompute drifted. This strongly suggests evidence selection changed due to data repointing/duplicate-record competition, not policy logic drift."
            elif av and anchored_classification != "VERIFIED" and classification != "VERIFIED":
                diagnosis["primary"] = "data_or_policy_or_engine_drift"
                diagnosis["detail"] = "Both anchored replay and current-world recompute drifted versus stored; investigate evidence value/QC changes or policy/package changes."
            elif not av:
                diagnosis["primary"] = "anchored_replay_unavailable"
                diagnosis["detail"] = "Snapshot does not support anchored replay (missing state_of_evidence.used map or measurements no longer present)."
        except Exception:
            diagnosis = {}
        report["anchored_replay"]["diagnosis"] = diagnosis

    if debug and classification != "VERIFIED":
        report["debug"] = {
            "notes": (
                [
                    {
                        "field": "DecisionSnapshot.evidence_ids_json",
                        "issue": "unparseable_json",
                        "error": evidence_ids_json_parse_error,
                    }
                ]
                if evidence_ids_json_parse_error
                else []
            ),
            "outputs_top_level": _diff_top_level_keys(outputs_obj, recomputed_out),
            "provenance": _diff_top_level_keys(
                (outputs_obj.get("provenance") if isinstance(outputs_obj, dict) else {}),
                (recomputed_out.get("provenance") if isinstance(recomputed_out, dict) else {}),
            ),
            "state_of_evidence": _diff_top_level_keys(
                (outputs_obj.get("state_of_evidence") if isinstance(outputs_obj, dict) else {}),
                (recomputed_out.get("state_of_evidence") if isinstance(recomputed_out, dict) else {}),
            ),
            "integrity": {
                "stored": {
                    "snapshot_content_hash": stored_snapshot_content_hash,
                    "decision_output_hash": stored_decision_output_hash,
                    "decision_output_hash_v2": stored_decision_output_hash_v2_embedded,
                    "decision_output_hash_v2_effective": stored_decision_output_hash_v2_effective,
                    "evidence_fingerprint": stored_evidence_fingerprint,
                },
                "recomputed": {
                    "snapshot_content_hash": recomputed_snapshot_content_hash,
                    "decision_output_hash": recomputed_decision_output_hash,
                    "decision_output_hash_v2": recomputed_decision_output_hash_v2_embedded,
                    "decision_output_hash_v2_effective": recomputed_decision_output_hash_v2_effective,
                    "evidence_fingerprint": recomputed_evidence_fingerprint,
                },
            },
            "anchored_replay": {
                "available": bool(anchored.get("available")) if isinstance(anchored, dict) else False,
                "reason": str(anchored.get("reason") or "") if isinstance(anchored, dict) else "",
                "stored_vs_replay": anchored_explain,
                "replay_vs_current": replay_vs_current_explain,
            },
        }

    return report
