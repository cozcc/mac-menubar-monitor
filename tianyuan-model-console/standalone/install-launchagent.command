#!/bin/zsh
set -euo pipefail

APP_ROOT="${TMC_INSTALL_DIR:-$HOME/Applications/Tianyuan Model Console}"
PYTHON="${TMC_PYTHON:-/usr/bin/python3}"
HOST="${TMC_HOST:-127.0.0.1}"
PORT="${TMC_PORT:-51280}"
TEMPLATE="$APP_ROOT/standalone/com.tianyuan.model-console.plist"
PLIST="$HOME/Library/LaunchAgents/com.tianyuan.model-console.plist"

if [[ ! -f "$APP_ROOT/model_console.py" ]]; then
  echo "没有找到安装目录：$APP_ROOT"
  echo "请先运行 standalone/install.command。"
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"

python3 - "$TEMPLATE" "$PLIST" "$APP_ROOT" "$PYTHON" "$HOST" "$PORT" <<'PY'
import sys
from pathlib import Path

template, plist, app_root, python_bin, host, port = sys.argv[1:]
text = Path(template).read_text(encoding="utf-8")
text = text.replace("__APP_ROOT__", app_root)
text = text.replace("__PYTHON__", python_bin)
text = text.replace("__HOST__", host)
text = text.replace("__PORT__", str(port))
Path(plist).write_text(text, encoding="utf-8")
PY

DOMAIN="gui/$(id -u)"
launchctl bootout "$DOMAIN" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl kickstart -k "$DOMAIN/com.tianyuan.model-console" >/dev/null 2>&1 || true

echo "已安装后台自启动：$PLIST"
echo "网页地址：http://$HOST:$PORT"
