#!/bin/bash
set -euo pipefail
# Stop persistent shuffle radio streaming

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
#!/usr/bin/env bash
set -euo pipefail

PIDFILE=/tmp/radio_ffmpeg.pid
PIPE=/tmp/radio_fifo

if [[ ! -f "$PIDFILE" ]]; then
  echo "no encoder pidfile ($PIDFILE); nothing to stop"
  exit 0
fi

PID=$(cat "$PIDFILE")
if ! kill -0 "$PID" 2>/dev/null; then
  echo "process $PID not running; removing stale pidfile"
  rm -f "$PIDFILE"
  exit 0
fi

echo "stopping ffmpeg (pid $PID)"
kill -TERM "$PID"
# wait up to 10 seconds
for i in {1..20}; do
  if kill -0 "$PID" 2>/dev/null; then
    sleep 0.5
  else
    break
  fi
done

if kill -0 "$PID" 2>/dev/null; then
  echo "pid $PID did not exit; sending SIGKILL"
  kill -KILL "$PID" 2>/dev/null || true
fi

rm -f "$PIDFILE"
# Optionally remove FIFO
# rm -f "$PIPE"

echo "stopped"
