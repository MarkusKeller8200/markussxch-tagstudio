"""MarKusSXCH TagStudio – Listen-Cache (#70): Tagger und Vergleich sofort aus dem Cache anzeigen.

Je eingelesenem Ordner eine Datei ~/TagStudio/cache/lists/<id>.json.gz mit je Titel: Grösse, Änderungszeit,
**Hash der Tag-Bytes** (wie MP3File.disk_sig), die Tag-Bytes selbst und die MPEG-Angaben (Dauer, Bitrate …).
Cover und andere grosse Frames liegen einmal als Objekt unter lists/objects (gleiche Cover eines Albums nur einmal).

Ablauf: Beim Einlesen wird für jede Datei nur `stat` gemacht. Stimmen Grösse und Änderungszeit mit dem Cache,
wird die Datei **nicht geöffnet** – die Tags kommen aus dem Cache. Danach prüft `verify` im Hintergrund jede so
geladene Datei über den Hash ihrer Tag-Bytes (liest nur den Tag-Bereich, kein Audio) und meldet Abweichungen –
auch von Programmen, die die Änderungszeit erhalten. Speichern ist zusätzlich durch den Konfliktschutz (#55)
abgesichert. Nur Standardbibliothek.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import threading

FORMAT = 1
DIR = os.path.join(os.path.expanduser("~"), "TagStudio", "cache", "lists")
INLINE_MAX = 4096          # grössere Frames (Cover, Wellenform-Daten) als Objekt
_lock = threading.Lock()


def _id(root: str) -> str:
    return hashlib.sha1(os.path.normcase(os.path.abspath(root)).encode("utf-8")).hexdigest()[:24]


def _obj_path(h: str) -> str:
    return os.path.join(DIR, "objects", h[:2], h + ".bin")


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def tag_sig(path: str) -> tuple[str, int, int]:
    """Hash der Tag-Bytes direkt von der Platte (wie MP3File.disk_sig) → (hash, size, mtime_ns).
    Liest nur den ID3v2-Bereich und die letzten 128 Byte."""
    import id3tags
    st = os.stat(path)
    return id3tags.disk_sig(path), st.st_size, st.st_mtime_ns


class ListCache:
    """Cache eines Ordners (bzw. einer einzelnen Datei)."""

    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.base = self.root if os.path.isdir(self.root) else os.path.dirname(self.root)
        self.path = os.path.join(DIR, _id(self.root) + ".json.gz")
        self.entries: dict = {}
        self.seen: set = set()
        self.dirty = False
        self.hits = self.misses = 0
        try:
            with gzip.open(self.path, "rt", encoding="utf-8") as fh:
                d = json.load(fh)
            if d.get("format") == FORMAT and os.path.normcase(d.get("root", "")) == os.path.normcase(self.root):
                self.entries = d.get("files", {})
        except (OSError, ValueError, EOFError):
            self.entries = {}

    def rel(self, path: str) -> str:
        return os.path.relpath(path, self.base).replace(os.sep, "/")

    # ------------------------------------------------------------------ lesen
    def lookup(self, path: str, st) -> dict | None:
        """Cache-Daten für MP3File.load(cached=…), wenn Grösse und Änderungszeit stimmen – sonst None."""
        r = self.rel(path)
        self.seen.add(r)
        e = self.entries.get(r)
        if not e or e.get("size") != st.st_size or e.get("mt") != st.st_mtime_ns:
            self.misses += 1
            return None
        try:
            parts = []
            for p in e["tag"]:
                if isinstance(p, str):
                    parts.append(base64.b64decode(p))
                else:
                    with open(_obj_path(p["o"]), "rb") as fh:
                        parts.append(fh.read())
            tag = b"".join(parts)
        except (OSError, KeyError, ValueError, TypeError):
            self.misses += 1
            return None
        self.hits += 1
        return {"head": tag[:10], "body": tag[10:], "v1": base64.b64decode(e.get("v1") or ""), "mpeg": e.get("mpeg", {}),
                "size": st.st_size, "mtime": st.st_mtime, "sig": e.get("sig")}

    # ------------------------------------------------------------------ schreiben
    def store(self, path: str, st, f) -> None:
        """Nach dem Lesen von der Platte: Eintrag anlegen (f._raw wird dabei entfernt)."""
        raw = f.__dict__.pop("_raw", None)
        if raw is None:
            return
        import snapshots
        head, body, v1 = raw
        parts = []
        for p in snapshots.split_tag(head + body):
            if len(p) > INLINE_MAX:
                h = hashlib.sha256(p).hexdigest()
                op = _obj_path(h)
                if not os.path.exists(op):
                    try:
                        os.makedirs(os.path.dirname(op), exist_ok=True)
                        tmp = op + ".tmp"
                        with open(tmp, "wb") as fh:
                            fh.write(p)
                        os.replace(tmp, op)
                    except OSError:
                        return
                parts.append({"o": h})
            else:
                parts.append(_b64(p))
        r = self.rel(path)
        self.seen.add(r)
        self.entries[r] = {"size": st.st_size, "mt": st.st_mtime_ns, "sig": f.disk_sig, "tag": parts,
                           "v1": _b64(v1), "mpeg": f.mpeg_state()}
        self.dirty = True

    def forget(self, path: str):
        if self.entries.pop(self.rel(path), None) is not None:
            self.dirty = True

    def save(self, prune: bool = True):
        """Cache schreiben; Einträge für nicht mehr vorhandene Dateien fallen weg."""
        if prune and self.seen:
            gone = set(self.entries) - self.seen
            for r in gone:
                del self.entries[r]
            self.dirty |= bool(gone)
        if not self.dirty:
            return
        try:
            os.makedirs(DIR, exist_ok=True)
            tmp = self.path + ".tmp"
            with _lock, gzip.open(tmp, "wt", encoding="utf-8", compresslevel=3) as fh:
                json.dump({"format": FORMAT, "root": self.root, "files": self.entries}, fh, separators=(",", ":"))
            os.replace(tmp, self.path)
            self.dirty = False
        except OSError:
            pass


def open_file(path: str, cache: ListCache | None, registry=None):
    """MP3File laden – aus dem Cache, wenn möglich. → (MP3File, aus_cache: bool)."""
    from id3tags import MP3File
    k = os.path.normcase(os.path.abspath(path))
    f = registry.get(k) if registry is not None else None
    if cache is None:
        if f is not None:
            f.load()
        else:
            f = MP3File(path)
        return f, False
    st = os.stat(path)
    hit = cache.lookup(path, st)
    if f is None:
        f = MP3File.__new__(MP3File)
        f.path = path
    if hit is not None:
        f.load(cached=hit)
        if hit.get("sig") and hit["sig"] != f.disk_sig:        # Cache beschädigt → von der Platte
            f.load(keep_raw=True)
            cache.store(path, st, f)
            hit = None
    else:
        f.load(keep_raw=True)
        cache.store(path, st, f)
    if registry is not None:
        registry[k] = f
    return f, hit is not None


def cache_size() -> tuple[int, int]:
    n = size = 0
    for root, _dirs, files in os.walk(DIR) if os.path.isdir(DIR) else []:
        for fn in files:
            if fn.endswith((".json.gz", ".bin")):
                try:
                    size += os.path.getsize(os.path.join(root, fn))
                    n += 1
                except OSError:
                    pass
    return n, size
