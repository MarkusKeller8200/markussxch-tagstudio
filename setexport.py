"""DJ-Set exportieren (#4): M3U8, Rekordbox-XML und CSV – nur Standardbibliothek.

Eingabe ist eine Liste von Einträgen (dict) in Set-Reihenfolge:
    {"path", "artist", "title", "album", "genre", "key" (Camelot-Code), "bpm", "energy",
     "duration" (Sekunden), "to_next" (Übergang aus setplan.transition oder None)}
"""
from __future__ import annotations

import os
import re
import urllib.parse
import xml.etree.ElementTree as ET

import keys

FORMATS = {"m3u8": "M3U8-Playlist", "xml": "Rekordbox-XML", "csv": "CSV (Excel)"}


def _label(e) -> str:
    a, t = (e.get("artist") or "").strip(), (e.get("title") or "").strip()
    if a and t:
        return f"{a} - {t}"
    return t or a or os.path.splitext(os.path.basename(e["path"]))[0]


def _rel(path: str, base: str) -> str:
    """Relativer Pfad, wenn möglich (anderes Laufwerk → absolut)."""
    try:
        return os.path.relpath(path, base)
    except ValueError:
        return path


# ---------------------------------------------------------------- M3U8
def m3u8(entries, dest_dir: str = "", relative: bool = False, name: str = "") -> str:
    lines = ["#EXTM3U"]
    if name:
        lines.append(f"#PLAYLIST:{name}")
    for e in entries:
        dur = int(round(e.get("duration") or 0)) or -1
        lines.append(f"#EXTINF:{dur},{_label(e)}")
        lines.append(_rel(e["path"], dest_dir) if relative and dest_dir else e["path"])
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- Rekordbox
def location(path: str) -> str:
    """Pfad → Rekordbox-Location (file://localhost/…, URL-kodiert, Schrägstriche)."""
    p = os.path.abspath(path).replace("\\", "/")
    if not p.startswith("/"):
        p = "/" + p                                   # C:/… → /C:/…
    return "file://localhost" + urllib.parse.quote(p, safe="/:")


def path_from_location(loc: str) -> str:
    p = urllib.parse.unquote(re.sub(r"^file://localhost", "", loc))
    if re.match(r"^/[A-Za-z]:/", p):                  # Windows
        p = p[1:].replace("/", "\\")
    return p


def rekordbox_xml(entries, name: str = "TagStudio DJ-Set", version: str = "", notation: str = "musical") -> str:
    root = ET.Element("DJ_PLAYLISTS", Version="1.0.0")
    ET.SubElement(root, "PRODUCT", Name="MarKusSXCH TagStudio", Version=version or "", Company="")
    col = ET.SubElement(root, "COLLECTION", Entries=str(len(entries)))
    for n, e in enumerate(entries, 1):
        a = {"TrackID": str(n), "Name": e.get("title") or os.path.splitext(os.path.basename(e["path"]))[0],
             "Artist": e.get("artist") or "", "Album": e.get("album") or "", "Genre": e.get("genre") or "",
             "Kind": "MP3 File", "TotalTime": str(int(round(e.get("duration") or 0))),
             "Location": location(e["path"])}
        if e.get("bpm"):
            a["AverageBpm"] = f"{float(e['bpm']):.2f}"
        if e.get("key"):
            a["Tonality"] = keys.format_key(e["key"], notation)
        # kein „Comments“: beim Import in eine bestehende Sammlung könnte das eigene Kommentare überschreiben
        ET.SubElement(col, "TRACK", **a)
    pls = ET.SubElement(root, "PLAYLISTS")
    top = ET.SubElement(pls, "NODE", Type="0", Name="ROOT", Count="1")
    node = ET.SubElement(top, "NODE", Name=name, Type="1", KeyType="0", Entries=str(len(entries)))
    for n in range(1, len(entries) + 1):
        ET.SubElement(node, "TRACK", Key=str(n))
    ET.indent(root, "  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def read_rekordbox(text: str) -> dict:
    """Rekordbox-XML lesen → {"tracks": {id: {…, path}}, "playlists": {name: [Pfade]}} (für Tests/Import)."""
    root = ET.fromstring(text)
    tracks = {}
    for t in root.iter("TRACK"):
        if t.get("Location"):
            d = dict(t.attrib)
            d["path"] = path_from_location(d["Location"])
            tracks[d["TrackID"]] = d
    lists = {}
    for node in root.iter("NODE"):
        if node.get("Type") == "1":
            lists[node.get("Name")] = [tracks[t.get("Key")]["path"] for t in node.findall("TRACK") if t.get("Key") in tracks]
    return {"tracks": tracks, "playlists": lists}


# ---------------------------------------------------------------- CSV
CSV_HEAD = ["Nr", "Künstler", "Titel", "Tonart", "Camelot", "BPM", "Energie", "Dauer", "Übergang", "BPM-Unterschied %",
            "Note", "Pfad"]


def csv_rows(entries, kinds: dict | None = None) -> list[list]:
    rows = []
    for n, e in enumerate(entries, 1):
        tr = e.get("to_next") or {}
        dur = int(round(e.get("duration") or 0))
        rows.append([n, e.get("artist") or "", e.get("title") or "",
                     keys.format_key(e["key"], "musical") if e.get("key") else "",
                     keys.format_key(e["key"], "camelot") if e.get("key") else "",
                     ("%g" % round(float(e["bpm"]), 2)).replace(".", ",") if e.get("bpm") else "",
                     "" if e.get("energy") is None else e["energy"],
                     f"{dur // 60}:{dur % 60:02d}" if dur else "",
                     (kinds or {}).get(tr.get("key"), tr.get("key", "")) if tr else "",
                     "" if not tr or tr.get("bpm_pct") is None else str(tr["bpm_pct"]).replace(".", ","),
                     tr.get("score", "") if tr else "", e["path"]])
    return rows


def write(fmt: str, dest: str, entries, **kw) -> int:
    """Datei schreiben; liefert die Anzahl Titel."""
    if fmt == "m3u8":
        text = m3u8(entries, os.path.dirname(os.path.abspath(dest)), kw.get("relative", False), kw.get("name", ""))
        with open(dest, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    elif fmt == "xml":
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(rekordbox_xml(entries, kw.get("name") or "TagStudio DJ-Set", kw.get("version", ""),
                                   kw.get("notation", "musical")))
    elif fmt == "csv":
        import tagger
        tagger.write_csv(dest, CSV_HEAD, csv_rows(entries, kw.get("kinds")))
    else:
        raise ValueError(f"Unbekanntes Format: {fmt}")
    return len(entries)
