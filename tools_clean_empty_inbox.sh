#!/usr/bin/env bash
set -euo pipefail
find ~/psi_codex/_artifacts/INBOX/from_Downloads -mindepth 1 -maxdepth 1 -type d -empty -print -delete
find ~/psi_codex/_artifacts/INBOX/from_Home      -mindepth 1 -maxdepth 1 -type d -empty -print -delete
