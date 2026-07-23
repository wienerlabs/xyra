#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="wienerlabs/xyra"
VERSION="${1:?usage: publish-release.sh <version> [app-path]   e.g. publish-release.sh v0.1.0}"
APP="${2:-/Applications/Xyra.app}"

command -v gh >/dev/null 2>&1 || { echo "error: gh CLI required (brew install gh)" >&2; exit 1; }
[ -d "$APP" ] || { echo "error: app not found: $APP" >&2; exit 1; }

BIN="$APP/Contents/MacOS/zed"
if ! grep -aq "Welcome to Xyra" "$BIN" 2>/dev/null; then
  echo "error: $APP is not a branded Xyra build (Welcome to Xyra not found). Unverified builds are not published." >&2
  exit 1
fi

ARCH="$(uname -m)"
if [ "$ARCH" = "arm64" ]; then ARCH="AppleSilicon"; else ARCH="Intel"; fi
ZED_BASE="$(defaults read "$APP/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null || echo unknown)"

STAGE="$(mktemp -d)"
ASSET="$STAGE/Xyra-$VERSION-macOS-$ARCH.zip"
echo "packaging: $ASSET"
ditto "$APP" "$STAGE/Xyra.app"
(cd "$STAGE" && ditto -c -k --sequesterRsrc --keepParent Xyra.app "$ASSET")
rm -rf "$STAGE/Xyra.app"
shasum -a 256 "$ASSET" | awk '{print $1}' > "$ASSET.sha256"
SIZE="$(du -h "$ASSET" | awk '{print $1}')"

NOTES_FILE="$STAGE/notes.md"
cat > "$NOTES_FILE" <<'EOF'
Xyra @VERSION@ (based on Zed @ZED_BASE@, macOS @ARCH@)

The agentic code editor where every change is cross-examined by a rival AI before you see it. Flat-rate, local-first, and yours.

## Install
```bash
git clone https://github.com/@REPO@.git && cd xyra && ./install.sh
```
install.sh downloads this release (no compilation) and applies the Wiener configuration.

## Source (GPL)
This binary is built from the GPLv3 zed-industries/zed tag `v@ZED_BASE@`, patched with `build/patch-brand.sh` and `build/rebrand-strings.py` in this repository. Reproduce the corresponding source exactly with `./build/build-xyra.sh`.
EOF
sed -i '' -e "s|@VERSION@|$VERSION|g" -e "s|@ARCH@|$ARCH|g" -e "s|@ZED_BASE@|$ZED_BASE|g" -e "s|@REPO@|$REPO|g" "$NOTES_FILE"

echo "creating GitHub release: $VERSION ($SIZE)"
if gh release view "$VERSION" --repo "$REPO" >/dev/null 2>&1; then
  gh release upload "$VERSION" "$ASSET" "$ASSET.sha256" --repo "$REPO" --clobber
  echo "updated existing release: $VERSION"
else
  gh release create "$VERSION" "$ASSET" "$ASSET.sha256" \
    --repo "$REPO" --title "Xyra $VERSION" --notes-file "$NOTES_FILE"
  echo "published release: https://github.com/$REPO/releases/tag/$VERSION"
fi

rm -rf "$STAGE"
