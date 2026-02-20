#!/bin/bash
set -euo pipefail

: "${SOURCEPASS:?SOURCEPASS is not set}"

ICECAST_HOST="127.0.0.1"
ICECAST_PORT="8001"
ICECAST_USER="source"
ICECAST_MOUNT="/stream.mp3"
ICECAST_URL="icecast://${ICECAST_USER}:${SOURCEPASS}@${ICECAST_HOST}:${ICECAST_PORT}${ICECAST_MOUNT}"

FIFO_PATH="/tmp/shuffle_radio.pcm"
PIDFILE="/tmp/shuffle_radio_ffmpeg.pid"
LOGFILE="/tmp/shuffle_radio_ffmpeg.log"
BITRATE="${BITRATE:-128k}"
SAMPLERATE="${SAMPLERATE:-44100}"

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "shuffle radio_ffmpeg: Already running (PID $(cat "$PIDFILE"))"
  exit 0
fi

if [[ ! -p "$FIFO_PATH" ]]; then
  rm -f "$FIFO_PATH"
  mkfifo "$FIFO_PATH"
fi

ffmpeg -hide_banner -loglevel warning \
  -f lavfi -i "anullsrc=channel_layout=stereo:sample_rate=${SAMPLERATE}" \
  -thread_queue_size 512 \
  -f s16le -ar ${SAMPLERATE} -ac 2 -i "$FIFO_PATH" \
  -filter_complex "[0][1]amix=inputs=2:duration=first:dropout_transition=0,aresample=async=1:first_pts=0[aout]" \
  -map "[aout]" \
  -vn -c:a libmp3lame -b:a "$BITRATE" \
  -ar ${SAMPLERATE} -ac 2 \
  -content_type audio/mpeg \
  -legacy_icecast 1 \
  -ice_genre "shuffle" \
  -ice_name "shuffle jukebox" \
  -f mp3 \
  "$ICECAST_URL" \
  >>"$LOGFILE" 2>&1 &

FFMPEG_PID=$!
echo "$FFMPEG_PID" > "$PIDFILE"
echo "shuffle radio_ffmpeg: Started (PID $FFMPEG_PID)"
