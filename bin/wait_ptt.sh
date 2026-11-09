#!/usr/bin/env bash
set -euo pipefail

PIN="${1:-17}"
CHIP="${2:-gpiochip0}"

# Strong debounce (button bounce was giving duplicate edges)
DEBOUNCE="200ms"

# Wait for a real press then a real release
gpiomon -c "$CHIP" -b pull-up -p "$DEBOUNCE" -e falling -n 1 -q "$PIN" >/dev/null
gpiomon -c "$CHIP" -b pull-up -p "$DEBOUNCE" -e rising  -n 1 -q "$PIN" >/dev/null
