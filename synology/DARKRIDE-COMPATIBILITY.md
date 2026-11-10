# DarkRide Webamp radio compatibility — 10 November 2026

Status: **confirmed working in the user's actual DarkRide radio**. The user
retried the unchanged public URL after deployment and reported “It now plays in
DarkRide.” The LAN/public anonymous-audio contract also passes. This conclusion
is based on actual client playback, not browser/FFmpeg decoding alone.

## Evidence and routing

The exact public URL remains `http://shuffle.tplinkdns.com:8001/stream.mp3`.
Initially a marked LAN request returned 200/audio bytes and appeared in the NAS
log, while the marked public request timed out and did not appear. The router
WAN address and public DNS both resolved to 62.255.197.214.

The user corrected the Deco forwarding destination to 192.168.68.81 TCP 8001.
After that change, both LAN and public requests returned HTTP/1.0 200,
`Content-Type: audio/mpeg`, and MP3 data; both marked requests appeared in the
Shuffle Player log. No further router change was made by this diagnosis.

## Compare the old implementation and the replacement

| Property | Old configuration in this repository | Synology before the CORS correction |
| --- | --- | --- |
| Encoder | FFmpeg/libmp3lame → Icecast | FFmpeg/libmp3lame → shared HTTP stream |
| MP3 sample rate / channels | 44.1 kHz, stereo | 44.1 kHz, stereo, measured by FFprobe |
| MP3 bitrate | 128 kbps in runner/sample environment | 256 kbps, measured by FFprobe |
| Audio MIME type | `audio/mpeg` declared by encoder | `audio/mpeg` measured in response |
| Finite Content-Length / redirect | Old live endpoint; original headers not captured | Neither a finite length nor a redirect |
| Cross-origin permission | Icecast provides configurable CORS; original response not captured | No Access-Control-Allow-Origin header |

The old runner is `systemd/shuffle-radio-runner.sh`; the alternate source script
is `ops/scripts/shuffle-radio-ffmpeg.sh`. Original Icecast response headers were
not retained, so this report does not invent an exact historical header capture.
The [Icecast sample configuration](https://github.com/xiph/Icecast-Server/blob/master/conf/icecast.xml.in)
includes CORS headers specifically to make streams embeddable.

Both current LAN and public streams decode as MP3 at 44.1 kHz/stereo/256 kbps.
The public URL also produced six seconds of non-silent mono 24 kHz PCM using the
historical DarkRide bridge's receiver settings. This rules out the earlier
network timeout and a generally undecodable/silent MP3 response, but does not
exercise Webamp's browser security checks. No bitrate/encoding change was made
without evidence that it was required.

## Actual installed client failure path

The active client was DarkRide 1.1.3.1. Its existing `resources.rcc` was opened
read-only and its relevant resource files inspected without changing the client
or server. Diagnostic copies are under ignored `synology/cache/`, not in Git.

- `qml/darkride/RadioPanel.qml` loads the radio from the application's qrc page
  in a WebEngineView, permitting remote URLs and omitting persistent cookies.
- `html/radio/webamp.darkride.min.js` identifies Webamp 2.3.1. Its media element
  sets `crossOrigin = "anonymous"` and routes an audio error to the
  `darkrideMediaError` event.
- `html/radio/radio.js` listens to that event, stops the player, and displays
  exactly “That station didn't play here. Try another.” It supplies duration 0
  for radio tracks rather than downloading the stream to discover its length.

The replacement response lacked the cross-origin permission required by this
actual playback path. A browser tab playing the URL directly and FFmpeg decoding
it do not test this requirement. See [Webamp's CORS guide](https://docs.webamp.org/docs/guides/cors/).

## Narrow server-side correction and validation

Only `/stream.mp3` responses now include `Access-Control-Allow-Origin: *`, with
GET/HEAD/OPTIONS allowed, Range/Icy-MetaData preflight headers, and relevant
response-header exposure. Anonymous origins, including `Origin: null` from the
qrc page, are supported without credentialed access. OPTIONS returns 204 and
does not start an encoder. Other library/API routes do not receive these headers.

The MP3 bytes, bitrate, live connection behavior, URL, browser lossless default,
and compatibility-track conversion are unchanged. No fake `icy-metaint` is
advertised: no metadata bytes are injected into the MPEG stream.

Regression tests cover anonymous and qrc/null origins, GET/HEAD/OPTIONS, error
responses, preflight without playback, route scoping, and continued live decoding
across short track transitions. The deployed public CORS response passed, and
the user confirmed audible playback in the actual DarkRide radio afterward.

The previous Git checkpoint `checkpoint/synology-working-20261110T105305Z` is
immutable and predates this correction. It proves the saved application source,
not completed DarkRide compatibility. This correction is included in the new
shared-station checkpoint; see [HANDOFF-2026-11-10.md](HANDOFF-2026-11-10.md).
Music and SQLite stay read-only;
the DarkRide server and router are not modified by this fix.

## Deployment verification

The corrected NAS image is
`sha256:9b69356ce58fd3d5bae4aae09f3418c9413ffea262c3c03b595eddca10a1c624`.
All 25 Python tests and the queue/quality/palette tests passed. The deployed LAN
and exact public stream URL passed anonymous-origin and null-origin HEAD/GET,
OPTIONS preflight, and public MP3 encoding checks using
`python -B synology/verify_webamp_cors.py`. Encoding remains MP3/44.1 kHz/stereo/
256 kbps. The original FLAC hash and the 17,623-row SQLite backup hash are
unchanged. Both source mounts remain read-only. DarkRide's container ID and
start time still match the pre-diagnosis values. No DarkRide source or settings
were changed; the installed client resource was only read.
