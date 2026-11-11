# DarkRide screen MP3 compatibility test

Screen URL: **http://shuffle.tplinkdns.com:8001/dr-screen**

Client entity script: **http://shuffle.tplinkdns.com:8001/dr-screen-entity.js**

Set those as the Web entity's `sourceUrl` and client `script`, respectively.
Both public-hostname URLs returned HTTP 200 on 11 November 2026. The LAN test
equivalents use `http://192.168.68.81:8001`. Set the entity's
web audio output to local if its editor exposes that choice. Keep station
selection, transport and seeking on http://192.168.68.81:8094/.

Turn the separate DarkRide radio off. With the station playing, load the screen.
The acceptance test is audible music from the screen and Shufflizer reacting to
that same music. If DarkRide blocks autoplay, the screen displays a message and
an **Enable screen audio** button. Interact with the Web entity and click it.
Judas confirmed in-world screen audio and beat-reactive Shufflizer visuals on
11 November 2026. Remote visitor playback and lossless playback remain unverified.

The page uses one `<audio>` element loading the existing same-origin live
`/stream.mp3`. Its Web Audio graph is media source → analyser → volume gain →
speakers. The embedded existing Shufflizer runtime receives that same analyser;
the gain can reach zero without reducing its input. This page makes no station
control requests and does not substitute individual-track playback.

The cinema protocol is reused: connect `scriptEventReceived`, emit `{"hello":true}`,
and emit `{"ready":true}` after the visualizer frame loads. On either message,
the entity script replies with `{"volume":N}`. Programme state comes from the
live stream, so cinema state messages are unnecessary and ignored.

Each visitor's independent setting is `darkride/shufflizer/sound` (default 100).
The entity listens for local-only messages on `darkride.shufflizer`, accepting
`{"sound":75}` from that visitor. For example, in DarkRide's scripting console:

```js
Messages.sendLocalMessage('darkride.shufflizer', JSON.stringify({sound: 75}));
```

Send `sound: 0` to check that the visualizer keeps reacting at zero volume, then
restore it to 100. Setting changes are also polled every 500 ms. No cinema
setting, channel, hall-distance rule, or cinema server script is modified.
Visitors can also adjust **My volume** directly on the screen overlay. That
slider changes the post-analysis gain immediately and asks the entity script
to remember the value in that visitor's own settings. The canvas remains fullscreen.

The separate [DJ remote](DJ-REMOTE.md) now controls the programme. The public
root redirects to `/dr-screen`; dashboard scripts and library search endpoints
are rejected on port 8001. The LAN dashboard also requires an owner signature
for all station mutations. The following image record describes the earlier
screen-only deployment; see the DJ remote deployment record for the latest image.

Validation: `node tests/test_dr_screen.cjs` covers the actual page graph,
handshake, clamping and malformed messages, autoplay fallback and entity/channel
isolation. The Python player suite covers listener routes plus existing station,
MP3 delivery and access checks. Existing queue, station, palette and quality JS
suites exercise dashboard regression behavior. Judas's separate in-world test
confirms audible MP3 screen playback and beat-reactive visuals; HTTP and script
checks alone do not establish remote visitor playback or lossless playback.

Deployed 11 November 2026 as `shuffle-player:dr-screen-20261111`, image
`sha256:1af694632bda90bab82f0d562407c0d77c87e570e870e1b82683bdaf036659e6`.
The four screen/visualizer routes returned HTTP 200 on port 8001 and a three-second
LAN MP3 decode passed. The existing 11-track queue, selected track, playback
position and playing state were restored after restart. Both library mounts
still report `RW=false`. Only Shuffle Player was recreated.

Pre-deployment files and station snapshot are saved on the NAS under
`/volume1/docker/shuffle-player/before-dr-screen-20261111T104936Z`.
For rollback, restore that directory's `compose.yaml`, pin its player image to
`sha256:523ad9b33a3e3d05479b9c2025681f1439d779349ee97853681d9bcb33aa74db`,
and recreate only `player` using `docker compose up -d --no-deps --no-build player`.
That restart resets in-memory station state; the saved `station.json` retains
the queue and position. No music or database restoration is needed.
