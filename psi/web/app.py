from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from psi.core.db import ensure_schema
from psi.core.storage import StorageConfig, ensure_storage
from psi.extensions import load_extensions
from psi.web.routers import (
    batches,
    decisions,
    evidence,
    files,
    molecules,
    programs,
    search,
    data_records,
)


def create_app(*, base_dir: Path | None = None) -> FastAPI:
    """Application factory.

    This is the seam that allows mounting multiple versions/apps in the future.
    """

    if base_dir is None:
        # repo root
        base_dir = Path(__file__).resolve().parents[2]

    app = FastAPI(title="PSI (Preclinical Systems Intelligence)")

    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
    # Release string (shown in UI footer). Keep as a single source of truth.
    templates.env.globals["PSI_VERSION"] = "v1.1.6"
    storage = StorageConfig(base_dir=base_dir)
    rules_path = base_dir / "psi_rules" / "psirules-0.1.0.yml"

    app.state.base_dir = base_dir
    app.state.templates = templates
    app.state.storage = storage
    app.state.rules_path = rules_path

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.on_event("startup")
    def _startup() -> None:
        ensure_schema()
        ensure_storage(storage)

        # load extensions (may add routes + registry entries)
        load_extensions(app)

    # include routers
    app.include_router(programs.router)
    app.include_router(molecules.router)
    app.include_router(batches.router)
    app.include_router(data_records.router)
    app.include_router(evidence.router)
    app.include_router(decisions.router)
    app.include_router(files.router)
    app.include_router(search.router)

    return app
