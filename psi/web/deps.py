from __future__ import annotations

from pathlib import Path

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from psi.core.db import SessionLocal
from psi.core.storage import StorageConfig


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_templates(request: Request):
    return request.app.state.templates


def get_storage_cfg(request: Request) -> StorageConfig:
    return request.app.state.storage


def get_rules_path(request: Request) -> Path:
    return request.app.state.rules_path
