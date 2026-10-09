"""MarKusSXCH TagStudio – Snapshots und Änderungsjournal (Konzept: docs/KONZEPT-SNAPSHOTS.md).

Ein Snapshot hält den Tag-Zustand aller MP3-Dateien eines überwachten Ordners fest – byte-genau, ohne Audio.
Gespeichert wird inhaltsadressiert (wie Git): jeder ID3-Frame liegt einmal als Objekt (SHA-256, zlib) im Speicher,
ein Manifest je Snapshot verweist nur darauf. Unveränderte Dateien und Frames kosten in weiteren Snapshots
fast nichts.

Speicher (Standard ~/TagStudio/Snapshots, wählbar):
  store.json                       Format-Version des Speichers
  objects/ab/<sha256>.z            Objekte (Frame-Bytes, Tag-Kopf, Padding, ID3v1)
  libs/<id>/library.json           überwachter Ordner
  libs/<id>/snaps/<id>.json.gz     Manifest eines Snapshots

Eintrag je Datei im Manifest: {"p": relativer Pfad (/), "size", "mt": mtime_ns, "audio": Audio-Schlüssel,
"th": SHA-256 des ganzen Tags (+ID3v1), "tag": [Objekt-Hashes] (Teile in Reihenfolge, ergeben den Tag-Bereich
byte-genau), "v1": Objekt-Hash|None, "ver": 2|3|4|0}.
Nur Standardbibliothek.
"""
from __future__ import annotations

import datetime
import gzip
import hashlib
import json
import os
import shutil
import struct
import tempfile
import time
import uuid
import zlib

FORMAT = 1                     # Format-Version des Speichers (store.json) – bei Änderungen erhöhen und migrieren
MANIFEST_VERSION = 1
DEFAULT_KEEP = 20              # automatische Snapshots, die immer bleiben
DEFAULT_WEEKS = 12             # danach je einer pro Woche für so viele Wochen


def default_dir() -> str:
    return os.path.join(os.path.expanduser("~"), "TagStudio", "Snapshots")


class StoreError(Exception):
    pass


# =========================================================================== Tag-Bereich lesen und zerlegen
def _syncsafe(b: bytes) -> int:
    return (b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3]


def read_tags(path: str) -> dict:
    """Tag-Bytes (ID3v2-Bereich inkl. Padding/Footer), ID3v1 und Audio-Grenzen einer Datei."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(10)
        tag, ver = b"", 0
        if len(head) == 10 and head[:3] == b"ID3" and head[3] in (2, 3, 4):
            ver = head[3]
            total = 10 + _syncsafe(head[6:10]) + (10 if ver == 4 and head[5] & 0x10 else 0)
            f.seek(0)
            tag = f.read(min(total, size))
        v1 = b""
        if size - len(tag) >= 128:
            f.seek(-128, os.SEEK_END)
            t = f.read(128)
            if t[:3] == b"TAG":
                v1 = t
    return {"tag": tag, "v1": v1, "ver": ver, "audio_start": len(tag), "audio_end": size - len(v1), "size": size}


def split_tag(tag: bytes) -> list[bytes]:
    """Tag-Bereich in Teile zerlegen: Kopf (+erweiterter Kopf), je Frame ein Teil, Rest (Padding/Footer).
    Die Teile ergeben aneinandergehängt immer exakt die Original-Bytes – eine falsch erkannte Grösse kostet nur
    Platz, nie Daten. Bei Unsynchronisation auf Tag-Ebene bleibt der Tag ein Stück."""
    if len(tag) < 10 or tag[:3] != b"ID3":
        return [tag] if tag else []
    ver, flags = tag[3], tag[5]
    if ver == 2 or (ver == 3 and flags & 0x80) or (flags & 0x40 and ver not in (3, 4)):
        return [tag]
    pos = 10
    if flags & 0x40 and len(tag) >= 14:
        ext = struct.unpack(">I", tag[10:14])[0] + 4 if ver == 3 else _syncsafe(tag[10:14])
        pos = min(len(tag), 10 + ext)
    parts = [tag[:pos]]
    end = len(tag) - (10 if ver == 4 and flags & 0x10 else 0)
    while pos + 10 <= end:
        fid = tag[pos:pos + 4]
        if fid == b"\x00\x00\x00\x00" or not all(48 <= c <= 57 or 65 <= c <= 90 for c in fid):
            break
        raw = tag[pos + 4:pos + 8]
        n = _syncsafe(raw) if ver == 4 and not any(c & 0x80 for c in raw) else struct.unpack(">I", raw)[0]
        if n <= 0 or pos + 10 + n > end:
            break
        parts.append(tag[pos:pos + 10 + n])
        pos += 10 + n
    if pos < len(tag):
        parts.append(tag[pos:])
    assert b"".join(parts) == tag
    return parts


def audio_key(path: str, info: dict) -> str:
    import waveform
    return waveform.audio_key(path, info["audio_start"], info["audio_end"])


# =========================================================================== Speicher
class Store:
    def __init__(self, root: str | None = None):
        self.root = os.path.abspath(root or default_dir())
        self.readonly = False
        meta = os.path.join(self.root, "store.json")
        if os.path.exists(meta):
            try:
                with open(meta, encoding="utf-8") as fh:
                    m = json.load(fh)
            except (OSError, ValueError) as ex:
                raise StoreError(f"Snapshot-Speicher nicht lesbar: {ex}") from ex
            fmt = int(m.get("format", 0))
            if fmt > FORMAT:
                self.readonly = True      # neueres TagStudio hat ihn angelegt → nur lesen
            elif fmt < FORMAT:
                self._migrate(fmt)
        self.format = FORMAT

    # ------------------------------------------------------------------ Grundlagen
    def _init(self):
        if self.readonly:
            raise StoreError("Dieser Snapshot-Speicher stammt aus einer neueren TagStudio-Version und wird nur "
                             "gelesen – bitte TagStudio aktualisieren.")
        os.makedirs(os.path.join(self.root, "objects"), exist_ok=True)
        os.makedirs(os.path.join(self.root, "libs"), exist_ok=True)
        meta = os.path.join(self.root, "store.json")
        if not os.path.exists(meta):
            from version import VERSION
            _write_json(meta, {"format": FORMAT, "created": _now(), "created_by": f"TagStudio {VERSION}"})

    def _migrate(self, old: int):
        """Ältere Formate anheben (Format 1 ist das erste – hier kommen künftige Schritte hin)."""
        return

    def _obj(self, h: str) -> str:
        return os.path.join(self.root, "objects", h[:2], h + ".z")

    def put(self, data: bytes) -> str:
        h = hashlib.sha256(data).hexdigest()
        p = self._obj(h)
        if not os.path.exists(p):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            tmp = p + ".tmp"
            with open(tmp, "wb") as fh:
                fh.write(zlib.compress(data, 6))
            os.replace(tmp, p)
        return h

    def get(self, h: str) -> bytes:
        try:
            with open(self._obj(h), "rb") as fh:
                return zlib.decompress(fh.read())
        except (OSError, zlib.error) as ex:
            raise StoreError(f"Objekt {h[:12]}… fehlt oder ist beschädigt") from ex

    # ------------------------------------------------------------------ Bibliotheken
    def _lib_dir(self, lid: str) -> str:
        if not lid or not all(c in "0123456789abcdef" for c in lid):
            raise StoreError("Ungültige Bibliothek")
        return os.path.join(self.root, "libs", lid)

    def libraries(self) -> list[dict]:
        base = os.path.join(self.root, "libs")
        out = []
        for lid in sorted(os.listdir(base)) if os.path.isdir(base) else []:
            try:
                with open(os.path.join(base, lid, "library.json"), encoding="utf-8") as fh:
                    d = json.load(fh)
                d["id"] = lid
                out.append(d)
            except (OSError, ValueError):
                continue
        return sorted(out, key=lambda d: d.get("name", "").lower())

    def library(self, lid: str) -> dict:
        with open(os.path.join(self._lib_dir(lid), "library.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        d["id"] = lid
        return d

    def add_library(self, root: str, name: str | None = None) -> dict:
        root = os.path.abspath(root)
        if not os.path.isdir(root):
            raise StoreError(f"Ordner nicht gefunden: {root}")
        for d in self.libraries():
            if os.path.normcase(d.get("root", "")) == os.path.normcase(root):
                return d
        self._init()
        lid = uuid.uuid4().hex[:12]
        d = {"root": root, "name": name or os.path.basename(root.rstrip("\\/")) or root, "created": _now()}
        os.makedirs(os.path.join(self._lib_dir(lid), "snaps"), exist_ok=True)
        _write_json(os.path.join(self._lib_dir(lid), "library.json"), d)
        d["id"] = lid
        return d

    def update_library(self, lid: str, **kw) -> dict:
        d = self.library(lid)
        d.update({k: v for k, v in kw.items() if k in ("root", "name")})
        _write_json(os.path.join(self._lib_dir(lid), "library.json"), {k: v for k, v in d.items() if k != "id"})
        return d

    def remove_library(self, lid: str):
        shutil.rmtree(self._lib_dir(lid), ignore_errors=True)
        self.gc()

    # ------------------------------------------------------------------ Snapshots
    def _snap_path(self, lid: str, sid: str) -> str:
        if not sid or not all(c.isalnum() or c in "-_" for c in sid):
            raise StoreError("Ungültiger Snapshot")
        return os.path.join(self._lib_dir(lid), "snaps", sid + ".json.gz")

    def snapshots(self, lid: str) -> list[dict]:
        """Snapshots einer Bibliothek (neueste zuerst), nur Kopfdaten."""
        d = os.path.join(self._lib_dir(lid), "snaps")
        out = []
        for n in os.listdir(d) if os.path.isdir(d) else []:
            if n.endswith(".json.gz"):
                try:
                    m = self.manifest(lid, n[:-8])
                except StoreError:
                    continue
                out.append({k: m.get(k) for k in ("id", "created", "label", "pinned", "auto", "count")})
        return sorted(out, key=lambda m: m["created"], reverse=True)

    def manifest(self, lid: str, sid: str) -> dict:
        try:
            with gzip.open(self._snap_path(lid, sid), "rt", encoding="utf-8") as fh:
                m = json.load(fh)
        except (OSError, ValueError) as ex:
            raise StoreError(f"Snapshot nicht lesbar: {ex}") from ex
        if int(m.get("v", 1)) > MANIFEST_VERSION:
            raise StoreError("Snapshot aus einer neueren TagStudio-Version – bitte aktualisieren.")
        return m

    def write_manifest(self, lid: str, m: dict) -> dict:
        self._init()
        p = self._snap_path(lid, m["id"])
        tmp = p + ".tmp"
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            json.dump(m, fh, separators=(",", ":"))
        os.replace(tmp, p)
        self._stats_dirty()
        return m

    def update_snapshot(self, lid: str, sid: str, label=None, pinned=None) -> dict:
        m = self.manifest(lid, sid)
        if label is not None:
            m["label"] = str(label)[:120]
        if pinned is not None:
            m["pinned"] = bool(pinned)
        self.write_manifest(lid, m)
        return {k: m.get(k) for k in ("id", "created", "label", "pinned", "auto", "count")}

    def delete_snapshot(self, lid: str, sid: str) -> int:
        os.remove(self._snap_path(lid, sid))
        self._stats_dirty()
        return self.gc()

    def latest(self, lid: str, before: str | None = None) -> dict | None:
        snaps = self.snapshots(lid)
        if before:
            snaps = [s for s in snaps if s["created"] < before]
        return self.manifest(lid, snaps[0]["id"]) if snaps else None

    # ------------------------------------------------------------------ Aufräumen
    def prune(self, lid: str, keep: int = DEFAULT_KEEP, weeks: int = DEFAULT_WEEKS, now: datetime.datetime | None = None
              ) -> list[str]:
        """Automatische Snapshots ausdünnen: die neuesten `keep` bleiben, danach je einer pro Kalenderwoche der
        letzten `weeks` Wochen. Angeheftete und benannte (nicht automatische) Snapshots bleiben immer."""
        now = now or datetime.datetime.now()
        autos = [s for s in self.snapshots(lid) if s.get("auto") and not s.get("pinned")]
        keep_ids = {s["id"] for s in autos[:max(0, keep)]}
        seen_weeks = set()
        limit = now - datetime.timedelta(weeks=max(0, weeks))
        for s in autos[max(0, keep):]:
            t = _parse(s["created"])
            wk = t.isocalendar()[:2]
            if t >= limit and wk not in seen_weeks:
                seen_weeks.add(wk)
                keep_ids.add(s["id"])
        gone = [s["id"] for s in autos if s["id"] not in keep_ids]
        for sid in gone:
            os.remove(self._snap_path(lid, sid))
        if gone:
            self._stats_dirty()
            self.gc()
        return gone

    def _all_refs(self) -> dict[str, list]:
        """Objekt → [(lib, snap)…] über alle Manifeste."""
        refs: dict[str, list] = {}
        for lib in self.libraries():
            for s in self.snapshots(lib["id"]):
                m = self.manifest(lib["id"], s["id"])
                for e in m["files"]:
                    for h in (e.get("tag") or []) + ([e["v1"]] if e.get("v1") else []):
                        refs.setdefault(h, []).append((lib["id"], s["id"]))
        return refs

    def gc(self) -> int:
        """Nicht mehr benutzte Objekte entfernen → freigegebene Bytes."""
        if self.readonly:
            return 0
        used = set(self._all_refs())
        freed = 0
        base = os.path.join(self.root, "objects")
        for d, _dirs, files in os.walk(base):
            for n in files:
                if n.endswith(".z") and n[:-2] not in used:
                    p = os.path.join(d, n)
                    try:
                        freed += os.path.getsize(p)
                        os.remove(p)
                    except OSError:
                        pass
        self._stats_dirty()
        return freed

    # ------------------------------------------------------------------ Speicherplatz
    def _stats_dirty(self):
        try:
            os.remove(os.path.join(self.root, "stats.json"))
        except OSError:
            pass

    def sizes(self) -> dict:
        """Belegter Platz: gesamt, je Bibliothek und je Snapshot (eigener Anteil = nur dort benutzte Objekte)."""
        cache = os.path.join(self.root, "stats.json")
        try:
            with open(cache, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            pass
        refs = self._all_refs()
        objsize = {}
        total = 0
        for d, _dirs, files in os.walk(os.path.join(self.root, "objects")):
            for n in files:
                if n.endswith(".z"):
                    s = os.path.getsize(os.path.join(d, n))
                    objsize[n[:-2]] = s
                    total += s
        own: dict[str, int] = {}
        libs: dict[str, int] = {}
        for h, where in refs.items():
            s = objsize.get(h, 0)
            snaps = {w for w in where}
            if len(snaps) == 1:
                k = "%s/%s" % next(iter(snaps))
                own[k] = own.get(k, 0) + s
            for lid in {w[0] for w in where}:
                libs[lid] = libs.get(lid, 0) + s
        for lib in self.libraries():
            for s in self.snapshots(lib["id"]):
                p = self._snap_path(lib["id"], s["id"])
                ms = os.path.getsize(p)
                k = f"{lib['id']}/{s['id']}"
                own[k] = own.get(k, 0) + ms
                libs[lib["id"]] = libs.get(lib["id"], 0) + ms
                total += ms
        out = {"total": total, "libs": libs, "snaps": own}
        if os.path.isdir(self.root) and not self.readonly:
            _write_json(cache, out)
        return out

    # ------------------------------------------------------------------ Tags eines Eintrags
    def tag_bytes(self, entry: dict) -> tuple[bytes, bytes]:
        tag = b"".join(self.get(h) for h in (entry.get("tag") or []))
        v1 = self.get(entry["v1"]) if entry.get("v1") else b""
        return tag, v1


class MemStore:
    """Für den Live-Zustand: Objekte nur im Speicher (nichts wird geschrieben)."""

    def __init__(self, base: Store):
        self.base, self.mem = base, {}

    def put(self, data: bytes) -> str:
        h = hashlib.sha256(data).hexdigest()
        self.mem.setdefault(h, data)
        return h

    def get(self, h: str) -> bytes:
        return self.mem[h] if h in self.mem else self.base.get(h)

    def tag_bytes(self, entry):
        tag = b"".join(self.get(h) for h in (entry.get("tag") or []))
        return tag, (self.get(entry["v1"]) if entry.get("v1") else b"")


# =========================================================================== Scan
def list_mp3(root: str, cancel=None) -> list[str]:
    from compare import scan
    return scan(root, True, cancel)


def rel(root: str, path: str) -> str:
    return os.path.relpath(path, root).replace(os.sep, "/")


def entry_for(path: str, root: str, sink, st=None) -> dict:
    """Datei lesen und Eintrag bilden; Objekte gehen in `sink` (Store oder MemStore)."""
    st = st or os.stat(path)
    info = read_tags(path)
    parts = split_tag(info["tag"])
    th = hashlib.sha256(info["tag"] + b"|" + info["v1"]).hexdigest()
    return {"p": rel(root, path), "size": st.st_size, "mt": st.st_mtime_ns, "audio": audio_key(path, info),
            "th": th, "tag": [sink.put(p) for p in parts], "v1": sink.put(info["v1"]) if info["v1"] else None,
            "ver": info["ver"]}


def scan(root: str, sink, prev: dict | None = None, thorough=False, cancel=None, progress=None) -> tuple[list, list]:
    """Alle MP3 unter root einlesen. Unveränderte Dateien (Grösse + Änderungszeit wie in `prev`) werden ohne Lesen
    übernommen. → (Einträge, Fehler)."""
    progress = progress or (lambda m: None)
    known = {e["p"]: e for e in (prev or {}).get("files", [])}
    paths = list_mp3(root, cancel)
    progress(("total", len(paths)))
    out, errors = [], []
    for i, p in enumerate(paths, 1):
        if cancel is not None and cancel.is_set():
            from compare import Cancelled
            raise Cancelled()
        try:
            st = os.stat(p)
            old = known.get(rel(root, p))
            if old and not thorough and old["size"] == st.st_size and old["mt"] == st.st_mtime_ns:
                out.append(old)
            else:
                out.append(entry_for(p, root, sink, st))
        except OSError as ex:
            errors.append(f"{rel(root, p)}: {ex}")
        if i % 25 == 0 or i == len(paths):
            progress(("progress", i, len(paths), p))
    return out, errors


def quick_changes(root: str, m: dict | None) -> dict:
    """Nur Grösse/Änderungszeit prüfen (schnell, ohne Lesen) → {"changed", "new", "removed", "total"}."""
    known = {e["p"]: e for e in (m or {}).get("files", [])}
    paths = list_mp3(root)
    seen, changed, new = set(), 0, 0
    for p in paths:
        r = rel(root, p)
        seen.add(r)
        e = known.get(r)
        try:
            st = os.stat(p)
        except OSError:
            continue
        if e is None:
            new += 1
        elif e["size"] != st.st_size or e["mt"] != st.st_mtime_ns:
            changed += 1
    return {"changed": changed, "new": new, "removed": len(set(known) - seen), "total": len(paths)}


def create(store: Store, lid: str, label: str = "", auto=False, pinned=False, thorough=False, cancel=None,
           progress=None) -> dict:
    lib = store.library(lid)
    if not os.path.isdir(lib["root"]):
        raise StoreError(f"Ordner nicht erreichbar: {lib['root']}")
    store._init()
    prev = store.latest(lid)
    files, errors = scan(lib["root"], store, prev, thorough, cancel, progress)
    now = datetime.datetime.now()
    m = {"v": MANIFEST_VERSION, "id": now.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6], "created": _now(now),
         "label": label or ("Automatisch" if auto else "Snapshot"), "auto": bool(auto), "pinned": bool(pinned),
         "root": lib["root"], "count": len(files), "files": files, "errors": errors[:200]}
    store.write_manifest(lid, m)
    return {k: m.get(k) for k in ("id", "created", "label", "pinned", "auto", "count")} | {"errors": errors}


# =========================================================================== Journal
def _mp3(tag: bytes, v1: bytes):
    """Tags als MP3File (über eine kleine Hilfsdatei, wie bei den Sicherungen)."""
    from id3tags import MP3File
    fd, tmp = tempfile.mkstemp(suffix=".mp3", prefix="tagstudio_snap_")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(tag + b"\x00" * 1024 + v1)
        return MP3File(tmp)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _disp(it) -> str:
    if it is None:
        return ""
    s = it.display().replace("\r", "").replace("\n", " ⏎ ")
    return s if len(s) <= 600 else s[:600] + " …"


def field_diff(old_f, new_f) -> list[dict]:
    return diff_items(old_f.items, new_f.items)


def diff_items(old: dict, new: dict) -> list[dict]:
    """Feldvergleich auf Werte (nicht Bytes) zweier Item-Sammlungen."""
    from id3tags import key_label, sort_key
    rows = []
    for k in sorted(set(old) | set(new), key=sort_key):
        a, b = old.get(k), new.get(k)
        if a == b:
            continue
        rows.append({"key": k, "label": key_label(k),
                     "state": "changed" if a is not None and b is not None else "removed" if b is None else "added",
                     "old": _disp(a), "new": _disp(b)})
    return rows


def journal(a: dict, b_files: list, src_a, src_b, detail_limit=5000) -> dict:
    """Unterschied Zustand A (Manifest) → B (Einträge). src_*: woher die Objekte kommen (Store/MemStore).
    → {"rows": [{"p", "p_old", "status", "fields": […], "ver": [a, b]}…], "counts": {…}}"""
    A = {e["p"]: e for e in a.get("files", [])}
    B = {e["p"]: e for e in b_files}
    rows = []
    only_a = [p for p in A if p not in B]
    only_b = [p for p in B if p not in A]
    # Umbenannt/verschoben: gleicher Audio-Schlüssel
    by_audio = {}
    for p in only_a:
        by_audio.setdefault(A[p]["audio"], []).append(p)
    pairs = [(p, p) for p in A if p in B]
    renamed = set()
    for p in only_b:
        cand = by_audio.get(B[p]["audio"])
        if cand:
            q = cand.pop(0)
            pairs.append((q, p))
            renamed.add(p)
    matched_a = {q for q, _p in pairs}
    for q, p in pairs:
        ea, eb = A[q], B[p]
        audio = ea["audio"] != eb["audio"]
        tags = ea["th"] != eb["th"]
        if not (audio or tags or p in renamed):
            continue
        fields = []
        status = "renamed" if p in renamed else "audio" if audio and not tags else "changed"
        if tags and len(rows) < detail_limit:
            fa, fb = _mp3(*src_a.tag_bytes(ea)), _mp3(*src_b.tag_bytes(eb))
            fields = field_diff(fa, fb)
            if not fields and status == "changed":
                status = "rewrite"           # Bytes anders, Werte gleich (v2.3→v2.4, Kodierung, Padding)
        rows.append({"p": p, "p_old": q if q != p else "", "status": status, "audio": audio,
                     "fields": fields, "ver": [ea.get("ver"), eb.get("ver")]})
    for p in only_b:
        if p not in renamed:
            rows.append({"p": p, "p_old": "", "status": "new", "audio": False, "fields": [], "ver": [None, B[p].get("ver")]})
    for p in only_a:
        if p not in matched_a:
            rows.append({"p": p, "p_old": "", "status": "removed", "audio": False, "fields": [],
                         "ver": [A[p].get("ver"), None]})
    rows.sort(key=lambda r: r["p"].lower())
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        if r["audio"] and r["status"] != "audio":
            counts["audio"] = counts.get("audio", 0) + 1
    return {"rows": rows, "counts": counts}


# =========================================================================== Hilfen
def _now(t: datetime.datetime | None = None) -> str:
    return (t or datetime.datetime.now()).strftime("%Y-%m-%dT%H:%M:%S")


def _parse(s: str) -> datetime.datetime:
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")


def _write_json(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def fmt_age(created: str) -> str:
    d = time.time() - _parse(created).timestamp()
    if d < 3600:
        return f"vor {max(1, int(d // 60))} Min."
    if d < 86400:
        return f"vor {int(d // 3600)} Std."
    return f"vor {int(d // 86400)} Tag(en)"
