from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode


@dataclass(frozen=True)
class HandoffContext:
    source: str = ""
    task_id: int | None = None
    return_to: str = ""
    captured: bool = False
    updated: bool = False
    next_step: str = ""
    from_task: bool = False


def _as_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _as_int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(value)
    except Exception:
        return None


def parse_handoff_context(query_like: Any) -> HandoffContext:
    getter = query_like.get if hasattr(query_like, "get") else lambda _k, _d=None: _d
    source = str(getter("source", "") or "").strip().lower()
    return HandoffContext(
        source=source,
        task_id=_as_int(getter("task_id", None)),
        return_to=str(getter("return_to", "") or "").strip(),
        captured=_as_bool(getter("captured", "")),
        updated=_as_bool(getter("updated", "")),
        next_step=str(getter("next", "") or "").strip().lower(),
        from_task=_as_bool(getter("from_task", "")),
    )


def get_handoff_context(request: Any) -> HandoffContext:
    query = getattr(request, "query_params", {}) or {}
    return parse_handoff_context(query)


def build_handoff_query(
    *,
    source: str = "",
    task_id: int | None = None,
    return_to: str = "",
    captured: bool = False,
    updated: bool = False,
    next_step: str = "",
    from_task: bool = False,
) -> dict[str, str]:
    q: dict[str, str] = {}
    if str(source or "").strip():
        q["source"] = str(source).strip().lower()
    if task_id is not None:
        q["task_id"] = str(int(task_id))
    if str(return_to or "").strip():
        q["return_to"] = str(return_to).strip()
    if captured:
        q["captured"] = "1"
    if updated:
        q["updated"] = "1"
    if str(next_step or "").strip():
        q["next"] = str(next_step).strip().lower()
    if from_task:
        q["from_task"] = "1"
    return q


def with_query(path: str, query: dict[str, Any]) -> str:
    clean = {str(k): str(v) for k, v in query.items() if str(v) != ""}
    if not clean:
        return str(path)
    return f"{path}?{urlencode(clean)}"


def build_return_url(
    path: str,
    *,
    source: str = "",
    task_id: int | None = None,
    return_to: str = "",
    captured: bool = False,
    updated: bool = False,
    next_step: str = "",
    from_task: bool = False,
) -> str:
    return with_query(
        path,
        build_handoff_query(
            source=source,
            task_id=task_id,
            return_to=return_to,
            captured=captured,
            updated=updated,
            next_step=next_step,
            from_task=from_task,
        ),
    )

