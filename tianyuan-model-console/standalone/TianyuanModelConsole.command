#!/bin/zsh
set -euo pipefail

THIS_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_ROOT="$(cd "$THIS_DIR/.." && pwd)"
PYTHON="${TMC_PYTHON:-python3}"
HOST="${TMC_HOST:-127.0.0.1}"
PORT="${TMC_PORT:-51280}"
URL="http://${HOST}:${PORT}"

cd "$APP_ROOT"

"$PYTHON" "$APP_ROOT/model_console.py" install-openclaw-plugin >/dev/null || true

if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$PORT" -sTCP:LISTEN | grep -q LISTEN; then
  open "$URL" >/dev/null 2>&1 || true
  echo "天元模型控制台已经在运行：$URL"
  exit 0
fi

(open "$URL" >/dev/null 2>&1 || true) &
echo "启动天元模型控制台：$URL"
exec "$PYTHON" "$APP_ROOT/model_console.py" serve --host "$HOST" --port "$PORT"
