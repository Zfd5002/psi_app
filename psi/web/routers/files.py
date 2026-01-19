from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from psi.services import files as svc
from psi.web.deps import get_db, get_storage_cfg

router = APIRouter()


@router.post("/filelinks/{filelink_id}/delete")
def filelink_delete(
    filelink_id: int,
    request: Request,
    db: Session = Depends(get_db),
    storage=Depends(get_storage_cfg),
):
    svc.delete_filelink(db, storage=storage, filelink_id=filelink_id)
    return RedirectResponse(url=request.headers.get("referer", "/"), status_code=303)


@router.get("/files/{file_id}/download")
def file_download(file_id: int, db: Session = Depends(get_db), storage=Depends(get_storage_cfg)):
    f = svc.get_file(db, file_id)
    if not f:
        raise HTTPException(404)
    path = svc.get_download_path(storage, f)
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type=f.mime or "application/octet-stream", filename=f.original_name)
