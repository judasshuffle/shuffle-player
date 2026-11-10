# Synology browser player

The working deployed version and future recovery procedure are recorded in
[CHECKPOINT-RESTORE.md](CHECKPOINT-RESTORE.md). SQLite and music are separate
from the GitHub application-code backup.

## Live NAS deployment — 10 November 2026

Shufflizer's Bank, Preset, and Palette controls now sit in their own panel between
Find your music and Search results. The iframe contains the display only.
The Synology UI adapter reads controls from the parent document while keeping
renderer state, palette preferences, custom colours, and shared browser audio
inside the existing Shufflizer runtime. The Pi visualizer sources are unchanged.

Remote listening addresses and the routing cutover are documented in
[REMOTE-LISTENING.md](REMOTE-LISTENING.md). The exact legacy MP3 URL remains
`http://shuffle.tplinkdns.com:8001/stream.mp3`. Synology also serves a shared,
on-demand MP3 radio at that path, plus the same player and per-track original/MP3
audio through NAS port 8001. The existing LAN port 8094 is retained. Public
router forwarding is a separate, unverified cutover; no DNS or router rule has
been changed by this deployment.

Playback quality defaults to **Lossless / original**: the original file bytes are
served directly, with no lossless-format conversion. The browser checks each
track's MIME type with `canPlayType` and suggests **MP3 compatibility** when
native support is not reported. Ogg FLAC is not introduced. Original lossy files
retain their original quality; selecting this mode cannot make them lossless.
The selector saves `shuffle.playback.quality` in browser local storage. Switching
keeps the queue, current track, pause/mute state, and restores playback time after
the replacement source's metadata loads. Rapid changes cancel stale playback.

MP3 is encoded on demand by the NAS container (256 kbps, stereo, 44.1 kHz).
The first request waits for conversion so the complete MP3 supports byte ranges
and seeking. Only disposable outputs are cached in `/cache`, a separate 512 MiB
RAM filesystem; completed outputs are limited to 256 MiB. One encoder runs at a
time, with a 180-second timeout. The cache is not in the music mount, `/data`, Git,
or the image and disappears with the container. No Pi service is contacted.
The application root, music, and database remain read-only.

`node tests/test_synology_quality.cjs` covers defaults, persistence, quality
switches, playback position, pause/mute state, rapid changes, and failure recovery.
The Python tests exercise real MP3 encoding, seeking/range reuse, unavailable
encoders, and unchanged source/index hashes. The demo image also includes FFmpeg;
MP3 mode requires a writable `/cache` tmpfs (the real Compose project supplies it).

The compact listening area comes first: album art alongside Shufflizer, followed
by transport/audio controls. Search and Shuffle All sit immediately below it;
search tips and musical styles expand on demand. Results and the playlist are
lower on the page so a long queue cannot push the listening area out of reach.

Musical styles: the browser lists 53 broad style families plus subgenres from
the existing index (133 choices in the supplied backup). Counts describe indexed
tags and can overlap. Unsupported/empty families are disabled; 1,777 untagged
tracks remain accessible through normal search and Shuffle All. Commands include
`play blues`, `queue genre disco`, `play 70s genre jazz`, and `genre: bossa nova`.
`play artist Pop` forces artist matching when a name overlaps a style.
Genre families include aliases and related subgenres; raw tags are never changed.
This reads SQLite genre values only, with no audio scanning or index rebuild.

The visualizer Palette menu now initialises after preset state is available.
Preset and Custom colours update the visualizer and the whole player theme,
including panels, buttons, text, borders, and inputs. Preferences restore from
browser local storage, including custom RGB/RGBA values. The shared Pi visualizer
sources are unchanged; Synology serves its own palette bootstrap and adaptations.
`node tests/test_synology_palette.cjs` exercises the actual selector, renderer
globals, frame-to-player theme changes, and saved Custom palette restoration.

Play matches replaces the browser queue and starts its first match. Per-track
Play also replaces the queue; Queue matches and Add to queue append.
Decades accept `80's`, `80s`, `1980s`, and curly apostrophes.
Current-track artwork reads embedded FLAC/ID3/MP4/Vorbis pictures first, then
checks conventional cover/folder/front JPEG, PNG, or WebP names beside that track.
Missing artwork displays a placeholder. Artwork is requested on demand, with no
disk cache, folder enumeration, or index changes. Mutagen 1.47.0 reads metadata
through files opened in binary read-only mode.

LAN URL: http://192.168.68.81:8094. Separate Compose project `shuffle-player`,
deployed in `/volume1/docker/shuffle-player` on GreatATuin (x86-64).
`compose.yaml` is copied to that directory with the application build context.
The SMB configuration confirms `docker` maps to `/volume1/docker`.

The real deployment uses `synology/Dockerfile`, without generated fixtures.
It runs as `1026:100`, with a read-only root filesystem, dropped capabilities,
and no-new-privileges. Only the NAS LAN address binds port 8094.
Music is bound read-only from `/volume1/Media/Media/LOSSLESS` to `/mnt/lossless`.
The dedicated data directory is bound read-only to `/data`.
No credentials are needed in the image or repository.

The supplied standalone backup was copied without overwriting an existing file.
Its SHA-256 on Windows and inside the container is
`4de36d001b655efe282136ab9c7491ab7920d9034a4807b1afcde9769a152c3b`.
Read-only SQL confirms 17,623 tracks. LAN Shuffle All pagination returns all
17,623 entries, of which 17,621 files are available; unavailable entries remain
in the index. `play 70s Bob Dylan` returns 49 available matches.
Full Hurricane FLAC delivery matches the NAS source SHA-256:
`73213176644d35c839a23711708cdf22816679f78af0a4d2148e399e6d837762`.
Byte ranges, HEAD, Shufflizer assets, and a 15-second FFmpeg decode pass.
Terminal checks verify delivery and decoding, not audible browser playback.

`python -B synology/verify_lan.py` repeats read-only LAN delivery checks.
`synology/verify_container.py` can be piped to Python in the running container
to compare the database and source audio hashes without changing them.
The original Pi, original database, music, and other containers were untouched.

The following sections document the original fixture demo and its pre-deployment
requirements; the verified paths and live deployment above supersede the earlier
unknown-path and deferred-deployment statements.

## Original fixture demonstration

This separate application searches an existing `tracks` table and plays its music
in the PC browser. No Pi, MPV, systemd, NAS credentials, scanner, migration, or
schema setup is used. The original application and scanner commits remain intact.

The local demo image contains nine newly generated 16-second WAV tracks and one
missing-track entry. Its SQLite database is created once at image build,
closed, made read-only, and served from a read-only container filesystem. There
are no host mounts. The queue exists only in each browser tab's memory.

## Local demonstration

Build `synology/Dockerfile.demo` with the repository root as context. Use an unused
loopback port, for example `127.0.0.1:8094:8080`, and a distinct container name.
Run with `--read-only --cap-drop=ALL --security-opt=no-new-privileges` and no mounts.
The existing 8092 and 8093 containers need not be stopped or changed.

At `/`, search for Copper, Orbit, Preview Synth, or Synthetic Sessions. Click Play
to hear a pulsed test tone and feed the embedded Shufflizer. Add tracks to the
queue, reorder playback by selecting a queue item, remove items, pause, seek, and
change volume using the native player. Queue completion advances automatically.
Missing entries stay visible but cannot be queued. No VU UI is added.

**Shuffle All** reads all rows from the existing index in batches, omits unavailable
files from the browser queue, shuffles the available tracks and starts playback.
It never walks folders, updates metadata or changes the index. It replaces the
current browser queue. Normal Play matches also replaces the queue; Queue matches
appends without starting or interrupting playback.

Type `play 70s Bob Dylan` or `queue 1970s Bob Dylan` in the search box. Both show
artist matches for 1970–1979 and wait for Play matches / Queue matches. This is
typed command interpretation, not voice recognition. Bare text still searches
artist, album and title. Two-digit decades 00s–20s mean 2000–2029, and 30s–90s mean
1930–1999; explicit four-digit decades remove ambiguity. Artist matching uses a
case-insensitive substring with bound SQL values, not fuzzy artist recognition.

The demo additionally contains synthetic tones labelled Bob Dylan (demo), with
years 1969, 1970, 1979, 1980 and unknown. The 70s command returns exactly the 1970
and 1979 entries and reports exclusion of the undated entry. `play 70s Undated
Artist` demonstrates the missing-year error. These are generated tones, not
Bob Dylan recordings. A database without a year column refuses decade queries;
matching rows with null/invalid years are excluded and reported. No artist's
tracks are substituted without the requested decade filter. Years must be usable
four-digit values; no dates are inferred from filenames or by scanning music.

Media uses same-origin HTTP with byte-range and HEAD support. Shufflizer uses the
same browser audio element and analyser; it does not create another stream or
fetch the Pi. Each browser has independent playback. Direct browser-supported
formats are supported; this version does not transcode unsupported codecs.

## Exact information required before real data can be connected

The container paths are fixed:

| Item | Required container path | Access |
| --- | --- | --- |
| Music folder | `/mnt/lossless` | Read-only |
| Directory containing the separate backup | `/data` | Read-only |
| Closed standalone SQLite backup | `/data/jukebox.db` | Read-only |

**The NAS-side absolute paths have not been verified and must be supplied.**
The SMB name `\\GreatATuin\Media\Media\LOSSLESS` does not establish which Synology
volume hosts that share. Provide the DSM-local absolute path to that exact music
directory, plus a dedicated absolute data-folder path for the separate backup.
Do not substitute a guessed `/volume1/...` path.

The backup must come from SQLite's consistent backup mechanism and be a separate
file, never the original `/home/dan/jukebox.db`. No Pi or original database has
been opened by this work. An authorized backup/export must be provided separately
before real-library testing. Do not raw-copy an active database, ignore its WAL,
or point the application at the original. Retain the delivered backup separately
from any future writable index work.

Before connecting that copy: validate its schema, confirm every track path is
under `/mnt/lossless`, and confirm no active WAL/journal files accompany it.
The app uses immutable read-only connections for this closed standalone copy.
An incompatible, missing, or journal-bearing database blocks startup; it is never
created, migrated, pruned, rebuilt, or vacuumed. Stored paths are not rewritten.
SQLite rowid tables are required in this first version. Only bounded SELECT
queries are executed after startup validation. Searching does not create indexes.

For Synology: use Container Manager with its native local-folder bind mounts,
both read-only, a non-root account with read/traverse ACL permissions, and a free
LAN-facing port. No SMB mount or password is needed when the files are on the
same NAS. Keep the service private to the trusted LAN; no authentication or
internet exposure is provided in this first version. Do not mount the Docker
socket or grant privileged mode. A real-data image without generated fixtures
and its deployment configuration are deferred until the paths, backup and target
CPU architecture are confirmed.

## Verification

`python -B -m unittest discover -s tests -v` checks typed search, SQL escaping,
audio bytes, seeking, missing files, path restrictions, blocked indexing routes,
and unchanged hashes of every test library/database file. Browser queue and
rendering still require interactive checking; HTTP tests do not prove audible
playback on the user's PC.

`node tests/test_synology_queue.cjs` tests the queue's UI code using DOM/WebAudio
test doubles: add, play, automatic next, previous, pause and missing-track state.
