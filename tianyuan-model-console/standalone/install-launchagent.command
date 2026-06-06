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
LABEL="com.tianyuan.model-console"

python3 - "$DOMAIN" "$LABEL" "$PLIST" <<'PY'
import subprocess
import sys
from pathlib import Path

domain, label, plist = sys.argv[1:]

def run(args, timeout=8):
    try:
        return subprocess.run(
            args,
            timeout=timeout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", "timeout")

if not Path(plist).exists():
    raise SystemExit(f"plist 不存在：{plist}")

run(["launchctl", "bootout", f"{domain}/{label}"], timeout=5)
bootstrap = run(["launchctl", "bootstrap", domain, plist], timeout=8)
if bootstrap.returncode != 0:
    current = run(["launchctl", "print", f"{domain}/{label}"], timeout=5)
    if current.returncode != 0:
        message = (bootstrap.stderr or bootstrap.stdout or "launchctl bootstrap failed").strip()
        raise SystemExit(message)

run(["launchctl", "kickstart", "-k", f"{domain}/{label}"], timeout=5)
PY

echo "已安装后台自启动：$PLIST"
echo "网页地址：http://$HOST:$PORT"
