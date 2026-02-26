from __future__ import annotations

import re

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from psi.core.fasta import normalize_aa_sequence, sha256_text
from psi.core.models import SequenceEntity
from psi.core.utils import now_utc


def _next_chain_id(db: Session) -> str:
    """Allocate next CHAINXXX id (local-first, monotonic best-effort)."""
    rows = db.query(SequenceEntity.chain_id).filter(SequenceEntity.chain_id.isnot(None)).all()
    mx = 0
    for (cid,) in rows:
        if not cid:
            continue
        m = re.match(r'^CHAIN(\d+)$', cid)
        if m:
            mx = max(mx, int(m.group(1)))
    return f"CHAIN{mx+1:03d}"


def _id_allocation_retry_exhausted(kind: str, attempts: int, err: IntegrityError, *, last_candidate: str | None = None) -> RuntimeError:
    suffix = f" Last attempted value: {last_candidate}." if str(last_candidate or "").strip() else ""
    return RuntimeError(
        f"Could not allocate a unique {kind} after {attempts} attempts due to a concurrent write. "
        f"Please retry.{suffix}"
    )


def get_or_create_chain(
    db: Session,
    sequence_text: str,
    *,
    type_hint: str | None = None,
    notes: str | None = None,
) -> SequenceEntity:
    """Global chain registry: de-dupe by sha256(sequence_norm) and ensure CHAINXXX."""
    seq = normalize_aa_sequence(sequence_text or "")
    if not seq:
        raise ValueError("Empty sequence")

    h = sha256_text(seq)
    ent = db.query(SequenceEntity).filter(SequenceEntity.sha256 == h).first()

    if ent is None:
        max_attempts = 3
        for attempt in range(max_attempts):
            ent = SequenceEntity(
                sha256=h,
                sequence_norm=seq,
                length=len(seq),
                alphabet="AA",
                created_at=now_utc(),
            )
            ent.chain_id = _next_chain_id(db)
            if type_hint:
                ent.type_hint = type_hint
            if notes:
                ent.notes = notes
            db.add(ent)
            try:
                db.flush()
                return ent
            except IntegrityError as exc:
                db.rollback()
                if attempt == max_attempts - 1:
                    raise _id_allocation_retry_exhausted("chain ID", max_attempts, exc) from exc
                ent = db.query(SequenceEntity).filter(SequenceEntity.sha256 == h).first()
                if ent is not None:
                    break

    if not ent.chain_id:
        max_attempts = 3
        for attempt in range(max_attempts):
            ent.chain_id = _next_chain_id(db)
            db.add(ent)
            try:
                db.flush()
                break
            except IntegrityError as exc:
                db.rollback()
                if attempt == max_attempts - 1:
                    raise _id_allocation_retry_exhausted("chain ID", max_attempts, exc) from exc

    if type_hint and not ent.type_hint:
        ent.type_hint = type_hint
        db.add(ent)
    if notes and not ent.notes:
        ent.notes = notes
        db.add(ent)

    db.flush()
    return ent


def _canonical_composition(chain_by_role: dict[str, str | None]) -> dict[str, str | None]:
    order = ['HC1','HC2','LC1','LC2']
    return {k: chain_by_role.get(k) for k in order}


def composition_sha256(chain_by_role: dict[str, str | None]) -> str:
    import json as _json
    canonical = _canonical_composition(chain_by_role)
    payload = _json.dumps(canonical, sort_keys=True, separators=(',', ':'))
    return sha256_text(payload)

