# Synology browser player — fixture-only first version

This separate application searches an existing `tracks` table and plays its music
in the PC browser. No Pi, MPV, systemd, NAS credentials, scanner, migration, or
schema setup is used. The original application and scanner commits remain intact.

The local demo image contains three newly generated 16-second WAV tracks and a
fourth missing-track entry. Its SQLite database is created once at image build,
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
