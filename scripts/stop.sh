#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JOB_LABEL="local.codex.minimonitor"
EXECUTABLE_PATH="$ROOT_DIR/dist/MiniMonitor"

launchctl remove "$JOB_LABEL" 2>/dev/null || true

PIDS="$(pgrep -f "$EXECUTABLE_PATH" || true)"
if [[ -z "$PIDS" ]]; then
  printf 'MiniMonitor is not running.\n'
  exit 0
fi

while IFS= read -r pid; do
  [[ -z "$pid" ]] && continue
  kill "$pid"
  printf 'Stopped MiniMonitor pid %s\n' "$pid"
done <<< "$PIDS"
