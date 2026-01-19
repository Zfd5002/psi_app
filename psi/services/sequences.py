from __future__ import annotations

from hashlib import sha256
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from psi.core.fasta import normalize_aa_sequence
from psi.core.models import SequenceEntity
from psi.core.utils import now_utc


def sha256_hex(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def get_or_create_sequence_entity(db: Session, seq: str) -> Optional[SequenceEntity]:
    s = normalize_aa_sequence(seq)
    if not s:
        return None
    h = sha256_hex(s)
    existing = db.execute(select(SequenceEntity).where(SequenceEntity.sha256 == h)).scalar_one_or_none()
    if existing:
        return existing
    ent = SequenceEntity(
        sha256=h,
        sequence_norm=s,
        length=len(s),
        alphabet="AA",
        created_at=now_utc(),
    )
    db.add(ent)
    db.commit()
    db.refresh(ent)
    return ent