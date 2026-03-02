from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from psi.services import portfolios as svc
from psi.web.deps import get_db, get_templates

router = APIRouter()


@router.get("/portfolios", response_class=HTMLResponse)
def list_portfolios(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    return templates.TemplateResponse("portfolios/list.html", {"request": request, "portfolios": svc.list_portfolios(db)})


@router.get("/portfolios/new", response_class=HTMLResponse)
def new_portfolio(request: Request):
    templates = get_templates(request)
    return templates.TemplateResponse("portfolios/form.html", {"request": request, "portfolio": None})


@router.post("/portfolios/new")
def create_portfolio(
    name: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    p = svc.create_portfolio(db, name=name, description=description)
    return RedirectResponse(url=f"/portfolios/{p.id}", status_code=303)


@router.get("/portfolios/{portfolio_id}", response_class=HTMLResponse)
def portfolio_detail(portfolio_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    try:
        ctx = svc.get_portfolio_detail(db, portfolio_id)
    except KeyError:
        raise HTTPException(404)
    ctx["request"] = request
    return templates.TemplateResponse("portfolios/detail.html", ctx)


@router.get("/portfolios/{portfolio_id}/edit", response_class=HTMLResponse)
def edit_portfolio(portfolio_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    p = svc.get_portfolio(db, portfolio_id)
    if not p:
        raise HTTPException(404)
    return templates.TemplateResponse("portfolios/form.html", {"request": request, "portfolio": p})


@router.post("/portfolios/{portfolio_id}/edit")
def update_portfolio(
    portfolio_id: int,
    name: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        p = svc.update_portfolio(db, portfolio_id=portfolio_id, name=name, description=description)
    except KeyError:
        raise HTTPException(404)
    return RedirectResponse(url=f"/portfolios/{p.id}", status_code=303)


@router.post("/portfolios/{portfolio_id}/memberships/add")
def add_portfolio_membership(
    portfolio_id: int,
    program_id: int = Form(...),
    sort_index: int = Form(0),
    db: Session = Depends(get_db),
):
    try:
        svc.add_portfolio_membership(db, portfolio_id=portfolio_id, program_id=program_id, sort_index=sort_index)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RedirectResponse(url=f"/portfolios/{portfolio_id}", status_code=303)


@router.post("/portfolios/{portfolio_id}/memberships/{membership_id}/sort")
def update_portfolio_membership_sort(
    portfolio_id: int,
    membership_id: int,
    sort_index: int = Form(...),
    db: Session = Depends(get_db),
):
    try:
        svc.update_portfolio_membership(db, membership_id=membership_id, sort_index=sort_index)
    except KeyError:
        raise HTTPException(404)
    return RedirectResponse(url=f"/portfolios/{portfolio_id}", status_code=303)


@router.post("/portfolios/{portfolio_id}/memberships/{membership_id}/remove")
def remove_portfolio_membership(
    portfolio_id: int,
    membership_id: int,
    db: Session = Depends(get_db),
):
    try:
        svc.remove_portfolio_membership(db, membership_id=membership_id)
    except KeyError:
        raise HTTPException(404)
    return RedirectResponse(url=f"/portfolios/{portfolio_id}", status_code=303)
