#!/bin/bash
set -euo pipefail

PIDFILE="/tmp/shuffle_radio_ffmpeg.pid"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "shuffle radio: Already running (PID $(cat "$PIDFILE"))"
  exit 0
fi

"$SCRIPT_DIR/radio_ffmpeg.sh"
