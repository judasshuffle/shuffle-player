# Station continuity verification — 11 November 2026

Branch: `feature/synology-browser-player`.

Before deployment GreatATuin ran owner-DJ image
`sha256:0aeaf6d7b131ea1aa1fef702909dd8a5a48d6ead1c9d7ba05ea26bb841a271e1`.
Its `/app/dr-screen.js` SHA256 was
`b923d26eb93e730e048828f237e5d4d54bf57cdb000d3229999d66666b163ce8`,
matching `c95008d`, and did **not** include reconnect commit `be02eb3`.

## Local verification

`node tests/test_dr_screen_station.cjs` starts the real Python station and
FFmpeg with two synthetic WAV tracks, then opens the actual screen in headless
Edge. A three-second 440 Hz track finishes naturally with an 880 Hz track
queued. Both frequencies are measured through the screen analyser; the station
advances to index 1 and remains playing. There is one MP3 request and one main
page navigation throughout. An explicit station Pause freezes the clock while
the existing stream remains connected. Known durations exercise the station
clock as well as the encoder's actual EOF. No end-of-track stall reproduced;
no change to Pause or server transport semantics was needed.

`node tests/test_dr_screen_reconnect.cjs` interrupts a local MP3 stream once
for 3.5 seconds. The already-open screen retries automatically and resumes
playback without navigation, additional audio elements, or additional WebAudio
sources. Native volume 0.8, mute=true and visitor gain 0.37 survive. After
unmuting, measurable output PCM returns with an output/input RMS ratio about
0.37. A second run with `RECONNECT_MUTED=0` verifies automatic audible PCM
recovery while unmuted, with the same volume settings and no unmute action.
This verifies browser audio processing, not an in-world listening result.

The 21 Python player tests and seven existing JS suites also pass. The new
natural-completion test requires Python, FFmpeg, Edge and the same local
`playwright-core` installation used by the reconnect test. It contacts only
loopback and creates disposable synthetic files.

## Deployment

Deployed image: `shuffle-player:continuity-20261111`, containing `be02eb3`,
`sha256:ebe2e0ada50737483d0390c1198ca6edc57ea6a5017adfa234f81b550881ea32`.
The legacy station API exposes only 100 queue entries around its selected
position. Deployment captures every window via signed owner requests, then
restores the original selection and playback state before restarting only the
Compose `player` service. The full ordered queue and selected position are
restored to the replacement process, retaining continuous shuffle behavior.
The NAS keeps a private `before-continuity-*` backup of station state, prior
application files, Compose configuration and rollback image ID.

Completed backup: `/volume1/docker/shuffle-player/before-continuity-20261111T140348Z`.
All 17,621 ordered entries were captured and restored, with index 711 and
“Amen (Take 2, Released Version)” selected and playing. Public asset hashes
match the saved sources; signed owner state/search and tablet asset checks pass.
Unsigned, forged and replayed mutations remain denied. The music and database
hashes match the prior baseline. DarkRide's ID and start time below are unchanged.
The public screen also produces measurable post-gain PCM in Edge (RMS 0.0169),
with one audio element and a running AudioContext.

The public URL remains `http://shuffle.tplinkdns.com:8001/stream.mp3`; ports,
owner key and tablet assets remain unchanged. Music, SQLite and owner-key mounts
remain read-only. DarkRide must retain container ID
`5e6f49e36e9d62c733749009975116fa48ad2d7c237d6869ca9fb3c35b7e0f82`
and start time `2026-11-10T08:40:17.278341659Z`.

A screen page loaded before this deployment still holds its old JavaScript.
Reload that screen once to receive the fix; later stream interruptions recover
on the already-open updated page without relogging. Actual DarkRide audio still
requires the owner's in-world listening check.
