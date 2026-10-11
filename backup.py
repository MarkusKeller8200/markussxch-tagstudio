"""
backup.py – automatische Sicherung der Tags vor dem Speichern und Wiederherstellung.

Pro Speichervorgang entsteht ein ZIP-Archiv im Sicherungsordner (Standard: ~/TagStudio/Sicherungen).
Es enthält für jede Datei die exakten Tag-Bytes (ID3v2-Bereich inkl. Padding, ggf. ID3v1) und ein Manifest
mit Pfad, Größe, Zeitstempel und einem Fingerabdruck der Audiodaten. Audio wird NICHT gesichert – deshalb
sind Sicherungen klein, und beim Wiederherstellen wird geprüft, ob die Audiodaten noch dieselben sind.

Seit 4.3.0 (#59) können Sicherungen auch im **Snapshot-Speicher** liegen: dann stehen die Tag-Bytes als Objekte im
gemeinsamen Speicher (gleiche Tags nur einmal, auch über Snapshots hinweg) und nur ein kleines Manifest
`backups/<Zeit>.json` kommt dazu. ZIP-Sicherungen bleiben lesbar und wiederherstellbar.

Nur Standardbibliothek. Keine Datei wird automatisch gelöscht.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import zipfile

FP_BYTES = 256 * 1024  # Audio-Fingerabdruck: MD5 der ersten 256 KB nach dem Tag
MANIFEST = "manifest.json"


def default_dir() -> str:
    home = os.path.expanduser("~")
    new = os.path.join(home, "TagStudio", "Sicherungen")
    old = os.path.join(home, "MP3TagCompare", "Sicherungen")  # Version ≤ 2.8
    return old if os.path.isdir(old) and not os.path.isdir(new) else new


# --------------------------------------------------------------------------- Datei-Layout
def read_layout(path: str) -> dict:
    """Ermittelt Tag-Bereich, ID3v1 und Audio-Fingerabdruck einer MP3-Datei."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(10)
        audio_start = 0
        if len(head) == 10 and head[:3] == b"ID3" and head[3] in (2, 3, 4):
            s = head[6:10]
            tsize = (s[0] << 21) | (s[1] << 14) | (s[2] << 7) | s[3]
            audio_start = 10 + tsize + (10 if head[3] == 4 and head[5] & 0x10 else 0)
        has_v1 = False
        if size >= 128:
            f.seek(-128, os.SEEK_END)
            has_v1 = f.read(3) == b"TAG"
        audio_end = size - (128 if has_v1 else 0)
        f.seek(audio_start)
        fp = hashlib.md5(f.read(min(FP_BYTES, max(0, audio_end - audio_start)))).hexdigest()
    return {"size": size, "audio_start": audio_start, "has_v1": has_v1,
            "audio_len": max(0, audio_end - audio_start), "audio_md5": fp}


# --------------------------------------------------------------------------- Sichern
class BackupWriter:
    """Sammelt die Tags mehrerer Dateien in einem ZIP. Verwendung: add(...) je Datei, dann close()."""

    def __init__(self, folder: str | None = None, label: str = "Vor dem Speichern"):
        self.folder = folder or default_dir()
        os.makedirs(self.folder, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d_%H%M%S")
        name, n = f"{stamp}.zip", 1
        while os.path.exists(os.path.join(self.folder, name)):
            n += 1
            name = f"{stamp}_{n}.zip"
        self.path = os.path.join(self.folder, name)
        self.zip = zipfile.ZipFile(self.path + ".part", "w", zipfile.ZIP_DEFLATED, compresslevel=6)
        self.entries = []
        self.label = label
        self.created = time.time()

    def add(self, path: str):
        """Sichert die aktuellen Tag-Bytes der Datei (so wie sie jetzt auf dem Datenträger liegen)."""
        lay = read_layout(path)
        i = len(self.entries)
        with open(path, "rb") as f:
            tag = f.read(lay["audio_start"])
            v1 = b""
            if lay["has_v1"]:
                f.seek(-128, os.SEEK_END)
                v1 = f.read(128)
        self.zip.writestr(f"{i:05d}.tag", tag)
        if v1:
            self.zip.writestr(f"{i:05d}.v1", v1)
        st = os.stat(path)
        self.entries.append({
            "id": i, "path": os.path.abspath(path), "name": os.path.basename(path),
            "mtime": st.st_mtime, "tag_md5": hashlib.md5(tag).hexdigest(), **lay})

    def close(self) -> str | None:
        """Schreibt das Manifest. Leere Sicherungen werden verworfen."""
        if not self.entries:
            self.zip.close()
            os.remove(self.path + ".part")
            return None
        man = {"format": 1, "created": self.created, "label": self.label, "files": self.entries}
        self.zip.writestr(MANIFEST, json.dumps(man, ensure_ascii=False, indent=1))
        self.zip.close()
        os.replace(self.path + ".part", self.path)
        return self.path

    def abort(self):
        try:
            self.zip.close()
            os.remove(self.path + ".part")
        except OSError:
            pass


class StoreBackupWriter:
    """Wie BackupWriter, aber die Tag-Bytes gehen in den Snapshot-Speicher (#59)."""

    def __init__(self, store, label: str = "Vor dem Speichern"):
        store._init()
        self.store = store
        folder = os.path.join(store.root, "backups")
        os.makedirs(folder, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d_%H%M%S")
        name, n = f"{stamp}.json", 1
        while os.path.exists(os.path.join(folder, name)):
            n += 1
            name = f"{stamp}_{n}.json"
        self.path = os.path.join(folder, name)
        self.entries = []
        self.label = label
        self.created = time.time()
        self._pins: set[str] = set()

    def _unpin(self):
        import snapshots
        snapshots.PINNED.difference_update(self._pins)
        self._pins = set()

    def add(self, path: str):
        import snapshots
        lay = read_layout(path)
        with open(path, "rb") as f:
            tag = f.read(lay["audio_start"])
            v1 = b""
            if lay["has_v1"]:
                f.seek(-128, os.SEEK_END)
                v1 = f.read(128)
        parts = [self.store.put(p) for p in snapshots.split_tag(tag)]
        hv1 = self.store.put(v1) if v1 else None
        self._pins.update(parts + ([hv1] if hv1 else []))
        snapshots.PINNED.update(self._pins)
        st = os.stat(path)
        self.entries.append({
            "id": len(self.entries), "path": os.path.abspath(path), "name": os.path.basename(path),
            "mtime": st.st_mtime, "tag_md5": hashlib.md5(tag).hexdigest(), **lay, "tag": parts, "v1": hv1})

    def close(self) -> str | None:
        try:
            if not self.entries:
                return None
            man = {"format": 2, "kind": "store", "created": self.created, "label": self.label, "files": self.entries}
            tmp = self.path + ".part"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(man, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
            self.store._stats_dirty()
            return self.path
        finally:
            self._unpin()

    def abort(self):
        self.entries = []        # Objekte ohne Manifest räumt das nächste Aufräumen des Speichers weg
        self._unpin()


def make_writer(folder: str | None, label: str, store=None):
    """Sicherung im Snapshot-Speicher (wenn angegeben und beschreibbar), sonst als ZIP im Sicherungsordner."""
    if store is not None and not getattr(store, "readonly", False):
        try:
            return StoreBackupWriter(store, label)
        except OSError:
            pass                  # Speicher nicht erreichbar → klassische ZIP-Sicherung
    return BackupWriter(folder, label)


def is_store_backup(path: str) -> bool:
    return path.endswith(".json") and os.path.basename(os.path.dirname(path)) == "backups"


def _store_of(path: str):
    import snapshots
    return snapshots.Store(os.path.dirname(os.path.dirname(os.path.abspath(path))))


def _manifest(path: str) -> dict:
    if is_store_backup(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    with zipfile.ZipFile(path) as z:
        return json.loads(z.read(MANIFEST))


def _entry_bytes(path: str, entry: dict, z=None, store=None) -> tuple[bytes, bytes]:
    """Gesicherte Tag-Bytes und ID3v1 einer Datei (ZIP oder Snapshot-Speicher)."""
    if is_store_backup(path):
        return (store or _store_of(path)).tag_bytes(entry)
    own = z is None
    z = z or zipfile.ZipFile(path)
    try:
        tag = z.read(f"{entry['id']:05d}.tag")
        name = f"{entry['id']:05d}.v1"
        v1 = z.read(name) if name in z.namelist() else b""
        return tag, v1
    finally:
        if own:
            z.close()


def store_backup_bytes(store, man: dict) -> int:
    """Belegter Platz einer Speicher-Sicherung: Manifest + benutzte Objekte (geteilte Objekte voll gezählt)."""
    seen, total = set(), 0
    for e in man.get("files", []):
        for h in (e.get("tag") or []) + ([e["v1"]] if e.get("v1") else []):
            if h not in seen:
                seen.add(h)
                try:
                    total += os.path.getsize(store._obj(h))
                except OSError:
                    pass
    return total


# --------------------------------------------------------------------------- Auflisten
def list_backups(folder: str | None = None, store=None) -> list[dict]:
    """ZIP-Sicherungen im Ordner und (falls angegeben) Sicherungen im Snapshot-Speicher, neueste zuerst."""
    folder = folder or default_dir()
    out = []
    if store is not None:
        bdir = os.path.join(store.root, "backups")
        for name in (os.listdir(bdir) if os.path.isdir(bdir) else []):
            if not name.endswith(".json"):
                continue
            p = os.path.join(bdir, name)
            try:
                with open(p, encoding="utf-8") as fh:
                    man = json.load(fh)
                out.append({"path": p, "name": name[:-5], "created": man.get("created", os.path.getmtime(p)),
                            "label": man.get("label", ""), "count": len(man.get("files", [])), "where": "store",
                            "bytes": os.path.getsize(p) + store_backup_bytes(store, man), "files": man.get("files", [])})
            except (OSError, ValueError):
                out.append({"path": p, "name": name[:-5], "created": os.path.getmtime(p), "label": "(beschädigt)",
                            "count": 0, "bytes": os.path.getsize(p), "files": [], "broken": True, "where": "store"})
    if not os.path.isdir(folder):
        return sorted(out, key=lambda b: b["created"], reverse=True)
    for name in sorted(os.listdir(folder), reverse=True):
        if not name.endswith(".zip"):
            continue
        p = os.path.join(folder, name)
        try:
            with zipfile.ZipFile(p) as z:
                man = json.loads(z.read(MANIFEST))
            out.append({"path": p, "name": name, "created": man.get("created", os.path.getmtime(p)),
                        "label": man.get("label", ""), "count": len(man.get("files", [])), "where": "zip",
                        "bytes": os.path.getsize(p), "files": man.get("files", [])})
        except (OSError, KeyError, ValueError, zipfile.BadZipFile):
            out.append({"path": p, "name": name, "created": os.path.getmtime(p), "label": "(beschädigt)",
                        "count": 0, "bytes": os.path.getsize(p), "files": [], "broken": True, "where": "zip"})
    return sorted(out, key=lambda b: b["created"], reverse=True)


def check_entry(entry: dict) -> tuple[str, str]:
    """Status einer gesicherten Datei: ('ok'|'same'|'missing'|'audio', Text)."""
    p = entry["path"]
    if not os.path.exists(p):
        return "missing", "Datei nicht mehr vorhanden"
    try:
        lay = read_layout(p)
    except OSError as ex:
        return "missing", f"nicht lesbar: {ex}"
    if lay["audio_md5"] != entry["audio_md5"] or lay["audio_len"] != entry["audio_len"]:
        return "audio", "Audiodaten haben sich geändert – andere Datei?"
    with open(p, "rb") as f:
        tag_now = f.read(lay["audio_start"])
    if hashlib.md5(tag_now).hexdigest() == entry["tag_md5"] and lay["has_v1"] == entry["has_v1"]:
        return "same", "Tags entsprechen bereits der Sicherung"
    return "ok", "wiederherstellbar"


# --------------------------------------------------------------------------- Änderungen ansehen
def read_backup_tags(zip_path: str, entry: dict):
    """Die gesicherten Tags einer Datei als MP3File (über eine kleine Hilfsdatei: Tag + Stille + ID3v1)."""
    import tempfile
    from id3tags import MP3File
    tag, v1 = _entry_bytes(zip_path, entry)
    fd, tmp = tempfile.mkstemp(suffix=".mp3", prefix="tagstudio_bk_")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(tag + b"\x00" * 1024 + v1)
        return MP3File(tmp)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def diff_entry(zip_path: str, entry: dict) -> dict:
    """Welche Felder unterscheiden sich zwischen Sicherung und heutiger Datei?
    → {"rows": [{"key", "label", "state": changed|added|removed, "old", "new"}], "version": (alt, neu), "missing"}"""
    from id3tags import MP3File, key_label, sort_key
    old = read_backup_tags(zip_path, entry)
    if not os.path.exists(entry["path"]):
        return {"rows": [], "missing": True, "version": [old.tag_desc, ""]}
    cur = MP3File(entry["path"])
    rows = []
    for k in sorted(set(old.items) | set(cur.items), key=sort_key):
        a, b = old.items.get(k), cur.items.get(k)
        if a == b:
            continue
        rows.append({"key": k, "label": key_label(k),
                     "state": "changed" if a is not None and b is not None else "removed" if b is None else "added",
                     "old": _disp(a), "new": _disp(b)})
    return {"rows": rows, "missing": False, "version": [old.tag_desc, cur.tag_desc]}


def _disp(it) -> str:
    if it is None:
        return ""
    s = it.display().replace("\r", "").replace("\n", " ⏎ ")
    return s if len(s) <= 2000 else s[:2000] + " …"


# --------------------------------------------------------------------------- Wiederherstellen
def restore(zip_path: str, ids: list[int] | None = None, safety_folder: str | None = None,
            force_audio: bool = False, on_progress=None, cancel=None, store=None) -> list[tuple[str, str, str]]:
    """Schreibt die gesicherten Tags zurück. Vorher wird der aktuelle Zustand selbst gesichert (im Snapshot-Speicher,
    wenn `store` angegeben, sonst als ZIP). Liefert [(pfad, status, text)]; status: 'restored'|'skipped'|'error'."""
    src_store = _store_of(zip_path) if is_store_backup(zip_path) else None
    import contextlib
    with (contextlib.nullcontext() if src_store else zipfile.ZipFile(zip_path)) as z:
        man = _manifest(zip_path)
        entries = [e for e in man["files"] if ids is None or e["id"] in ids]
        todo, results = [], []
        for e in entries:
            st, txt = check_entry(e)
            if st == "ok" or (st == "audio" and force_audio):
                todo.append(e)
            else:
                results.append((e["path"], "skipped", txt))
        if not todo:
            return results
        # Sicherheitsnetz: aktuellen Zustand vor dem Zurückschreiben sichern
        safety = make_writer(safety_folder or os.path.dirname(zip_path),
                             f"Vor Wiederherstellung von {os.path.basename(zip_path)}", store)
        for e in todo:
            try:
                safety.add(e["path"])
            except OSError:
                pass
        safety.close()
        for n, e in enumerate(todo, 1):
            if cancel is not None and cancel.is_set():
                results.append((e["path"], "skipped", "abgebrochen"))
                continue
            if on_progress:
                on_progress(n, len(todo), e["path"])
            try:
                tag, v1 = _entry_bytes(zip_path, e, z, src_store)
                _write_tags(e["path"], tag, v1)
                results.append((e["path"], "restored", "wiederhergestellt"))
            except Exception as ex:  # noqa: BLE001
                results.append((e["path"], "error", str(ex)))
    return results


def _write_tags(path: str, tag: bytes, v1: bytes):
    """Ersetzt Tag-Bereich und ID3v1 einer Datei; Audio bleibt byte-identisch (über temporäre Datei)."""
    lay = read_layout(path)
    if len(tag) == lay["audio_start"] and bool(v1) == lay["has_v1"]:
        # gleiche Größe → direkt an Ort und Stelle (schnell, auch bei großen Dateien)
        with open(path, "r+b") as f:
            f.write(tag)
            if v1:
                f.seek(-128, os.SEEK_END)
                f.write(v1)
        return
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".mp3restore_", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "wb") as out, open(path, "rb") as src:
            out.write(tag)
            src.seek(lay["audio_start"])
            remaining = lay["audio_len"]
            while remaining > 0:
                chunk = src.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                out.write(chunk)
                remaining -= len(chunk)
            out.write(v1)
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


