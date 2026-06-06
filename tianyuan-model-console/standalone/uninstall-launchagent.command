#!/bin/zsh
set -euo pipefail

PLIST="$HOME/Library/LaunchAgents/com.tianyuan.model-console.plist"

launchctl unload "$PLIST" >/dev/null 2>&1 || true
rm -f "$PLIST"

echo "已移除天元模型控制台后台自启动。"
