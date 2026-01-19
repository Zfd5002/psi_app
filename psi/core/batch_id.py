from __future__ import annotations

import re
from sqlalchemy.orm import Session

from .models import Batch, Molecule

BATCH_SUFFIX_RE = re.compile(r"^(?P<prefix>.+?)-(?P<num>\d{3})$")


def next_batch_id(db: Session, molecule: Molecule) -> str:
    """Auto-increment batch id: <molecule.primary_id>-001, -002, ..."""
    prefix = molecule.primary_id
    existing = (
        db.query(Batch)
        .filter(Batch.molecule_id == molecule.id)
        .all()
    )
    max_n = 0
    for b in existing:
        m = BATCH_SUFFIX_RE.match(b.batch_id or "")
        if m and m.group("prefix") == prefix:
            try:
                max_n = max(max_n, int(m.group("num")))
            except ValueError:
                pass
    return f"{prefix}-{max_n + 1:03d}"
