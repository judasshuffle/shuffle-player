#!/bin/bash
set -euo pipefail

PIDFILE="/tmp/shuffle_radio_ffmpeg.pid"
FIFO_PATH="/tmp/shuffle_radio.pcm"

if [[ -f "$PIDFILE" ]]; then
  PID="$(cat "$PIDFILE")"
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" || true
    sleep 2
    if kill -0 "$PID" 2>/dev/null; then
      echo "shuffle radio: PID $PID did not terminate, sending SIGKILL"
      kill -9 "$PID" || true
    fi
    echo "shuffle radio: Stopped ffmpeg (PID $PID)"
  fi
  rm -f "$PIDFILE"
else
  echo "shuffle radio: Not running"
fi

if [[ -p "$FIFO_PATH" ]]; then
  rm -f "$FIFO_PATH"
fi
