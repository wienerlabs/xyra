#!/usr/bin/env bash
set -euo pipefail

SRC="${1:?usage: patch-brand.sh <zed-source-dir>}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if sed --version >/dev/null 2>&1; then
  sed_i() { sed -i "$@"; }
else
  sed_i() { sed -i '' "$@"; }
fi

sed_i 's/ReleaseChannel::Stable => "Zed"/ReleaseChannel::Stable => "Xyra"/' "$SRC/crates/release_channel/src/lib.rs"
sed_i 's/"Welcome to Zed"/"Welcome to Xyra"/' "$SRC/crates/workspace/src/welcome.rs"
sed_i "s/The editor for what's next/The Wiener Labs editor/" "$SRC/crates/workspace/src/welcome.rs"

if grep -q '^name = "Zed"$' "$SRC/crates/zed/Cargo.toml"; then
  sed_i 's/^name = "Zed"$/name = "Xyra"/' "$SRC/crates/zed/Cargo.toml"
fi

if grep -q '^default = \["gpui/default"\]$' "$SRC/crates/gpui_macos/Cargo.toml" 2>/dev/null; then
  sed_i 's|^default = \["gpui/default"\]$|default = ["gpui/default", "runtime_shaders"]|' "$SRC/crates/gpui_macos/Cargo.toml"
fi

if grep -q '^gpui_macos = { path = "crates/gpui_macos", default-features = false }$' "$SRC/Cargo.toml"; then
  sed_i 's|^gpui_macos = { path = "crates/gpui_macos", default-features = false }$|gpui_macos = { path = "crates/gpui_macos", default-features = false, features = ["runtime_shaders"] }|' "$SRC/Cargo.toml"
fi

for ICON in app-icon.png app-icon@2x.png; do
  TARGET="$SRC/crates/zed/resources/$ICON"
  [ -f "$TARGET" ] || continue
  if command -v sips >/dev/null 2>&1; then
    SIZE=$(sips -g pixelWidth "$TARGET" | awk '/pixelWidth/ {print $2}')
    sips -z "$SIZE" "$SIZE" "$REPO_DIR/assets/xyra-icon.png" --out "$TARGET" >/dev/null
  elif command -v convert >/dev/null 2>&1; then
    SIZE=$(identify -format "%w" "$TARGET" 2>/dev/null || echo 512)
    convert "$REPO_DIR/assets/xyra-icon.png" -resize "${SIZE}x${SIZE}" "$TARGET"
  else
    cp "$REPO_DIR/assets/xyra-icon.png" "$TARGET"
  fi
done

mkdir -p "$SRC/assets/themes/xyra"
cp "$REPO_DIR/settings/themes/xyra.json" "$SRC/assets/themes/xyra/xyra.json"

if [ -f "$SRC/assets/images/zed_logo.svg" ]; then
  cp "$REPO_DIR/assets/xyra-logo.svg" "$SRC/assets/images/zed_logo.svg"
fi

python3 "$REPO_DIR/build/rebrand-strings.py" "$SRC" --apply | tail -1

for MD in "$SRC/crates/agent_skills/builtin/"*/SKILL.md; do
  [ -f "$MD" ] || continue
  perl -i -pe 's/\bZed\b/Xyra/g' "$MD"
done

python3 "$REPO_DIR/build/patch-agent-icons.py" "$SRC"
python3 "$REPO_DIR/build/patch-font-button.py" "$SRC"

if [ -n "${XYRA_TEAM_ID:-}" ]; then
  sed_i "s/APPLE_NOTARIZATION_TEAM=\"[A-Z0-9]*\"/APPLE_NOTARIZATION_TEAM=\"$XYRA_TEAM_ID\"/" "$SRC/script/bundle-mac"
  echo "notarization team ID set: $XYRA_TEAM_ID"
fi

echo "brand patch applied: release channel, welcome screen and logo, bundle name, icons, embedded Xyra theme, all UI strings, embedded skills"
