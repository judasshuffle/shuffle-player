# Rolling station queue — 11 November 2026

The queue is disposable. Do not capture or restore the previous all-library
queue during deployments. This supersedes the preservation procedure in the
earlier continuity record.

## Programme rules

- **Shuffle All** samples individual tracks from the full indexed library.
  Unavailable files are excluded when selected. Duration comes from the existing
  index; missing durations are read from the selected file's tags. An unreadable
  duration uses a four-minute planning estimate, without writing metadata.
- The current song's remaining duration plus upcoming songs targets 3,600 seconds.
  The last whole song can take it over the target. Each completion replenishes
  the buffer, both with listeners and with only the station clock running.
- Random picks prefer a different artist, avoid the last 50 completed or skipped
  tracks where possible, and mix albums. There are no duplicate random tracks in
  the upcoming buffer. A small filtered library can produce a shorter buffer;
  it cycles using the oldest recent candidates when alternatives run out.
- **Play matches / Play now** replaces the programme with a rolling random mix
  from that search's available individual tracks. The pool retains the artist,
  decade or style constraint for future top-ups. `play 70s Bob Dylan` keeps its
  1970–1979 Dylan pool and mixes albums; it does not choose entire albums.
- **Add to queue** keeps the current song, then existing requests, then new
  requests, then random picks. Replanning the random tail keeps requests ahead
  of it. Adding requests never resumes a deliberate Pause.
- **Play the album Blonde on Blonde** is an explicit exact album-title request.
  All songs play in disc and track order even if the album exceeds an hour.
  Disc tags are read from just those files when absent from SQLite. Ambiguous
  duplicate disc/track positions or missing ordering fail with a review message
  instead of silently scrambling an album. Library shuffle follows the album.
- Ten prior queue entries remain for Previous. They do not count towards the
  hour ahead. The larger candidate pool is metadata, not an audio playback queue.

## Verification

`python -B -m unittest discover -s tests -p test_station_programming.py -v`
checks horizon size, artist/album mixing, recent avoidance, bounded history,
filtered replenishment, request priority during Pause, paused startup, ordered
over-hour albums and library resumption. It also encodes real short WAV tracks
past the initial batch, keeps the same subscriber and decodes the output MP3.

`node tests/test_dr_screen_station.cjs --rolling` uses the actual Python station,
FFmpeg and screen in Edge: six short-track completions past the initial buffer,
audible PCM, one MP3 request, one main-page navigation, and no Next command.
The standard invocation checks natural advancement and deliberate Pause.
The existing 21 Python player tests and seven JS suites cover compatibility,
read-only delivery, permissions, tablet signing, screen volume and browser UI.

An isolated NAS container with the existing mounts read-only verified a fresh
18-track buffer of about 66 minutes, 49 matching 1970s Dylan candidates, and the
actual 14-song Blonde on Blonde sequence from Rainy Day Women through Sad-Eyed
Lady of the Lowlands. Local/browser checks do not replace in-world listening.

## Deployment procedure

Deployed image: `sha256:8114fcea13ad48d5bc2689ee6e37c58470c3193a843737f10a8945b0318f7e1d`.
The previous queue was discarded; startup produced 14 tracks / 63.32 minutes,
playing. Rollback configuration is retained on the NAS at
`/volume1/docker/shuffle-player/before-rolling-20261111T142457Z`.
Public screen output produced measurable PCM (RMS 0.00475) with one audio
element. Signed owner state/search, public asset hashes and access restrictions
passed. The SQLite and Hurricane source hashes remain unchanged. Ports, owner
key, read-only mounts and DarkRide container/start time were retained.

Build `shuffle-player:rolling-shuffle-20261111`, retain the old image and Compose
configuration, and read only the old station's playing/paused state with an owner
signature. Set `SHUFFLE_START_PAUSED` to `0` when playing, or `1` when paused.
Recreate only Compose service `player`; discard the old queue. The replacement
starts a fresh library hour, preserving deliberate Pause from process startup.
Do not walk the old queue's windows, copy music, rebuild SQLite or rotate keys.

Keep the public URL `http://shuffle.tplinkdns.com:8001/stream.mp3`, port mappings,
read-only music/SQLite/key mounts, and read-only root filesystem. Keep DarkRide
running. `verify_dr_remote.py` checks signed owner state/search and public assets
without authorised queue mutations; `verify_container.py` checks source/index
hashes through the read-only mounts. Historical live-station verification scripts
can replace the programme and should not be used as deployment smoke checks.
