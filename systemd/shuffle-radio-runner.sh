#!/usr/bin/env bash
set -euo pipefail

MONITOR="radio_sink.monitor"

ICECAST_URL="icecast://source:${SOURCEPASS}@127.0.0.1:8001/stream.mp3"

echo "=== shuffle-radio-runner starting ==="
echo "User: $(id -un) UID: $(id -u)"
echo "XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-<unset>}"
echo "PULSE_SERVER=${PULSE_SERVER:-<unset>}"

echo "--- pactl info ---"
pactl info || true

echo "--- pactl sources ---"
pactl list short sources || true

# Wait up to 60s for the monitor source to exist
for i in {1..60}; do
  if pactl list short sources 2>/dev/null | awk '{print $2}' | grep -qx "$MONITOR"; then
    echo "Found monitor source: $MONITOR"
    break
  fi
  echo "Waiting for monitor source ($i/60)..."
  sleep 1
done

# Hard fail if missing
pactl list short sources 2>/dev/null | awk '{print $2}' | grep -qx "$MONITOR"

echo "Starting ffmpeg..."
exec /usr/bin/ffmpeg -hide_banner -nostdin -loglevel info \
  -f pulse -i "$MONITOR" \
  -ac 2 -ar 44100 \
  -c:a libmp3lame -b:a 128k \
  -content_type audio/mpeg \
  -f mp3 "$ICECAST_URL"
