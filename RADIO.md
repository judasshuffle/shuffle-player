# Radio Mode (Second Life stream)

Radio mode streams your Pi jukebox to Second Life using **Icecast2** (always on) and an **ffmpeg-based Auto-DJ** (started/stopped by voice or scripts). Everything runs as user `dan`. No cloud; all local.

- **Stream URL (LAN):** `http://192.168.68.57:8000/stream.mp3`
- **Stream URL (public):** `http://<your-public-ip>:8000/stream.mp3` (after port-forward 8000 → 192.168.68.57)
- **Format:** MP3, 192 kbps, 44.1 kHz stereo
- **Mount:** `stream.mp3` (fixed for Second Life)

---

## 1. Installation

```bash
sudo apt update
sudo apt install -y ffmpeg
```

Icecast2 (if not already installed):

```bash
sudo apt install -y icecast2
```

---

## 2. Icecast configuration

Edit `/etc/icecast2/icecast.xml` and set:

- `<port>8000</port>`
- `<bind-address>0.0.0.0</bind-address>`
- `<source-password>REPLACE_WITH_SIMPLE_PASSWORD</source-password>`
- `<admin-user>admin</admin-user>`
- `<admin-password>REPLACE_WITH_ADMIN_PASSWORD</admin-password>`

The **source password** must match the value you put in `/home/dan/radio.env` (see below).

Then:

```bash
sudo systemctl enable icecast2
sudo systemctl restart icecast2
```

**Verify:** Open `http://192.168.68.57:8000` in a browser; you should see the Icecast status page.

---

## 3. Icecast logging (for debugging)

Ensure Icecast writes logs so you can diagnose source-connection issues:

- In `/etc/icecast2/icecast.xml`, confirm `<logging>` is present and that log files go to `/var/log/icecast2` (or your distro’s path).
- Enable at least **error** and **access** logs. Example:

  ```xml
  <logging>
      <accesslog>access.log</accesslog>
      <errorlog>error.log</errorlog>
      <loglevel>2</loglevel>
  </logging>
  ```

- Create the log directory if needed and set ownership so the Icecast user can write:

  ```bash
  sudo mkdir -p /var/log/icecast2
  sudo chown icecast2:icecast2 /var/log/icecast2
  ```

Then restart Icecast: `sudo systemctl restart icecast2`.

**Tail logs (no admin auth required):**

```bash
sudo tail -f /var/log/icecast2/error.log
sudo tail -f /var/log/icecast2/access.log
```

Use these when the mount is missing or `/stream.mp3` returns 400: error.log shows source rejections; access.log shows client requests.

---

## 4. Radio password (required before first stream)

Create `/home/dan/radio.env` with the **same** source password as in `icecast.xml`:

```bash
cp /home/dan/radio.env.sample /home/dan/radio.env
nano /home/dan/radio.env
```

Set:

```
SOURCEPASS=your_actual_source_password
```

Do not commit `radio.env` (it contains the password). Only `radio.env.sample` (no real password) is in the repo.

---

## 5. Radio files

- **`/home/dan/radio_ffmpeg.sh`** – Auto-DJ: early logging (timestamp, whoami, pwd, MUSIC_ROOT, radio.env loaded, SOURCEPASS length only, ICECAST_URL without password); checks /mnt/lossless exists and readable, ffmpeg present, no CRLF in radio.env; indexes `/mnt/lossless` (recursive, skips Playlists); loops: “Selecting track…”, “Now playing”, “Connecting to Icecast”, ffmpeg to Icecast; after ~3s checks mount with curl and logs “Mount not available yet (HTTP XXX)” if not 200. No secrets in logs.
- **`/home/dan/start_radio.sh`** – Idempotent start: kills any existing `radio_ffmpeg.sh` and ffmpeg-icecast, clears log, writes “start_radio invoked at …” to log, starts DJ in background, writes PID to `/home/dan/radio.pid`. Exit 0.
- **`/home/dan/stop_radio.sh`** – Kills by PID file if present, kills stray ffmpeg-icecast, removes PID file, appends “stop_radio invoked at …” to log. Exit 0.
- **`/home/dan/radio_status.sh`** – Healthcheck: prints Icecast listener (ss), mount HTTP response (curl -I /stream.mp3), ffmpeg process list, last 30 lines of `radio_stdout.log`. Exit 0 if `/stream.mp3` returns HTTP 200; nonzero otherwise. No admin auth needed.

Scripts are executable.

---

## 6. Voice commands (jukebox)

When the voice jukebox is running:

- **"Start radio"** / **"Start the radio"** → runs `start_radio.sh` (non-blocking).
- **"Stop radio"** / **"Stop the radio"** → runs `stop_radio.sh` (non-blocking).

mpv local playback is unchanged. Radio start/stop does not block or crash the jukebox.

---

## 7. Manual start/stop

```bash
# Start streaming
/home/dan/start_radio.sh

# Stop streaming
/home/dan/stop_radio.sh
```

Logs: stdout/stderr of the Auto-DJ go to `/home/dan/radio_stdout.log` (cleared on each start). “Now playing” and “Connecting to Icecast” are printed per track; failures go to stderr.

---

## 8. Clear test flow

1. **Icecast up:** Confirm `http://192.168.68.57:8000` loads the Icecast status page.
2. **Password:** Create `/home/dan/radio.env` with `SOURCEPASS=` matching `<source-password>` in `/etc/icecast2/icecast.xml`.
3. **Start:** Run `/home/dan/start_radio.sh`.
4. **Healthcheck:** Run `/home/dan/radio_status.sh`. It should show:
   - Icecast listening on port 8000.
   - ffmpeg (or `radio_ffmpeg.sh`) process running.
   - `curl -I http://localhost:8000/stream.mp3` returns **200 OK**.
   - Recent “Now playing” / “Connecting to Icecast” lines in the log.
5. **Listen from another device:** Open `http://192.168.68.57:8000/stream.mp3` in a browser or VLC on another machine on the LAN; confirm audio plays.
6. **If it fails:** See “If /stream.mp3 is 400” below.
7. **Stop:** Run `/home/dan/stop_radio.sh`.

---

## If /stream.mp3 is 400 (diagnose)

When the mount is missing (HTTP 400) but the script is running, run these in order:

1. **Healthcheck:**
   ```bash
   /home/dan/radio_status.sh
   ```

2. **Recent Auto-DJ log (early logging, indexing, “Now playing”, “Mount not available”):**
   ```bash
   tail -n 120 /home/dan/radio_stdout.log
   ```

3. **Processes (script + ffmpeg):**
   ```bash
   pgrep -af 'radio_ffmpeg|ffmpeg'
   ```

4. **Mount HTTP response:**
   ```bash
   curl -I http://localhost:8000/stream.mp3
   ```

5. **Check for Windows CRLF in `radio.env` (would break SOURCEPASS):**  
   If you see `^M` at end of lines, fix with `dos2unix`:
   ```bash
   cat -A /home/dan/radio.env
   dos2unix /home/dan/radio.env
   ```

Then check Icecast error log for source rejections (wrong password, etc.):

```bash
sudo tail -f /var/log/icecast2/error.log
```

---

## 9. Second Life and port forward

- In your router, forward external port **8000** to **192.168.68.57** (Pi) when streaming from the Pi.
- Public stream URL: `http://<your-public-ip>:8000/stream.mp3`
- In Second Life land music settings, set the stream URL to that public URL.

Only one broadcaster (Windows OR Pi) should have port 8000 forwarded at a time.

---

## Summary

| Component   | Role                          | How it runs             |
|------------|--------------------------------|-------------------------|
| Icecast2   | Stream server (mount `stream.mp3`) | `systemctl` (always on) |
| ffmpeg DJ  | Encoder/player (`radio_ffmpeg.sh`) | Scripts only (voice or manual) |
| Port 8000  | HTTP stream                   | Forward to Pi when streaming |

All offline/local. No Liquidsoap required. No admin authentication needed for checking mount existence (use `radio_status.sh` or `curl -I` on `/stream.mp3`).
