# Sources preview — 17 November 2026

- Player: http://192.168.68.81:8095/
- Sources: http://192.168.68.81:8095/sources
- Screen: http://192.168.68.81:8095/dr-screen
- Preview MP3: http://192.168.68.81:8002/stream.mp3

Use the existing owner key. Unlock now survives navigation and refreshes in the
same tab. Select **Remember on this browser** to retain it across tabs and browser
restarts. **Lock** clears stored access. The key stays in browser storage; only
request signatures travel to the server. This is intended for a trusted browser.

Test and save a named direct HTTP(S) audio URL, then select it when ready.
Selection tests it again before changing playback. A failed test leaves the
current source playing. Both sources use the same shared `/stream.mp3` output.
The main player retains its original/MP3 track monitor for the library and uses
the shared MP3 for radio. Each visualizer analyses its page's existing audio.

## Deployment and preservation

Compose project `shuffle-sources-preview`, container
`shuffle-sources-preview-player-1`, lives under
`/volume1/docker/shuffle-sources-preview`. Configuration:
`app/synology/compose.preview.yaml`, build context `app`.

Production ports 8094/8001, router forwarding, the Pi and DarkRide installation
are unchanged. The existing public URL
`http://shuffle.tplinkdns.com:8001/stream.mp3` continues serving production.
Changing the isolated preview cannot change what production listeners hear.

Container root, `/mnt/lossless`, `/data` and owner-key mounts remain read-only.
`/working` is a separate persistent directory containing the working SQLite index,
scan lock, backups and scan history. It is seeded once using SQLite's backup API;
subsequent starts check and reuse it. `/settings/sources.json` is a different
persistent mount, outside the index. Source writes use atomic replacement and
the active source restores at startup.

The preserved original backup has 17,623 tracks and SHA-256
`4de36d001b655efe282136ab9c7491ab7920d9034a4807b1afcde9769a152c3b`.

## Scanning

**Scan for changes** requires the signed owner unlock. It takes a nonblocking
file/process lock and makes an automatic SQLite backup before reusing the Pi's
`scripts/update_index_sqlite.py` scanner. Pruning is disabled. Unchanged
mtime/size entries skip tag reads; changed files update by path, preserving row
IDs and original added time. Missing tracks remain indexed. Missing, unreadable
or empty music roots stop the scan, and traversal/read errors are reported.

Scanning runs asynchronously while audio continues. Player queries and the
scanner use the same working index; the station catalog and genre counts refresh
on completion. Sources shows last completion, added/updated/unchanged counts,
total and errors. Pre-scan backups under `working/backups` are retained without
an automatic deletion policy in this preview.

Two generated FLAC tones were added to the NAS folder `Shuffle Preview Sample`
by host copies, without a writable player music mount. Search **Shuffle Preview
Sample** finds both. First scan: **96 added, 0 updated, 17,621 unchanged**, total
**17,719**. The 96 are 94 existing NAS tracks absent from the supplied backup plus
the two samples. Both original missing entries remain. Second scan: **0 added,
0 updated, 17,717 unchanged**, same total, no duplicate paths. Both scans created
an automatic backup and left the original backup hash unchanged.

## Verification

- Real NAS integration: library to saved Radio Paradise to library, two HTTP
  listeners kept open, non-silent 48,000-byte PCM decodes in every phase, failed
  HTML station test isolation, unsigned control rejection, search/shuffle/skip.
- Preview restart: external source restored, working-index hash unchanged,
  read-only music/backup mounts verified, production container ID/start unchanged.
- Real isolated headless Edge against the NAS preview: main player and screen
  audio/analyser signals, loaded visualizer canvases in every source phase,
  external radio analysis packets at EventBridge, sample search, skip/shuffle,
  remembered owner unlock across navigation/refresh, no page JavaScript errors.
- Existing Edge reconnect test: induced interruption recovered while preserving
  volume, mute, single source/audio element and page.
- Local tests: 22 player HTTP/media tests, 15 station programming tests,
  queue/quality/station UI, owner signatures/session/opt-in persistence/Lock,
  incremental add/skip/changed tags/retained missing entries/read-error rollback,
  music features/relay and screen graph tests.
- Linux guards: seed only once, preserve subsequent working-index changes and
  original backup; unavailable root/held lock stop before scan or backup.

The user also reported successful playback/visualization in Edge. An earlier
interactive computer-use attempt stopped on unsupported Firefox URL policy;
subsequent headless tests used an isolated profile, not existing browser tabs.

Sources now clears transient connection errors after reconnecting. The owner
client renews its server challenge after a preview restart without key re-entry.

The audio analysis feed works for both library and radio because it measures
actual decoded audio. Existing in-world lights still follow the production
screen until a preview/new screen is connected. No in-world installer or shared
publisher setting was changed in this preview; the placeable radio is next.

## Private DarkRide connection settings

Sources now includes **DarkRide connection**, with owner-only saved stream and
screen URLs. **Use this player's URLs** fills this installation's current URLs;
**Save my connection** persists them in `/settings/connection.json`, outside the
image, music index, source archive, and release defaults. Fresh installs start
blank. The private settings file is also ignored by Git and excluded by the
Docker build allowlist. Lock clears the URL fields from the page; unsigned or
public-port requests to `/api/listening` are denied. Saved source stream URLs
are also omitted from unsigned `/api/sources` responses.

The hard-coded personal domain was removed from the player HTML, listening API
default, entity script comment, and bundled DJ script. The tracked production
Compose example no longer provides a personal domain default; the running
production deployment was not changed. Historical deployment notes retain their
record of old deployment addresses. Hosted DJ scripts derive their server from
their own URL; private local DJ installers must set
`darkride/shufflizer/server-base` in local Settings when they are implemented.

The saved connection describes the address to use in DarkRide. Saving it does
not rewrite an existing screen/entity or change router forwarding. On the same
LAN, the preview screen is `http://192.168.68.81:8095/dr-screen` and its stream is
`http://192.168.68.81:8095/stream.mp3` (the listener-only port 8002 still works too).
Production at port 8001 remains a separate station. A saved/hidden address is
not authentication on the stream itself; someone who knows a public link can
still use it.

Verification: all 23 player HTTP/media tests passed, including private-setting
save/restore, invalid-URL rejection, owner-only reads/writes and public-port
rejection. The real isolated Edge test saved preview LAN URLs, reloaded them,
verified Lock clears fields, verified unsigned source responses omit URLs,
checked personal addresses are absent from release HTML/DJ assets, and measured
live screen audio analysis. DJ/native remote and owner-unlock tests also passed.

## Guided setup for people new to streaming

Sources now guides users through four steps: hear audio at home, set up outside
listening, test on mobile data with Wi-Fi off, and copy the matching DarkRide
link. Router and troubleshooting explanations expand on demand. One public
player address generates the audio and screen URLs. Pasting an existing screen
URL also works, including an old cache-busting query; the UI extracts its base.

The public field rejects private/local/loopback/CGNAT addresses with a plain
explanation, rather than labelling a home address internet-ready. Explicit
home-only links remain supported, including previous saved URLs. Saved data is
still owner-only in the separate private settings directory.

The preview supplies `SHUFFLE_LOCAL_LISTENING_BASE` to display its actual home
address and listening-only host port in the router guide. Other installations
should supply their own value; if absent, the guide asks the owner to check their
installation instead of suggesting that they expose the owner-control port.
Existing live forwarding rules must be left intact when testing a separate
preview. No router, firewall, DNS, TLS or production deployment was changed.

A local audio-playback test reports only that audio reached that browser. It
never proves outside reachability. The outside-home confirmation is explicitly
labelled as the user's own test, not an independent probe. It is persisted only
for the saved public base and reset when that address changes. No personal URL
is sent to an external testing service. Port forwarding, reverse proxy/TLS,
firewall, double-router and CGNAT guidance is provided in plain language, with
an optional router manufacturer's guide link.

Verification: public-address validation and generation, confirmation persistence
and invalidation, existing saved-URL compatibility, all 23 player HTTP/media
tests, and owner-unlock tests passed. Real isolated Edge checked private-IP
mistakes, pasted-screen normalization, local audio without a false internet
claim, user-confirmed test/reset, correct preview router port, owner-only saved
settings, Lock, mobile layout without horizontal overflow, and real screen
audio. Temporary public `.example` addresses were restored to the prior preview
connection. Desktop and 390px phone screenshots were inspected.
