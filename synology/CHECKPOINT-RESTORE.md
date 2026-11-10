# Working Synology checkpoint — 10 November 2026

Checkpoint tag: **`checkpoint/synology-working-20261110T105305Z`**

Feature branch: `feature/synology-browser-player` in
https://github.com/judasshuffle/shuffle-player.
The annotated tag identifies the application backup commit; resolve its full
hash with `git rev-parse checkpoint/synology-working-20261110T105305Z^{commit}`.
This is a code/configuration/documentation backup, not a database, music, or
container-image backup. Creating it does not redeploy or restart anything.

## Recorded deployment

| Item | Verified value |
| --- | --- |
| NAS | GreatATuin, `192.168.68.81`, x86-64 |
| Compose project / service | `shuffle-player` / `player` |
| Project directory | `/volume1/docker/shuffle-player` |
| Windows share | `\\GreatATuin\docker\shuffle-player` |
| Container | `shuffle-player-player-1` |
| Immutable deployed image ID | `sha256:a2ead10ca12e64c993919737db15c3b2dd0190376807647be9561265448ba30c` |
| Existing mutable image tag | `shuffle-player:synology-be65178` |
| Container start time | `2026-11-10T10:48:46.454655842Z` |
| Runtime | Python 3.12.11, Alpine 3.22.1, FFmpeg 6.1.2, Mutagen 1.47.0 |
| Published NAS ports | `192.168.68.81:8001` and `:8094` → container `8080` |
| Music mount | `/volume1/Media/Media/LOSSLESS` → `/mnt/lossless`, read-only |
| Database directory | `/volume1/docker/shuffle-player/data` → `/data`, read-only |
| SQLite file | `/data/jukebox.db`, immutable read-only connections, 17,623 entries |
| Temporary compatibility cache | `/cache`, separate 512 MiB tmpfs; disposable |

At checkpoint preparation, SHA-256 comparison of all 20 application/visualizer
files in the running image matched the local source being committed. The
deployed Dockerfile, Compose file, and Docker ignore file also matched local
files. The old `be65178` image-tag suffix is historical; use the immutable image
ID above to identify the exact running build, and this Git checkpoint to identify
its application source. Documentation and ignore rules are not runtime assets.

The player includes typed artist/decade/style search, Shuffle All, per-browser
queues, artwork, original/lossless playback by default, optional MP3 conversion,
and Shufflizer with controls below Find your music. It also serves a continuous,
shared MP3 radio independent of browser queues and independent of the Pi.

Preserve `http://shuffle.tplinkdns.com:8001/stream.mp3` exactly. The same public
host/port can serve the player and direct original/MP3 track URLs. Public router
forwarding remains unverified; do not claim remote reachability based on this
checkpoint. See [REMOTE-LISTENING.md](REMOTE-LISTENING.md). No historical HTTP
lossless URL was confirmed or invented.

## Separate database backup — retain outside Git

The original verified standalone backup remains at:

`C:\Users\DanGr\Downloads\ShufflePlayerBackups\20261109-192207\jukebox.db`

Its separate NAS copy remains at:

`/volume1/docker/shuffle-player/data/jukebox.db`

Both files were verified at checkpoint preparation with SHA-256:

`4de36d001b655efe282136ab9c7491ab7920d9034a4807b1afcde9769a152c3b`

Do not overwrite an existing database during a code restore. Verify its hash,
retain the Windows backup, and keep both NAS mounts read-only. Do not run the
legacy Pi scanner, migrations, index rebuilds, resync, or pruning. Music and
SQLite contents are intentionally absent from this application backup.

## Restore source into a fresh checkout

These are future restore instructions, **not commands run during this backup**.

```powershell
git clone --branch checkpoint/synology-working-20261110T105305Z --single-branch https://github.com/judasshuffle/shuffle-player.git C:\Projects\shuffle-player-restore
git -C C:\Projects\shuffle-player-restore rev-parse HEAD
```

Use a fresh directory instead of resetting or cleaning an existing working tree.
For a future deployment, copy only application/configuration files from this
checkout to the existing NAS project directory:

- Root `.dockerignore` to the NAS project root.
- `synology/compose.yaml` to NAS project-root `compose.yaml`.
- `synology/` source and Dockerfile to the NAS project's `synology/` directory.
- `web/shufflizer/index.html`, `css/`, and `js/` to the matching NAS directories.

Leave `/volume1/docker/shuffle-player/data` and the music directory in place.
Check `docker compose config` from the NAS project directory before deployment;
it must still bind the real music and separate database directory read-only.
The Compose build context is the NAS project root, not the `synology` subfolder.

## Restore the exact retained image, if still present on this NAS

The image ID is recorded, but the image itself is not uploaded to GitHub. If it
still exists on the NAS, use it to recover the exact build without rebuilding.
From `/volume1/docker/shuffle-player`, after restoring the matching configuration:

```sh
/usr/local/bin/docker image inspect sha256:a2ead10ca12e64c993919737db15c3b2dd0190376807647be9561265448ba30c
/usr/local/bin/docker image tag sha256:a2ead10ca12e64c993919737db15c3b2dd0190376807647be9561265448ba30c shuffle-player:checkpoint-20261110t105305z
```

Create a local `compose.restore.yaml` beside the restored `compose.yaml`:

```yaml
services:
  player:
    image: shuffle-player:checkpoint-20261110t105305z
    pull_policy: never
```

Then, **only when intentionally performing a restore**:

```sh
/usr/local/bin/docker compose -f compose.yaml -f compose.restore.yaml config --quiet
/usr/local/bin/docker compose -f compose.yaml -f compose.restore.yaml up -d --no-deps --no-build player
```

## Rebuild if the exact image is unavailable

With source from the checkpoint copied as above, from the NAS project root:

```sh
/usr/local/bin/docker compose config --quiet
/usr/local/bin/docker compose build player
/usr/local/bin/docker compose up -d --no-deps player
```

The application source is fixed by the tag. The Dockerfile's Python base tag and
Alpine package repositories are not fully pinned, so a future rebuild may differ
in base/runtime dependency versions from the recorded image. Run the checks below;
do not describe a rebuilt image as byte-identical to the saved image ID.
Do not use `compose down`, remove unrelated containers, change main, or change
router/DNS rules as part of a code restore.

## Verify a future restore

Local code checks:

```powershell
python -B -m unittest discover -s tests -v
node tests/test_synology_queue.cjs
node tests/test_synology_quality.cjs
node tests/test_synology_palette.cjs
```

From the Windows checkout on this LAN, the read-only NAS checks are:

```powershell
python -B synology/verify_lan.py
python -B synology/verify_quality_lan.py
python -B synology/verify_remote_preparation.py
Get-Content -Raw synology/verify_container.py | ssh -o BatchMode=yes Dan@GreatATuin '/usr/local/bin/docker exec -i shuffle-player-player-1 python -B -'
```

Verify that the container is healthy, original audio bytes and SQLite hashes
match, source mounts are read-only, and the continuous MP3 stream supports
midstream joins. The network checks do not establish audible browser playback or
public Internet reachability. DarkRide and all unrelated services must remain
unchanged.
