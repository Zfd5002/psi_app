#!/usr/bin/env bash
set -euo pipefail

# ----------------------------------------
# PSI code-only ZIP builder
# ----------------------------------------
#
# Usage:
#   ./compress.sh                # auto-detect version, build zip, and (by default) install desktop shortcut
#   ./compress.sh v1.2.3         # override version tag
#   ./compress.sh --no-desktop   # build zip only
#
# Notes:
# - Version is sourced from psi/web/app.py (templates.env.globals["PSI_VERSION"] = "vX.Y.Z")
# - Desktop shortcut install is idempotent and safe to re-run.
#

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

# --- arg parsing ---
VERSION_OVERRIDE=""
INSTALL_DESKTOP=1

for arg in "$@"; do
  case "$arg" in
    --no-desktop)
      INSTALL_DESKTOP=0
      ;;
    --desktop)
      INSTALL_DESKTOP=1
      ;;
    v*)
      # allow a single version override like "v1.2.3"
      VERSION_OVERRIDE="$arg"
      ;;
    *)
      echo "Unknown argument: $arg"
      echo "Usage: ./compress.sh [vX.Y.Z] [--no-desktop]"
      exit 2
      ;;
  esac
done

# --- detect version from source of truth ---
detect_version() {
  local app_py="$REPO_ROOT/psi/web/app.py"
  if [ ! -f "$app_py" ]; then
    return 1
  fi
  # Extract PSI_VERSION from the Jinja env global assignment
  # Example line:
  # templates.env.globals["PSI_VERSION"] = "v1.2.1"
  local v
  v="$(grep -Eo 'PSI_VERSION"\][[:space:]]*=[[:space:]]*"v[^"]+"' "$app_py" | head -n 1 | sed -E 's/.*"((v[^"]+))".*/\1/')"
  if [ -n "${v:-}" ]; then
    echo "$v"
    return 0
  fi
  return 1
}

VERSION=""
if [ -n "${VERSION_OVERRIDE:-}" ]; then
  VERSION="$VERSION_OVERRIDE"
else
  if VERSION="$(detect_version)"; then
    :
  else
    echo "⚠️  WARNING: Could not auto-detect PSI_VERSION from psi/web/app.py"
    VERSION="unknown"
  fi
fi

ZIP="$HOME/Downloads/psi_repo_update_${VERSION}_code_only.zip"

echo "📦 Building PSI code-only ZIP"
echo "Repo: $REPO_ROOT"
echo "Output: $ZIP"
echo "Version tag: $VERSION"
echo

# Remove existing zip if present
if [ -f "$ZIP" ]; then
  echo "⚠️  Removing existing ZIP"
  rm -f "$ZIP"
fi

# Create ZIP
zip -r "$ZIP" . \
  -x ".git/*" \
  -x ".venv/*" \
  -x "uploads/*" \
  -x "psi/uploads/*" \
  -x "*.sqlite" -x "*.db" \
  -x "__pycache__/*" -x "**/__pycache__/*" \
  -x "*.pyc" -x "*.pyo" \
  -x ".pytest_cache/*" -x ".mypy_cache/*" -x ".ruff_cache/*" \
  -x "psi/web/templates/molecules/*.bak_*"

echo
echo "✅ ZIP created successfully"
ls -lh "$ZIP"

echo
echo "🔍 Verifying exclusions..."
if zipinfo -1 "$ZIP" | egrep -i '(\.git/|\.venv/|uploads/|\.sqlite$|\.db$|__pycache__/|\.pyc$)' >/dev/null; then
  echo "❌ ERROR: Forbidden files detected in ZIP"
  zipinfo -1 "$ZIP" | egrep -i '(\.git/|\.venv/|uploads/|\.sqlite$|\.db$|__pycache__/|\.pyc$)'
  exit 1
else
  echo "✅ ZIP is clean (no git, venv, DB, uploads, or caches)"
fi

# Optional desktop shortcut install
if [ "$INSTALL_DESKTOP" -eq 1 ]; then
  if [ -f "$REPO_ROOT/scripts/install_desktop_shortcut.sh" ]; then
    echo
    echo "🖥️  Installing desktop shortcut (idempotent)..."
    bash "$REPO_ROOT/scripts/install_desktop_shortcut.sh"
  else
    echo
    echo "⚠️  Desktop shortcut installer not found at scripts/install_desktop_shortcut.sh"
    echo "    (This is non-fatal; ZIP still built.)"
  fi
fi

echo
echo "🚀 Ready to upload or apply via overlay"
