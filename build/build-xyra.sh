#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$HOME/.cache/xyra/zed-src"
TAG="v1.10.3"
XYRA_APP="/Applications/Xyra.app"
BREW_BIN="$(dirname "$(command -v brew 2>/dev/null || echo /opt/homebrew/bin/brew)")"

if ! xcrun -sdk macosx metal --version >/dev/null 2>&1; then
  echo "Hata: Metal derleyicisi yok. App Store'dan Xcode kurun, sonra:" >&2
  echo "  sudo xcode-select -s /Applications/Xcode.app/Contents/Developer" >&2
  echo "  sudo xcodebuild -runFirstLaunch" >&2
  exit 1
fi

command -v cargo >/dev/null 2>&1 || { echo "Hata: Rust gerekli (https://rustup.rs)" >&2; exit 1; }

if ! pmset -g batt | grep -q "AC Power"; then
  echo "Uyarı: pil gücündesiniz, derleme 30-60 dakika sürebilir. Şarj kablosu önerilir."
fi

if [ ! -d "$SRC/.git" ]; then
  git clone --depth 1 --branch "$TAG" https://github.com/zed-industries/zed.git "$SRC"
fi
git -C "$SRC" checkout -f "$TAG" 2>/dev/null || git -C "$SRC" checkout -f FETCH_HEAD 2>/dev/null || true
git -C "$SRC" reset --hard >/dev/null
git -C "$SRC" clean -fdq

"$REPO_DIR/build/patch-brand.sh" "$SRC"

cd "$SRC"
./script/bundle-mac -l

APP_PATH="$(find "$SRC/target" -maxdepth 4 -name "*.app" -type d 2>/dev/null | head -1)"
[ -n "$APP_PATH" ] || { echo "Hata: derlenen .app bulunamadı" >&2; exit 1; }

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
  echo "Doğrulandı: welcome ekranı Xyra diyor."
fi

echo "Xyra kaynaktan derlendi ve kuruldu: $XYRA_APP"
command -v xyra-doctor >/dev/null 2>&1 && xyra-doctor || true
