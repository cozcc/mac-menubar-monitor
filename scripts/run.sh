#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JOB_LABEL="local.codex.minimonitor"
EXECUTABLE_PATH="$(bash "$ROOT_DIR/scripts/build.sh")"

launchctl remove "$JOB_LABEL" 2>/dev/null || true
launchctl submit -l "$JOB_LABEL" -- "$EXECUTABLE_PATH"
sleep 1

if pgrep -f "$EXECUTABLE_PATH" >/dev/null; then
  printf 'Started MiniMonitor: %s\n' "$EXECUTABLE_PATH"
else
  printf 'MiniMonitor did not stay running.\n' >&2
  exit 1
fi
