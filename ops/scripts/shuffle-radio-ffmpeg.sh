#!/usr/bin/env bash
set -euo pipefail

[[ -f /etc/shuffle-radio.env ]] && set -a && source /etc/shuffle-radio.env && set +a

MONITOR="$(pactl get-default-sink).monitor"

if [[ -z "${MONITOR:-}" ]]; then
  echo "Could not find radio_sink.monitor. Available sources:" >&2
  pactl list short sources >&2
  exit 1
fi

exec /usr/bin/ffmpeg -hide_banner -loglevel warning \
  -f pulse -i "$MONITOR" \
  -ac 2 -ar ${SAMPLERATE} \
  -vn -c:a libmp3lame -b:a ${BITRATE} \
  -content_type audio/mpeg \
  -legacy_icecast 1 \
  -ice_genre shuffle \
  -ice_name "shuffle jukebox" \
  -f mp3 \
  "icecast://source:${SOURCEPASS}@127.0.0.1:8001/stream.mp3"
