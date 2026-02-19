#!/usr/bin/env bash
set -euo pipefail

# PSI heavy compute helper: installs ANARCI into the *active* virtualenv.
#
# Why this exists:
# - ANARCI is not reliably pip-wheel-installable across environments.
# - Installing from source via setup.py is the most reproducible path.
#
# Usage:
#   source .venv/bin/activate
#   ./scripts/install_anarci.sh
#
# Requirements:
# - git (for cloning)
# - hmmer (for ANARCI runtime)
#
# This script is safe to run multiple times.

ANARCI_COMMIT="${ANARCI_COMMIT:-79f6c575056dedef86cb8f405ebb039197}"
ANARCI_REPO="${ANARCI_REPO:-https://github.com/oxpig/ANARCI.git}"

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  echo "ERROR: No active virtualenv detected (VIRTUAL_ENV is empty)."
  echo "Activate your venv first, e.g.: source .venv/bin/activate"
  exit 1
fi

PYTHON_BIN="$(command -v python || true)"
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "ERROR: python not found on PATH inside the virtualenv."
  exit 1
fi

echo "Using python: ${PYTHON_BIN}"
echo "Virtualenv: ${VIRTUAL_ENV}"

# Quick check: if ANARCI already imports, exit early.
if python - <<'PY' >/dev/null 2>&1
import anarci
PY
then
  echo "ANARCI already installed (import succeeds). Nothing to do."
  exit 0
fi

echo ""
echo "NOTE: ANARCI requires HMMER on your system."
echo "If you haven't installed it yet, on Ubuntu run:"
echo "  sudo apt-get update && sudo apt-get install -y hmmer"
echo ""

WORKDIR="$(mktemp -d)"
trap 'rm -rf "${WORKDIR}"' EXIT

echo "Cloning ANARCI into: ${WORKDIR}"
git clone --quiet "${ANARCI_REPO}" "${WORKDIR}/ANARCI"
cd "${WORKDIR}/ANARCI"

echo "Checking out commit: ${ANARCI_COMMIT}"
git checkout --quiet "${ANARCI_COMMIT}"

echo "Installing ANARCI via setup.py into the active virtualenv..."
# Ensure pip deps used by ANARCI are present
python -m pip install --quiet --no-cache-dir "biopython==1.83" || true

python setup.py install

echo ""
echo "Verifying import..."
python - <<'PY'
import anarci
print("anarci import OK:", anarci.__file__)
PY

echo ""
echo "Done."
