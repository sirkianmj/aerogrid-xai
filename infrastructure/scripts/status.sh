#!/usr/bin/env bash
# status.sh — report the state of the AeroGrid launchd services.

set -uo pipefail

echo "=== launchctl entries ==="
if launchctl list | grep -q aerogrid; then
    launchctl list | grep aerogrid
else
    echo "(none registered)"
fi

echo
echo "=== listening ports ==="
for port in 5432 6379 9000 9001 8000 5173; do
    if lsof -iTCP:"${port}" -sTCP:LISTEN -n -P > /dev/null 2>&1; then
        echo "port ${port}: LISTENING"
    else
        echo "port ${port}: not listening"
    fi
done
