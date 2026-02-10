# shuffle-player

Offline voice-controlled music player for Raspberry Pi.

## What it does
- Records a short utterance (push-to-talk via Enter for now)
- Transcribes locally using faster-whisper (offline)
- Matches an artist folder from `artists.txt`
- If you say an artist + decade (e.g. "play Bob Dylan 80s"), it builds a ~1 hour playlist from your indexed metadata and plays it
- Plays audio using `mpv`

## Files
- `src/voice_loop.py` - main voice loop + playback
- `src/build_jukebox_index.py` - scans music library + writes `jukebox_index.json`

## Setup (high level)
- Mount your music at `/mnt/lossless`
- Create `artists.txt` from your library folder names:
  - `ls -1 /mnt/lossless > /home/dan/artists.txt`
- Build the index:
  - `nohup /home/dan/asr-env/bin/python /home/dan/build_jukebox_index.py > /home/dan/jukebox_index.log 2>&1 &`
- Run:
  - `source /home/dan/asr-env/bin/activate`
  - `python3 /home/dan/voice_loop.py`

## Example voice commands
- "play Bob Dylan"
- "play Bob Dylan 80s"
