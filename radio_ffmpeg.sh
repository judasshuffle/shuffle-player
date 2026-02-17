#!/bin/bash
set -euo pipefail
# Persistent ffmpeg streamer for Icecast using PCM FIFO + silence fallback

: "${SOURCEPASS:?SOURCEPASS is not set}"

ICECAST_HOST="127.0.0.1"
ICECAST_PORT="8001"
ICECAST_USER="source"
ICECAST_MOUNT="/stream.mp3"
ICECAST_URL="icecast://${ICECAST_USER}:${SOURCEPASS}@${ICECAST_HOST}:${ICECAST_PORT}${ICECAST_MOUNT}"

FIFO_PATH="/tmp/shuffle_radio.pcm"
PIDFILE="/tmp/shuffle_radio_ffmpeg.pid"
LOGFILE="/tmp/shuffle_radio_ffmpeg.log"

# Idempotency: if already running, do nothing
if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "shuffle radio_ffmpeg: Already running (PID $(cat "$PIDFILE"))"
    exit 0
fi

# Ensure FIFO exists and is a FIFO
if [[ ! -p "$FIFO_PATH" ]]; then
    rm -f "$FIFO_PATH"
    mkfifo "$FIFO_PATH"
fi


# Start ffmpeg: anullsrc is input 0, FIFO PCM is input 1, amix uses duration=first
ffmpeg -hide_banner -loglevel warning \
    -thread_queue_size 512 \
    -f lavfi -i "anullsrc=channel_layout=stereo:sample_rate=44100" \
    -thread_queue_size 512 \
    -f s16le -ar 44100 -ac 2 -i "$FIFO_PATH" \
    -filter_complex "[0][1]amix=inputs=2:duration=first:dropout_transition=2[aout]" \
    -map "[aout]" \
    -vn -c:a libmp3lame -b:a 128k \
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
#!/bin/bash
set -euo pipefail
# Persistent ffmpeg streamer for Icecast using PCM FIFO + silence fallback

: "${SOURCEPASS:?SOURCEPASS is not set}"

ICECAST_HOST="127.0.0.1"
ICECAST_PORT="8001"
ICECAST_USER="source"
ICECAST_MOUNT="/stream.mp3"
ICECAST_URL="icecast://${ICECAST_USER}:${SOURCEPASS}@${ICECAST_HOST}:${ICECAST_PORT}${ICECAST_MOUNT}"

FIFO_PATH="/tmp/shuffle_radio.pcm"
PIDFILE="/tmp/shuffle_radio_ffmpeg.pid"
LOGFILE="/tmp/shuffle_radio_ffmpeg.log"

# Check for running ffmpeg process first (idempotency)
if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "shuffle radio_ffmpeg: Already running (PID $(cat "$PIDFILE"))"
    exit 0
fi

# Create FIFO if it doesn't exist or is not a FIFO
if [[ ! -p "$FIFO_PATH" ]]; then
    rm -f "$FIFO_PATH"
    mkfifo "$FIFO_PATH"
fi

# Start ffmpeg: mix silence (anullsrc) with FIFO PCM, so stream never drops
ffmpeg -hide_banner -loglevel warning \
    -thread_queue_size 512 \
    -f s16le -ar 44100 -ac 2 -i "$FIFO_PATH" \
    -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 \
    -filter_complex "[1][0]amix=inputs=2:duration=longest:dropout_transition=2[aout]" \
    -map "[aout]" \
    -vn -c:a libmp3lame -b:a 128k \
    -content_type audio/mpeg \
    -legacy_icecast 1 \
    -ice_genre "shuffle" \
    -ice_name "shuffle jukebox" \
    -f mp3 \
    "$ICECAST_URL" \
    >> "$LOGFILE" 2>&1 &

FFMPEG_PID=$!
echo $FFMPEG_PID > "$PIDFILE"
echo "shuffle radio_ffmpeg: Started (PID $FFMPEG_PID)"
  -c:a libmp3lame -b:a 128k -ar 44100 -ac 2
  -content_type audio/mpeg -f mp3 "$ICECAST_URL"
)

# Run ffmpeg in the foreground and write PID
"${FFMPEG_CMD[@]}" &
FFPID=$!
echo "$FFPID" > "$PIDFILE"

# Wait for ffmpeg to exit (keeps the script long-running so PIDfile is reliable)
wait $FFPID

# If ffmpeg exits for any reason, cleanup happens via trap
exit 0
