# Heavy compute installation (v1.1.2a)

PSI is local-first and runs in two dependency tiers.

## Core (ELN + viewer UI; no heavy compute)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn psi.web.asgi:app --reload --host 127.0.0.1 --port 8000
```

## Heavy compute (domains + numbering; optional)

```bash
source .venv/bin/activate
pip install -r requirements.txt -r requirements-heavy.txt
```

Notes:
- Heavy compute is also gated per-molecule via `molecules.heavy_compute_enabled`.
- On Ubuntu, ANARCI requires HMMER:
  `sudo apt-get update && sudo apt-get install -y hmmer`
- If `anarci` installation fails from `requirements-heavy.txt` in your environment, use the fallback installer:
  `./scripts/install_anarci.sh`
