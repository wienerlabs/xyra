#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZED_APP="/Applications/Zed.app"
XYRA_APP="/Applications/Xyra.app"
BREW_BIN="$(dirname "$(command -v brew 2>/dev/null || echo /opt/homebrew/bin/brew)")"

echo "Not: Xyra normalde kendi içinden otomatik güncellenir. Bu script sadece temiz yeniden kurulum içindir."

pgrep -x Xyra >/dev/null 2>&1 || pgrep -x Zed >/dev/null 2>&1 && {
  echo "Hata: Xyra açıkken güncellenemez, önce uygulamayı kapatın." >&2
  exit 1
}

brew install --cask zed --force

if [ -d "$XYRA_APP" ] && [ -d "$ZED_APP" ]; then
  mv "$XYRA_APP" "$HOME/.Trash/Xyra-eski-$(date +%Y%m%d%H%M%S).app"
fi

if [ -d "$ZED_APP" ]; then
  mv "$ZED_APP" "$XYRA_APP"
fi

brew uninstall --cask zed --force >/dev/null 2>&1 || true
ln -sfn "$XYRA_APP/Contents/MacOS/cli" "$BREW_BIN/xyra"
ln -sfn "$XYRA_APP/Contents/MacOS/cli" "$BREW_BIN/zed"

if fileicon set "$XYRA_APP" "$REPO_DIR/assets/xyra-icon.png" 2>/dev/null; then
  killall Dock 2>/dev/null || true
  echo "Güncellendi ve simge yeniden uygulandı."
else
  echo "Güncellendi. Simgeyi manuel uygulayın (README sorun giderme bölümü)."
fi
