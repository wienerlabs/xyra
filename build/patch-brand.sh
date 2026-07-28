#!/usr/bin/env bash
set -euo pipefail

SRC="${1:?usage: patch-brand.sh <zed-source-dir>}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python

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
  elif command -v magick >/dev/null 2>&1; then
    SIZE=$(magick identify -format "%w" "$TARGET" 2>/dev/null || echo 512)
    magick "$REPO_DIR/assets/xyra-icon.png" -resize "${SIZE}x${SIZE}" "$TARGET"
  elif convert --version 2>/dev/null | grep -qi imagemagick; then
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

"$PY" "$REPO_DIR/build/rebrand-strings.py" "$SRC" --apply | tail -1

for MD in "$SRC/crates/agent_skills/builtin/"*/SKILL.md; do
  [ -f "$MD" ] || continue
  perl -i -pe 's/\bZed\b/Xyra/g' "$MD"
done

"$PY" "$REPO_DIR/build/patch-agent-icons.py" "$SRC"
"$PY" "$REPO_DIR/build/patch-font-button.py" "$SRC"
"$PY" "$REPO_DIR/build/patch-grok-onboarding.py" "$SRC"
"$PY" "$REPO_DIR/build/patch-ui-scale.py" "$SRC"
"$PY" "$REPO_DIR/build/patch-money-rain.py" "$SRC"
"$PY" "$REPO_DIR/build/patch-ui-labels.py" "$SRC"
"$PY" "$REPO_DIR/build/patch-xyra-panel-buttons.py" "$SRC"
"$PY" "$REPO_DIR/build/patch-xyra-session.py" "$SRC"

if [ "${XYRA_LOCAL_BUILD:-}" = "1" ]; then
  "$PY" - "$SRC" <<'PYEOF'
import re, sys
p = sys.argv[1] + "/crates/zed/src/main.rs"
s = open(p, encoding="utf-8").read()
new = re.sub(
    r"let should_install_crash_handler = matches!\(.*?!= ReleaseChannel::Dev;",
    "let should_install_crash_handler = false;",
    s, count=1, flags=re.S,
)
if new != s:
    open(p, "w", encoding="utf-8").write(new)
    print("crash handler disabled for local unsigned source build")
else:
    print("warning: crash handler pattern not found", file=sys.stderr)
PYEOF
fi

if [ -n "${XYRA_LANG:-}" ] && [ "$XYRA_LANG" != "en" ]; then
  "$PY" "$REPO_DIR/build/translate-strings.py" "$SRC" --lang "$XYRA_LANG" --apply | tail -1
fi

if [ -f "$SRC/script/bundle-windows.ps1" ]; then
  PS1_FILE="$SRC/script/bundle-windows.ps1"
  sed_i 's/{{2DB0DA96-CA55-49BB-AF4F-64AF36A86712}/{{EF205767-8E1A-429E-BF57-6D266458D92B}/' "$PS1_FILE"
  sed_i 's/\$appName = "Zed"$/$appName = "Xyra"/' "$PS1_FILE"
  sed_i 's/\$appDisplayName = "Zed"$/$appDisplayName = "Xyra"/' "$PS1_FILE"
  sed_i 's/\$appSetupName = "Zed-\$Architecture"/$appSetupName = "Xyra-$Architecture"/' "$PS1_FILE"
  sed_i 's/\$regValueName = "Zed"$/$regValueName = "Xyra"/' "$PS1_FILE"
  sed_i 's/\$appUserId = "ZedIndustries.Zed"$/$appUserId = "WienerLabs.Xyra"/' "$PS1_FILE"
  sed_i 's/\$appShellNameShort = "Z&ed"$/$appShellNameShort = "X\&yra"/' "$PS1_FILE"
  echo "windows installer identity patched"
fi

if [ -f "$SRC/crates/zed/resources/windows/zed.iss" ]; then
  ISS_FILE="$SRC/crates/zed/resources/windows/zed.iss"
  sed_i 's/AppPublisher=Zed Industries/AppPublisher=Wiener Labs/' "$ISS_FILE"
  sed_i 's|AppPublisherURL=https://www.zed.dev/|AppPublisherURL=https://github.com/wienerlabs/xyra|' "$ISS_FILE"
fi

WIN_ICO="$SRC/crates/zed/resources/windows/app-icon.ico"
if [ -f "$WIN_ICO" ] && command -v magick >/dev/null 2>&1; then
  magick "$REPO_DIR/assets/xyra-icon.png" -define icon:auto-resize=256,128,96,64,48,32,16 "$WIN_ICO"
  echo "windows app icon replaced"
fi

if [ -n "${XYRA_TEAM_ID:-}" ]; then
  sed_i "s/APPLE_NOTARIZATION_TEAM=\"[A-Z0-9]*\"/APPLE_NOTARIZATION_TEAM=\"$XYRA_TEAM_ID\"/" "$SRC/script/bundle-mac"
  echo "notarization team ID set: $XYRA_TEAM_ID"
fi

echo "brand patch applied: release channel, welcome screen and logo, bundle name, icons, embedded Xyra theme, all UI strings, embedded skills"
