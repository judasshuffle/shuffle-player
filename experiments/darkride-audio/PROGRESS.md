# Shuffle → DarkRide: paused progress, 24 October 2026

Work stopped at the user's request. No further experiments or builds were started.

## Confirmed result

**One avatar has been tested.** The live Shuffle music is audible at a temporary
speaker in cromptonmoor and fades with distance. Multi-avatar playback and
listener synchronization remain unverified. This supersedes earlier conversation
statements claiming that two avatars had been tested.

The existing public Icecast URL responded with HTTP 200. FFmpeg identified
128 kb/s, 44.1 kHz stereo MP3. The local bridge receives that live stream once,
decodes it into two-second, 24 kHz/16-bit mono WAV chunks, and serves a bounded
in-memory queue on **127.0.0.1:18791 only**. The broadcaster's viewer uses
`SoundCache.getSound` and `Audio.playSound(..., localOnly: false)` at the speaker's
coordinates. This is delayed live audio, not a prerecorded substitute.

The original bridge completed a three-minute decoding run. A separate 30-second
probe verified changing, non-silent audio, correct WAV format and no bridge
restarts. These checks do not establish gapless in-world playback.

## Known problem and saved fix

Playback has audible gaps/clicks roughly every two seconds. The original viewer
logs also showed occasional longer stalls while fresh chunks continued arriving.

`speaker.js` now uses a wall-clock schedule instead of starting the next injector
inside the previous injector's `finished` callback. It polls for chunks separately,
bounds the pending queue and returns to recent audio after stalls. The revision
was saved and reloaded into the viewer, initially off, but **has not completed a
listening test or a two-minute validation**. Treat it as an untested fix.

It still creates a separate injector for every two-second WAV. Accurate JavaScript
timing alone cannot guarantee sample-continuous playback, shared mixer buffering
or click-free transitions between separate injectors. Gapless music is not achieved.

## API findings

Reviewed current DarkRide source at `8e5744e7694fbf29be52464497bda29939369742`
and the user's viewer source at `96723e851d5363569f8113eaa28f23d03fa9394c`.
The running binary's exact correspondence to that checkout was not independently
established.

- `libraries/networking/src/HTTPResourceRequest.cpp` reads the completed HTTP
  response; `libraries/audio/src/Sound.cpp` processes it in `downloadFinished`.
  SoundCache is not an incremental Icecast decoder.
- `libraries/script-engine/src/AudioScriptingInterface.h` exposes file-backed
  `playSound`, not a public append-PCM/ring-buffer injection API.
- `AudioInjector` supports positional playback but has no script-facing PCM append
  method. It sends uncompressed 24 kHz audio to the mixer in the inspected source.
- Entity server scripts and assignment clients have audio APIs, but that does not
  establish a continuous live PCM input. `Agent.takeHeardAudio` is an output/read
  API, not an injection API. No supported continuous PCM append path was found in
  the inspected interfaces; investigation is not exhaustive.

Read-only Pi inspection established Snapcast at **192.168.68.57:1704**, configured
as **PCM, 48 kHz, 16-bit stereo**. Source FLAC files must not be confused with this
transport codec. Snapcast support has not been implemented in this bridge.

## Saved files

- `bridge.py`: local live MP3 decoder and bounded WAV HTTP service.
- `speaker.js`: temporary domain speaker, broadcaster click on/off and +/- volume;
  includes the untested scheduler fix.
- `probe_bridge.py`: read-only 30-second bridge validation, previously run.
- `capture_output.py`: untested 125-second default-speaker loopback capture and
  near-silence analysis. Prepared but **never run**; it refuses microphone capture.
  Silence measurements alone would not prove the absence of clicks.
- `.gitignore`: excludes downloaded runtime dependencies, caches, logs and audio.
  Isolated FFmpeg and capture packages remain locally in `.runtime` and `.capture`;
  they are not committed or installed into the system Python environment.

## Resume here

1. Start `python experiments/darkride-audio/bridge.py --run-seconds 1800` from the
   repository. It uses the locally downloaded FFmpeg, or accepts `--ffmpeg PATH`.
2. In the broadcaster viewer only, enter cromptonmoor, open Running Scripts
   (Ctrl+J) and load `http://127.0.0.1:18791/speaker.js`. Stop/reload any previous
   copy first to avoid duplicate broadcasters. The script accepts cromptonmoor's
   user-confirmed UUID `6ad726af-0095-1000-8000-3b449dbf752a`.
3. Click the new blue box to start. Listen continuously for at least two minutes;
   collect `SHUFFLE: ... lateMs=` viewer logs and, if useful, output-only capture.
   Report all remaining clicks, stalls and gaps without treating log timing as
   an acoustic measurement.
4. If gaps persist, finish checking existing supported continuous audio inputs
   and a persistent injection stream with jitter buffering and audio-clock timing.
   Do not substitute larger disconnected files and call that gapless. If a proper
   solution requires viewer/server code changes, explain that boundary and stop:
   rebuilding either is outside the user's constraints.
5. Once continuous playback works, test a second avatar, distance fading, remote
   listening, synchronization, on/off, volume and recovery after interruption.

## State left at pause

The most recently created test speaker is
`{32b6685e-1ba6-4cb6-ba85-0a5519bdb2e3}`, near
`(5005.395, 5015.621, 5009.481)`. It was created at about 09:58 BST with a one-hour
lifetime. Stopping its script removes its two temporary entities. The current
bridge run was already bounded to 30 minutes and ends around 10:21 BST; no new
test was started after the pause request. The revised script was last observed off.

The Raspberry Pi was only read/streamed from: no restart, configuration change,
installation or write. No DarkRide server configuration or binaries were changed;
only the explicitly requested temporary in-world entities were created. No
additional internet port was exposed, no public stream URL changed, and no viewer
or server build or Synology migration was performed.
