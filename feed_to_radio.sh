#!/usr/bin/env bash
set -euo pipefail

FIFO="/tmp/shuffle_radio.pcm"
LOCK="/tmp/shuffle_radio_feed.lock"
SAMPLERATE="${SAMPLERATE:-44100}"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /path/to/audiofile [more files...]"
  exit 1
fi

if [[ ! -p "$FIFO" ]]; then
  echo "FIFO not found at $FIFO. Start the radio encoder first."
  exit 1
fi

exec 9>"$LOCK"
flock -n 9 || { echo "Another feed is in progress."; exit 1; }

for INFILE in "$@"; do
  [[ -f "$INFILE" ]] || { echo "Missing file: $INFILE"; continue; }

  ffmpeg -y -hide_banner -nostdin -loglevel error \
    -re -i "$INFILE" \
    -vn -ac 2 -ar "${SAMPLERATE}" \
    -f s16le -acodec pcm_s16le \
    "$FIFO"
done
