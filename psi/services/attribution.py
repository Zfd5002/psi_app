from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from psi.core.models import Actor, AttributionEvent
from psi.core.utils import json_dumps_compact, now_utc


def _get_or_create_local_actor(db: Session, *, handle: str = "local-user") -> Actor:
    actor = db.query(Actor).filter(Actor.handle == handle).one_or_none()
    if actor is not None:
        return actor
    actor = Actor(display_name="Local User", handle=handle, created_at=now_utc())
    db.add(actor)
    db.flush()
    return actor


def record_attribution_event(
    db: Session,
    *,
    event_type: str,
    entity_type: str,
    entity_id: int,
    metadata: dict[str, Any] | None = None,
    actor_handle: str = "local-user",
) -> AttributionEvent:
    actor = _get_or_create_local_actor(db, handle=actor_handle)
    ev = AttributionEvent(
        actor_id=int(actor.id),
        event_type=str(event_type),
        entity_type=str(entity_type),
        entity_id=int(entity_id),
        metadata_json=(json_dumps_compact(metadata or {}) if metadata is not None else None),
        created_at=now_utc(),
    )
    db.add(ev)
    return ev
