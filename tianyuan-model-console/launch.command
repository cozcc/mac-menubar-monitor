#!/bin/zsh
set -euo pipefail

ROOT="/Users/vv/.openclaw/openfei/tianyuan-model-console"
PORT="${TMC_PORT:-51280}"
HOST="${TMC_HOST:-127.0.0.1}"

python3 "$ROOT/model_console.py" install-openclaw-plugin >/dev/null
python3 "$ROOT/model_console.py" serve --host "$HOST" --port "$PORT"
