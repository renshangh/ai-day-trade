"""The v3 HTTP boundary persists records and rejects stale or cross-site writes."""

import http.client
import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import server  # noqa: E402
import v3_store  # noqa: E402


def test_v3_state_api(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "V3_STORE", v3_store.DeskStore(tmp_path / "state.json"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    port = httpd.server_address[1]

    def request(method, body=None, origin=None):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        conn.request(method, "/api/v3/state", body=json.dumps(body) if body is not None else None, headers=headers)
        response = conn.getresponse()
        result = response.status, json.loads(response.read())
        conn.close()
        return result

    try:
        status, initial = request("GET")
        assert status == 200 and initial["revision"] == 0
        data = v3_store.empty_data()
        data["observations"].append({"title": "Test observation"})
        status, saved = request("POST", {"expectedRevision": 0, "data": data}, f"http://127.0.0.1:{port}")
        assert status == 200 and saved["revision"] == 1
        assert request("GET")[1] == saved
        assert request("POST", {"expectedRevision": 0, "data": data})[0] == 409
        assert request("POST", {"expectedRevision": 1, "data": data}, "http://evil.example")[0] == 403
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=3)
