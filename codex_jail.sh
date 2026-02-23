#!/usr/bin/env bash
set -euo pipefail

# Hard-enforce working directory
cd /home/zach/psi_codex

# Allowed write roots (strict)
ALLOW_RW=(
  "/home/zach/psi_codex"
)

# Allowed read-only roots (best-effort; this script can't truly enforce RO,
# but we will refuse obvious write ops that mention these paths)
ALLOW_RO=(
  "/home/zach/psi_repo"
)

is_under() {
  local path="$1"
  local root="$2"
  [[ "$path" == "$root"* ]]
}

deny_if_contains_system_roots() {
  local cmd="$1"
  if echo "$cmd" | egrep -q '(^|[[:space:]])(/etc|/usr|/bin|/sbin|/var|/opt|/lib|/proc|/sys)(/|[[:space:]]|$)'; then
    echo "DENY: references system path."
    echo "CMD: $cmd"
    exit 2
  fi
}

deny_write_ops_outside_codex() {
  local cmd="$1"

  # classify "write-ish" operations (conservative)
  if echo "$cmd" | egrep -qi '(^|[[:space:]])(rm|mv|cp|rsync|tee|chmod|chown|mkdir|rmdir|truncate|dd|sed[[:space:]]+-i|perl[[:space:]]+-pi|git[[:space:]]+(add|commit|checkout|merge|rebase|tag|push)|zip|tar)([[:space:]]|$)'; then
    # extract absolute paths
    mapfile -t paths < <(echo "$cmd" | tr ' ' '\n' | egrep '^/' || true)

    for p in "${paths[@]}"; do
      # allow writes only under codex
      if is_under "$p" "/home/zach/psi_codex"; then
        continue
      fi

      # if command mentions psi_repo during a write-ish op, deny
      if is_under "$p" "/home/zach/psi_repo"; then
        echo "DENY: write-ish command referencing read-only repo root: $p"
        echo "CMD: $cmd"
        exit 3
      fi

      # allow /tmp only for staging inside codex workflows IF you want:
      # (commented out because you requested codex-only writes)
      # if is_under "$p" "/tmp"; then continue; fi

      echo "DENY: path outside writable codex root: $p"
      echo "CMD: $cmd"
      exit 4
    done
  fi
}

cmd="${*:-}"
if [[ -z "$cmd" ]]; then
  echo "Usage: codex_jail.sh <command...>"
  exit 1
fi

deny_if_contains_system_roots "$cmd"
deny_write_ops_outside_codex "$cmd"

exec bash -lc "$cmd"
