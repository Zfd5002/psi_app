from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from psi.services import plans as plans_svc
from psi.web.deps import get_db, get_templates

router = APIRouter()


@router.get("/plans", response_class=HTMLResponse)
def plans_list(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    rows = plans_svc.list_plans(db, include_archived=False, limit=200)
    return templates.TemplateResponse(
        "plans/list.html",
        {
            "request": request,
            "plans": rows,
        },
    )


@router.get("/plans/{plan_id}", response_class=HTMLResponse)
def plan_detail(plan_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    try:
        ctx = plans_svc.build_plan_detail(db, plan_id=int(plan_id))
    except KeyError:
        raise HTTPException(404)
    ctx["request"] = request
    return templates.TemplateResponse("plans/detail.html", ctx)


@router.post("/plans/{plan_id}/instantiate")
def instantiate_plan(
    plan_id: int,
    request: Request,
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
):
    plans_svc.create_tasks_from_plan(db, plan_id=int(plan_id))
    target = str(redirect_to or "").strip() or f"/plans/{int(plan_id)}"
    return RedirectResponse(url=target, status_code=303)


@router.post("/plans/steps/{step_id}/instantiate")
def instantiate_plan_step(
    step_id: int,
    request: Request,
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
):
    plans_svc.create_task_from_plan_step(db, step_id=int(step_id))
    target = str(redirect_to or "").strip() or "/plans"
    return RedirectResponse(url=target, status_code=303)
