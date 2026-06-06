#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="MiniMonitor"
BUILD_DIR="$ROOT_DIR/dist"
EXECUTABLE_PATH="$BUILD_DIR/$APP_NAME"

rm -rf "$BUILD_DIR/$APP_NAME.app"
mkdir -p "$BUILD_DIR"

clang \
  -fobjc-arc \
  -mmacosx-version-min=12.0 \
  "$ROOT_DIR/Sources/MiniMonitor/main.m" \
  -o "$EXECUTABLE_PATH" \
  -framework Cocoa

codesign --force --sign - "$EXECUTABLE_PATH" >/dev/null 2>&1

printf '%s\n' "$EXECUTABLE_PATH"
