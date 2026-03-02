from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from psi.services import lineage as svc
from psi.web.deps import get_db, get_templates

router = APIRouter()


@router.get("/lineage/programs/{program_id}", response_class=HTMLResponse)
def program_lineage(program_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    ctx = svc.get_program_lineage(db, program_id=int(program_id))
    ctx["request"] = request
    return templates.TemplateResponse("lineage/program_detail.html", ctx)


@router.get("/lineage/portfolios/{portfolio_id}", response_class=HTMLResponse)
def portfolio_lineage(portfolio_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    try:
        ctx = svc.get_portfolio_lineage(db, portfolio_id=int(portfolio_id))
    except KeyError:
        raise HTTPException(404)
    ctx["request"] = request
    return templates.TemplateResponse("lineage/portfolio_detail.html", ctx)
