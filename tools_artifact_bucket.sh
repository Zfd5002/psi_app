#!/usr/bin/env bash
set -euo pipefail
v="${1:-}"
case "$v" in
  v1.2.9*) echo "v1.2.9" ;;
  v1.3.0*) echo "v1.3.0" ;;
  v2.0*)   echo "v2.0" ;;
  *)       echo "other" ;;
esac
