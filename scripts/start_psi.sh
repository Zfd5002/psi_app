#!/usr/bin/env bash
set -euo pipefail

# ----------------------------------------
# Start PSI (local-first)
# ----------------------------------------
#
# Launch contract:
# - USER launch (default): stable local run for normal daily use.
# - DEV launch (explicit): same app entrypoint with --reload.
#
# Usage:
#   ./scripts/start_psi.sh                 # USER launch (default; no reload)
#   ./scripts/start_psi.sh --user          # USER launch (explicit)
#   ./scripts/start_psi.sh --dev           # DEV launch (with reload)
#   ./scripts/start_psi.sh --reload        # DEV launch alias
#   ./scripts/start_psi.sh --prod          # backward-compatible alias for --user
#   ./scripts/start_psi.sh --no-browser    # do not auto-open browser
#
# Assumptions:
# - Script can be run from any working directory.
# - Repo-local venv exists at <repo>/.venv.
#
# Failure categories (wrapper-targetable):
# - launch:error:env_missing
# - launch:error:dependency_missing
# - launch:error:port_in_use
# - launch:error:runtime_failed

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# --- arg parsing ---
MODE="user"
FORCE_BROWSER=""
HOST_OVERRIDE=""
PORT_OVERRIDE=""
for arg in "$@"; do
  case "$arg" in
    --user|--prod)
      MODE="user"
      ;;
    --dev|--reload)
      MODE="dev"
      ;;
    --no-browser)
      FORCE_BROWSER="0"
      ;;
    --browser)
      FORCE_BROWSER="1"
      ;;
    --host=*)
      HOST_OVERRIDE="${arg#*=}"
      ;;
    --port=*)
      PORT_OVERRIDE="${arg#*=}"
      ;;
    -h|--help)
      cat <<'EOF'
Usage: ./scripts/start_psi.sh [options]

Modes:
  --user, --prod      USER launch (default; no reload)
  --dev, --reload     DEV launch (with reload)

Options:
  --host=HOST         Bind host (default: PSI_HOST or 127.0.0.1)
  --port=PORT         Bind port (default: PSI_PORT or 8000)
  --no-browser        Disable browser auto-open
  --browser           Force browser auto-open
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg"
      echo "Usage: ./scripts/start_psi.sh [--user|--dev|--reload|--prod] [--host=HOST] [--port=PORT] [--no-browser|--browser]"
      exit 2
      ;;
  esac
done

if [ ! -d ".venv" ]; then
  echo "❌ launch:error:env_missing"
  echo "   .venv not found in $REPO_ROOT"
  echo "   Create it first: python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "❌ launch:error:env_missing"
  echo "   Missing interpreter at .venv/bin/python"
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# --- host/port contract ---
HOST="${PSI_HOST:-127.0.0.1}"
PORT="${PSI_PORT:-8000}"
if [ -n "$HOST_OVERRIDE" ]; then
  HOST="$HOST_OVERRIDE"
fi
if [ -n "$PORT_OVERRIDE" ]; then
  PORT="$PORT_OVERRIDE"
fi

# --- dependency contract ---
if ! command -v uvicorn >/dev/null 2>&1; then
  echo "❌ launch:error:dependency_missing"
  echo "   uvicorn not found in active environment."
  echo "   Reinstall core dependencies: pip install -r requirements.txt"
  exit 1
fi

if ! python - <<'PY' >/dev/null 2>&1
import uvicorn  # noqa: F401
import psi.web.asgi  # noqa: F401
PY
then
  echo "❌ launch:error:dependency_missing"
  echo "   Could not import launch dependencies (uvicorn / psi.web.asgi)."
  echo "   Reinstall core dependencies: pip install -r requirements.txt"
  exit 1
fi

# --- port contract ---
if ! python - "$HOST" "$PORT" <<'PY' >/dev/null 2>&1
import socket
import sys

host = str(sys.argv[1])
port = int(sys.argv[2])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind((host, port))
finally:
    s.close()
PY
then
  echo "❌ launch:error:port_in_use"
  echo "   Could not bind ${HOST}:${PORT} (already in use or unavailable)."
  echo "   Use --port=<PORT> or stop the process using this port."
  exit 1
fi

# Start server in background (so launcher can optionally open browser)
UVICORN_ARGS=(psi.web.asgi:app --host "$HOST" --port "$PORT")
if [ "$MODE" = "dev" ]; then
  UVICORN_ARGS+=(--reload)
fi

echo "PSI launch mode: ${MODE}"
echo "PSI entrypoint: psi.web.asgi:app"
echo "PSI bind: http://${HOST}:${PORT}"

uvicorn "${UVICORN_ARGS[@]}" &
PID=$!

# Browser-open behavior is launcher-level, not app-level.
OPEN_BROWSER="${PSI_OPEN_BROWSER:-}"
if [ -n "$FORCE_BROWSER" ]; then
  OPEN_BROWSER="$FORCE_BROWSER"
fi
if [ -z "$OPEN_BROWSER" ]; then
  if [ "$MODE" = "user" ]; then
    OPEN_BROWSER="1"
  else
    OPEN_BROWSER="0"
  fi
fi
if [ "$OPEN_BROWSER" != "0" ] && command -v xdg-open >/dev/null 2>&1; then
  sleep 1
  xdg-open "http://${HOST}:${PORT}" >/dev/null 2>&1 || true
fi

# Wait on uvicorn so terminal stays open; preserve failure signal.
if ! wait "$PID"; then
  echo "❌ launch:error:runtime_failed"
  echo "   Uvicorn exited unexpectedly."
  exit 1
fi
