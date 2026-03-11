# PSI (Preclinical Systems Intelligence)

Local-first scientific application built with FastAPI + Jinja2, SQLAlchemy, and SQLite.

## Install

Core (ELN + viewer):

```bash
pip install -r requirements.txt
```

Heavy compute (domains + numbering, etc.):

```bash
pip install -r requirements.txt -r requirements-heavy.txt
```

If `anarci` fails to install from `requirements-heavy.txt` in your environment, use:

```bash
./scripts/install_anarci.sh
```

This repo was refactored from an MVP layout into a layered, extensible architecture designed for:

- clean long-term growth by a small team
- adding new modules (scientific domains/workflows) without touching core code
- supporting future API versions (`/v1`, `/v2`, or separate mounted apps)

## Architecture

```
psi/
  core/             # framework-agnostic domain core (stable)
  services/         # business logic (use cases)
  web/              # FastAPI + Jinja2 delivery layer
    app.py          # create_app() factory
    asgi.py         # ASGI entrypoint: app = create_app()
    deps.py         # shared dependencies
    routers/        # thin feature routers (HTTP parsing only)
    templates/      # Jinja templates
    static/         # static assets
  extensions/       # optional modules (routes + registry extensions)
  scripts/          # smoke tests / small utilities

psi_rules/
  psirules-0.1.0.yml
```

### Layer responsibilities

- **`psi/core`**
  - Database models
  - `ensure_schema` (safe schema evolution)
  - Registry + evidence/data mappings
  - Decision engine
  - Audit logging primitives
  - Local file storage helpers

## PSI v1.01 (antibody-aware molecules + computed results)

v1.01 introduces an **additive, backward-compatible** upgrade for antibody-centric workflows:

- Molecule format: **IgG** or **scFv** (legacy/unstructured still supported)
- Structured storage of molecule components (`molecule_components`)
- Deterministic auto-generated molecule descriptions (`description_auto`) with optional user override (`description_user`)
- Computed results system (`property_runs`, `property_values`) that never overwrites experimental data
- Automatic FAST computed properties and (when structured) antibody numbering (Kabat/IMGT/Chothia)
- Heavy compute architecture via an extension (`psi/extensions/structure`), gated by:
  - `PSI_ENABLE_HEAVY_COMPUTE=1`
  - per-molecule checkbox in the UI

  This layer is intentionally reusable by the web UI, future APIs, CLI tools, and batch jobs.

- **`psi/services`**
  - Owns all business rules (e.g. batch auto-increment, citation validation, decision snapshot persistence, audit logging, file linking + orphan cleanup)
  - Called by routers and future non-web tooling

- **`psi/web`**
  - Thin routers that parse requests, call services, and render templates
  - `create_app()` factory so multiple apps/versions can coexist

## Running

Create a virtualenv, install requirements, and run:

```bash
uvicorn psi.web.asgi:app --reload
```

The legacy entrypoint `psi.app:app` is kept for backwards compatibility.

## Extensions

Extensions are light-weight modules under `psi/extensions/<name>`.
Enable by setting an environment variable:

```bash
export PSI_EXTENSIONS=cmc,eln
```

Each extension may implement `init_extension(app: FastAPI) -> None` and can:

- register additional routers
- extend the registry (by importing and modifying `psi.core.registry` in a controlled way)
- ship additional templates (recommended: mount templates under the extension and configure Jinja2 as needed)

The extension system is intentionally minimal—no plugin framework.

## Smoke tests

Run the minimal (no-pytest) smoke tests:

```bash
python -m psi.scripts.smoke_test
```

## Test gates

PSI uses tiered deterministic test gates for development speed and release confidence.

Tier 1 (everyday patch iteration):

```bash
python -m compileall -q psi
bash scripts/test_fast_gate.sh
python -m psi.tools.di_contract_smoke
python -m psi.tools.di_replay_regression --limit 5
python -c "from psi.version import PSI_VERSION; print(PSI_VERSION)"
```

Tier 2 (milestone / end-of-chain validation):

```bash
bash scripts/test_milestone_gate.sh
```

Tier 3 (full release validation):

```bash
pytest -q
```

Fast gate source of truth:
- Node ID allowlist: `tests/fast_gate_nodeids.txt`
- One pytest node ID per line, deterministic order.

Milestone gate source of truth:
- Curated target file list: `tests/milestone_gate_targets.txt`
