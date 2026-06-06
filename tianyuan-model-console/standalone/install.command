#!/bin/zsh
set -euo pipefail

THIS_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_ROOT="$(cd "$THIS_DIR/.." && pwd)"
APP_ROOT="${TMC_INSTALL_DIR:-$HOME/Applications/Tianyuan Model Console}"
PYTHON="${TMC_PYTHON:-python3}"

mkdir -p "$APP_ROOT"

rsync -a --delete \
  --exclude ".git" \
  --exclude ".DS_Store" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  --exclude "dist" \
  --exclude "*.bak.*_model_console" \
  "$SOURCE_ROOT"/ "$APP_ROOT"/

chmod +x "$APP_ROOT/launch.command" \
  "$APP_ROOT/bin/tianyuan-model-console.js" \
  "$APP_ROOT/standalone/TianyuanModelConsole.command" \
  "$APP_ROOT/standalone/install.command" \
  "$APP_ROOT/standalone/install-launchagent.command" \
  "$APP_ROOT/standalone/uninstall-launchagent.command" \
  "$APP_ROOT/scripts/package_standalone.sh" 2>/dev/null || true

"$PYTHON" "$APP_ROOT/model_console.py" install-openclaw-plugin >/dev/null

echo "天元模型控制台已安装到：$APP_ROOT"
echo "启动命令：$APP_ROOT/standalone/TianyuanModelConsole.command"
echo "网页地址：http://127.0.0.1:${TMC_PORT:-51280}"
echo "OpenClaw / WorkBuddy / CodeBuddy 的路径和模型参数请在网页里的“路径设置”和“模型配置”中填写。"
open "$APP_ROOT" >/dev/null 2>&1 || true
