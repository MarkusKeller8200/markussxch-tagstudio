"""MarKusSXCH TagStudio – Spiegel der Musikbibliothek in einen Cloud-Ordner (#403, docs/KONZEPT-CLOUD.md §4c).

Einweg-Kopie Bibliothek → Spiegel, z. B. in den OneDrive-Ordner des Desktop-Clients (Kontoart „Privat“, #405). Im
Spiegel wird nie bearbeitet; TagStudio arbeitet weiter nur mit der lokalen Bibliothek.

- Je Bibliothek ein Unterordner ``<Ziel>/<Name der Bibliothek>/…`` mit denselben Unterordnern.
- Kopiert wird, was fehlt oder sich geändert hat (Grösse oder Änderungszeit); geschrieben wird als ``.part`` und erst
  dann umbenannt – der Client lädt nie eine halbe Datei hoch. Die Änderungszeit wird übernommen.
- Dateien im Spiegel ohne Gegenstück in der Bibliothek („überzählig“) werden nur gemeldet und erst nach Rückfrage
  gelöscht.
- ``index.json`` (Titel, Künstler, BPM, Tonart, Dauer, relativer Pfad) und Playlists als M3U8 mit relativen Pfaden
  für einen späteren Web-Player (#404) bzw. die OneDrive-App.
- Platzschätzung vor dem Lauf; Abo und Speichergrösse entscheidet der Benutzer.

Nur Standardbibliothek.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time

AUDIO_EXTS = (".mp3", ".wav", ".aif", ".aiff", ".flac", ".m4a", ".ogg", ".opus")
INDEX = "index.json"
PLAYLIST_DIR = "Playlists"
TOLERANCE = 2.0                     # Sekunden (FAT/exFAT und Cloud-Clients runden Änderungszeiten)
DEFAULT_SUB = "TagStudio-Spiegel"


def clean_cfg(c) -> dict:
    """Einstellung des Spiegels: {"folder", "libraries": [ids] | [] = alle aktiven, "online_only", "auto", "playlists"}."""
    c = c if isinstance(c, dict) else {}
    libs = c.get("libraries")
    return {"folder": str(c.get("folder") or "").strip(),
            "libraries": [str(x) for x in libs if str(x)] if isinstance(libs, list) else [],
            "online_only": bool(c.get("online_only", False)),
            "auto": bool(c.get("auto", False)),
            "playlists": c.get("playlists", True) is not False}


def safe_name(name: str) -> str:
    """Ordnername einer Bibliothek im Spiegel (ohne Zeichen, die Windows/macOS/OneDrive ablehnen)."""
    n = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(name or "").strip()).strip(" .")
    return n[:80] or "Bibliothek"


def _skip(name: str) -> bool:
    low = name.lower()
    return name.startswith(".") or low.endswith((".part", ".tmp")) or low in ("desktop.ini", "thumbs.db")


def _walk(root: str):
    """(rel, size, mtime) aller Audiodateien unter root (rel mit „/“)."""
    root = os.path.abspath(root)
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                entries = list(it)
        except OSError:
            continue
        for e in entries:
            if _skip(e.name):
                continue
            try:
                if e.is_dir(follow_symlinks=False):
                    stack.append(e.path)
                elif e.is_file(follow_symlinks=False) and e.name.lower().endswith(AUDIO_EXTS):
                    st = e.stat()
                    yield os.path.relpath(e.path, root).replace(os.sep, "/"), st.st_size, st.st_mtime
            except OSError:
                continue


def _inside(child: str, root: str) -> bool:
    c, r = os.path.normcase(os.path.abspath(child)), os.path.normcase(os.path.abspath(root))
    return c == r or c.startswith(r.rstrip(os.sep) + os.sep)


def plan(libs: list[dict], target: str) -> dict:
    """libs: [{"id", "name", "path"}] → was zu tun ist (ohne etwas zu ändern).

    → {"libs": [{id, name, dest, files, bytes, copy, copy_bytes, same, extra}], "copy": [(src, dst, size, mtime)],
       "extra": [dst …], "files", "bytes", "copy_bytes", "present_bytes", "extra_bytes", "error"}"""
    out = {"libs": [], "copy": [], "extra": [], "files": 0, "bytes": 0, "copy_bytes": 0, "present_bytes": 0,
           "extra_bytes": 0, "error": ""}
    if not target:
        out["error"] = "Kein Ziel-Ordner für den Spiegel angegeben."
        return out
    target = os.path.abspath(target)
    used = set()
    for lib in libs:
        src = os.path.abspath(lib["path"])
        if _inside(target, src) or _inside(src, target):
            out["error"] = f"Spiegel und Bibliothek dürfen nicht ineinander liegen ({lib['name']})."
            return out
        name = safe_name(lib.get("name") or lib.get("id"))
        while name.lower() in used:
            name += "_"
        used.add(name.lower())
        dest = os.path.join(target, name)
        have = {r: (s, m) for r, s, m in _walk(dest)} if os.path.isdir(dest) else {}
        row = {"id": lib.get("id", ""), "name": name, "src": src, "dest": dest, "files": 0, "bytes": 0, "copy": 0,
               "copy_bytes": 0, "same": 0, "extra": 0}
        seen = set()
        for rel, size, mt in _walk(src):
            seen.add(rel.lower())
            row["files"] += 1
            row["bytes"] += size
            old = have.get(rel)
            if old is None:
                # Gross-/Kleinschreibung: auf Windows/macOS dieselbe Datei
                old = next((v for k, v in have.items() if k.lower() == rel.lower()), None)
            if old and old[0] == size and abs(old[1] - mt) <= TOLERANCE:
                row["same"] += 1
                out["present_bytes"] += size
                continue
            if old:
                out["present_bytes"] += old[0]
            row["copy"] += 1
            row["copy_bytes"] += size
            out["copy"].append((os.path.join(src, *rel.split("/")), os.path.join(dest, *rel.split("/")), size, mt))
        for rel, (size, _m) in have.items():
            if rel.lower() not in seen:
                row["extra"] += 1
                out["extra"].append(os.path.join(dest, *rel.split("/")))
                out["extra_bytes"] += size
        out["files"] += row["files"]
        out["bytes"] += row["bytes"]
        out["copy_bytes"] += row["copy_bytes"]
        out["libs"].append(row)
    return out


def free_space(path: str) -> int | None:
    """Freier Platz auf dem Laufwerk des (nächsten vorhandenen) Ordners – den freien Platz in der Cloud kennt
    TagStudio ohne Anmeldung nicht."""
    p = os.path.abspath(path or ".")
    while p and not os.path.isdir(p):
        parent = os.path.dirname(p)
        if parent == p:
            return None
        p = parent
    try:
        return shutil.disk_usage(p).free
    except OSError:
        return None


def estimate(pl: dict, extra_bytes: int = 0) -> dict:
    """Platzschätzung aus plan(): Musik gesamt, schon im Spiegel, noch zu kopieren; extra_bytes = z. B. Sicherungen
    der Programmdaten (#402)."""
    need = pl["bytes"] + extra_bytes
    return {"music": pl["bytes"], "present": pl["present_bytes"], "to_copy": pl["copy_bytes"], "other": extra_bytes,
            "total": need, "files": pl["files"]}


def copy_file(src: str, dst: str, mtime: float | None = None):
    """Atomar kopieren: ``dst.part`` schreiben, Änderungszeit übernehmen, dann umbenennen."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".part"
    try:
        shutil.copyfile(src, tmp)
        st = os.stat(src)
        os.utime(tmp, (st.st_atime, mtime if mtime is not None else st.st_mtime))
        os.replace(tmp, dst)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def run(pl: dict, cancel=None, progress=None, log=None) -> dict:
    """Kopien aus plan() ausführen. → {"copied", "bytes", "errors": [..], "paths": [dst]}"""
    res = {"copied": 0, "bytes": 0, "errors": [], "paths": []}
    n = len(pl["copy"])
    for i, (src, dst, size, mt) in enumerate(pl["copy"]):
        if cancel is not None and cancel():
            break
        if progress:
            progress(i, n, src)
        try:
            copy_file(src, dst, mt)
            res["copied"] += 1
            res["bytes"] += size
            res["paths"].append(dst)
        except OSError as ex:
            res["errors"].append(f"{os.path.basename(src)}: {ex}")
            if log:
                log(f"Fehler beim Kopieren {src}: {ex}")
    return res


def delete_extra(paths: list[str], target: str) -> dict:
    """Überzählige Dateien im Spiegel löschen – nur nach Rückfrage in der Oberfläche und nur unterhalb des Ziels."""
    done, errors = 0, []
    for p in paths:
        if not _inside(p, target) or os.path.normcase(os.path.abspath(p)) == os.path.normcase(os.path.abspath(target)):
            errors.append(f"{p}: liegt nicht im Spiegel")
            continue
        if not os.path.basename(p).lower().endswith(AUDIO_EXTS):
            errors.append(f"{p}: keine Audiodatei")
            continue
        try:
            os.remove(p)
            done += 1
        except FileNotFoundError:
            done += 1
        except OSError as ex:
            errors.append(f"{p}: {ex}")
    return {"deleted": done, "errors": errors}


def set_online_only(paths: list[str]) -> str:
    """Nach dem Hochladen „nur online“ (Platz freigeben). Windows: ``attrib +u`` (OneDrive „Dateien bei Bedarf“);
    macOS: nicht per Befehl möglich, solange OneDrive läuft → Hinweis. → Meldung (leer = nichts zu sagen)."""
    if not paths:
        return ""
    if not sys.platform.startswith("win"):
        return ("macOS: Platz im Finder freigeben (Rechtsklick auf den Spiegel-Ordner › „Speicherplatz freigeben“) – "
                "TagStudio kann das nicht selbst.")
    bad = 0
    for p in paths:
        try:
            subprocess.run(["attrib", "+u", "-p", p], check=False, capture_output=True, timeout=20,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.SubprocessError):
            bad += 1
    return f"„Nur online“ für {len(paths) - bad} Datei(en) gesetzt – OneDrive gibt den Platz nach dem Hochladen frei." \
        if len(paths) > bad else "„Nur online“ liess sich nicht setzen (OneDrive „Dateien bei Bedarf“ aus?)."


# =========================================================================== index.json und Playlists
def read_meta(path: str) -> dict:
    """Wenige Tag-Felder für index.json (Fehler → leere Felder)."""
    try:
        import id3tags
        f = id3tags.MP3File(path)
        g = f.text
        return {"title": g("TIT2"), "artist": g("TPE1"), "album": g("TALB"), "genre": g("TCON"), "bpm": g("TBPM"),
                "key": g("TKEY"), "duration": round(float(getattr(f, "duration", 0) or 0), 1)}
    except Exception:  # noqa: BLE001 – Index ist nur eine Beigabe
        return {}


def write_index(target: str, pl: dict, previous: dict | None = None) -> int:
    """``index.json`` im Spiegel neu schreiben (Einträge mit gleicher Grösse/Zeit aus dem vorigen Index übernehmen).
    → Anzahl Einträge"""
    prev = {}
    for e in (previous or {}).get("tracks") or []:
        if isinstance(e, dict) and e.get("path"):
            prev[e["path"]] = e
    tracks = []
    for lib in pl["libs"]:
        for rel, size, mt in _walk(lib["dest"]):
            path = f"{lib['name']}/{rel}"
            old = prev.get(path)
            if old and old.get("size") == size and abs(float(old.get("mtime") or 0) - mt) <= TOLERANCE:
                tracks.append(old)
                continue
            e = {"path": path, "size": size, "mtime": round(mt, 1)}
            if rel.lower().endswith(".mp3"):
                e.update(read_meta(os.path.join(lib["dest"], *rel.split("/"))))
            tracks.append(e)
    data = {"format": 1, "app": "MarKusSXCH TagStudio", "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "libraries": [x["name"] for x in pl["libs"]], "tracks": tracks}
    _write_json(os.path.join(target, INDEX), data)
    return len(tracks)


def load_index(target: str) -> dict:
    try:
        with open(os.path.join(target, INDEX), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def map_path(path: str, pl: dict) -> str:
    """Pfad in der Bibliothek → Pfad im Spiegel (leer, wenn die Datei in keiner gespiegelten Bibliothek liegt)."""
    for lib in pl["libs"]:
        if _inside(path, lib["src"]):
            return os.path.join(lib["dest"], os.path.relpath(os.path.abspath(path), lib["src"]))
    return ""


def write_playlists(target: str, playlists: list[dict], pl: dict) -> int:
    """Playlists als M3U8 mit relativen Pfaden in ``<Ziel>/Playlists`` (nur Titel, die im Spiegel liegen)."""
    import setexport
    pdir = os.path.join(target, PLAYLIST_DIR)
    n = 0
    for p in playlists:
        entries = []
        for it in p.get("items") or []:
            m = map_path(it.get("path") or "", pl) if it.get("path") else ""
            if m:
                entries.append({"path": m, "artist": it.get("artist", ""), "title": it.get("title", ""),
                                "duration": it.get("dur") or 0})
        if not entries:
            continue
        folder = [safe_name(x) for x in str(p.get("folder") or "").split("/") if x.strip()]
        dest_dir = os.path.join(pdir, *folder)
        os.makedirs(dest_dir, exist_ok=True)
        text = setexport.m3u8(entries, dest_dir, True, p.get("name", ""))
        # Schrägstriche statt „\\“: dieselbe Liste gilt auf Windows, macOS, im Web und in der OneDrive-App
        text = "\n".join(ln if ln.startswith("#") else ln.replace("\\", "/") for ln in text.split("\n"))
        _write_text(os.path.join(dest_dir, safe_name(p.get("name")) + ".m3u8"), text)
        n += 1
    return n


def _write_json(path: str, data):
    _write_text(path, json.dumps(data, ensure_ascii=False, indent=1))


def _write_text(path: str, text: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)
