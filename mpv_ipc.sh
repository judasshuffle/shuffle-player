#!/usr/bin/env bash
set -euo pipefail
SOCK=/tmp/radio_mpv.sock

if [ ! -S "$SOCK" ]; then
  echo "mpv socket not found: $SOCK"
  exit 1
fi

# Usage:
#   ./mpv_ipc.sh '{"command":["playlist-next","force"]}'
msg="$1"
printf '%s\n' "$msg" | socat - "$SOCK"
