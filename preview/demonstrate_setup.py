"""Exercise the setup HTTP dialogue locally; shut down on completion."""
import http.client
import json
from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
import server


def main():
    httpd = server.dashboard.ThreadingHTTPServer(("127.0.0.1", 0), server.PreviewHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    def request(path, body=None):
        client = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=5)
        client.request("GET" if body is None else "POST", path,
                       body=None if body is None else json.dumps(body),
                       headers={} if body is None else {"Content-Type": "application/json"})
        response = client.getresponse()
        data = response.read()
        client.close()
        assert response.status == 200, (response.status, data)
        return data

    try:
        assert b"Connect your music library" in request("/setup")
        output = []
        for choice in [dict(mode="existing"), dict(mode="existing", fixture="different-path"),
                       dict(mode="existing", fixture="different-path", music_path="/mnt/lossless"),
                       dict(mode="existing", fixture="incompatible"),
                       dict(mode="existing", unavailable=True), dict(mode="new")]:
            result = json.loads(request("/api/setup/validate", choice))
            token = result.pop("confirmation_token", None)
            output.append({"selection": choice, "result": result})
            if token:
                output.append({"confirmation": json.loads(request("/api/setup/confirm",
                               {"token": token, "confirmed": True}))})
        print(json.dumps(output, indent=2))
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()
        if server.setup_demo:
            server.setup_demo.close()


if __name__ == "__main__":
    main()
