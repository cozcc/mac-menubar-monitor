#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(python3 - "$ROOT/model_console.py" <<'PY'
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
match = re.search(r'^PLUGIN_VERSION\s*=\s*"([^"]+)"', text, re.M)
if not match:
    raise SystemExit("PLUGIN_VERSION not found")
print(match.group(1))
PY
)"
PACKAGE_NAME="tianyuan-model-console-standalone-${VERSION}"
DIST="$ROOT/dist"
WORK="$(mktemp -d)"
ARCHIVE="$DIST/${PACKAGE_NAME}.tar.gz"

cleanup() {
  rm -rf "$WORK"
}
trap cleanup EXIT

mkdir -p "$DIST" "$WORK/$PACKAGE_NAME"

rsync -a \
  --exclude ".git" \
  --exclude ".DS_Store" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  --exclude "dist" \
  --exclude "*.bak.*_model_console" \
  "$ROOT"/ "$WORK/$PACKAGE_NAME"/

chmod +x "$WORK/$PACKAGE_NAME/launch.command" \
  "$WORK/$PACKAGE_NAME/bin/tianyuan-model-console.js" \
  "$WORK/$PACKAGE_NAME/standalone/TianyuanModelConsole.command" \
  "$WORK/$PACKAGE_NAME/standalone/install.command" \
  "$WORK/$PACKAGE_NAME/standalone/install-launchagent.command" \
  "$WORK/$PACKAGE_NAME/standalone/uninstall-launchagent.command"

tar -C "$WORK" -czf "$ARCHIVE" "$PACKAGE_NAME"
shasum -a 256 "$ARCHIVE" > "$ARCHIVE.sha256"

echo "$ARCHIVE"
echo "$ARCHIVE.sha256"
