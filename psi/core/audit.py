from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from .models import AuditEvent
from .utils import diff_json, json_dumps_compact, now_utc


def record_audit(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    action: str,
    before: Optional[dict[str, Any]] = None,
    after: Optional[dict[str, Any]] = None,
    reason: Optional[str] = None,
    actor: str = "local-user",
) -> AuditEvent:
    """Record an immutable audit event.

    Callers are expected to commit the session.
    """

    ev = AuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        timestamp=now_utc(),
        before_json=json_dumps_compact(before) if before is not None else None,
        after_json=json_dumps_compact(after) if after is not None else None,
        diff_json=(
            json_dumps_compact(diff_json(before, after))
            if before is not None and after is not None
            else None
        ),
        reason=reason,
    )
    db.add(ev)
    return ev
