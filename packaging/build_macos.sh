#!/usr/bin/env bash
# Build MoneyTalks.app and dist/MoneyTalks-<version>.dmg on macOS.
#
#   pip install -r requirements-app.txt
#   packaging/build_macos.sh 0.2.0
#
# The app is ad-hoc signed (no Apple Developer ID), so macOS asks for
# confirmation the first time it is opened from a browser download.
set -euo pipefail

VERSION="${1:?usage: packaging/build_macos.sh <version>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

APP="dist/MoneyTalks.app"
DMG="dist/MoneyTalks-${VERSION}.dmg"
# Sign and package in a temp folder: iCloud-synced folders (e.g. ~/Documents)
# keep re-adding Finder metadata to bundles, which codesign rejects.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
SIGNED="$WORK/stage/MoneyTalks.app"

echo "==> Building MoneyTalks ${VERSION}"
rm -rf build dist
MONEYTALKS_VERSION="$VERSION" pyinstaller --noconfirm --clean packaging/MoneyTalks.spec

echo "==> Smoke-testing the bundle"
"$APP/Contents/MacOS/MoneyTalks" --smoke-test

echo "==> Signing (ad-hoc)"
mkdir -p "$WORK/stage"
ditto --norsrc --noextattr "$APP" "$SIGNED"
xattr -cr "$SIGNED"
codesign --force --deep --sign - "$SIGNED"
codesign --verify --deep --strict "$SIGNED"

echo "==> Creating ${DMG}"
ln -s /Applications "$WORK/stage/Applications"
hdiutil create -volname "MoneyTalks ${VERSION}" -srcfolder "$WORK/stage" -ov -format UDZO "$DMG"

echo "==> Done: ${DMG}"
