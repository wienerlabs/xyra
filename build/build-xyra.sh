#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$HOME/.cache/xyra/zed-src"
TAG="v1.10.3"
XYRA_APP="/Applications/Xyra.app"
BREW_BIN="$(dirname "$(command -v brew 2>/dev/null || echo /opt/homebrew/bin/brew)")"

if ! xcode-select -p >/dev/null 2>&1; then
  echo "error: Command Line Tools required: xcode-select --install" >&2
  exit 1
fi

command -v cargo >/dev/null 2>&1 || { echo "error: Rust required (https://rustup.rs)" >&2; exit 1; }

if ! command -v cmake >/dev/null 2>&1; then
  echo "installing cmake (required by Zed's wasmtime dependency)..."
  brew install cmake || { echo "error: cmake required (brew install cmake)" >&2; exit 1; }
fi

if ! pmset -g batt | grep -q "AC Power"; then
  echo "warning: on battery power, the build can take 30-60 minutes. A charger is recommended."
fi

if [ ! -d "$SRC/.git" ]; then
  git clone --depth 1 --branch "$TAG" https://github.com/zed-industries/zed.git "$SRC"
fi
git -C "$SRC" checkout -f "$TAG" 2>/dev/null || git -C "$SRC" checkout -f FETCH_HEAD 2>/dev/null || true
git -C "$SRC" reset --hard >/dev/null
git -C "$SRC" clean -fdq

XYRA_LOCAL_BUILD=1 "$REPO_DIR/build/patch-brand.sh" "$SRC"

cd "$SRC"
STAMP="$(mktemp)"
./script/bundle-mac -l || echo "warning: bundle-mac exited nonzero (likely the optional DMG licensing step); verifying the .app was still produced"

APP_PATH="$(find "$SRC/target" -maxdepth 4 -name "*.app" -type d -newer "$STAMP" 2>/dev/null | head -1)"
rm -f "$STAMP"
[ -n "$APP_PATH" ] || { echo "error: no freshly built .app found (bundle-mac likely failed before packaging)" >&2; exit 1; }

STAGED="$HOME/.cache/xyra/Xyra.app"
rm -rf "$STAGED"
ditto "$APP_PATH" "$STAGED"

if [ -d "$XYRA_APP" ]; then
  osascript -e 'tell application "Finder" to delete (POSIX file "/Applications/Xyra.app" as alias)' >/dev/null
fi
mv "$STAGED" "$XYRA_APP"

ln -sfn "$XYRA_APP/Contents/MacOS/cli" "$BREW_BIN/xyra"
ln -sfn "$XYRA_APP/Contents/MacOS/cli" "$BREW_BIN/zed"
killall Dock 2>/dev/null || true

BINARY="$(find "$XYRA_APP/Contents/MacOS" -type f -name "[Xx]yra" -o -type f -name "[Zz]ed" 2>/dev/null | head -1)"
if [ -n "$BINARY" ] && strings "$BINARY" | grep -q "Welcome to Xyra"; then
  echo "verified: the welcome screen says Xyra."
fi

echo "Xyra built from source and installed: $XYRA_APP"
command -v xyra-doctor >/dev/null 2>&1 && xyra-doctor || true
