# Shared DarkRide station — 10 November 2026

The LAN page at http://192.168.68.81:8094/ controls the continuous radio at
http://shuffle.tplinkdns.com:8001/stream.mp3. Play matches replaces the NAS
queue and starts it; Queue matches appends. Shuffle All, Previous, Next,
Play/Pause, queue selection/removal and seeking operate on that same station.
All listeners hear the same music. DarkRide's buffer can delay changes.

The browser monitor starts off to prevent duplicate audio while using DarkRide.
Enable **Listen in this browser** for local audio and the reactive Shufflizer.
Its Lossless/original default and remembered MP3 compatibility choice affect
only the monitor; DarkRide keeps its compatible continuous MP3 stream.
Original music and SQLite remain mounted read-only. No index scan or rebuild.

The queue and clock live in NAS process memory and reset to Shuffle All after
a container restart. Without listeners the clock advances without encoding.
With listeners, pause sends MP3 silence and skips switch encoder input without
closing the HTTP stream. Only selected/previewed tracks have metadata read.

NAS port 8094 maps to container port 8081 (control listener). Public port 8001
still maps to 8080, where station mutations always return 403. Controls require
a process-only random token, trusted LAN Host and matching Origin when present.
No station credentials are stored in Git or the image. Radio CORS is preserved.
The public webpage shows station state and offers local listening, without controls.

Tests cover server queue semantics and clock, unauthorized/public controls,
continuous connections during pause/skip, browser station actions and independent
monitor quality, plus the previous playback, artwork and palette checks.

Before this change the deployed image was
`sha256:9b69356ce58fd3d5bae4aae09f3418c9413ffea262c3c03b595eddca10a1c624`.
For rollback use that retained local image with port 8094 mapped back to 8080
and 8001 still mapped to 8080; recreate only Compose service `player` with
`up -d --no-deps --no-build player`. It has working Webamp CORS but separate
browser/radio queues. Do not use the older checkpoint image as a CORS fix.
The database and separate Windows backup require no restoration or changes.

## Verified deployment

Image: `sha256:523ad9b33a3e3d05479b9c2025681f1439d779349ee97853681d9bcb33aa74db`.
Container health is healthy. Public decoded audio correlated with selected
originals Hurricane (0.9692) and Black Diamond Bay (0.9909) after Next.
The live script also verified queue replacement, seek, pause/resume, matching
public station state and rejected public control. It left Hurricane playing
with 49 indexed 1970s Bob Dylan tracks queued.

SQLite retains 17,623 entries and SHA256
`4de36d001b655efe282136ab9c7491ab7920d9034a4807b1afcde9769a152c3b`.
Hurricane original retains SHA256
`73213176644d35c839a23711708cdf22816679f78af0a4d2148e399e6d837762`.
Both mounts report RW=false. DarkRide retained container ID
`5e6f49e36e9d62c733749009975116fa48ad2d7c237d6869ca9fb3c35b7e0f82`
and start time `2026-11-10T08:40:17.278341659Z`.

Application code is saved by the shared-station checkpoint described in
[HANDOFF-2026-11-10.md](HANDOFF-2026-11-10.md). The earlier checkpoint tag is
unchanged. Local pre-change source is retained under ignored
`synology/cache/before-shared-station-20261110/`.
