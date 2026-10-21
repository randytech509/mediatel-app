#!/usr/bin/env bash
# Assemble Mediatel.app depuis le binaire release, génère l'icône .icns et
# signe en ad-hoc (indispensable sur Apple Silicon, sinon refus de lancement).
set -euo pipefail
cd "$(dirname "$0")/.."
# Xcode complet installé mais licence non acceptée : on bâtit avec les
# Command Line Tools (SDK complet, aucune licence requise).
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Library/Developer/CommandLineTools}"
APP="build/Mediatel.app"
NAME="Mediatel"

echo "→ compilation release"
swift build -c release >/dev/null
BIN=".build/release/$NAME"

echo "→ structure .app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/$NAME"

echo "→ icône"
swift scripts/make-icon.swift build/icon.png 1024 >/dev/null
ICONSET="build/$NAME.iconset"; rm -rf "$ICONSET"; mkdir -p "$ICONSET"
for e in "16 16x16" "32 16x16@2x" "32 32x32" "64 32x32@2x" "128 128x128" \
         "256 128x128@2x" "256 256x256" "512 256x256@2x" "512 512x512" "1024 512x512@2x"; do
    set -- $e
    sips -z "$1" "$1" build/icon.png --out "$ICONSET/icon_$2.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/$NAME.icns"

echo "→ Info.plist + PkgInfo"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>$NAME</string>
  <key>CFBundleDisplayName</key><string>Mediatel</string>
  <key>CFBundleExecutable</key><string>$NAME</string>
  <key>CFBundleIdentifier</key><string>com.randytech.mediatel</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleIconFile</key><string>$NAME</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>LSApplicationCategoryType</key><string>public.app-category.utilities</string>
</dict></plist>
PLIST
printf 'APPL????' > "$APP/Contents/PkgInfo"

echo "→ signature ad-hoc"
codesign --force --deep --sign - "$APP"

echo "✓ $APP"
