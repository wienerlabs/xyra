#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZED_APP="/Applications/Zed.app"
XYRA_APP="/Applications/Xyra.app"
ZED_CONFIG_DIR="$HOME/.config/zed"
BREW_BIN="$(dirname "$(command -v brew 2>/dev/null || echo /opt/homebrew/bin/brew)")"

fail() { echo "Hata: $1" >&2; exit 1; }

command -v brew >/dev/null 2>&1 || fail "Homebrew gerekli: https://brew.sh"

echo "[1/6] Uygulamalar kuruluyor (Zed, Grok Build, fileicon, JetBrains Mono Nerd Font)"
if [ ! -d "$XYRA_APP" ] && [ ! -d "$ZED_APP" ]; then
  brew install --cask zed
fi
brew list --cask grok-build >/dev/null 2>&1 || brew install --cask grok-build
brew list fileicon >/dev/null 2>&1 || brew install fileicon
brew list --cask font-jetbrains-mono-nerd-font >/dev/null 2>&1 || brew install --cask font-jetbrains-mono-nerd-font

echo "[2/6] Zed ayarları yazılıyor"
mkdir -p "$ZED_CONFIG_DIR"
if [ -f "$ZED_CONFIG_DIR/settings.json" ]; then
  BACKUP="$ZED_CONFIG_DIR/settings.json.bak.$(date +%Y%m%d%H%M%S)"
  cp "$ZED_CONFIG_DIR/settings.json" "$BACKUP"
  echo "  mevcut settings.json yedeklendi: $BACKUP"
fi
cp "$REPO_DIR/settings/settings.json" "$ZED_CONFIG_DIR/settings.json"
mkdir -p "$ZED_CONFIG_DIR/themes"
cp "$REPO_DIR/settings/themes/xyra.json" "$ZED_CONFIG_DIR/themes/xyra.json"
cp "$REPO_DIR/assets/xyra-icon.png" "$ZED_CONFIG_DIR/xyra-icon.png"

echo "[3/6] Uygulama Xyra olarak adlandırılıyor"
if [ -d "$ZED_APP" ] && [ ! -d "$XYRA_APP" ]; then
  if mv "$ZED_APP" "$XYRA_APP" 2>/dev/null; then
    echo "  Zed.app -> Xyra.app"
  else
    echo "  Uyarı: yeniden adlandırma macOS tarafından engellendi."
    echo "  Sistem Ayarları > Gizlilik ve Güvenlik > Uygulama Yönetimi altında Terminal'e izin verin ve scripti tekrar çalıştırın."
  fi
fi

echo "[4/6] Xyra simgesi uygulanıyor"
TARGET_APP="$XYRA_APP"
[ -d "$TARGET_APP" ] || TARGET_APP="$ZED_APP"
if fileicon set "$TARGET_APP" "$REPO_DIR/assets/xyra-icon.png" 2>/dev/null; then
  killall Dock 2>/dev/null || true
  echo "  simge uygulandı"
else
  echo "  Uyarı: simge otomatik uygulanamadı (Uygulama Yönetimi izni gerekli)."
  echo "  Manuel yol: Finder'da uygulamayı seçip cmd+I, sol üstteki küçük simgeye tıklayın, assets/xyra-icon.png dosyasını Önizleme'de açıp cmd+A cmd+C ile kopyalayın ve cmd+V ile yapıştırın."
fi

echo "[5/6] Homebrew zed kaydı kaldırılıyor ve xyra komutu oluşturuluyor"
if [ -d "$XYRA_APP" ]; then
  if brew list --cask zed >/dev/null 2>&1; then
    brew uninstall --cask zed --force >/dev/null 2>&1 || true
    echo "  brew zed kaydı kaldırıldı, güncellemeler artık Xyra içinden otomatik"
  fi
  ln -sfn "$XYRA_APP/Contents/MacOS/cli" "$BREW_BIN/xyra"
  ln -sfn "$XYRA_APP/Contents/MacOS/cli" "$BREW_BIN/zed"
  echo "  xyra komutu hazır: $BREW_BIN/xyra"
fi

echo "[6/6] Kurulum tamamlandı"
echo ""
echo "Sonraki adımlar:"
echo "  1. grok login --oauth        (kendi SuperGrok veya X Premium+ hesabınızla)"
echo "  2. Xyra'yı açın, sağ üstten GitHub ile giriş yapın (Zeta tab tamamlama için)"
echo "  3. Agent paneli: cmd+? açın, + menüsünden Grok Build veya Claude Code seçin"
