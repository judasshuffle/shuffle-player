# Remote listening: preserve the existing address

The LAN player now controls the radio's shared queue. Public listening stays
at the exact URL below, while station changes are accepted only on LAN 8094.
See [SHARED-STATION.md](SHARED-STATION.md). Earlier independent-queue descriptions
below are historical.

Current follow-up: the user has corrected TCP 8001 forwarding to the NAS.
The public URL now returns MP3 bytes and its marked requests appear in the
Shuffle Player logs, matching LAN behavior. A separate Webamp CORS requirement
was then identified in the actual installed DarkRide client and fixed on the
radio endpoint. See [DARKRIDE-COMPATIBILITY.md](DARKRIDE-COMPATIBILITY.md).
The user confirmed that the unchanged URL now plays in the actual DarkRide
radio. The older inspection/cutover notes below describe the evidence before
this follow-up.

The user confirmed that the MP3 address must remain exactly:

**http://shuffle.tplinkdns.com:8001/stream.mp3**

It is recorded in `README.md` at commit `adae5fa`, removed from that README by
`9e5dbbb`, and used again by `experiments/darkride-audio/bridge.py` at `a007347`.
Its hostname, HTTP scheme, external TCP port 8001, and `/stream.mp3` path are
preserved. No previous HTTP lossless address was confirmed; no further historical
lossless address search or Snapcast migration is required.

## Addresses served by the NAS

| Purpose | Public address after router cutover |
| --- | --- |
| Player, with original/lossless default and MP3 selector | http://shuffle.tplinkdns.com:8001/ |
| Existing continuous MP3 radio address | http://shuffle.tplinkdns.com:8001/stream.mp3 |
| Direct original audio for a selected track | `http://shuffle.tplinkdns.com:8001/media/{id}?quality=original` |
| Direct compatibility MP3 for the same track | `http://shuffle.tplinkdns.com:8001/media/{id}?quality=mp3` |

For example, track 1134 (Hurricane) has the original FLAC endpoint
http://shuffle.tplinkdns.com:8001/media/1134?quality=original.
This is direct audio, not an HTML player. It retains byte-range seeking and the
original file bytes. No Ogg conversion is imposed. The player checks native
format support and retains its per-browser compatibility preference.
Current-track links on the player use the same origin, so remote playback never
tries to fetch a private NAS/Pi address. `/api/listening` reports public addresses.

`/stream.mp3` is a shared Shuffle All radio output with one real-time encoder
and up to 16 listeners. It continues across tracks, supports midstream joins,
and does not depend on an open browser or the Pi. The browser's individual queue
is independent of that shared radio. The encoder stops when nobody is listening.
Selection reads existing SQLite row IDs and checks only the selected indexed
paths. Missing entries are retained. Nothing scans folders, rebuilds the index,
or modifies music or SQLite. No source/stream credentials are required.

## Routing and cutover

The separate Shuffle Player service binds both NAS LAN ports 8094 and 8001 to
its existing container port 8080. Ports 8001 and 8094 serve the same application;
the original LAN player remains available. No DSM/nginx or unrelated-container
configuration is changed.

Inspection on 10 November 2026 resolved `shuffle.tplinkdns.com` to
`62.255.197.214`. A public-address status request from the LAN timed out before
deployment. That does not establish the router's existing forwarding target or
prove external reachability: NAT loopback may differ from outside access.

The remaining router rule must send **external TCP 8001 to
192.168.68.81 TCP 8001**, preserving the public port and every other forwarding
rule. Keep the existing hostname/DDNS arrangement. Do not repoint the whole
hostname to a private LAN address, change DNS for other services, or redirect
unrelated HTTP/HTTPS ports. Router administration is not available in this
session; public routing must not be claimed complete until that rule and a test
from outside the LAN are verified.

Verify direct MP3 decoding, original FLAC bytes/ranges, and both player qualities
through port 8001 locally, then repeat against the exact public addresses after
cutover. The station URL must return MPEG audio continuously; redirecting it to
an HTML page or one finite track is not a compatible replacement.

## Verified NAS state

After deployment, all 24 Python tests and quality/queue/palette UI tests passed.
Real NAS port-8001 checks decoded continuous MP3 with two simultaneous listeners,
including a midstream join. Direct original FLAC delivery matched the source
SHA-256 and served byte ranges correctly. Both published ports are present and
the container is healthy. The 17,623-row database retains its verified SHA-256,
both source mounts remain read-only, and DarkRide's container ID/start time are
unchanged. Public `/stream.mp3` and `/api/listening` requests from this LAN still
timed out after deployment. No router or DNS changes were made. The remaining
action is to verify/correct the single external TCP-8001 forwarding rule and
then confirm these public addresses from outside the LAN.

## Router inspection follow-up

A later read-only check used SSDP discovery against the router at 192.168.68.1
and its advertised WAN connection control service. `GetSpecificPortMappingEntry`
for external TCP 8001 returned UPnP fault 714 rather than a destination. The
Windows NAT-UPnP COM query also failed locally with error 0x80070002.
The diagnostic is retained as `inspect_router_forwarding.py`; it never invokes
AddPortMapping or DeletePortMapping. Manual/static router rules may not appear
in UPnP, so these results do **not** establish that forwarding still targets the
Pi, that no manual forwarding rule exists, or that the NAS is publicly reachable.

The remaining authenticated router check is the existing TCP-8001 rule's
internal destination. If it is the old Pi at 192.168.68.57, change only that
destination to 192.168.68.81, internal TCP port 8001. Keep external TCP port 8001,
the hostname, and every unrelated rule unchanged. Public stream reachability
must then be checked from outside the LAN.

The NAS container was not rebuilt for this inspection. Continuous MP3 decoding
and midstream joining were verified again, as were original FLAC delivery and
the unchanged source/database hashes. Original/lossless remains the default
browser quality and MP3 remains the saved per-browser compatibility option.
