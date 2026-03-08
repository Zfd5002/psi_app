from __future__ import annotations

from datetime import date, timedelta

from psi.services import program_board as svc


def _mk_board() -> dict:
    today = date.today()
    return {
        "groups": {
            "ready": [
                {
                    "primary_id": "M-A",
                    "top_task_owner_text": "Dr A",
                    "top_task_urgency": "high",
                    "top_task_status": "planned",
                    "top_task_due_date": str(today + timedelta(days=2)),
                    "open_task_count": 1,
                }
            ],
            "failed": [
                {
                    "primary_id": "M-B",
                    "top_task_owner_text": "Dr B",
                    "top_task_urgency": "critical",
                    "top_task_status": "blocked",
                    "top_task_due_date": str(today - timedelta(days=1)),
                    "open_task_count": 2,
                }
            ],
            "missing_data": [
                {
                    "primary_id": "M-C",
                    "top_task_owner_text": "",
                    "top_task_urgency": "normal",
                    "top_task_status": "",
                    "top_task_due_date": "",
                    "open_task_count": 0,
                }
            ],
            "not_evaluated": [],
        }
    }


def _flatten_ids(board: dict) -> list[str]:
    out: list[str] = []
    for grp in ("ready", "failed", "missing_data", "not_evaluated"):
        for row in (board.get("groups", {}).get(grp) or []):
            out.append(str(row.get("primary_id") or ""))
    return out


def test_apply_board_filters_owner_and_status() -> None:
    board = _mk_board()
    out = svc.apply_board_filters(board, owner="dr b", status="blocked")
    assert _flatten_ids(out) == ["M-B"]


def test_apply_board_filters_due_windows() -> None:
    board = _mk_board()
    due_soon = svc.apply_board_filters(board, due="due_soon")
    assert _flatten_ids(due_soon) == ["M-A"]

    overdue = svc.apply_board_filters(board, due="overdue")
    assert _flatten_ids(overdue) == ["M-B"]


def test_apply_board_filters_open_status() -> None:
    board = _mk_board()
    out = svc.apply_board_filters(board, status="open")
    assert _flatten_ids(out) == ["M-A", "M-B"]
