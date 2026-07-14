#!/usr/bin/env bash
set -euo pipefail

SRC="${1:?kullanım: patch-brand.sh <zed-kaynak-dizini>}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

sed -i '' 's/ReleaseChannel::Stable => "Zed"/ReleaseChannel::Stable => "Xyra"/' "$SRC/crates/release_channel/src/lib.rs"
sed -i '' 's/"Welcome to Zed"/"Welcome to Xyra"/' "$SRC/crates/workspace/src/welcome.rs"
sed -i '' "s/The editor for what's next/The Wiener Labs editor/" "$SRC/crates/workspace/src/welcome.rs"

if grep -q '^name = "Zed"$' "$SRC/crates/zed/Cargo.toml"; then
  sed -i '' 's/^name = "Zed"$/name = "Xyra"/' "$SRC/crates/zed/Cargo.toml"
fi

if grep -q '^default = \["gpui/default"\]$' "$SRC/crates/gpui_macos/Cargo.toml"; then
  sed -i '' 's|^default = \["gpui/default"\]$|default = ["gpui/default", "runtime_shaders"]|' "$SRC/crates/gpui_macos/Cargo.toml"
fi

if grep -q '^gpui_macos = { path = "crates/gpui_macos", default-features = false }$' "$SRC/Cargo.toml"; then
  sed -i '' 's|^gpui_macos = { path = "crates/gpui_macos", default-features = false }$|gpui_macos = { path = "crates/gpui_macos", default-features = false, features = ["runtime_shaders"] }|' "$SRC/Cargo.toml"
fi

for ICON in app-icon.png app-icon@2x.png; do
  TARGET="$SRC/crates/zed/resources/$ICON"
  if [ -f "$TARGET" ]; then
    SIZE=$(sips -g pixelWidth "$TARGET" | awk '/pixelWidth/ {print $2}')
    sips -z "$SIZE" "$SIZE" "$REPO_DIR/assets/xyra-icon.png" --out "$TARGET" >/dev/null
  fi
done

mkdir -p "$SRC/assets/themes/xyra"
cp "$REPO_DIR/settings/themes/xyra.json" "$SRC/assets/themes/xyra/xyra.json"

if [ -f "$SRC/assets/images/zed_logo.svg" ]; then
  cp "$REPO_DIR/assets/xyra-logo.svg" "$SRC/assets/images/zed_logo.svg"
fi

python3 "$REPO_DIR/build/rebrand-strings.py" "$SRC" --apply | tail -1

echo "marka yaması uygulandı: release channel, welcome ekranı ve logosu, bundle adı, simgeler, gömülü Xyra teması, tüm UI stringleri"
