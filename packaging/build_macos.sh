#!/usr/bin/env bash
# Build the AeroGrid-XAI desktop POC on macOS.
# Usage: bash packaging/build_macos.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

echo "==> repo: $REPO"
echo "==> python: $(python3 --version)"


# Rebuild the frontend bundle before packing. Without this, a stale
# frontend/dist from a previous branch gets packed into the .app, and
# changes to frontend/src do not take effect after bash build_macos.sh.
echo "==> rebuilding frontend bundle"
pushd "$REPO/frontend" > /dev/null
npm run build
popd > /dev/null

if ! command -v pyinstaller >/dev/null 2>&1; then
    echo "==> pyinstaller not found; installing from packaging/requirements-desktop.txt"
    pip install -r packaging/requirements-desktop.txt
fi
echo "==> pyinstaller: $(pyinstaller --version)"

rm -rf build dist

echo "==> building"
pyinstaller --clean --noconfirm packaging/aerogrid.spec 2>&1 | tail -n 30

echo
echo "==> output"
ls -la dist/aerogrid-desktop/ | head -n 10
echo
echo "==> binary size"
du -sh dist/aerogrid-desktop
