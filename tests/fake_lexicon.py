"""Nachgebaute Lexicon Local API für Tests (#146, #237–#239) – nur das, was TagStudio benutzt.

Verhalten nach der OpenAPI-Beschreibung 1.0.0: Antworten {"data": …}, Fehler {"message", "errorCode"} mit HTTP 400,
Suche mit filter[feld] (Text: enthält, ohne Gross-/Kleinschreibung; id: Komma-Liste), source non-archived/all.
"""
import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


def _norm(p):
    return str(p or "").replace("\\", "/").lower()


class State:
    def __init__(self, tracks=None, tags=None, playlists=None):
        self.tracks = copy.deepcopy(tracks or [])
        self.tags = copy.deepcopy(tags or {"categories": [], "tags": []})
        self.playlists = copy.deepcopy(playlists or [])     # flache Liste {id, name, type, parentId, trackIds}
        self.selected, self.selected_playlists = [], []
        self.calls = []                                    # (Methode, Pfad, Parameter)
        self.busy = 0                                      # so oft mit Fehlercode 2 antworten
        self.next_id = 1000
        self.lock = threading.Lock()

    def by_id(self, tid):
        return next((t for t in self.tracks if t["id"] == int(tid)), None)

    def tree(self, parent=None):
        out = []
        for p in self.playlists:
            if p.get("parentId") == parent:
                node = {k: v for k, v in p.items() if k not in ("trackIds", "parentId")}
                kids = self.tree(p["id"])
                if kids:
                    node["playlists"] = kids
                out.append(node)
        return out

    def playlist_tracks(self, pid):
        p = next(x for x in self.playlists if x["id"] == pid)
        if str(p["type"]) == "1":
            seen, ids = set(), []
            for c in self.playlists:
                if c.get("parentId") == pid:
                    for i in self.playlist_tracks(c["id"]):
                        if i not in seen:
                            seen.add(i)
                            ids.append(i)
            return ids
        return list(p.get("trackIds") or [])


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

    def _err(self, code, msg):
        self._send(400, {"message": msg, "errorCode": code})

    def _query(self):
        q = parse_qs(urlparse(self.path).query)
        filt = {k[7:-1]: v[0] for k, v in q.items() if k.startswith("filter[")}
        return q, filt

    def do_GET(self):  # noqa: N802
        s, u = self.state, urlparse(self.path)
        q, filt = self._query()
        s.calls.append(("GET", u.path, {k: v for k, v in q.items()}))
        src = (q.get("source") or ["non-archived"])[0]
        pool = [t for t in s.tracks if src == "all" or (src == "archived") == bool(t.get("archived"))]
        if u.path == "/v1/tracks":
            lim, off = int((q.get("limit") or [1000])[0]), int((q.get("offset") or [0])[0])
            return self._send(200, {"data": {"total": len(pool), "limit": lim, "offset": off,
                                             "tracks": pool[off:off + min(lim, 2)]}})       # kleine Seiten testen
        if u.path == "/v1/search/tracks":
            for bad in ("limit", "offset"):                  # wie das echte Lexicon (Rückmeldung 17.10.2026)
                if bad in q:
                    return self._err(5, f"'{bad}' is not allowed, value: {q[bad][0]}")
            res = pool
            for k, v in filt.items():
                if k == "id":
                    ids = {int(x) for x in v.split(",") if x.strip()}
                    res = [t for t in res if t["id"] in ids]
                elif k == "location":
                    res = [t for t in res if _norm(v) in _norm(t.get("location"))]
                else:
                    res = [t for t in res if str(v).lower() in str(t.get(k) or "").lower()]
            return self._send(200, {"data": {"total": len(res), "tracks": res}})
        if u.path == "/v1/track":
            t = s.by_id((q.get("id") or ["0"])[0])
            return self._send(200, {"data": {"track": t}}) if t else self._err(100, "Track does not exist")
        if u.path == "/v1/tracks/selected":
            return self._send(200, {"data": {"ids": s.selected}})
        if u.path == "/v1/playlists":
            return self._send(200, {"data": {"playlists": s.tree()}})
        if u.path == "/v1/playlists/selected":
            return self._send(200, {"data": {"ids": s.selected_playlists}})
        if u.path == "/v1/playlist":
            pid = int((q.get("id") or ["0"])[0])
            p = next((x for x in s.playlists if x["id"] == pid), None)
            if p is None:
                return self._err(101, "Playlist does not exist")
            return self._send(200, {"data": {"playlist": {**{k: v for k, v in p.items() if k != "trackIds"},
                                                           "trackIds": s.playlist_tracks(pid)}}})
        if u.path == "/v1/tags":
            return self._send(200, {"data": s.tags})
        return self._send(400, {"message": f"Endpoint {u.path} does not exist", "errorCode": 4})

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def _write(self, method):
        s, u = self.state, urlparse(self.path)
        b = self._body()
        s.calls.append((method, u.path, b))
        with s.lock:
            if s.busy:
                s.busy -= 1
                return self._err(2, "Too many requests")
            if method == "PATCH" and u.path == "/v1/track":
                t = s.by_id(b["id"])
                if t is None:
                    return self._err(100, "Track does not exist")
                t.update(b.get("edits") or {})
                return self._send(200, {"data": {"track": t}})
            if method == "PATCH" and u.path == "/v1/track/location":
                t = s.by_id(b["id"])
                if t is None:
                    return self._err(100, "Track does not exist")
                t["location"], t["locationUnique"] = b["location"], _norm(b["location"])
                return self._send(200, {"data": {"track": t}})
            if method == "POST" and u.path == "/v1/tracks":
                out = []
                for loc in b.get("locations") or []:
                    s.next_id += 1
                    t = {"id": s.next_id, "location": loc, "locationUnique": _norm(loc), "archived": 0, "incoming": 1}
                    s.tracks.append(t)
                    out.append(t)
                return self._send(200, {"data": {"tracks": out}})
            if method == "POST" and u.path == "/v1/playlist":
                s.next_id += 1
                s.playlists.append({"id": s.next_id, "name": b["name"], "type": str(b["type"]),
                                    "parentId": b.get("parentId"), "trackIds": []})
                return self._send(200, {"data": {"id": s.next_id}})
            if method == "PATCH" and u.path == "/v1/playlist-tracks":
                p = next((x for x in s.playlists if x["id"] == b["id"]), None)
                if p is None:
                    return self._err(101, "Playlist does not exist")
                p["trackIds"] = list(p.get("trackIds") or []) + list(b["trackIds"])
                return self._send(200, {"data": {}})
            if method == "POST" and u.path == "/v1/tag":
                s.next_id += 1
                tag = {"id": s.next_id, "label": b["label"], "categoryId": b["categoryId"]}
                s.tags["tags"].append(tag)
                return self._send(200, tag)
            if method == "POST" and u.path == "/v1/control":
                return self._send(200, {})
        return self._send(400, {"message": f"Endpoint {u.path} does not exist", "errorCode": 4})

    def do_PATCH(self):  # noqa: N802
        self._write("PATCH")

    def do_POST(self):  # noqa: N802
        self._write("POST")

    def do_DELETE(self):  # noqa: N802
        self._write("DELETE")


def start(state: State):
    """→ (server, url). server.shutdown(); server.server_close() zum Beenden."""
    h = type("H", (Handler,), {"state": state})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"
