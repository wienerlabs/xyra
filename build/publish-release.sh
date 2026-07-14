#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="wienerlabs/xyra"
VERSION="${1:?kullanım: publish-release.sh <version> [app-yolu]   örn: publish-release.sh v0.1.0}"
APP="${2:-/Applications/Xyra.app}"

command -v gh >/dev/null 2>&1 || { echo "Hata: gh CLI gerekli (brew install gh)" >&2; exit 1; }
[ -d "$APP" ] || { echo "Hata: uygulama bulunamadı: $APP" >&2; exit 1; }

BIN="$APP/Contents/MacOS/zed"
if ! grep -aq "Welcome to Xyra" "$BIN" 2>/dev/null; then
  echo "Hata: $APP markalı bir Xyra derlemesi değil (Welcome to Xyra bulunamadı). Doğrulanmamış build yayınlanmaz." >&2
  exit 1
fi

ARCH="$(uname -m)"
[ "$ARCH" = "arm64" ] || ARCH="x86_64"
ZED_BASE="$(defaults read "$APP/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null || echo unknown)"

STAGE="$(mktemp -d)"
ASSET="$STAGE/Xyra-$VERSION-macos-$ARCH.zip"
echo "Paketleniyor: $ASSET"
ditto "$APP" "$STAGE/Xyra.app"
(cd "$STAGE" && ditto -c -k --sequesterRsrc --keepParent Xyra.app "$ASSET")
rm -rf "$STAGE/Xyra.app"
shasum -a 256 "$ASSET" | awk '{print $1}' > "$ASSET.sha256"
SIZE="$(du -h "$ASSET" | awk '{print $1}')"

NOTES_FILE="$STAGE/notes.md"
cat > "$NOTES_FILE" <<'EOF'
Xyra @VERSION@ (Zed @ZED_BASE@ tabanli, macOS @ARCH@)

Wiener Labs dahili editoru. Grok Build ve Claude Code agent panelinde, Xyra temasi ve markasi gomulu.

## Kurulum
```bash
git clone https://github.com/@REPO@.git && cd xyra && ./install.sh
```
install.sh bu release'i indirir (derleme gerektirmez) ve Wiener yapilandirmasini uygular.

## Kaynak (GPL)
Bu binary, GPLv3 lisansli zed-industries/zed `v@ZED_BASE@` etiketinden, bu repodaki `build/patch-brand.sh` ve `build/rebrand-strings.py` yamalariyla derlenmistir. Karsilik gelen kaynagi `./build/build-xyra.sh` ile birebir yeniden uretebilirsiniz.
EOF
sed -i '' -e "s|@VERSION@|$VERSION|g" -e "s|@ARCH@|$ARCH|g" -e "s|@ZED_BASE@|$ZED_BASE|g" -e "s|@REPO@|$REPO|g" "$NOTES_FILE"

echo "GitHub Release olusturuluyor: $VERSION ($SIZE)"
if gh release view "$VERSION" --repo "$REPO" >/dev/null 2>&1; then
  gh release upload "$VERSION" "$ASSET" "$ASSET.sha256" --repo "$REPO" --clobber
  echo "Mevcut release guncellendi: $VERSION"
else
  gh release create "$VERSION" "$ASSET" "$ASSET.sha256" \
    --repo "$REPO" --title "Xyra $VERSION" --notes-file "$NOTES_FILE"
  echo "Release yayinlandi: https://github.com/$REPO/releases/tag/$VERSION"
fi

rm -rf "$STAGE"
