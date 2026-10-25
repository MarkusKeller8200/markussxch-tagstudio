"""MarKusSXCH TagStudio – Gekaufte Titel (#285): Käufe aller Stores sammeln, mit der Bibliothek abgleichen.

Gespeichert im Datenordner des Profils (``~/TagStudio/Käufe/kaeufe.json``, atomar geschrieben):

    {"format": 1,
     "stores": {"beatport": {"name": "Beatport", "refreshed": 1761350000, "count": 120}},
     "items":  {"beatport:123": {"store": "beatport", "id": "123", "title", "mix", "artist", "dur", "key", "bpm",
                                 "catalog", "isrc", "label", "release", "genre", "url", "bought", "dl",
                                 "first_seen", "status", "file", "downloaded"}}}

Die Stores sind Plugins mit ``store_purchases(ctx)`` (Liste der Käufe) und ``store_download(ctx, items, dest)``.
„Aktualisieren“ führt neue Käufe zu und behält bei bekannten zuerst gesehen, Datei und Download. Der Abgleich nutzt
dieselbe Zuordnung wie „Mit Bibliothek abgleichen“ bei den Playlists (ISRC bzw. Künstler + Titel + Mix).
Nur Standardbibliothek.
"""
from __future__ import annotations

import json
import os
import re
import time

import playlists

FORMAT = 1
FIELDS = ("id", "title", "mix", "artist", "dur", "key", "bpm", "catalog", "isrc", "label", "release", "genre", "url",
          "bought", "dl", "preorder")
STATUSES = ("library", "inbox", "unclear", "missing")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _num(v):
    try:
        x = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return x if x == x and x > 0 else None


def clean_item(store: str, x) -> dict | None:
    """Eintrag eines Stores vereinheitlichen; ohne ID oder Titel → None."""
    if not isinstance(x, dict) or x.get("id") in (None, "") or not str(x.get("title") or "").strip():
        return None
    out = {"store": str(store), "id": str(x["id"])}
    for k in ("title", "mix", "artist", "key", "catalog", "isrc", "label", "release", "genre", "url"):
        v = " ".join(str(x.get(k) or "").split())[:300]
        if v:
            out[k] = v
    if out.get("isrc"):
        out["isrc"] = out["isrc"].upper()
    if out.get("url") and not out["url"].startswith("https://"):
        out.pop("url")
    d = _num(x.get("dur"))
    if d:
        out["dur"] = int(round(d))
    b = _num(x.get("bpm"))
    if b:
        out["bpm"] = round(b, 2)
    bought = str(x.get("bought") or "").strip()
    if _DATE.match(bought):
        out["bought"] = bought[:19]
    if isinstance(x.get("dl"), dict):
        out["dl"] = x["dl"]
    if x.get("preorder"):
        out["preorder"] = True
    if x.get("received"):
        out["received"] = True                             # beim Store schon einmal heruntergeladen
    return out


def key_of(store, sid) -> str:
    return f"{store}:{sid}"


class Store:
    def __init__(self, root: str):
        self.root = root
        self.path = os.path.join(root, "kaeufe.json")
        self._data: dict | None = None
        self._mtime = None

    def _stamp(self):
        try:
            return os.path.getmtime(self.path)
        except OSError:
            return None

    @property
    def data(self) -> dict:
        if self._data is not None and self._stamp() != self._mtime:     # von außen geändert (anderes Fenster, Test)
            self._data = None
        if self._data is None:
            self._mtime = self._stamp()
            try:
                with open(self.path, encoding="utf-8") as fh:
                    d = json.load(fh)
            except (OSError, ValueError):
                d = {}
            d = d if isinstance(d, dict) else {}
            d["format"] = FORMAT
            for k in ("stores", "items"):
                if not isinstance(d.get(k), dict):
                    d[k] = {}
            self._data = d
        return self._data

    def save(self):
        os.makedirs(self.root, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)
        self._mtime = self._stamp()

    def items(self) -> list[dict]:
        return list(self.data["items"].values())

    def merge(self, store: str, name: str, items, full: bool = True) -> dict:
        """Käufe eines Stores zuführen → {"new", "total"}. Bekannte behalten first_seen, status, file, downloaded."""
        now = int(time.time())
        all_ = self.data["items"]
        new = 0
        for x in items or []:
            it = clean_item(store, x)
            if it is None:
                continue
            k = key_of(store, it["id"])
            old = all_.get(k)
            if old is None:
                new += 1
                it["first_seen"] = now
                it["status"] = "missing"
            else:
                for f in ("first_seen", "status", "file", "downloaded", "cands", "reason", "linked"):
                    if f in old:
                        it[f] = old[f]
                if not it.get("bought") and old.get("bought"):
                    it["bought"] = old["bought"]
            all_[k] = it
        n = sum(1 for v in all_.values() if v.get("store") == store)
        meta = dict(self.data["stores"].get(store) or {})
        meta.update(name=str(name), refreshed=now, count=n)
        if full:
            meta["full_at"] = now                              # ganze Liste geholt (sonst nur neue Käufe)
        self.data["stores"][store] = meta
        self.save()
        return {"new": new, "total": n}

    def set_file(self, key, path, downloaded=False):
        it = self.data["items"].get(key)
        if it is None:
            return
        it["file"] = path
        it["status"] = "inbox"
        if downloaded:
            it["downloaded"] = int(time.time())

    def link(self, key, path, inbox: str = ""):
        """Kauf von Hand einer Datei zuordnen (bleibt bei weiteren Abgleichen); path "" = Zuordnung aufheben."""
        it = self.data["items"].get(key)
        if it is None:
            raise ValueError("Kauf nicht gefunden.")
        if path:
            if not os.path.isfile(path):
                raise ValueError("Datei nicht gefunden.")
            inbox_k = playlists.nk(inbox) + os.sep if inbox else ""
            it.update(file=path, linked=True, reason="von Hand zugeordnet",
                      status="inbox" if inbox_k and playlists.nk(path).startswith(inbox_k) else "library")
            it.pop("cands", None)
        else:
            for k in ("linked", "file", "cands"):
                it.pop(k, None)
            it.update(status="missing", reason="")
        self.save()

    def match(self, index, inbox: str = "", strict: bool = False) -> dict:
        """Status aller Käufe neu bestimmen. index: playlists.LibIndex der Bibliothek (inkl. Eingang).
        Dateien im Eingangsordner → „im Eingang“, sonst „in Bibliothek“. strict (#338): Mix muss passen, auch bei
        gleicher ISRC (playlists.match_ref). → Zähler je Status"""
        inbox_k = playlists.nk(inbox) + os.sep if inbox else ""
        count = {s: 0 for s in STATUSES}
        for it in self.data["items"].values():
            if it.get("linked") and it.get("file") and os.path.isfile(it["file"]):     # von Hand zugeordnet (#290)
                it["status"] = "inbox" if inbox_k and playlists.nk(it["file"]).startswith(inbox_k) else "library"
                it["reason"] = "von Hand zugeordnet"
                it.pop("cands", None)
                count[it["status"]] += 1
                continue
            it.pop("linked", None)
            ref = {k: it.get(k, "") for k in ("artist", "title", "mix", "isrc")}
            ref["dur"] = it.get("dur") or 0
            r = playlists.match_ref(ref, index, strict=strict)
            it["reason"] = r.get("reason", "")
            it["kind"] = r.get("kind", "")
            if r["status"] == "sure" and r.get("path"):
                it["file"] = r["path"]
                it["status"] = "inbox" if inbox_k and playlists.nk(r["path"]).startswith(inbox_k) else "library"
                it.pop("cands", None)
            elif it.get("downloaded") and it.get("file") and os.path.isfile(it["file"]):
                it["status"] = "inbox"                     # eben heruntergeladen, Tags weichen evtl. noch ab
            elif r["status"] == "unclear":
                it["status"] = "unclear"
                it["cands"] = list(r.get("candidates") or [])[:3]
                it.pop("file", None)
            else:
                it["status"] = "missing"
                it.pop("file", None)
                it.pop("cands", None)
            count[it["status"]] += 1
        self.save()
        return count
