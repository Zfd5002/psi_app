from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def apply_board_filters(
    board: dict,
    *,
    q: str | None = None,
    owner: str | None = None,
    urgency: str | None = None,
    status: str | None = None,
    due: str | None = None,
) -> dict:
    groups = board.get("groups") if isinstance(board, dict) else {}
    if not isinstance(groups, dict):
        return board

    q_filter = str(q or "").strip().lower()
    owner_filter = str(owner or "").strip().lower()
    urgency_filter = str(urgency or "").strip().lower()
    status_filter = str(status or "").strip().lower()
    due_filter = str(due or "").strip().lower()

    if urgency_filter not in {"", "critical", "high", "normal", "low"}:
        urgency_filter = ""
    if status_filter not in {"", "planned", "in_progress", "blocked", "done", "open"}:
        status_filter = ""
    if due_filter not in {"", "overdue", "due_soon"}:
        due_filter = ""

    def _due_match(row: dict[str, Any]) -> bool:
        if not due_filter:
            return True
        raw = str(row.get("top_task_due_date") or "").strip()
        if not raw:
            return False
        try:
            d = date.fromisoformat(raw)
        except Exception:
            return False
        today = date.today()
        if due_filter == "overdue":
            return d < today
        if due_filter == "due_soon":
            return today <= d <= (today + timedelta(days=7))
        return True

    def _task_row_match(row: dict[str, Any]) -> bool:
        if q_filter and q_filter not in str(row.get("primary_id") or "").lower():
            return False
        if owner_filter and owner_filter not in str(row.get("top_task_owner_text") or "").lower():
            return False
        if urgency_filter and urgency_filter != str(row.get("top_task_urgency") or "").lower():
            return False
        if status_filter:
            if status_filter == "open":
                if int(row.get("open_task_count") or 0) <= 0:
                    return False
            elif status_filter != str(row.get("top_task_status") or "").lower():
                return False
        if not _due_match(row):
            return False
        return True

    filtered_groups = {
        k: [
            row
            for row in (groups.get(k) or [])
            if isinstance(row, dict) and _task_row_match(row)
        ]
        for k in ("ready", "failed", "missing_data", "not_evaluated")
    }
    return {**board, "groups": filtered_groups}
