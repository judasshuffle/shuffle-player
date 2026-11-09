# Music-library setup demonstration

Open `/setup` on the preview to step through local-folder or NAS instructions,
existing-index or new-library selection, read-only validation, and explicit
confirmation. This stage is a dialogue prototype: every database and WAV file is
generated in an owned temporary directory. Confirmation never launches a scanner
or creates a user index. The synthetic dashboard's controls remain mocked.

Try these demonstrations:

1. Compatible index + `/music`: three existing entries; one unchanged, one
   changed, one missing retained, plus one new file. Database remains unchanged.
2. Different-path index + `/music`: blocked. Set `/mnt/lossless` and validate
   again: accepted, without rewriting the index.
3. Incompatible schema: blocked; no migration or replacement offered.
4. Unavailable NAS simulation: blocked; no scan permitted.
5. New library: validation creates no index; confirmation is simulated only.

Run `python -B preview/demonstrate_setup.py` to exercise these dialogues through
a temporary loopback HTTP server. It prints the actual responses and stops the
server on completion. Run `python -B -m unittest discover -s tests -v` for the
preservation tests, including byte-for-byte hashes of all fixture files before
and after validation and confirmation.

## Run the fixture-only Docker demo

Build with `docker --context desktop-linux build -f preview/Dockerfile -t
shuffle-library-setup:demo .` (one line). Run a **new** uniquely named container on
an unused loopback port, e.g. `127.0.0.1:8093:8092`, without disturbing the 8092
preview. Use `--read-only --tmpfs /tmp:rw,noexec,nosuid,size=16m --cap-drop=ALL
--security-opt=no-new-privileges`. The tmpfs holds only disposable demonstration
fixtures. No music or database mounts are needed. This work does not start or
deploy that container.

## What a real installation will need (not enabled in this demo)

- A folder readable by the Docker host. For NAS music, mount SMB/NFS on the host
  first, or use a separately configured Docker-managed network mount. Windows
  mapped drives must be tested for accessibility from Docker Desktop; do not
  assume the Linux engine inherits the user's share authentication.
- Read-only music access. Use long-form bind mounting with missing-source
  creation disabled (`bind.create_host_path: false` in Compose). No privileged
  app container or Docker socket is needed. The wizard will explain the mount;
  it cannot mount arbitrary host folders from the browser.
- Keep credentials in the host credential manager or a private mount credential
  file outside this repository. Never enter passwords in the wizard or bake
  them into an image, Compose file, environment file, generated command or log.
- Keep the SQLite directory, including WAL/SHM files, and backups on persistent
  **local** storage, separate from the NAS. Never store the only index in a
  container's writable layer or automatically remove its volume.
- New libraries may use `/music` inside the container. Existing indexes require
  their original absolute path prefix, for example `/mnt/lossless`. Mount there
  rather than changing stored paths. Set `JUKEBOX_MUSIC_ROOT` consistently and
  align `JUKEBOX_DB_PATH` and the voice loop's `JUKEBOX_DB` in a future adapter.
- Validate existing databases read-only and require compatible columns. The demo
  uses immutable reads only for its own closed fixtures and rejects WAL/journal
  files. A real adapter must use a verified consistent offline snapshot or a
  separately reviewed read-only strategy; it must not ignore active WAL data.
- A real indexing stage is deliberately deferred. It must retain the preserved
  scanner's consistent backup, exclusive scan lock and mtime/size comparison,
  while disabling schema initialization, `--force`, pruning, and automatic
  database creation for existing indexes. It must never run the current resync
  wrapper unchanged, because that wrapper invokes `--prune`.
- Require explicit scan confirmation after validation, then revalidate the
  source identity and database. Check mount identity/readability before and
  during traversal; stop on disconnect or read errors and retain every missing
  entry. A directory existing alone is insufficient proof that a NAS is mounted.
  Filesystem checks can time out slowly on unavailable network mounts; the real
  worker needs bounded execution and cancellation.
- Interrupted incremental work should retain committed batches and skip their
  unchanged files on retry. It still enumerates the library; it never clears or
  fully rebuilds the index. Initial creation is allowed only for an explicitly
  selected new library and a verified unused destination, never over an index.

No production application or scanner code is changed by this demonstration.
