"""
backup.py – automatische Sicherung der Tags vor dem Speichern und Wiederherstellung.

Pro Speichervorgang entsteht ein ZIP-Archiv im Sicherungsordner (Standard: ~/TagStudio/Sicherungen).
Es enthält für jede Datei die exakten Tag-Bytes (ID3v2-Bereich inkl. Padding, ggf. ID3v1) und ein Manifest
mit Pfad, Größe, Zeitstempel und einem Fingerabdruck der Audiodaten. Audio wird NICHT gesichert – deshalb
sind Sicherungen klein, und beim Wiederherstellen wird geprüft, ob die Audiodaten noch dieselben sind.

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


# --------------------------------------------------------------------------- Auflisten
def list_backups(folder: str | None = None) -> list[dict]:
    folder = folder or default_dir()
    out = []
    if not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder), reverse=True):
        if not name.endswith(".zip"):
            continue
        p = os.path.join(folder, name)
        try:
            with zipfile.ZipFile(p) as z:
                man = json.loads(z.read(MANIFEST))
            out.append({"path": p, "name": name, "created": man.get("created", os.path.getmtime(p)),
                        "label": man.get("label", ""), "count": len(man.get("files", [])),
                        "bytes": os.path.getsize(p), "files": man.get("files", [])})
        except (OSError, KeyError, ValueError, zipfile.BadZipFile):
            out.append({"path": p, "name": name, "created": os.path.getmtime(p), "label": "(beschädigt)",
                        "count": 0, "bytes": os.path.getsize(p), "files": [], "broken": True})
    return out


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
    with zipfile.ZipFile(zip_path) as z:
        tag = z.read(f"{entry['id']:05d}.tag")
        names = set(z.namelist())
        v1 = z.read(f"{entry['id']:05d}.v1") if f"{entry['id']:05d}.v1" in names else b""
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
            force_audio: bool = False, on_progress=None, cancel=None) -> list[tuple[str, str, str]]:
    """Schreibt die gesicherten Tags zurück. Vorher wird der aktuelle Zustand selbst gesichert.
    Liefert [(pfad, status, text)]; status: 'restored'|'skipped'|'error'."""
    with zipfile.ZipFile(zip_path) as z:
        man = json.loads(z.read(MANIFEST))
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
        safety = BackupWriter(safety_folder or os.path.dirname(zip_path),
                              label=f"Vor Wiederherstellung von {os.path.basename(zip_path)}")
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
                tag = z.read(f"{e['id']:05d}.tag")
                v1 = z.read(f"{e['id']:05d}.v1") if e["has_v1"] else b""
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


def folder_size(folder: str | None = None) -> int:
    folder = folder or default_dir()
    if not os.path.isdir(folder):
        return 0
    return sum(os.path.getsize(os.path.join(folder, n)) for n in os.listdir(folder) if n.endswith(".zip"))
