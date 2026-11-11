# Owner DJ remote and visitor screen

Use these verified public URLs on the Web entity:

- Source URL: **http://shuffle.tplinkdns.com:8001/dr-screen**
- Client entity script: **http://shuffle.tplinkdns.com:8001/dr-screen-entity.js**

The existing fullscreen Shufflizer and same-element MP3 audio graph remain.
Visitors use **My volume** on the screen; the setting belongs to their client
and affects only their sound, after audio analysis. Station controls stay out
of the screen. DarkRide autoplay may still require **Enable screen audio**.

## Install your DJ remote

In DarkRide Interface's Running Scripts window, load this **local private file**:

`C:\Projects\shuffle-player\synology\secrets\install-owner-remote.js`

Keep that file and the other files in its directory private and together. The
installer stores your owner signing key in your local DarkRide Settings and
loads the bundled local remote. A **SHUFFLIZER** tablet button opens its UI.
The installer, UI and signing code are local files; the private key is never
put in entity properties, shared Messages, public source, a URL, or browser HTML.
The private directory is ignored by Git and excluded from the Docker build.

Search by artist, title, album or typed command such as `play 70s Bob Dylan`.
Search only previews matches. **Play now** replaces the station queue with all
available matching tracks. **Add to queue** appends all matches without
interrupting playback. **Shuffle All** replaces the queue with all available
indexed tracks in random order. **Next** advances the shared station.
Changing the search text disables Play/Add until that search has been reviewed.

Visitors do not need this installer. Optionally, they can load the public
Interface script `http://shuffle.tplinkdns.com:8001/dr-dj.js` for a tablet remote
with personal volume only. Public-script mode never signs DJ commands, even
if a key happens to exist in Settings. No visitor is granted an owner credential.

## Server enforcement and dashboard

The dashboard remains **http://192.168.68.81:8094/**. Enter the private owner key
from `synology/secrets/owner-key` in its owner access field to unlock controls in
that tab. Locking or closing the tab removes the in-memory key. The old LAN
token has been removed: being on the LAN alone no longer permits mutations.

Only the single provisioned owner key can authorize station changes. It is a
capability paired to your client, not an avatar/display-name claim. The server
verifies HMAC-SHA256 over method, exact route, boot epoch, timestamp, nonce and
the SHA256 of the exact request body. Requests expire after 120 seconds, and
used nonces cannot replay. The boot epoch rejects signatures from before a
restart. No configured key means all station mutations fail closed. The key
stays on disk in a private NAS directory and is mounted read-only at
`/run/shuffle-owner/owner-key`, separate from the image and music/database.
The vendored js-sha256 0.11.1 library retains its MIT license.

The signed `/api/dj` endpoint handles search, state and DJ commands.
The LAN `/api/station/control` also requires signatures. Public requests to the
legacy control endpoint are rejected. Public `/` redirects to `/dr-screen`;
dashboard JavaScript and unsigned library-search endpoints return 403 on 8001.
Public station status returns no queue preview, key, or control token.

Replace the NAS owner-key file and restart the player to revoke a lost pairing;
then regenerate the private local installer with the replacement key. Do not
share the old installer or copy the key into a public script.

## Validation

`python -B synology/verify_dr_remote.py` verifies public source/assets, owner
state/search, unsigned and forged-owner rejection, replay rejection, private
dashboard routing and absence of credentials in public assets without changing
the station queue. The live MP3 also passes a three-second public decode.

The 21 Python player tests cover queue semantics, permissions, missing keys,
expired signatures, body tampering, replay and server-restart epochs. The screen,
native remote and remote UI JS tests cover volume routing, handshake, owner versus
visitor behavior, exact signature compatibility, search review and DJ buttons.
Existing queue, station, quality and palette regressions also pass.

Judas confirmed in-world screen audio, beat-reactive Shufflizer visuals and
tablet queue control on 11 November 2026. This is user-confirmed client behavior,
separate from HTTP delivery/decoding and script tests. Remote visitor playback
and lossless playback remain unverified; do not infer either from this confirmation.

## Deployment record — 11 November 2026

Image: `shuffle-player:owner-dj-20261111`,
`sha256:0aeaf6d7b131ea1aa1fef702909dd8a5a48d6ead1c9d7ba05ea26bb841a271e1`.
The final public-hostname checks returned 200 for both entity URLs, remote assets
and signing library. Signed owner state/search succeeded; unsigned commands,
forged owner fields, replay and legacy mutations returned 403. Public dashboard
assets/search are private, and no credential was present in public assets.
The exact public MP3 URL decoded successfully. All three mounts report `RW=false`.

The live 12-track queue with Good Bait selected was restored after recreation,
including playback position and playing state. Deployment backups are under
`/volume1/docker/shuffle-player/before-owner-dj-20261111T110922Z` and the earlier
`before-owner-dj-20261111T110636Z`. The latter retains the pre-owner deployment's
Compose file and source. Rolling back before owner auth would reopen LAN-only
control authorization, so retain owner auth when reverting presentation changes.
