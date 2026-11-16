# Shufflizer -> DarkRide music feed, version 1

The existing screen URL stays **http://shuffle.tplinkdns.com:8001/dr-screen**.
The MP3 remains **http://shuffle.tplinkdns.com:8001/stream.mp3**. No extra port,
music connection, microphone, MIDI driver or cloud service is required.

The page's existing media-element source feeds an independent analysis branch
before the visitor-volume gain. The original 1024-point visualiser analyser and
audible path are unchanged. [music-features.js](./music-features.js) computes
features; [music-telemetry.js](./music-telemetry.js) sends them through the existing
EventBridge. [dr-screen-entity.js](./dr-screen-entity.js) validates and relays them.
No part of this feed edits lights, haze, entities, queues or station transport.

## DarkRide messages

- Local channel: `darkride.shufflizer.music.v1`, up to 20 messages/second.
- Optional shared channel: `darkride.shufflizer.music.shared.v1`, up to 10/second.
- Local is always the default. Shared publishing requires this setting on ONE
  chosen viewer, using the actual playing Web entity ID:

```js
Settings.setValue("darkride/shufflizer/musicPublisherEntity", "{YOUR-WEB-ENTITY-ID}");
```

Disable shared publishing without stopping music:

```js
Settings.setValue("darkride/shufflizer/musicPublisherEntity", "");
```

This setting selects a sender, not an authentication credential or distributed
leader election. Only configure one publisher. Shared consumers must explicitly
pin the allowed sender using the `sender` supplied by `Messages.messageReceived`
and the expected source entity; do not trust packet `sourceSession` as authority.
Never let arbitrary messages execute scripts or supply entity IDs to edit.

Envelope fields: `type:"shufflizer.music"`, `v:1`, browser `session`, analysis
`epoch`, increasing `seq`, audio-context seconds `t`, sender clock milliseconds
`wall`, `state`, advisory `stationTrackId`, `f`, `sourceEntity`, `sourceSession`.
States are `playing`, `paused`, `buffering`, `suspended`. Inactive states send
zero/silent data at approximately 1 Hz; a closed page sends nothing.

Use local arrival time for a 2-3 second stale-data timeout, not a comparison of
different machines' wall clocks. Revert gracefully to a baseline on inactivity,
silence or timeout. Visitor buffering differs; this is not sample-perfect
synchronisation with every listener. Analyse/render locally if that is essential.

`stationTrackId` comes from station polling, NOT an audible MP3 boundary: metadata
can lead buffered audio. It must not reset beat timing or trigger precisely timed
song transitions. It is an ID only, not title/artist or filesystem metadata.

## Feature fields (`packet.f`)

| Field | Meaning / units |
| --- | --- |
| `rms`, `peak`, `db` | PCM RMS, absolute sample peak, RMS dBFS (floor -120). RMS is not perceptual LUFS. |
| `energy` | RMS relative to a slowly tracked local baseline, clamped 0..1; not an automatic brightness command. |
| `bands` | Eight relative spectral **power** shares: 20-60, 60-150, 150-400, 400-1000, 1000-2500, 2500-6000, 6000-12000, 12000-20000 Hz (limited by Nyquist). |
| `bass`, `mid`, `treble` | Sums of bands 0-1, 2-4, 5-7. Not isolated kick/vocal/hi-hat stems. |
| `centroid`, `brightness` | Magnitude-weighted spectral centre in Hz and a logarithmic 0..1 colour-control proxy. Not musical pitch. |
| `rolloff` | Frequency below which 85% of measured 20Hz-20kHz spectral power lies. |
| `flatness` | Spectral noisiness proxy, 0..1; not an instrument classification. |
| `flux`, `onset` | Positive spectral change and adaptive attack strength (0..1). Brief startup warm-up suppresses false first beats. |
| `beat`, `beatId`, `beatTime` | This frame's attack trigger, monotonically increasing detected-beat counter, and its latest audio-context timestamp (or null). Musical beat tracking is heuristic. |
| `bpm`, `tempoConfidence`, `beatPhase` | Estimated 70-180 BPM, heuristic evidence score 0..1, and estimated phase since the latest attack. Null tempo/phase until supported by several attacks/history; no first-beat-of-bar claim. |
| `pitchHz`, `pitchConfidence` | Optional dominant periodicity estimate, approximately 70-1000 Hz, four times/s; null when unsupported. Confidence measures periodicity, not probability of a correct melody note. Full-rate correlation avoids decimation aliasing. Mixed music, octave ambiguities and harmonics remain difficult. |
| `dominantHz` | Strongest spectrum bin, not necessarily a fundamental frequency. |
| `chroma` | Smoothed relative pitch-class energies, C,C#,D,D#,E,F,F#,G,G#,A,A#,B; coarse 250-4000Hz FFT-bin mapping. Useful colour texture, **not** a reliable chord/key detector. |
| `trend` | Fast vs slow RMS change, -1..1: build/settle cue, not a semantic chorus/drop detector. |
| `crest`, `zcr` | Peak/RMS ratio (capped 20), waveform zero-crossing fraction. Percussiveness/texture proxies only. |
| `silent` | RMS below 0.003. Separate this from transport pause or buffering. |
| `stereo` | Null if unavailable/disabled; otherwise channel RMS `left`,`right`, `balance` (-1 left to +1 right), `correlation` (-1..1 or null in silence), `width=(1-correlation)/2`. Mono is upmixed before splitting. This is correlation-based width, not spatial source separation. |

Most values are rounded to three decimals. Relative band/chroma arrays can differ
slightly from a sum of one after rounding. Treat confidence scores as heuristic,
not calibrated probabilities. No inferred genre, lyrics, singer identity, true
downbeat, semantic song sections or polyphonic note transcription is claimed.

Deduplicate attacks using `(source, session, beatId)`, resetting consumer state
when the session changes. Use `seq` to discard duplicates/older packets. The beat
counter survives feature resets; `epoch` changes on adapter recovery/reset. Because
the shared rate is lower, `beat` may be false by delivery: `beatId`/`beatTime`
preserve the latest event, including one between outgoing shared frames.

## Performance / failure behaviour

- Native 4096-point FFT; reused typed arrays; 20 Hz extraction/transport.
- Pitch is capped to four analyses/s; tempo to once/s; onset history <=220 frames.
- Optional stereo branch uses two 1024-sample analysers. No output from any
  sidecar branch is connected to the speakers.
- Browser packet <=1080 UTF-8 bytes; relay packet <=1200 bytes. The relay checks
  source entity, schema/ranges, duplicates and rate before broadcasting.
- Normally under 1 KB per packet. Shared transport is at most about 12 KB/s from
  the selected publisher, before message/network overhead and recipient fan-out.
- Browser diagnostic objects: `window.ShufflizerMusic.last`, `.stats`, `.error`.
  Stats expose frame/drop counts and recent analysis p95 (not total viewer CPU).
- Disable all telemetry with `localStorage.setItem('shufflizer.music.enabled','false')`
  and reload. Disable stereo alone with `shufflizer.music.stereo='false'` in
  localStorage and reload. Audio/visuals keep working if the sidecar fails.
- Timers may be throttled when a Web page is hidden or suspended. Do not promise
  background analysis from the hidden floor overlay; do not re-show that opaque
  floor merely to enable music. Use an active appropriate screen surface.

## Install / validation

Both Dockerfiles include the sidecars; [.dockerignore](../.dockerignore) explicitly
allows them and continues excluding credentials/music/database. The server only
adds public static routes; station controls remain signed-owner-only.

After deployment, an already-loaded Web entity still has old code. Reload its
screen page and client entity script once, then enable screen audio if asked.
Do not restart the NAS or DarkRide domain. The first iteration deliberately
does NOT modify the approved lighting installer or automatically enable shared
publishing; connect a separately tested consumer next.

Local tests:

```text
node tests/test_music_features.cjs
node tests/test_music_relay.cjs
node tests/test_music_browser.cjs
node tests/test_dr_screen.cjs
node tests/test_dr_screen_reconnect.cjs
python -B -m unittest discover -s tests -p test_synology_player.py
python -B -m unittest discover -s tests -p test_station_programming.py -k recovery
```

The real Edge test uses a localhost synthetic stereo WAV: one stream/source,
20Hz packets, volume=0 analysis, pitch/tempo, stereo and suspend/resume. It is not
an in-world DarkRide test or proof of performance on every visitor's hardware.
The full station-programming suite currently has a Windows FFmpeg temporary-file
cleanup race in its pre-existing real-short-track test; the new recovery test
passes separately. Do not change playback logic just to mask that test cleanup.

The scoped [deployment helper](./deploy-music-feed.py) builds before downtime,
backs up the live sources/Compose/image ID and full exposed queue, recreates only
Compose service `player`, restores ordered queue/current track/position/preset
and filter, and verifies DarkRide container ID/start time are unchanged. Its
`resume_program` hint on the existing signed `replace` action preserves future
filtered top-ups; this does not relax authentication or allow library writes.
