#!/usr/bin/env bash
# uninstall.sh — stop and remove the AeroGrid launchd plists.

set -euo pipefail

DST="${HOME}/Library/LaunchAgents"

found=0
for plist in "${DST}"/com.forgex4.aerogrid.*.plist; do
    [ -e "${plist}" ] || continue
    label="$(basename "${plist}" .plist)"
    launchctl bootout "gui/${UID}/${label}" 2>/dev/null || true
    rm -f "${plist}"
    echo "removed ${label}"
    found=1
done

if [ "${found}" -eq 0 ]; then
    echo "nothing to remove"
fi
