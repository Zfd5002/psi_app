from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from psi.web.deps import get_db
from psi.services import qc as qc_svc

router = APIRouter()


@router.post("/qc/measurement/{measurement_id}")
def qc_measurement(
    measurement_id: int,
    record_id: int = Form(...),
    action: str = Form(...),
    actor: str = Form(...),
    note: str = Form(""),
    ignore_policy: str = Form("include"),
    ignore_reason_code: str = Form(""),
    ignore_note: str = Form(""),
    clear_legacy_ignore: int = Form(0),
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        qc_svc.append_qc_event(
            db,
            measurement_id=int(measurement_id),
            record_id=int(record_id) if record_id else None,
            metric_key=None,
            action=action,
            actor=actor,
            note=note or None,
            ignore_policy=ignore_policy or None,
            ignore_reason_code=ignore_reason_code or None,
            ignore_note=ignore_note or None,
            clear_legacy_ignore=bool(int(clear_legacy_ignore or 0)),
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    target = (redirect_to or "").strip() or f"/data/{int(record_id)}"
    return RedirectResponse(url=target, status_code=303)
