#!/usr/bin/env bash
set -euo pipefail

PIN="${1:-17}"
CHIP="${2:-gpiochip0}"
EDGE="${3:-falling}"   # falling=press (pull-up), rising=release
DEBOUNCE="${4:-200ms}"

# Wait for exactly one edge
gpiomon -c "$CHIP" -b pull-up -p "$DEBOUNCE" -e "$EDGE" -n 1 -q "$PIN" >/dev/null
