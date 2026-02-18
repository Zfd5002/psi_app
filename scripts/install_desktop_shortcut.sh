#!/usr/bin/env bash
set -euo pipefail

# ----------------------------------------
# Install a desktop shortcut to start PSI
# ----------------------------------------
#
# This script is safe to re-run. It will:
# - Ensure scripts/start_psi.sh is executable
# - Create a .desktop launcher on your Desktop
#
# Notes:
# - Some desktop environments require: right-click icon -> "Allow Launching"
#

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
START_SCRIPT="$REPO_ROOT/scripts/start_psi.sh"
TEMPLATE="$REPO_ROOT/scripts/PSI.desktop.template"

# Determine Desktop dir
DESKTOP_DIR=""
if command -v xdg-user-dir >/dev/null 2>&1; then
  DESKTOP_DIR="$(xdg-user-dir DESKTOP || true)"
fi
if [ -z "${DESKTOP_DIR:-}" ] || [ "${DESKTOP_DIR:-}" = "DESKTOP" ]; then
  DESKTOP_DIR="$HOME/Desktop"
fi
mkdir -p "$DESKTOP_DIR"

if [ ! -f "$START_SCRIPT" ]; then
  echo "❌ ERROR: start script not found: $START_SCRIPT"
  exit 1
fi

chmod +x "$START_SCRIPT"

LAUNCHER="$DESKTOP_DIR/PSI.desktop"

# Render launcher
if [ -f "$TEMPLATE" ]; then
  sed \
    -e "s|__REPO_ROOT__|$REPO_ROOT|g" \
    -e "s|__START_SCRIPT__|$START_SCRIPT|g" \
    "$TEMPLATE" > "$LAUNCHER"
else
  cat > "$LAUNCHER" <<EOF
[Desktop Entry]
Version=1.0
Name=PSI
Comment=Preclinical Systems Intelligence
Exec=$START_SCRIPT
Icon=utilities-terminal
Terminal=true
Type=Application
Categories=Development;
EOF
fi

chmod +x "$LAUNCHER"

echo "✅ Desktop shortcut installed: $LAUNCHER"
echo "   If double-click doesn't launch, right-click the icon and choose “Allow Launching”."
