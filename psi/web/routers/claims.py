from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from psi.services import claims as claims_svc
from psi.web.deps import get_db, get_templates

router = APIRouter()


@router.get("/claims", response_class=HTMLResponse)
def claims_list(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    rows = claims_svc.list_claims(db, include_archived=False, limit=200)
    return templates.TemplateResponse(
        "claims/list.html",
        {
            "request": request,
            "claims": rows,
        },
    )


@router.get("/claims/{claim_id}", response_class=HTMLResponse)
def claim_detail(claim_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    try:
        ctx = claims_svc.get_claim_detail(db, claim_id=int(claim_id))
    except KeyError:
        raise HTTPException(404)
    ctx["request"] = request
    return templates.TemplateResponse("claims/detail.html", ctx)
