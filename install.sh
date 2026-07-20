#!/usr/bin/env bash
set -euo pipefail
export HOMEBREW_NO_AUTO_UPDATE=1

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="wienerlabs/xyra"
XYRA_APP="/Applications/Xyra.app"
ZED_CONFIG_DIR="$HOME/.config/zed"
BREW_BIN="$(dirname "$(command -v brew 2>/dev/null || echo /opt/homebrew/bin/brew)")"

METHOD="release"
for arg in "$@"; do
  case "$arg" in
    --source) METHOD="source" ;;
    --release) METHOD="release" ;;
    -h|--help)
      echo "Usage: ./install.sh [--release | --source]"
      echo "  --release  download the prebuilt Xyra from GitHub Releases (default, fast)"
      echo "  --source   build from source (no Xcode needed, ~45-60 min)"
      exit 0 ;;
  esac
done

fail() { echo "error: $1" >&2; exit 1; }
command -v brew >/dev/null 2>&1 || fail "Homebrew required: https://brew.sh"

quit_running_xyra() {
  osascript -e 'tell application "Xyra" to quit' >/dev/null 2>&1 || true
  sleep 1
  pkill -f "Xyra.app/Contents/MacOS/zed" >/dev/null 2>&1 || true
  sleep 1
}

install_app_from_release() {
  command -v gh >/dev/null 2>&1 || brew install gh
  gh auth status >/dev/null 2>&1 || fail "gh sign-in required: gh auth login"
  local arch tmp zip
  arch="$(uname -m)"; [ "$arch" = "arm64" ] || arch="x86_64"
  tmp="$(mktemp -d)"
  echo "  downloading the latest release ($arch)..."
  if ! gh release download --repo "$REPO" --pattern "Xyra-*-macos-$arch.zip" --dir "$tmp" 2>/dev/null; then
    rm -rf "$tmp"; return 1
  fi
  zip="$(ls "$tmp"/Xyra-*-macos-$arch.zip 2>/dev/null | head -1)"
  [ -n "$zip" ] || { rm -rf "$tmp"; return 1; }
  if [ -f "$zip.sha256" ]; then
    echo "  verifying sha256..."
    echo "$(cat "$zip.sha256")  $zip" | shasum -a 256 -c - >/dev/null || fail "sha256 verification failed"
  fi
  quit_running_xyra
  [ -d "$XYRA_APP" ] && mv "$XYRA_APP" "$HOME/.Trash/Xyra-$(date +%Y%m%d%H%M%S).app"
  ditto -x -k "$zip" "$tmp/extracted"
  ditto "$tmp/extracted/Xyra.app" "$XYRA_APP"
  xattr -dr com.apple.quarantine "$XYRA_APP" 2>/dev/null || true
  rm -rf "$tmp"
  return 0
}

echo "[1/5] installing the Xyra app ($METHOD)"
if [ "$METHOD" = "source" ]; then
  "$REPO_DIR/build/build-xyra.sh"
else
  if ! install_app_from_release; then
    echo "  no release found, falling back to a source build (~45-60 min)"
    "$REPO_DIR/build/build-xyra.sh"
  fi
fi

echo "[2/5] helper tools (Grok Build, JetBrains Mono, gh)"
brew list --cask grok-build >/dev/null 2>&1 || brew install --cask grok-build
brew list --cask font-jetbrains-mono-nerd-font >/dev/null 2>&1 || brew install --cask font-jetbrains-mono-nerd-font

echo "[3/5] writing Zed settings"
mkdir -p "$ZED_CONFIG_DIR" "$ZED_CONFIG_DIR/themes" "$ZED_CONFIG_DIR/snippets"
for F in settings.json tasks.json keymap.json; do
  if [ -f "$ZED_CONFIG_DIR/$F" ]; then
    cp "$ZED_CONFIG_DIR/$F" "$ZED_CONFIG_DIR/$F.bak.$(date +%Y%m%d%H%M%S)"
  fi
  cp "$REPO_DIR/settings/$F" "$ZED_CONFIG_DIR/$F"
done
cp "$REPO_DIR/settings/themes/xyra.json" "$ZED_CONFIG_DIR/themes/xyra.json"
cp "$REPO_DIR/settings/snippets/"*.json "$ZED_CONFIG_DIR/snippets/"
cp "$REPO_DIR/assets/xyra-icon.png" "$ZED_CONFIG_DIR/xyra-icon.png"
if [ -f "$ZED_CONFIG_DIR/AGENTS.md" ]; then
  cp "$ZED_CONFIG_DIR/AGENTS.md" "$ZED_CONFIG_DIR/AGENTS.md.bak.$(date +%Y%m%d%H%M%S)"
fi
cp "$REPO_DIR/settings/AGENTS.md" "$ZED_CONFIG_DIR/AGENTS.md"
for SKILL_DIR in "$REPO_DIR/grok/skills/"*/; do
  SKILL_NAME="$(basename "$SKILL_DIR")"
  mkdir -p "$HOME/.grok/skills/$SKILL_NAME"
  cp "$SKILL_DIR/SKILL.md" "$HOME/.grok/skills/$SKILL_NAME/SKILL.md"
done

echo "[4/5] installing xyra commands and the semantic context engine"
if [ -d "$XYRA_APP" ]; then
  ln -sfn "$XYRA_APP/Contents/MacOS/cli" "$BREW_BIN/xyra"
  ln -sfn "$XYRA_APP/Contents/MacOS/cli" "$BREW_BIN/zed"
fi
install -m 0755 "$REPO_DIR/bin/xyra-fix" "$REPO_DIR/bin/xyra-doctor" "$REPO_DIR/bin/xyra-council" "$REPO_DIR/bin/xyra-cosmos" "$REPO_DIR/bin/xyra-watch" "$REPO_DIR/bin/xyra-grok-keepalive" "$BREW_BIN/"
install -m 0755 "$REPO_DIR/context/xyra_context.py" "$BREW_BIN/xyra-context"
mkdir -p "$HOME/.xyra"
rm -rf "$HOME/.xyra/council"
cp -R "$REPO_DIR/context/council" "$HOME/.xyra/council"
( cd "$HOME/.xyra" && python3 -m unittest council.test_council >/dev/null 2>&1 ) && echo "  council engine: tests green" || true
python3 -c "import numpy" 2>/dev/null || python3 -m pip install --user --quiet numpy 2>/dev/null || true
if command -v ollama >/dev/null 2>&1; then
  ollama list 2>/dev/null | grep -qi nomic-embed || ollama pull nomic-embed-text >/dev/null 2>&1 &
fi
if command -v grok >/dev/null 2>&1; then
  grok mcp add -s user xyra-context "$BREW_BIN/xyra-context" -- mcp >/dev/null 2>&1 || true
fi
"$BREW_BIN/xyra-grok-keepalive" install >/dev/null 2>&1 && echo "  grok session keepalive: active (auto-renews sign-in every 2h)" || true

echo "[5/5] install complete"
killall Dock 2>/dev/null || true
echo ""
echo "Next steps:"
echo "  1. grok login --oauth        (with your own SuperGrok or X Premium+ account)"
echo "  2. open Xyra, sign in with GitHub from the top right (for Zeta edit predictions)"
echo "  3. agent panel: press cmd+?, pick Grok Build or Claude Code from the + menu"
echo "  4. xyra-doctor        (to verify the install)"
