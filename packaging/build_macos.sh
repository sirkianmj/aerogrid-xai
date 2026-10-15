#!/usr/bin/env bash
# Build the AeroGrid-XAI desktop POC on macOS.
# Usage: bash packaging/build_macos.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

echo "==> repo: $REPO"
echo "==> python: $(python3 --version)"

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
