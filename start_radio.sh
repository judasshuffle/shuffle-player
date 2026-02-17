#!/bin/bash
set -euo pipefail
# Start persistent shuffle radio streaming

PIDFILE="/tmp/shuffle_radio_ffmpeg.pid"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "shuffle radio: Already running (PID $(cat "$PIDFILE"))"
  exit 0
fi

"$SCRIPT_DIR/radio_ffmpeg.sh"
#!/usr/bin/env bash
set -euo pipefail

# Start the persistent ffmpeg encoder (radio_ffmpeg.sh).
# Configure ICECAST_URL before calling (or edit this script to set it).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE=/tmp/radio_ffmpeg.pid
LOG=/tmp/radio_ffmpeg.log

# Example: export ICECAST_URL=icecast://source:password@localhost:8000/mount
: "${ICECAST_URL:=icecast://source:password@localhost:8000/mount}"
export ICECAST_URL

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "ffmpeg encoder already running (pid $(cat "$PIDFILE"))"
  exit 0
fi

nohup "$SCRIPT_DIR/radio_ffmpeg.sh" >> "$LOG" 2>&1 &
# Give ffmpeg a moment to start and write PID
sleep 1
if [[ -f "$PIDFILE" ]]; then
  echo "started ffmpeg (pid $(cat "$PIDFILE")), log=$LOG"
  exit 0
else
  echo "failed to start ffmpeg — check $LOG" >&2
  exit 1
fi
