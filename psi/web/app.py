from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from psi.core.db import ensure_schema
from psi.core.storage import StorageConfig, ensure_storage
from psi.extensions import load_extensions
from psi.web.ui_labels import humanize_decision_key, humanize_key, humanize_path_token, humanize_state
from psi.web.routers import (
    batches,
    builder,
    decisions,
    di,
    evidence,
    files,
    lineage,
    molecules,
    reports,
    portfolios,
    portfolio,
    claims,
    plans,
    programs,
    search,
    data_records,
    qc,
)

# Canonical, importable, grep-friendly version source.
from psi.version import PSI_VERSION as _PSI_VERSION

# Backward-compat alias – do not redefine version here.
PSI_VERSION = _PSI_VERSION


def create_app(*, base_dir: Path | None = None) -> FastAPI:
    """Application factory.

    This is the seam that allows mounting multiple versions/apps in the future.
    """

    if base_dir is None:
        # repo root
        base_dir = Path(__file__).resolve().parents[2]

    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
    # Release string (shown in UI footer). Single source of truth: psi/version.py
    templates.env.globals["PSI_VERSION"] = PSI_VERSION
    templates.env.filters["humanize_key"] = humanize_key
    templates.env.filters["humanize_decision_key"] = humanize_decision_key
    templates.env.filters["humanize_state"] = humanize_state
    templates.env.filters["humanize_path_token"] = humanize_path_token
    storage = StorageConfig(base_dir=base_dir)
    rules_path = base_dir / "psi_rules" / "psirules-0.1.0.yml"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        ensure_schema()
        ensure_storage(storage)

        # load extensions (may add routes + registry entries)
        load_extensions(app)
        yield

    app = FastAPI(title="PSI (Preclinical Systems Intelligence)", lifespan=lifespan)

    app.state.base_dir = base_dir
    app.state.templates = templates
    app.state.storage = storage
    app.state.rules_path = rules_path

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # include routers
    app.include_router(programs.router)
    app.include_router(builder.router)
    app.include_router(portfolios.router)
    app.include_router(portfolio.router)
    app.include_router(claims.router)
    app.include_router(plans.router)
    app.include_router(reports.router)
    app.include_router(lineage.router)
    app.include_router(molecules.router)
    app.include_router(batches.router)
    app.include_router(data_records.router)
    app.include_router(evidence.router)
    app.include_router(decisions.router)
    app.include_router(di.router)
    app.include_router(files.router)
    app.include_router(search.router)
    app.include_router(qc.router)

    return app
