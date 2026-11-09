"""Local HTTP checks with temporary assets and mocked production interfaces."""
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen


PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dashboard", PROJECT / "web/control_server.py")
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class DashboardTests(unittest.TestCase):
    def test_dashboard_and_standalone_with_isolated_interfaces(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "visualizer"
            shutil.copytree(PROJECT / "web/shufflizer", root)
            (root / "test-cover.jpg").write_bytes(b"temporary artwork fixture")
            scanner = Path(directory) / "scanner.sh"
            scanner.write_text("# test placeholder; never executed\n")
            with patch.object(dashboard, "ROOT", str(root)), \
                 patch.object(dashboard, "RESYNC_SCRIPT", str(scanner)), \
                 patch.object(dashboard, "run") as run, \
                 patch.object(dashboard, "mpv_command") as mpv, \
                 patch.object(dashboard, "read_nowplaying", return_value={
                     "text": "Test Artist — Test Track", "album": "Test Album",
                     "art_url": "/test-cover.jpg"}), \
                 patch.object(dashboard, "get_library_stats", return_value={"track_count": 3}), \
                 patch.object(subprocess, "run", side_effect=AssertionError("External process forbidden")), \
                 patch.object(sqlite3, "connect", side_effect=AssertionError("Database access forbidden")):
                run.return_value = subprocess.CompletedProcess([], 0, "Synthetic scan result", "")
                server = dashboard.ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = "http://127.0.0.1:" + str(server.server_port)

                def get(path):
                    with urlopen(base + path, timeout=5) as response:
                        return response.read()

                def post(path):
                    with urlopen(Request(base + path, method="POST"), timeout=5) as response:
                        return json.load(response)

                try:
                    html = get("/").decode()
                    self.assertEqual(get("/control").decode(), html)
                    self.assertIn('/index.html?embed=1', html)
                    for retained in ("coverArt", "npText", "npAlbum", "refreshNowPlaying",
                                     "refreshLibraryStats", "shuffleAll", "nextTrack", "prevTrack",
                                     "outputCtl", "systemCtl", "updateLibrary"):
                        self.assertIn(retained, html)
                    for removed in ("vuLeft", "vuRight", "refreshVu", "/api/vu", "vu-wrap"):
                        self.assertNotIn(removed, html)
                    standalone = get("/index.html")
                    self.assertEqual(get("/index.html?embed=1"), standalone)
                    for asset in ("/js/main.js", "/js/audio.js", "/js/engine.js", "/css/style.css"):
                        self.assertTrue(get(asset))
                    self.assertIn("Test Track", json.loads(get("/api/nowplaying"))["text"])
                    self.assertEqual(get("/test-cover.jpg"), b"temporary artwork fixture")
                    self.assertEqual(json.loads(get("/api/library/stats"))["track_count"], 3)
                    run.assert_not_called()  # Loading the dashboard never starts a scan.
                    self.assertTrue(post("/control/next")["ok"])
                    mpv.assert_called_once_with(["playlist-next", "force"])
                    self.assertEqual(post("/api/library/resync")["output"], "Synthetic scan result")
                    run.assert_called_once_with([str(scanner)])  # Mock only; no scanner executes.
                    with self.assertRaises(HTTPError) as error:
                        get("/api/vu")
                    self.assertEqual(error.exception.code, 400)
                    self.assertEqual(dashboard.PORT, 8091)
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join()


if __name__ == "__main__":
    unittest.main()
