"""Playlists aus DJ-Programmen lesen (#278): Serato (Crates), Engine DJ (Datenbank), VirtualDJ (Ordner, Playlists).

Nur lesen – die Bibliotheken der Programme werden nie verändert. Die Engine-Datenbank wird vor dem Lesen in einen
Arbeitsordner kopiert (auch eine laufende Engine-Software stört so nicht). Nur Standardbibliothek.

Formate:
  Serato     _Serato_/Subcrates/<A%%B>.crate – Datensätze aus Kennung (4 Zeichen), Länge (uint32, big endian),
             Inhalt; „otrk“ enthält „ptrk“ (Pfad, UTF-16BE) relativ zum Laufwerk, auf dem _Serato_ liegt.
             „%%“ im Dateinamen trennt Unter-Crates.
  Engine DJ  Engine Library/Database2/m.db (Engine DJ 2.x–4.x, SQLite): Playlist (title, parentListId, nextListId),
             PlaylistEntity (listId, trackId, nextEntityId), Track (path relativ zum Ordner „Engine Library“).
  VirtualDJ  VirtualDJ/Folders/**/*.vdjfolder (XML mit <song path=…>; Filter-Ordner werden übersprungen) und
             VirtualDJ/Playlists/*.m3u (Zeilen #EXTVDJ:<artist>…</artist><title>…</title>…).
read_library(app, path) → [{"key", "folder", "name", "items": [{"path", "artist", "title", "dur"}]}]
"""
from __future__ import annotations

import glob
import html
import os
import re
import shutil
import sqlite3
import struct
import tempfile
import xml.etree.ElementTree as ET

APPS = {"serato": "Serato DJ", "engine": "Engine DJ", "vdj": "VirtualDJ"}


# --------------------------------------------------------------------------- Standardorte
def _volumes() -> list[str]:
    """Wurzeln externer Laufwerke (Mac: /Volumes/*, Windows: D:\\ … Z:\\)."""
    out = []
    if os.name == "nt":
        out += [f"{c}:\\" for c in "DEFGHIJKLMNOPQRSTUVWXYZ" if os.path.isdir(f"{c}:\\")]
    else:
        out += sorted(glob.glob("/Volumes/*")) + sorted(glob.glob("/media/*/*"))
    return out


def candidates(app: str, home: str | None = None, volumes: list[str] | None = None) -> list[str]:
    """Mögliche Bibliotheksorte (auch nicht vorhandene) – find_libraries() filtert die vorhandenen."""
    home = home or os.path.expanduser("~")
    vols = _volumes() if volumes is None else volumes
    if app == "serato":
        return [os.path.join(home, "Music", "_Serato_")] + [os.path.join(v, "_Serato_") for v in vols]
    if app == "engine":
        return [os.path.join(home, "Music", "Engine Library")] + [os.path.join(v, "Engine Library") for v in vols]
    if app == "vdj":
        loc = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
        return [os.path.join(home, "Documents", "VirtualDJ"), os.path.join(home, "Library", "Application Support", "VirtualDJ"),
                os.path.join(loc, "VirtualDJ")] + [os.path.join(v, "VirtualDJ") for v in vols]
    raise ValueError(f"Unbekanntes Programm: {app}")


def library_root(app: str, path: str) -> str:
    """Gewählten Ordner bzw. gewählte Datei auf den Bibliotheksordner zurückführen ('' = keine Bibliothek)."""
    p = os.path.normpath(str(path or ""))
    if app == "serato":
        for c in (p, os.path.join(p, "_Serato_"), os.path.dirname(p), os.path.dirname(os.path.dirname(p))):
            if os.path.isdir(os.path.join(c, "Subcrates")) and os.path.basename(c).lower().startswith("_serato_"):
                return c
        return ""
    if app == "engine":
        for c in (p, os.path.join(p, "Engine Library"), os.path.dirname(p), os.path.dirname(os.path.dirname(p))):
            if os.path.isfile(os.path.join(c, "Database2", "m.db")):
                return c
        return ""
    if app == "vdj":
        for c in (p, os.path.join(p, "VirtualDJ"), os.path.dirname(p), os.path.dirname(os.path.dirname(p))):
            if os.path.isdir(os.path.join(c, "Folders")) or os.path.isdir(os.path.join(c, "Playlists")):
                return c
        return ""
    raise ValueError(f"Unbekanntes Programm: {app}")


def find_libraries(app: str, home: str | None = None, volumes: list[str] | None = None) -> list[str]:
    out, seen = [], set()
    for c in candidates(app, home, volumes):
        r = library_root(app, c) if os.path.isdir(c) else ""
        if r and os.path.normcase(r) not in seen:
            seen.add(os.path.normcase(r))
            out.append(r)
    return out


# --------------------------------------------------------------------------- Serato
def _serato_records(data: bytes):
    i = 0
    while i + 8 <= len(data):
        tag = data[i:i + 4].decode("latin-1")
        (n,) = struct.unpack(">I", data[i + 4:i + 8])
        yield tag, data[i + 8:i + 8 + n]
        i += 8 + n


def serato_crate_paths(data: bytes) -> list[str]:
    out = []
    for tag, body in _serato_records(data):
        if tag == "otrk":
            for t2, b2 in _serato_records(body):
                if t2 == "ptrk":
                    out.append(b2.decode("utf-16-be", errors="replace"))
    return out


def serato_base(root: str) -> str:
    """Laufwerk, zu dem die Pfade in den Crates relativ sind (Ordner, in dem _Serato_ auf einem Laufwerk liegt)."""
    parent = os.path.dirname(os.path.normpath(root))
    drive, rest = os.path.splitdrive(parent)
    if drive and rest in ("", "\\", "/"):
        return drive + os.sep                                       # E:\_Serato_
    m = re.match(r"^(/Volumes/[^/]+|/media/[^/]+/[^/]+)$", parent.replace("\\", "/"))
    if m:
        return m.group(1)                                           # externes Laufwerk am Mac/Linux
    return (drive + os.sep) if drive else "/"


def _serato_path(rel: str, base: str) -> str:
    rel = rel.replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", rel):
        return os.path.normpath(rel)
    return os.path.normpath(os.path.join(base, rel.lstrip("/")))


def read_serato(root: str) -> list[dict]:
    base = serato_base(root)
    out = []
    crates = glob.glob(os.path.join(root, "Subcrates", "*.crate"))
    for f in sorted(crates, key=lambda x: [p.lower() for p in os.path.basename(x)[:-6].split("%%")]):
        parts = [p for p in os.path.basename(f)[:-6].split("%%") if p]
        if not parts:
            continue
        with open(f, "rb") as fh:
            paths = serato_crate_paths(fh.read())
        out.append({"key": "/".join(parts), "folder": "/".join(parts[:-1]), "name": parts[-1],
                    "items": [{"path": _serato_path(p, base)} for p in paths]})
    return out


# --------------------------------------------------------------------------- Engine DJ
def _chain(rows: dict, nxt: str) -> list:
    """Verkettete Liste (next = Nachfolger, 0 = Ende) in Reihenfolge bringen; Unverkettetes hinten anhängen."""
    pointed = {r[nxt] for r in rows.values() if r[nxt]}
    heads = [k for k in rows if k not in pointed]
    order, seen = [], set()
    for h in sorted(heads):
        k = h
        while k and k in rows and k not in seen:
            seen.add(k)
            order.append(k)
            k = rows[k][nxt]
    order += sorted(k for k in rows if k not in seen)
    return order


def read_engine(root: str, work_dir: str | None = None) -> list[dict]:
    db = os.path.join(root, "Database2", "m.db")
    if not os.path.isfile(db):
        raise ValueError("Keine Engine-DJ-Datenbank (Engine Library/Database2/m.db) gefunden.")
    tmp = tempfile.mkdtemp(prefix="ts_engine_", dir=work_dir)
    try:
        copy = os.path.join(tmp, "m.db")
        shutil.copy2(db, copy)
        for ext in ("-wal", "-shm"):
            if os.path.isfile(db + ext):
                shutil.copy2(db + ext, copy + ext)
        con = sqlite3.connect(copy)
        try:
            con.row_factory = sqlite3.Row
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"Playlist", "PlaylistEntity", "Track"} <= tables:
                raise ValueError("Diese Engine-Datenbank ist zu alt (nur Engine DJ 2 und neuer).")
            lists = {r["id"]: {"title": r["title"] or "", "parent": r["parentListId"] or 0, "next": r["nextListId"] or 0}
                     for r in con.execute("SELECT id, title, parentListId, nextListId FROM Playlist")}
            tracks = {r["id"]: r for r in con.execute("SELECT * FROM Track")}
            ents: dict = {}
            for r in con.execute("SELECT id, listId, trackId, nextEntityId FROM PlaylistEntity"):
                ents.setdefault(r["listId"], {})[r["id"]] = {"track": r["trackId"], "next": r["nextEntityId"] or 0}
        finally:
            con.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    def path_of(lid):
        names, k, seen = [], lid, set()
        while k and k in lists and k not in seen:
            seen.add(k)
            names.append(lists[k]["title"])
            k = lists[k]["parent"]
        return list(reversed(names))

    children: dict = {}
    for k, v in lists.items():
        children.setdefault(v["parent"] if v["parent"] in lists else 0, {})[k] = v
    out = []

    def walk(parent):
        sub = children.get(parent, {})
        for k in _chain(sub, "next"):
            names = path_of(k)
            e = ents.get(k, {})
            items = []
            for eid in _chain(e, "next"):
                t = tracks.get(e[eid]["track"])
                if t is None:
                    continue
                rel = str(t["path"] or "")
                p = rel if re.match(r"^([A-Za-z]:[\\/]|/)", rel) else os.path.normpath(os.path.join(root, rel))
                keys = t.keys()
                items.append({"path": p, "artist": (t["artist"] if "artist" in keys else "") or "",
                              "title": (t["title"] if "title" in keys else "") or "",
                              "dur": int(t["length"] or 0) if "length" in keys and t["length"] else 0})
            if e or k not in children:
                out.append({"key": "/".join(names), "folder": "/".join(names[:-1]), "name": names[-1], "items": items})
            walk(k)
    walk(0)
    return out


# --------------------------------------------------------------------------- VirtualDJ
def read_vdjfolder(text: str) -> list[dict] | None:
    """Inhalt einer .vdjfolder-Datei → Einträge; None für Filter-Ordner (keine feste Liste)."""
    root = ET.fromstring(text)
    if root.tag.lower() == "filterfolder" or root.find("filter") is not None:
        return None
    out = []
    for s in root.iter("song"):
        p = s.get("path") or ""
        if p:
            try:
                dur = int(float(s.get("songlength") or 0))
            except ValueError:
                dur = 0
            out.append({"path": p, "artist": s.get("artist") or "", "title": s.get("title") or "", "dur": dur})
    return out


_VDJ_TAG = re.compile(r"<(artist|title|songlength)>(.*?)</\1>", re.S | re.I)


def read_vdj_m3u(text: str, base: str) -> list[dict]:
    out, meta = [], {}
    for line in str(text or "").lstrip("\ufeff").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTVDJ:"):
            meta = {m.group(1).lower(): html.unescape(m.group(2)).strip() for m in _VDJ_TAG.finditer(line)}
            continue
        if line.startswith("#"):
            continue
        p = line
        if not re.match(r"^([A-Za-z]:[\\/]|/|\\\\)", p):
            p = os.path.normpath(os.path.join(base, p))
        try:
            dur = int(float(meta.get("songlength") or 0))
        except ValueError:
            dur = 0
        out.append({"path": p, "artist": meta.get("artist", ""), "title": meta.get("title", ""), "dur": dur})
        meta = {}
    return out


def read_vdj(root: str) -> list[dict]:
    out = []
    fdir = os.path.join(root, "Folders")
    for f in sorted(glob.glob(os.path.join(fdir, "**", "*.vdjfolder"), recursive=True), key=str.lower):
        rel = os.path.relpath(f, fdir).replace("\\", "/")[:-len(".vdjfolder")]
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                items = read_vdjfolder(fh.read())
        except ET.ParseError:
            continue
        if items is None:
            continue
        parts = rel.split("/")
        out.append({"key": "Folders/" + rel, "folder": "/".join(parts[:-1]), "name": parts[-1], "items": items})
    pdir = os.path.join(root, "Playlists")
    for f in sorted(glob.glob(os.path.join(pdir, "**", "*.m3u*"), recursive=True), key=str.lower):
        rel = os.path.relpath(f, pdir).replace("\\", "/")
        rel = rel[:rel.rfind(".")]
        with open(f, encoding="utf-8-sig", errors="replace") as fh:
            items = read_vdj_m3u(fh.read(), os.path.dirname(f))
        parts = ["Playlists"] + rel.split("/")
        out.append({"key": "Playlists/" + rel, "folder": "/".join(parts[:-1]), "name": parts[-1], "items": items})
    return out


# --------------------------------------------------------------------------- gemeinsam
def read_library(app: str, path: str, work_dir: str | None = None) -> list[dict]:
    root = library_root(app, path)
    if not root:
        raise ValueError(f"Hier liegt keine {APPS.get(app, app)}-Bibliothek: {path}")
    if app == "serato":
        return read_serato(root)
    if app == "engine":
        return read_engine(root, work_dir)
    return read_vdj(root)
