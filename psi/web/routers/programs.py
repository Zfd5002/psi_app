from __future__ import annotations

from datetime import date, timedelta

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from psi.core.models import Molecule
from psi.web.deps import get_db, get_templates
from psi.services import programs as svc
from psi.services import data_records as data_records_svc
from psi.services import dev_board as dev_board_svc
from psi.services import experiment_tasks as experiment_tasks_svc
from psi.services import narratives as narratives_svc

router = APIRouter()


@router.get("/programs", response_class=HTMLResponse)
def list_programs(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    return templates.TemplateResponse("programs/list.html", {"request": request, "programs": svc.list_programs(db)})


@router.get("/programs/new", response_class=HTMLResponse)
def new_program(request: Request):
    templates = get_templates(request)
    return templates.TemplateResponse("programs/form.html", {"request": request, "program": None})


@router.post("/programs/new")
def create_program(
    name: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    p = svc.create_program(db, name=name, description=description)
    return RedirectResponse(url=f"/programs/{p.id}", status_code=303)


@router.get("/programs/{program_id}", response_class=HTMLResponse)
def program_detail(program_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    try:
        pol_filter = request.query_params.get("policy_version")
        verify_lineage = str(request.query_params.get("verify") or "").strip() == "1"
        ctx = svc.get_program_detail(
            db,
            program_id,
            policy_version_filter=(pol_filter or None),
            verify_lineage=verify_lineage,
        )
    except KeyError:
        raise HTTPException(404)
    ctx["request"] = request
    return templates.TemplateResponse("programs/detail.html", ctx)


@router.get("/programs/{program_id}/narrative", response_class=HTMLResponse)
def program_narrative_detail(program_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    p = svc.get_program(db, int(program_id))
    if p is None:
        raise HTTPException(404)
    narrative = narratives_svc.build_program_narrative(db, program_id=int(program_id))
    q = getattr(request, "query_params", {}) or {}
    brief = str((q.get("view") if hasattr(q, "get") else "") or "").strip().lower() == "brief"
    return templates.TemplateResponse(
        "programs/narrative.html",
        {
            "request": request,
            "program": p,
            "narrative": narrative,
            "narrative_brief": brief,
        },
    )


@router.get("/programs/{program_id}/narrative/export")
def program_narrative_export(program_id: int, db: Session = Depends(get_db)):
    p = svc.get_program(db, int(program_id))
    if p is None:
        raise HTTPException(404)
    n = narratives_svc.build_program_narrative(db, program_id=int(program_id))
    lines = [
        f"Program Narrative Export: {str(p.name or '')}",
        f"Scientific thesis: {str(n.get('scientific_thesis') or '')}",
        f"Current state: {str(n.get('current_state_summary') or '')}",
        f"Next milestone: {str(n.get('next_milestone') or '')}",
        f"Milestone rationale: {str(n.get('milestone_rationale') or '')}",
        f"Overall stage: {str(n.get('overall_stage') or '')}",
        f"Confidence summary: {str(n.get('confidence_summary') or '')}",
    ]
    return Response(
        content="\\n".join(lines) + "\\n",
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="program_{int(program_id)}_narrative.txt"'},
    )


@router.get("/programs/{program_id}/board", response_class=HTMLResponse)
def program_development_board(program_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    program = svc.get_program(db, int(program_id))
    if not program:
        raise HTTPException(404)
    board = dev_board_svc.build_development_board(db, program_id=int(program_id))
    board_filter = str(request.query_params.get("filter") or "all").strip().lower()
    allowed = {"all", "ready", "failed", "missing"}
    if board_filter not in allowed:
        board_filter = "all"
    if board_filter != "all":
        filt_map = {"ready": "ready", "failed": "failed", "missing": "missing_data"}
        keep = filt_map.get(board_filter, "")
        groups = board.get("groups") if isinstance(board, dict) else {}
        if isinstance(groups, dict):
            board = {
                **board,
                "groups": {
                    "ready": list(groups.get("ready") or []) if keep == "ready" else [],
                    "failed": list(groups.get("failed") or []) if keep == "failed" else [],
                    "missing_data": list(groups.get("missing_data") or []) if keep == "missing_data" else [],
                    "not_evaluated": [],
                },
            }
    q = str(request.query_params.get("q") or "").strip().lower()
    owner_filter = str(request.query_params.get("owner") or "").strip().lower()
    urgency_filter = str(request.query_params.get("urgency") or "").strip().lower()
    status_filter = str(request.query_params.get("task_status") or "").strip().lower()
    due_filter = str(request.query_params.get("due") or "").strip().lower()
    if urgency_filter not in {"", "critical", "high", "normal", "low"}:
        urgency_filter = ""
    if status_filter not in {"", "planned", "in_progress", "blocked", "done", "open"}:
        status_filter = ""
    if due_filter not in {"", "overdue", "due_soon"}:
        due_filter = ""

    def _due_match(row: dict) -> bool:
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

    def _task_row_match(row: dict) -> bool:
        if q and q not in str(row.get("primary_id") or "").lower():
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

    if q:
        groups = board.get("groups") if isinstance(board, dict) else {}
        if isinstance(groups, dict):
            board = {
                **board,
                "groups": {
                    k: [
                        row
                        for row in (groups.get(k) or [])
                        if isinstance(row, dict) and _task_row_match(row)
                    ]
                    for k in ("ready", "failed", "missing_data", "not_evaluated")
                },
            }
    elif owner_filter or urgency_filter or status_filter or due_filter:
        groups = board.get("groups") if isinstance(board, dict) else {}
        if isinstance(groups, dict):
            board = {
                **board,
                "groups": {
                    k: [row for row in (groups.get(k) or []) if isinstance(row, dict) and _task_row_match(row)]
                    for k in ("ready", "failed", "missing_data", "not_evaluated")
                },
            }
    return templates.TemplateResponse(
        "programs/board.html",
        {
            "request": request,
            "program": program,
            "board": board,
            "board_filter": board_filter,
            "board_query": q,
            "board_owner_filter": owner_filter,
            "board_urgency_filter": urgency_filter,
            "board_task_status_filter": status_filter,
            "board_due_filter": due_filter,
        },
    )


@router.get("/programs/{program_id}/edit", response_class=HTMLResponse)
def edit_program(program_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    p = svc.get_program(db, program_id)
    if not p:
        raise HTTPException(404)
    return templates.TemplateResponse("programs/form.html", {"request": request, "program": p})


@router.post("/programs/{program_id}/edit")
def update_program(
    program_id: int,
    name: str = Form(...),
    description: str = Form(""),
    reason: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        p = svc.update_program(db, program_id=program_id, name=name, description=description, reason=reason)
    except KeyError:
        raise HTTPException(404)
    return RedirectResponse(url=f"/programs/{p.id}", status_code=303)


@router.post("/programs/{program_id}/memberships/add")
def add_program_membership(
    program_id: int,
    molecule_id: int = Form(...),
    sort_index: int = Form(0),
    db: Session = Depends(get_db),
):
    try:
        svc.add_program_membership(db, program_id=program_id, molecule_id=molecule_id, sort_index=sort_index)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RedirectResponse(url=f"/programs/{program_id}", status_code=303)


@router.post("/programs/{program_id}/memberships/{membership_id}/sort")
def update_program_membership_sort(
    program_id: int,
    membership_id: int,
    sort_index: int = Form(...),
    db: Session = Depends(get_db),
):
    try:
        svc.update_program_membership(db, membership_id=membership_id, sort_index=sort_index)
    except KeyError:
        raise HTTPException(404)
    return RedirectResponse(url=f"/programs/{program_id}", status_code=303)


@router.post("/programs/{program_id}/memberships/{membership_id}/remove")
def remove_program_membership(
    program_id: int,
    membership_id: int,
    db: Session = Depends(get_db),
):
    try:
        svc.remove_program_membership(db, membership_id=membership_id)
    except KeyError:
        raise HTTPException(404)
    return RedirectResponse(url=f"/programs/{program_id}", status_code=303)


@router.post("/programs/{program_id}/molecules/{molecule_id}/role")
def update_program_molecule_role(
    program_id: int,
    molecule_id: int,
    role: str = Form("active"),
    rationale: str = Form(""),
    db: Session = Depends(get_db),
):
    p = svc.get_program(db, program_id)
    if not p:
        raise HTTPException(404)
    m = db.get(Molecule, int(molecule_id))
    if m is None:
        raise HTTPException(404)
    if int(m.program_id) != int(program_id):
        raise HTTPException(status_code=400, detail="molecule_not_in_program")
    svc.upsert_program_molecule_status(
        db,
        program_id=int(program_id),
        molecule_id=int(molecule_id),
        role=role,
        rationale=rationale,
    )
    return RedirectResponse(url=f"/programs/{program_id}", status_code=303)


@router.post("/programs/{program_id}/review/approve-all", name="program_review_approve_all")
def program_review_approve_all(
    program_id: int,
    actor: str = Form("scientist"),
    db: Session = Depends(get_db),
):
    p = svc.get_program(db, program_id)
    if not p:
        raise HTTPException(404)
    queue = svc.build_program_review_queue(db, program_id=program_id)
    record_ids = sorted(
        {
            int(row.get("record_id"))
            for group in queue
            for row in (group.get("records") or [])
            if isinstance(row, dict) and row.get("record_id") is not None
        }
    )
    for rid in record_ids:
        data_records_svc.apply_bulk_qc_action_for_record(
            db,
            record_id=int(rid),
            action="approve",
            actor=(actor or "scientist"),
            note=None,
        )
    return RedirectResponse(url=f"/programs/{program_id}", status_code=303)


@router.post("/programs/{program_id}/review/reject-all", name="program_review_reject_all")
def program_review_reject_all(
    program_id: int,
    actor: str = Form("scientist"),
    db: Session = Depends(get_db),
):
    p = svc.get_program(db, program_id)
    if not p:
        raise HTTPException(404)
    queue = svc.build_program_review_queue(db, program_id=program_id)
    record_ids = sorted(
        {
            int(row.get("record_id"))
            for group in queue
            for row in (group.get("records") or [])
            if isinstance(row, dict) and row.get("record_id") is not None
        }
    )
    for rid in record_ids:
        data_records_svc.apply_bulk_qc_action_for_record(
            db,
            record_id=int(rid),
            action="reject",
            actor=(actor or "scientist"),
            note=None,
        )
    return RedirectResponse(url=f"/programs/{program_id}", status_code=303)


@router.post("/programs/{program_id}/tasks/create")
def create_experiment_task(
    program_id: int,
    molecule_id: int = Form(...),
    metric_key: str = Form(""),
    suggested_assay: str = Form(""),
    owner_text: str = Form(""),
    due_date: str = Form(""),
    urgency: str = Form("normal"),
    source_kind: str = Form("manual"),
    source_snapshot_id: int | None = Form(None),
    notes: str = Form(""),
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
):
    p = svc.get_program(db, int(program_id))
    if not p:
        raise HTTPException(404)
    m = db.get(Molecule, int(molecule_id))
    if m is None:
        raise HTTPException(404)
    if int(m.program_id) != int(program_id):
        raise HTTPException(status_code=400, detail="molecule_not_in_program")
    experiment_tasks_svc.create_experiment_task(
        db,
        program_id=int(program_id),
        molecule_id=int(molecule_id),
        metric_key=metric_key,
        suggested_assay=suggested_assay,
        owner_text=owner_text,
        due_date=due_date,
        urgency=urgency,
        source_kind=source_kind,
        source_snapshot_id=source_snapshot_id,
        notes=notes,
    )
    target = str(redirect_to or "").strip() or f"/programs/{program_id}/board"
    return RedirectResponse(url=target, status_code=303)


@router.post("/programs/{program_id}/tasks/{task_id}/status")
def update_experiment_task_status(
    program_id: int,
    task_id: int,
    status: str = Form(...),
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        task = experiment_tasks_svc.update_task_status(db, task_id=int(task_id), status=status)
    except KeyError:
        raise HTTPException(404)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if int(task.program_id) != int(program_id):
        raise HTTPException(status_code=400, detail="task_not_in_program")
    target = str(redirect_to or "").strip() or f"/programs/{program_id}/board"
    return RedirectResponse(url=target, status_code=303)


@router.post("/programs/{program_id}/tasks/{task_id}/start")
def start_experiment_task(
    program_id: int,
    task_id: int,
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
):
    return update_experiment_task_status(
        program_id=program_id,
        task_id=task_id,
        status="in_progress",
        redirect_to=redirect_to,
        db=db,
    )


@router.post("/programs/{program_id}/tasks/{task_id}/block")
def block_experiment_task(
    program_id: int,
    task_id: int,
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
):
    return update_experiment_task_status(
        program_id=program_id,
        task_id=task_id,
        status="blocked",
        redirect_to=redirect_to,
        db=db,
    )


@router.post("/programs/{program_id}/tasks/{task_id}/done")
def complete_experiment_task(
    program_id: int,
    task_id: int,
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
):
    return update_experiment_task_status(
        program_id=program_id,
        task_id=task_id,
        status="done",
        redirect_to=redirect_to,
        db=db,
    )


@router.post("/programs/{program_id}/tasks/{task_id}/owner")
def update_experiment_task_owner(
    program_id: int,
    task_id: int,
    owner_text: str = Form(""),
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        task = experiment_tasks_svc.assign_task_owner(db, task_id=int(task_id), owner_text=owner_text)
    except KeyError:
        raise HTTPException(404)
    if int(task.program_id) != int(program_id):
        raise HTTPException(status_code=400, detail="task_not_in_program")
    target = str(redirect_to or "").strip() or f"/programs/{program_id}/board"
    return RedirectResponse(url=target, status_code=303)


@router.post("/programs/{program_id}/tasks/{task_id}/due-date")
def update_experiment_task_due_date(
    program_id: int,
    task_id: int,
    due_date: str = Form(""),
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        task = experiment_tasks_svc.set_task_due_date(db, task_id=int(task_id), due_date=due_date)
    except KeyError:
        raise HTTPException(404)
    if int(task.program_id) != int(program_id):
        raise HTTPException(status_code=400, detail="task_not_in_program")
    target = str(redirect_to or "").strip() or f"/programs/{program_id}/board"
    return RedirectResponse(url=target, status_code=303)


@router.post("/programs/{program_id}/tasks/{task_id}/urgency")
def update_experiment_task_urgency(
    program_id: int,
    task_id: int,
    urgency: str = Form("normal"),
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        task = experiment_tasks_svc.set_task_urgency(db, task_id=int(task_id), urgency=urgency)
    except KeyError:
        raise HTTPException(404)
    if int(task.program_id) != int(program_id):
        raise HTTPException(status_code=400, detail="task_not_in_program")
    target = str(redirect_to or "").strip() or f"/programs/{program_id}/board"
    return RedirectResponse(url=target, status_code=303)


@router.post("/programs/{program_id}/tasks/{task_id}/notes")
def update_experiment_task_notes(
    program_id: int,
    task_id: int,
    notes: str = Form(""),
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        task = experiment_tasks_svc.set_task_notes(db, task_id=int(task_id), notes=notes)
    except KeyError:
        raise HTTPException(404)
    if int(task.program_id) != int(program_id):
        raise HTTPException(status_code=400, detail="task_not_in_program")
    target = str(redirect_to or "").strip() or f"/programs/{program_id}/board"
    return RedirectResponse(url=target, status_code=303)


@router.post("/programs/{program_id}/tasks/create-and-start-data")
def create_task_and_start_data_entry(
    program_id: int,
    molecule_id: int = Form(...),
    metric_key: str = Form(""),
    suggested_assay: str = Form(""),
    source_snapshot_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    p = svc.get_program(db, int(program_id))
    if not p:
        raise HTTPException(404)
    m = db.get(Molecule, int(molecule_id))
    if m is None:
        raise HTTPException(404)
    if int(m.program_id) != int(program_id):
        raise HTTPException(status_code=400, detail="molecule_not_in_program")
    task = experiment_tasks_svc.create_experiment_task(
        db,
        program_id=int(program_id),
        molecule_id=int(molecule_id),
        metric_key=metric_key,
        suggested_assay=suggested_assay,
        source_kind="board",
        source_snapshot_id=source_snapshot_id,
    )
    method = str(suggested_assay or metric_key or "").strip()
    title = f"Run {metric_key} experiment".strip() if str(metric_key or "").strip() else "Run recommended experiment"
    query = urlencode(
        {
            "program_id": int(program_id),
            "molecule_id": int(molecule_id),
            "method": method,
            "title": title,
            "task_id": int(task.id),
        }
    )
    return RedirectResponse(url=f"/data/new?{query}", status_code=303)
