"""Nachgebaute lokale API der OpenKeyScan-App für Tests (#244) – nach https://www.openkeyscan.com/api.

keys: {Pfad: Tonart in der Schreibweise der App}; Warteschlange: eine Abfrage von /analyze/results lang „queued“,
danach „done“. auto_tag=True ändert die Datei beim Analysieren (wie das Auto-Tagging der App).
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


class State:
    def __init__(self, keys=None, auto_tag=False, results_shape="list"):
        self.keys = dict(keys or {})
        self.auto_tag = auto_tag
        self.results_shape = results_shape        # "list" | "dict" | "empty" (nur /analyze/result liefert)
        self.queue = {}                           # Pfad → Abfragen bis fertig
        self.calls = []
        self.no_health = False                    # ältere App ohne /health (antwortet 404)
        self.default = None                       # Tonart für alle anderen Dateien (UI-Test)
        self.lock = threading.Lock()

    def analyse(self, path):
        if self.auto_tag and os.path.exists(path):
            st = os.stat(path)
            os.utime(path, (st.st_atime, st.st_mtime + 5))
        return self.keys.get(path, self.default)


class Handler(BaseHTTPRequestHandler):
    state: State = None

    def log_message(self, *a):
        pass

    def _send(self, code, body):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _row(self, p):
        s = self.state
        if s.queue.get(p, 0) > 0:
            return {"file": p, "status": "queued", "currentKey": "", "analyzedKey": None}
        k = s.analyse(p) if p in s.queue else s.keys.get(p, s.default)
        s.queue.pop(p, None)
        if k is None:
            return {"file": p, "status": "errored", "error": "Unsupported file"}
        return {"file": p, "status": "done", "currentKey": "", "analyzedKey": k}

    def do_GET(self):  # noqa: N802
        s, u = self.state, urlparse(self.path)
        s.calls.append(("GET", u.path))
        if u.path == "/health" and not s.no_health:
            return self._send(200, {"status": "ok"})
        with s.lock:
            if u.path == "/analyze/results":
                if s.results_shape == "empty":
                    return self._send(200, [])
                rows = []
                for p in list(s.queue):
                    if s.queue[p] > 0:
                        s.queue[p] -= 1
                        rows.append({"file": p, "status": "queued"})
                    else:
                        rows.append(self._row(p))
                return self._send(200, {"results": rows} if s.results_shape == "dict" else rows)
            if u.path == "/analyze/result":
                p = parse_qs(u.query).get("file", [""])[0]
                if p in s.queue and s.queue[p] > 0:
                    s.queue[p] -= 1
                    return self._send(200, {"file": p, "status": "queued"})
                return self._send(200, self._row(p))
        return self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        s, u = self.state, urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        b = json.loads(self.rfile.read(n) or b"{}")
        s.calls.append(("POST", u.path, b))
        with s.lock:
            if u.path == "/analyze/single":
                k = s.analyse(b.get("file"))
                if k is None:
                    return self._send(200, {"success": False, "file": b.get("file"), "error": "Unsupported file"})
                return self._send(200, {"success": True, "file": b.get("file"), "key": k})
            if u.path == "/analyze/add":
                for p in b.get("files") or []:
                    s.queue[p] = 1
                return self._send(200, {"success": True, "queued": len(b.get("files") or [])})
        return self._send(404, {"error": "not found"})

    def do_DELETE(self):  # noqa: N802
        self.state.calls.append(("DELETE", urlparse(self.path).path))
        self._send(200, {"success": True})


def start(state, port=0):
    h = type("H", (Handler,), {"state": state})
    ThreadingHTTPServer.allow_reuse_address = True
    srv = ThreadingHTTPServer(("127.0.0.1", port), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"
