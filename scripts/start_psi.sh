#!/usr/bin/env bash
set -euo pipefail

# ----------------------------------------
# Start PSI (local-first)
# ----------------------------------------
#
# Starts:
#   uvicorn psi.web.app:create_app --factory [--reload]
#
# Usage:
#   ./scripts/start_psi.sh          # dev (reload)
#   ./scripts/start_psi.sh --prod   # prod-like (no reload)
#
# Assumptions:
# - This repo lives at __REPO_ROOT__
# - Python venv exists at __REPO_ROOT__/.venv
#

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# --- arg parsing ---
RELOAD=1
for arg in "$@"; do
  case "$arg" in
    --prod)
      RELOAD=0
      ;;
    --reload)
      RELOAD=1
      ;;
    -h|--help)
      echo "Usage: ./scripts/start_psi.sh [--prod|--reload]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg"
      echo "Usage: ./scripts/start_psi.sh [--prod|--reload]"
      exit 2
      ;;
  esac
done

if [ ! -d ".venv" ]; then
  echo "❌ ERROR: .venv not found in $REPO_ROOT"
  echo "   Create it first (or adjust this script)."
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# Start server in background (so we can optionally open the browser)
UVICORN_ARGS=(psi.web.app:create_app --factory)
if [ "$RELOAD" -eq 1 ]; then
  UVICORN_ARGS+=(--reload)
fi

uvicorn "${UVICORN_ARGS[@]}" &
PID=$!

# Optionally open browser (default on; disable with PSI_OPEN_BROWSER=0)
if [ "${PSI_OPEN_BROWSER:-1}" != "0" ] && command -v xdg-open >/dev/null 2>&1; then
  sleep 1
  xdg-open "http://127.0.0.1:8000" >/dev/null 2>&1 || true
fi

# Wait on uvicorn so terminal stays open
wait "$PID"
