#!/usr/bin/env bash
set -euo pipefail
export HOMEBREW_NO_AUTO_UPDATE=1

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZED_APP="/Applications/Zed.app"
XYRA_APP="/Applications/Xyra.app"
BREW_BIN="$(dirname "$(command -v brew 2>/dev/null || echo /opt/homebrew/bin/brew)")"

echo "Note: Xyra normally updates itself in place. This script is only for a clean reinstall."

pgrep -x Xyra >/dev/null 2>&1 || pgrep -x Zed >/dev/null 2>&1 && {
  echo "error: cannot update while Xyra is running, quit the app first." >&2
  exit 1
}

brew install --cask zed --force

if [ -d "$XYRA_APP" ] && [ -d "$ZED_APP" ]; then
  mv "$XYRA_APP" "$HOME/.Trash/Xyra-old-$(date +%Y%m%d%H%M%S).app"
fi

if [ -d "$ZED_APP" ]; then
  mv "$ZED_APP" "$XYRA_APP"
fi

brew uninstall --cask zed --force >/dev/null 2>&1 || true
ln -sfn "$XYRA_APP/Contents/MacOS/cli" "$BREW_BIN/xyra"
ln -sfn "$XYRA_APP/Contents/MacOS/cli" "$BREW_BIN/zed"

if fileicon set "$XYRA_APP" "$REPO_DIR/assets/xyra-icon.png" 2>/dev/null; then
  killall Dock 2>/dev/null || true
  echo "Updated and icon reapplied."
else
  echo "Updated. Apply the icon manually (see the README troubleshooting section)."
fi
