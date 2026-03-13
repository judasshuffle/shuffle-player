Shuffle Player

Raspberry Pi shuffle radio with voice control, internet streaming, and lossless listening.

Shuffle Player is a personal project exploring how far a small Raspberry Pi can be pushed as a music server, radio station, and voice-controlled jukebox.

It combines:

a local FLAC music library

offline speech recognition

Icecast internet radio

lossless Snapcast streaming

a simple web control panel

Features
Voice-controlled jukebox

Say things like:

play Bob Dylan
play Bob Dylan 80s

The system:

records a short voice command

transcribes it locally (no cloud)

matches an artist in your library

builds a playlist

plays it instantly

All processing runs offline on the Raspberry Pi.

Internet radio stream

Shuffle can broadcast as a public internet radio station using Icecast.

Public stream:

http://shuffle.tplinkdns.com:8001/stream.mp3

Works with:

VLC

web browsers

internet radio players

Second Life radio streams

HD Lossless listening

For full quality audio you can use the Shuffle Lossless Listener.

Download:

https://github.com/judasshuffle/shuffle-player/raw/main/releases/Shuffle-Lossless-Listener.zip

Install:

Download the zip

Extract it

Run 1-Install Shuffle Listener.bat

Use the desktop shortcut Start Shuffle Lossless

This connects directly to the Shuffle lossless stream.

Web control panel

Shuffle includes a small browser control panel to manage the system.

You can:

start / stop the radio

switch stream modes

monitor services

control playback

Example layout:

Shuffle Control

MPV Status
Icecast Status

Stream Mode
[ Public MP3 ]   [ HD Lossless ]

Radio Control
[ Start Radio ]  [ Stop Radio ]
Architecture
                Voice Commands
               (faster-whisper)
                      │
                      ▼
                 Shuffle Player
                      │
                      ▼
                     mpv
                      │
                      ▼
                Audio Output
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
 Icecast Internet Stream       Snapcast Lossless
      stream.mp3              Shuffle Listener
Project Structure
shuffle-player
│
├─ src
│   ├─ voice_loop.py
│   ├─ build_jukebox_index.py
│
├─ web
│   └─ control panel
│
├─ releases
│   └─ Shuffle-Lossless-Listener.zip
Setup (high level)

Mount your music library:

/mnt/lossless

Create an artist list:

ls -1 /mnt/lossless > artists.txt

Build the music index:

python build_jukebox_index.py

Start the voice player:

python voice_loop.py
Example voice commands
play Bob Dylan
play Bob Dylan 80s
play Miles Davis

Shuffle will automatically generate a playlist from the indexed library.

Status

This is a personal learning project exploring:

local speech recognition

Raspberry Pi audio systems

streaming architectures

automation and control panels

It is intentionally experimental and opinionated rather than a polished commercial product.

License

MIT License 