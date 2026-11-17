# Sources live migration

The exact previous live application was backed up to GitHub before promotion:
[backup/synology-live-20261117](https://github.com/judasshuffle/shuffle-player/tree/backup/synology-live-20261117),
commit `df845f4dc1659180950d5cdece0a87e791398043`.
Its code archive preserves all 33 deployed application/visualizer files byte for
byte. Credentials, settings, databases, music and station state are excluded.

`deploy-sources.py` stages/builds the new application before replacing the live
player. It checks the audited old image, records a private NAS rollback backup,
pins the old image, and tests the new image in a container with no published
ports. That preflight checks startup remains paused and library search works.

The live service retains ports 8094 (owner LAN player) and 8001 (listening), the
existing owner key, and read-only music/backup mounts. Separate persistent
`working` and `settings` directories are added under the live deployment root.
The tested preview index is promoted through SQLite's backup API while holding
the preview scan lock. Existing settings and working databases are never reset.
Fresh live source settings import saved stations but keep the current library
programme. The live listening address is taken from the old runtime configuration,
not embedded as a release default. No outside-home test is automatically claimed.

The user explicitly waived queue preservation. The new station starts paused
with a fresh disposable library queue. No restore, toggle, skip or source-change
command is sent to the live service during migration. Saved stations, private
connection settings and the tested working library are promoted separately.

The NAS rollback directory keeps the old Compose/code/image details and available
station snapshot. On failure, the helper restores the old image and configuration
while retaining Pause; the ordered queue snapshot is kept for recovery instead
of calling legacy commands that might resume playback. Preview and DarkRide
containers are not restarted. The original 17,623-track backup hash is checked
before and after migration.

The live endpoints remain:

- Owner player: `http://192.168.68.81:8094/`
- Sources/setup: `http://192.168.68.81:8094/sources`
- Existing public screen and stream retain their current host and port 8001.

This change does not modify router forwarding, DNS, DarkRide entities or the
in-world installer. Starting the player remains an explicit owner action.

## Completed live deployment - 17 November 2026

Release code commit: `50d2ca3636586079c083c7f8f7fc67ca40c6256d` on
`feature/synology-browser-player`.

Deployed image:
`sha256:7f1539105807b5136269e322e8c9cd1393c67e2d63d958b44d764c563ce68f10`

Private NAS rollback directory:
`/volume1/docker/shuffle-player/before-sources-20261117T093423Z`.

Preflight and live checks passed. The live working index has 17,719 entries;
the original 17,623-track backup hash is unchanged. Music, original database and
owner-key mounts remain read-only, the application root is read-only, and live
working/settings mounts are separate from preview. Owner key and both listening
ports are unchanged. The DarkRide container ID/start time were checked unchanged.
The disposable queue was rebuilt as the user requested. Playback remains paused.

The user's Dismuke URL passed the server's audio-decode test and was saved as a
station in the private live settings. It was not selected, embedded in release
defaults, or used to resume playback.

An isolated real Edge check against the live service passed: owner unlock,
Sources/guided setup, Dismuke's saved entry, two sample-album search results,
listening-port hint 8001, owner-only connection settings, and the existing public
screen with its old `music-feed` query suffix. The screen consumed the live MP3
while the station remained paused (silence is intentional). No transport, skip,
shuffle, scan or source-change command was sent during this live acceptance test.
