"""Kleiner Client für die Lexicon Local API 1.0.0 (#237–#239) – nur Standardbibliothek.

Grundlage: offizielle OpenAPI-Beschreibung (https://www.lexicondj.com/developer/api-docs.yaml).
- GET liest Parameter aus der Adresse: Listen als wiederholte Schlüssel (fields=id&fields=title), Objekte in
  Klammerschreibweise (filter[location]=…). Alle anderen Methoden bekommen einen JSON-Rumpf.
- Antworten: {"data": …}; Fehler: {"message", "errorCode"} meist mit HTTP 400.
- Fehlercode 2 = Lexicon ist mit ändernden Anfragen beschäftigt → kurz warten und wiederholen.
- Die API hat keine Anmeldung und lauscht im ganzen Netzwerk: TagStudio spricht sie nie über einen Proxy an und
  schreibt nur an eine Adresse auf diesem Rechner (is_local), siehe #239.
"""
from __future__ import annotations

import ipaddress
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT = "http://localhost:48624"
BUSY = 2                 # zu viele ändernde Anfragen in der Warteschlange
PAGE = 1000              # höchstens 1000 Titel je Seite


class LexiconError(RuntimeError):
    def __init__(self, msg, code=None, status=None):
        super().__init__(msg)
        self.code, self.status = code, status


def is_local(base: str) -> bool:
    """Adresse auf diesem Rechner (localhost, 127.x, ::1)?"""
    host = (urllib.parse.urlparse(base or "").hostname or "").lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def encode_query(params: dict) -> str:
    """GET-Parameter wie in der API-Beschreibung: Listen wiederholt, Objekte in Klammern, None weglassen."""
    pairs = []
    for k, v in (params or {}).items():
        if v is None:
            continue
        if isinstance(v, dict):
            for sk, sv in v.items():
                if sv is not None:
                    pairs.append((f"{k}[{sk}]", _scalar(sv)))
        elif isinstance(v, (list, tuple)):
            for x in v:
                pairs.append((k, json.dumps(x, separators=(",", ":")) if isinstance(x, dict) else _scalar(x)))
        else:
            pairs.append((k, _scalar(v)))
    return urllib.parse.urlencode(pairs)


def _scalar(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


class Client:
    def __init__(self, base: str = DEFAULT, timeout: float = 20, opener=None, sleep=time.sleep, retries: int = 5):
        base = (base or DEFAULT).strip().rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        if not re.match(r"^https?://[^/\s]+$", base):
            raise LexiconError(f"Ungültige Adresse: {base}")
        self.base, self.timeout, self.retries, self._sleep = base, timeout, retries, sleep
        self._opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({})).open   # nie über einen Proxy
        self.calls: list[tuple] = []          # (Methode, Pfad) – fürs Protokoll

    @property
    def local(self) -> bool:
        return is_local(self.base)

    # ------------------------------------------------------------------ Grundlage
    def request(self, method: str, path: str, params: dict | None = None):
        method = method.upper()
        url = f"{self.base}/v1{path}"
        data = None
        if method == "GET":
            q = encode_query(params or {})
            url += ("?" + q) if q else ""
        else:
            data = json.dumps(params or {}).encode("utf-8")
        for attempt in range(self.retries + 1):
            req = urllib.request.Request(url, data=data, method=method,
                                         headers={"Accept": "application/json", "Content-Type": "application/json"})
            self.calls.append((method, path))
            try:
                with self._opener(req, timeout=self.timeout) as r:
                    raw = r.read()
                body = json.loads(raw.decode("utf-8")) if raw.strip() else {}
                return body.get("data", body) if isinstance(body, dict) else body
            except urllib.error.HTTPError as ex:
                try:
                    err = json.loads(ex.read().decode("utf-8"))
                except Exception:  # noqa: BLE001
                    err = {}
                code, msg = err.get("errorCode"), err.get("message") or ""
                if code == BUSY and attempt < self.retries:
                    self._sleep(0.3 * (attempt + 1))          # Lexicon beschäftigt: kurz warten
                    continue
                raise LexiconError(f"Lexicon meldet Fehler {code if code is not None else ex.code}"
                                   f"{': ' + msg if msg else ''} ({method} {path})", code, ex.code) from ex
            except (urllib.error.URLError, OSError, ValueError) as ex:
                raise LexiconError(f"Keine Verbindung zu Lexicon unter {self.base} – läuft Lexicon und ist die Local API "
                                   f"eingeschaltet (Settings › Integrations)? ({getattr(ex, 'reason', ex)})") from ex
        raise LexiconError("Lexicon ist beschäftigt – bitte später nochmals versuchen.", BUSY)

    def get(self, path, params=None):
        return self.request("GET", path, params)

    # ------------------------------------------------------------------ Titel
    def tracks(self, fields=None, source="non-archived", progress=None) -> list:
        """Alle Titel (seitenweise)."""
        out, offset, total = [], 0, None
        while total is None or offset < total:
            d = self.get("/tracks", {"limit": PAGE, "offset": offset, "source": source, "fields": fields})
            page = d.get("tracks") or []
            total = int(d.get("total") or 0)
            out += page
            offset += len(page)
            if progress:
                progress(len(out), total)
            if not page:
                break
        return out

    def total(self) -> int:
        return int(self.get("/tracks", {"limit": 1, "offset": 0, "fields": ["id"]}).get("total") or 0)

    def search(self, filt: dict, fields=None, source="non-archived", limit=50) -> list:
        d = self.get("/search/tracks", {"filter": filt, "fields": fields, "source": source, "limit": limit})
        return d.get("tracks") or []

    def track(self, tid):
        return self.get("/track", {"id": tid}).get("track")

    def selected_ids(self) -> list:
        return [int(i) for i in self.get("/tracks/selected").get("ids") or []]

    def tracks_by_ids(self, ids, fields=None) -> list:
        """Titel zu IDs in der gegebenen Reihenfolge (Suche mit Komma-Liste, in Blöcken)."""
        ids = [int(i) for i in ids]
        found = {}
        for k in range(0, len(ids), 200):
            part = ids[k:k + 200]
            for t in self.search({"id": ",".join(map(str, part))}, fields, source="all", limit=len(part)):
                found[t.get("id")] = t
        return [found[i] for i in ids if i in found]

    def patch_track(self, tid, edits: dict):
        return self.request("PATCH", "/track", {"id": tid, "edits": edits}).get("track")

    def set_location(self, tid, location: str, check=True):
        return self.request("PATCH", "/track/location", {"id": tid, "location": location, "checkFileExists": bool(check)})

    def add_tracks(self, locations) -> list:
        return self.request("POST", "/tracks", {"locations": list(locations)}).get("tracks") or []

    # ------------------------------------------------------------------ Playlists
    def playlists(self) -> list:
        return self.get("/playlists").get("playlists") or []

    def playlist(self, pid):
        return self.get("/playlist", {"id": pid}).get("playlist")

    def playlist_by_path(self, path: list, ptype="2"):
        return self.get("/playlist-by-path", {"path": list(path), "type": ptype}).get("playlist")

    def selected_playlists(self) -> list:
        return [int(i) for i in self.get("/playlists/selected").get("ids") or []]

    def playlist_create(self, name: str, ptype="2", parent=None) -> int:
        body = {"name": name, "type": ptype}
        if parent is not None:
            body["parentId"] = parent
        return int(self.request("POST", "/playlist", body).get("id"))

    def playlist_add(self, pid, track_ids, index=None):
        body = {"id": pid, "trackIds": [int(i) for i in track_ids]}
        if index is not None:
            body["index"] = index
        return self.request("PATCH", "/playlist-tracks", body)

    # ------------------------------------------------------------------ Tags, Wiedergabe, Steuerung
    def tags(self) -> dict:
        d = self.get("/tags")
        return {"categories": d.get("categories") or [], "tags": d.get("tags") or []}

    def tag_create(self, category_id, label: str) -> dict:
        d = self.request("POST", "/tag", {"categoryId": category_id, "label": label})
        return d.get("tag", d) if isinstance(d, dict) else {}

    def playing(self) -> dict:
        return self.get("/playing") or {}

    def queue(self) -> list:
        return (self.get("/queue") or {}).get("tracks") or []

    def control(self, action: str, parameters: dict | None = None):
        body = {"action": action}
        if parameters is not None:
            body["parameters"] = parameters
        return self.request("POST", "/control", body)


# =========================================================================== Hilfen
def norm_path(p: str) -> str:
    return (p or "").replace("\\", "/").strip().lower()


def flatten(nodes, depth=0, trail=()) -> list[dict]:
    """Playlist-Baum → Liste mit Pfad (Ordnernamen) und Tiefe."""
    out = []
    for n in nodes or []:
        path = trail + (str(n.get("name") or ""),)
        out.append({"id": n.get("id"), "name": n.get("name") or "", "type": str(n.get("type")), "depth": depth,
                    "path": list(path)})
        out += flatten(n.get("playlists"), depth + 1, path)
    return out
