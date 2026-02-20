#!/usr/bin/env bash
set -euo pipefail

cd /home/dan/shuffle-player/src

# Prefer a project venv if it exists, otherwise fall back
if [[ -x /home/dan/shuffle-player/.venv/bin/python ]]; then
  PY=/home/dan/shuffle-player/.venv/bin/python
elif [[ -x /home/dan/asr-env/bin/python ]]; then
  PY=/home/dan/asr-env/bin/python
else
  PY=/usr/bin/python3
fi

exec "$PY" /home/dan/shuffle-player/src/voice_loop.py
