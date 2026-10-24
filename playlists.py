"""MarKusSXCH TagStudio – Playlists (#267): Speicher, Ordner, Archiv und Playlist-Ordner (M3U8).

Massgebend ist der Speicher im Datenordner des Profils (``~/TagStudio/Playlists``):

    index.json          Ordner, zuletzt benutzt, geschriebene M3U8 (Pfad + SHA-256), ignorierte fremde Dateien
    pl_<id>.json        eine Datei je Playlist (atomar geschrieben)

Zusätzlich liegt jede aktive Playlist als M3U8 im **Playlist-Ordner** (Standard ``<Basisordner>/03_Playlists``),
Unterordner = Ordner im Baum, Pfade relativ zur M3U8. TagStudio schreibt dort nur eigene Dateien und überschreibt
nie eine Datei, die ein anderes Programm geändert hat (→ ``external_changes``).

Archivieren statt Löschen (wie bei den Titeln, #173): die Playlist bekommt ``archived``, ihre M3U8 wandert nach
``<Archiv>/_Playlists/…`` mit Vermerk in ``_aussortiert.csv`` (Bereich „Playlists“). Endgültig gelöscht wird nur
eine archivierte Playlist. Nur Standardbibliothek.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
import re
import secrets
import shutil
import time
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET

import archive
import setexport

FORMAT = 1
KINDS = ("manual", "djset", "smart", "import", "queue")
ITEM_KEYS = ("path", "size", "akey", "added", "lock", "note", "artist", "title", "dur", "ref")
MIRROR_EXT = ".m3u8"
ARCHIVE_SUB = "_Playlists"          # im Archiv-Ordner
MIRROR_ARCHIVE = "_Archiv"          # im Playlist-Ordner, wenn kein Archiv-Ordner festgelegt ist
AREA = "Playlists"
UNDO_MAX = 50
RECENT_MAX = 8
_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


# =========================================================================== kleine Hilfen
def nk(p: str) -> str:
    """Vergleichsschlüssel eines Pfads (Gross-/Kleinschreibung unter Windows egal)."""
    return os.path.normcase(os.path.abspath(p))


def clean_name(name) -> str:
    n = " ".join(str(name or "").split())[:120]
    if not n:
        raise ValueError("Bitte einen Namen eingeben.")
    return n


def clean_folder(folder) -> str:
    """„Sets / 2026“ bzw. „Sets\\2026“ → „Sets/2026“ (ohne leere Teile, „.“ und „..“)."""
    parts = re.split(r"[/\\]+", str(folder or ""))
    out = [" ".join(p.split())[:80] for p in parts]
    return "/".join(p for p in out if p and p not in (".", ".."))


def safe_part(part: str) -> str:
    """Teil eines Dateinamens: verbotene Zeichen → _, keine reservierten Namen unter Windows."""
    s = _BAD.sub("_", part).strip(" .") or "_"
    return s + "_" if s.split(".")[0].upper() in _RESERVED else s


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _write_text(path: str, text: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def _unique(path: str) -> str:
    stem, ext = os.path.splitext(path)
    k, cand = 1, path
    while os.path.exists(cand):
        k += 1
        cand = f"{stem} ({k}){ext}"
    return cand


def clean_item(x) -> dict | None:
    """Eintrag bereinigen. Ein Eintrag braucht einen Pfad oder eine Angabe „ref“ ohne Datei (#271:
    {"artist", "title", "mix", "isrc", "dur", "source", "url"} – z. B. aus einer CSV oder einer fremden Trackliste)."""
    if isinstance(x, str):
        x = {"path": x}
    if not isinstance(x, dict):
        return None
    out = {k: x[k] for k in ITEM_KEYS if k in x and x[k] not in (None, "")}
    if not isinstance(out.get("path", ""), str) or not (out.get("path") or isinstance(out.get("ref"), dict)):
        return None
    if isinstance(out.get("ref"), dict):
        r = {k: str(out["ref"][k]).strip()[:300] for k in ("artist", "title", "mix", "isrc", "source")
             if str(out["ref"].get(k) or "").strip()}
        u = str(out["ref"].get("url") or "").strip()
        if u.startswith("https://") and len(u) < 400:                 # #280: Link zur Quelle (Spotify, SoundCloud …)
            r["url"] = u
        if out["ref"].get("dur"):
            try:
                r["dur"] = int(float(out["ref"]["dur"]))
            except (TypeError, ValueError):
                pass
        if r.get("artist") or r.get("title") or r.get("isrc"):
            out["ref"] = r
        else:
            del out["ref"]
            if not out.get("path"):
                return None
    elif "ref" in out:
        del out["ref"]
    if "lock" in out:
        out["lock"] = bool(out["lock"])
        if not out["lock"]:
            del out["lock"]
    return out


# =========================================================================== M3U / M3U8
def parse_m3u(text: str, base_dir: str) -> list[dict]:
    """M3U/M3U8 lesen → [{"path", "label", "dur"}]. Relative Pfade gelten ab base_dir; file://-Adressen und
    Windows-Pfade mit „\\“ (auch auf macOS geschrieben) werden verstanden."""
    out, label, dur = [], "", None
    for line in str(text or "").splitlines():
        s = line.strip().lstrip("﻿")
        if not s:
            continue
        if s.upper().startswith("#EXTINF:"):
            head, _, lab = s[8:].partition(",")
            try:
                dur = int(float(head.split()[0])) if head.split() else None
            except ValueError:
                dur = None
            label = lab.strip()
            continue
        if s.startswith("#"):
            continue
        p = s
        if p.lower().startswith("file://"):
            p = setexport.path_from_location(p) if p.lower().startswith("file://localhost") \
                else urllib.parse.unquote(re.sub(r"^file://", "", p, flags=re.I))
            if re.match(r"^/[A-Za-z]:/", p):
                p = p[1:]
        win_abs = bool(re.match(r"^[A-Za-z]:[\\/]", p)) or p.startswith("\\\\")
        if os.sep == "/" and not win_abs:
            p = p.replace("\\", "/")
        rooted = p.startswith(("/", "\\"))                      # unter Windows ab Python 3.13 nicht „isabs“
        if not win_abs and not rooted and not os.path.isabs(p):
            p = os.path.normpath(os.path.join(base_dir, p))
        out.append({"path": p, "label": label, "dur": dur if dur and dur > 0 else None})
        label, dur = "", None
    return out


def m3u_text(pl: dict, dest_dir: str) -> str:
    entries = [{"path": it["path"], "artist": it.get("artist", ""), "title": it.get("title", ""),
                "duration": it.get("dur") or 0} for it in pl.get("items") or [] if it.get("path")]
    return setexport.m3u8(entries, dest_dir, True, pl.get("name", ""))


# =========================================================================== Abgleich mit der Bibliothek (#271, #281)
_MIXWORDS = r"mix|edit|remix|version|dub|rework|bootleg|vip|instrumental|acapella|a cappella|extended|original|radio|club|remaster(?:ed)?|live"
_MIX_RE = re.compile(r"\s*[\(\[]([^\)\]]*\b(?:" + _MIXWORDS + r")\b[^\)\]]*)[\)\]]\s*$", re.I)
_DASH_MIX_RE = re.compile(r"^(.*?\S)\s+[-–—]\s+([^-–—]*\b(?:" + _MIXWORDS + r")\b[^-–—]*)$", re.I)   # „Song - Extended Mix“
_FEAT_RE = re.compile(r"\s*[\(\[]?\b(?:feat|ft|featuring)\b\.?\s+[^\)\]]*[\)\]]?", re.I)
_ART_SPLIT = re.compile(r"\s*(?:,|&|;|/|\bx\b|\bvs\.?|\band\b|\bund\b|\bfeat\.?|\bft\.?|\bfeaturing\b)\s*", re.I)
_MIX_TAIL = ("mix", "version", "edit")
SIMILAR = 0.88                       # Titel ähnlich genug für „unklar“ mit Vorschlag (#281)
MIX_RANK = ("extended", "", "club", "original", "dub", "instrumental")   # Vorzug bei „Anderer Mix gilt als gefunden“


def norm(s) -> str:
    """Vergleichsform: ohne Akzente und Satzzeichen, klein, einfache Leerzeichen."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", s).split())


def mix_key(mix) -> str:
    """Mix für den Vergleich: „Extended Mix“ = „Extended“ = „Extended Version“; „Original Mix“ und „Remastered 2011“
    gelten wie keine Angabe; Remixe behalten den Namen („X Remix“)."""
    m = norm(mix)
    if not m or m in ("original", "original mix", "original version", "album version") or m.startswith("remaster") \
            or re.fullmatch(r"(\d{4} )?remaster(ed)?( \d{4})?( version)?", m):
        return ""
    w = m.split()
    if len(w) > 1 and w[-1] in _MIX_TAIL:
        w = w[:-1]
    return " ".join(w)


def split_title(title, mix="") -> tuple[str, str]:
    """„Song (Extended Mix)“ bzw. „Song - Extended Mix“ → ("song", "extended"); „Original Mix“ = keine Angabe."""
    t = _FEAT_RE.sub(" ", str(title or "")).strip()
    found = ""
    m = _MIX_RE.search(t)
    if m:
        found, t = m.group(1), t[:m.start()]
    else:
        m = _DASH_MIX_RE.match(t)
        if m:
            t, found = m.group(1), m.group(2)
    return norm(t), mix_key(mix or found)


def artist_keys(artist) -> set:
    return {norm(a) for a in _ART_SPLIT.split(str(artist or "")) if norm(a)}


def lib_entry(path, artist, title, isrc="", dur=0, subtitle="") -> dict:
    """Eintrag des Bibliotheks-Index. subtitle (TIT3): Mix, wenn er nicht im Titel steht."""
    base, mix = split_title(title)
    if not mix and subtitle and re.search(r"\b(?:" + _MIXWORDS + r")\b", subtitle, re.I):
        mix = mix_key(subtitle)
    return {"path": path, "artist": artist, "title": title, "isrc": norm(isrc).replace(" ", ""), "dur": dur or 0,
            "akeys": artist_keys(artist), "base": base, "mix": mix}


class LibIndex:
    """Bibliothek für den Abgleich, mit Nachschlagen über ISRC, Titel und Künstler (schnell auch bei grossen
    Sammlungen)."""

    def __init__(self, entries):
        self.entries = list(entries)
        self.isrc, self.base, self.artist = {}, {}, {}
        for e in self.entries:
            if e["isrc"]:
                self.isrc.setdefault(e["isrc"], []).append(e)
            self.base.setdefault(e["base"], []).append(e)
            for a in e["akeys"]:
                self.artist.setdefault(a, []).append(e)

    def __len__(self):
        return len(self.entries)


def _ratio(a, b) -> float:
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio()


def _mix_rank(e) -> int:
    return MIX_RANK.index(e["mix"]) if e["mix"] in MIX_RANK else len(MIX_RANK)


def match_ref(ref: dict, index, any_mix: bool = False) -> dict:
    """Eintrag ohne Datei mit der Bibliothek abgleichen → {"status": sure|unclear|missing, "path" (Vorschlag),
    "candidates", "reason"}. Gleiche ISRC oder gleicher Künstler + Titel + Mix = sicher; anderer Mix (Radio Edit ≠
    Extended Mix) = unklar, mit any_mix sicher (Extended Mix bevorzugt); nur ähnlicher Titel = unklar mit Vorschlag."""
    ix = index if isinstance(index, LibIndex) else LibIndex(index)
    isrc = norm(ref.get("isrc")).replace(" ", "")
    if isrc:
        hits = ix.isrc.get(isrc) or []
        if len(hits) == 1:
            return {"status": "sure", "path": hits[0]["path"], "candidates": [hits[0]["path"]], "reason": "gleiche ISRC"}
    base, mix = split_title(ref.get("title"), ref.get("mix", ""))
    ak = artist_keys(ref.get("artist"))
    if not base:
        return {"status": "missing", "path": "", "candidates": [], "reason": "ohne Titel"}
    dur = int(ref.get("dur") or 0)
    dur_ok = lambda e: not dur or not e["dur"] or abs(e["dur"] - dur) <= 20       # noqa: E731
    cand = [e for e in ix.base.get(base) or [] if not ak or not e["akeys"] or ak & e["akeys"]]
    exact = [e for e in cand if e["mix"] == mix]
    if exact:
        fit = [e for e in exact if dur_ok(e)]
        if len(fit) == 1:
            return {"status": "sure", "path": fit[0]["path"], "candidates": [e["path"] for e in exact[:12]],
                    "reason": "Titel, Künstler und Mix"}
        pool = fit or exact
        return {"status": "unclear", "path": pool[0]["path"], "candidates": [e["path"] for e in pool[:12]],
                "reason": "mehrere Treffer" if len(fit) > 1 else "Länge weicht ab"}
    if cand:
        cand.sort(key=_mix_rank)
        best = cand[0]
        why = f"anderer Mix: {best['mix'] or 'ohne Angabe'}"
        if any_mix and (len(cand) == 1 or _mix_rank(cand[0]) < _mix_rank(cand[1])):
            return {"status": "sure", "path": best["path"], "candidates": [e["path"] for e in cand[:12]], "reason": why}
        return {"status": "unclear", "path": best["path"], "candidates": [e["path"] for e in cand[:12]], "reason": why}
    # Rückfall: ähnlicher Titel bei passendem Künstler (Tippfehler, „&“/„and“, Zusätze)
    pool = {id(e): e for a in ak for e in ix.artist.get(a, [])}.values() if ak else []
    sims = sorted(((_ratio(base, e["base"]), e) for e in pool), key=lambda x: (-x[0], _mix_rank(x[1])))
    sims = [(r, e) for r, e in sims if r >= SIMILAR]
    if sims:
        r, e = sims[0]
        return {"status": "unclear", "path": e["path"], "candidates": [x["path"] for _r, x in sims[:12]],
                "reason": f"Titel ähnlich ({round(r * 100)} %)"}
    if not ak:
        return {"status": "missing", "path": "", "candidates": [], "reason": "nicht gefunden"}
    other = [e for e in ix.base.get(base) or []]
    if other:
        return {"status": "unclear", "path": "", "candidates": [e["path"] for e in other[:12]], "reason": "anderer Künstler"}
    return {"status": "missing", "path": "", "candidates": [], "reason": "nicht gefunden"}


def ref_keys(ref: dict) -> list:
    """Erkennungsmerkmale eines Eintrags ohne Datei: Link, ISRC, Künstler + Titel + Mix (#282)."""
    out = []
    if ref.get("url"):
        out.append("u:" + str(ref["url"]).split("?")[0].rstrip("/").lower())
    isrc = norm(ref.get("isrc")).replace(" ", "")
    if isrc:
        out.append("i:" + isrc)
    base, mix = split_title(ref.get("title"), ref.get("mix", ""))
    if base:
        out.append("t:" + " ".join(sorted(artist_keys(ref.get("artist")))) + "|" + base + "|" + mix)
    return out


def keep_links(old_items, new_items) -> tuple[list, int]:
    """Beim erneuten Holen einer Playlist bestehende Verknüpfungen (Eintrag ohne Datei → Datei) übernehmen (#282).
    → (neue Einträge, Anzahl übernommener Verknüpfungen)"""
    linked = {}
    for x in old_items or []:
        if isinstance(x, dict) and x.get("path") and isinstance(x.get("ref"), dict):
            for key in ref_keys(x["ref"]):
                linked.setdefault(key, x)
    out, n = [], 0
    for x in new_items or []:
        x = dict(x) if isinstance(x, dict) else {"path": x}
        if not x.get("path") and isinstance(x.get("ref"), dict):
            old = next((linked[k] for k in ref_keys(x["ref"]) if k in linked), None)
            if old is not None:
                x["path"] = old["path"]
                for k in ("lock", "note"):
                    if old.get(k):
                        x[k] = old[k]
                n += 1
        out.append(x)
    return out, n


# =========================================================================== Import und Export (#271)
_CSV_COLS = {"path": ("pfad", "path", "location", "datei", "file", "dateipfad", "filename"),
             "artist": ("künstler", "kuenstler", "artist", "interpret", "artists", "artist name(s)", "artist name",
                        "artist names"),
             "title": ("titel", "title", "track", "name", "track title", "track name"),
             "mix": ("mix", "version", "remix", "mix name"),
             "isrc": ("isrc",),
             "dur": ("dauer", "duration", "länge", "laenge", "length", "time", "zeit"),
             "dur_ms": ("duration (ms)", "duration ms", "duration_ms")}       # Spotify-Exporte (Exportify u. a.)


def _dur(v) -> int:
    v = str(v or "").strip()
    try:
        if ":" in v:
            p = [float(x) for x in v.split(":")]
            return int(p[-1] + 60 * p[-2] + (3600 * p[-3] if len(p) > 2 else 0))
        return int(float(v.replace(",", "."))) if v else 0
    except ValueError:
        return 0


def parse_csv(text: str, base_dir: str = "") -> list[dict]:
    """CSV (Komma, Semikolon oder Tab) → Einträge: mit Pfadspalte Dateien, sonst Angaben ohne Datei (Künstler,
    Titel, Mix, ISRC, Dauer). Ohne erkannte Kopfzeile: erste Spalte als Pfad bzw. „Künstler - Titel“."""
    text = str(text or "").lstrip("\ufeff")
    first = text.splitlines()[0] if text.strip() else ""
    delim = max((";", ",", "\t"), key=first.count) if first else ";"
    rows = [r for r in csv.reader(text.splitlines(), delimiter=delim) if any(c.strip() for c in r)]
    if not rows:
        return []
    head = [norm(c) for c in rows[0]]
    col = {}
    for key, names in _CSV_COLS.items():
        for i, h in enumerate(head):
            if h in {norm(n) for n in names} and key not in col:
                col[key] = i
    out = []
    if col:
        for r in rows[1:]:
            g = lambda k: r[col[k]].strip() if k in col and col[k] < len(r) else ""  # noqa: E731
            p = g("path")
            if p:
                if not re.match(r"^[A-Za-z]:[\\/]", p) and not p.startswith(("/", "\\")) and base_dir:
                    p = os.path.normpath(os.path.join(base_dir, p))
                out.append({"path": p, "artist": g("artist"), "title": g("title")})
            elif g("title") or g("isrc"):
                dur = _dur(g("dur")) or _dur(g("dur_ms")) // 1000
                out.append({"ref": {"artist": g("artist"), "title": g("title"), "mix": g("mix"), "isrc": g("isrc"),
                                    "dur": dur, "source": "csv"}})
        return out
    for r in rows:
        c = r[0].strip()
        if re.search(r"\.(mp3|flac|wav|aiff?|m4a|ogg)$", c, re.I):
            out.append({"path": c if os.path.isabs(c) or not base_dir else os.path.normpath(os.path.join(base_dir, c))})
        else:
            a, sep, t = c.partition(" - ")
            out.append({"ref": {"artist": a.strip() if sep else "", "title": (t if sep else c).strip(), "source": "csv"}})
    return out


_TL_TIME = re.compile(r"^\[?\(?\d{1,2}:\d{2}(?::\d{2})?\)?\]?\s*")
_TL_NUM = re.compile(r"^(?:#?\d{1,3}[.):]?|\d{1,3}/\d{1,3})\s+")
_TL_SEP = re.compile(r"\s+[-–—]\s+")
_TL_TAIL = re.compile(r"\s*\[[^\]]*\]\s*$")


def parse_tracklist(text: str, source: str = "text") -> tuple[list[dict], int]:
    """Kopierte Trackliste (1001Tracklists, MixID, Beatport, eigene Notizen) → (Einträge ohne Datei, unbekannte).
    Je Zeile „Künstler – Titel (Mix)“; Nummern, Zeitmarken, „w/“ und ein Label in eckigen Klammern am Ende fallen
    weg. „ID – ID“ (unbekannter Titel) wird gezählt, aber nicht übernommen; Zeilen ohne Trennstrich zählen nicht."""
    out, unknown = [], 0
    for line in str(text or "").splitlines():
        t = line.strip().strip("\u200b")
        for _ in range(3):                                   # „01 [12:34] …“ oder „[12:34] 01. …“
            t = _TL_NUM.sub("", _TL_TIME.sub("", t)).strip()
        if t.lower().startswith("w/ "):
            t = t[3:].strip()
        t = _TL_TAIL.sub("", t)
        parts = _TL_SEP.split(t, maxsplit=1)
        if len(parts) != 2:
            continue
        artist, title = parts[0].strip(), parts[1].strip()
        if not title or not artist:
            continue
        if norm(title) in ("id", "id id") or norm(artist) == "id" and norm(title).startswith("id"):
            unknown += 1
            continue
        out.append({"ref": {"artist": artist, "title": title, "source": source}})
    return out, unknown


def read_rekordbox_tree(text: str) -> list[dict]:
    """Rekordbox-XML → [{"folder": "Sets/2026", "name": "Freitag", "paths": [...]}] mit dem Ordnerbaum."""
    root = ET.fromstring(text)
    tracks = {}
    for t in root.iter("TRACK"):
        if t.get("Location") and t.get("TrackID"):
            tracks[t.get("TrackID")] = setexport.path_from_location(t.get("Location"))
    out = []

    def walk(node, path):
        for n in node.findall("NODE"):
            if n.get("Type") == "0":
                walk(n, path + [n.get("Name") or ""])
            elif n.get("Type") == "1":
                by_loc = n.get("KeyType") == "1"
                paths = [setexport.path_from_location(t.get("Key")) if by_loc else tracks.get(t.get("Key"))
                         for t in n.findall("TRACK")]
                out.append({"folder": "/".join(x for x in path if x), "name": n.get("Name") or "Playlist",
                            "paths": [p for p in paths if p]})
    pl = root.find("PLAYLISTS")
    if pl is not None:
        tops = pl.findall("NODE")
        walk(tops[0] if len(tops) == 1 and tops[0].get("Type") == "0" and tops[0].get("Name") == "ROOT" else pl, [])
    return out


def rekordbox_tree(groups, version: str = "", notation: str = "musical") -> str:
    """Mehrere Playlists mit Ordnerbaum als Rekordbox-XML. groups: [{"folder", "name", "entries"}], Einträge wie in
    setexport (path, title, artist, album, genre, duration, bpm, key)."""
    import keys
    root = ET.Element("DJ_PLAYLISTS", Version="1.0.0")
    ET.SubElement(root, "PRODUCT", Name="MarKusSXCH TagStudio", Version=version or "", Company="")
    col = ET.SubElement(root, "COLLECTION")
    ids = {}
    for g in groups:
        for e in g["entries"]:
            k = nk(e["path"])
            if k in ids:
                continue
            ids[k] = str(len(ids) + 1)
            a = {"TrackID": ids[k], "Name": e.get("title") or os.path.splitext(os.path.basename(e["path"]))[0],
                 "Artist": e.get("artist") or "", "Album": e.get("album") or "", "Genre": e.get("genre") or "",
                 "Kind": "MP3 File", "TotalTime": str(int(round(e.get("duration") or 0))),
                 "Location": setexport.location(e["path"])}
            if e.get("bpm"):
                a["AverageBpm"] = f"{float(e['bpm']):.2f}"
            if e.get("key"):
                a["Tonality"] = keys.format_key(e["key"], notation)
            ET.SubElement(col, "TRACK", **a)
    col.set("Entries", str(len(ids)))
    pls = ET.SubElement(root, "PLAYLISTS")
    top = ET.SubElement(pls, "NODE", Type="0", Name="ROOT")
    nodes = {"": top}

    def folder_node(path):
        if path in nodes:
            return nodes[path]
        parent, _, name = path.rpartition("/")
        n = ET.SubElement(folder_node(parent), "NODE", Type="0", Name=name)
        nodes[path] = n
        return n
    for g in groups:
        n = ET.SubElement(folder_node(g.get("folder") or ""), "NODE", Name=g["name"], Type="1", KeyType="0",
                          Entries=str(len(g["entries"])))
        for e in g["entries"]:
            ET.SubElement(n, "TRACK", Key=ids[nk(e["path"])])
    for n in nodes.values():
        n.set("Count", str(len(n.findall("NODE"))))
    ET.indent(root, "  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


# =========================================================================== Speicher
class Store:
    def __init__(self, root: str, mirror: str = "", archive_dir: str = ""):
        self.root = root
        self.mirror = mirror or ""
        self.archive_dir = archive_dir or ""
        self._pls: dict[str, dict] | None = None
        self._index: dict | None = None
        self.undo_stack: list[dict] = []
        self.redo_stack: list[dict] = []

    # ------------------------------------------------------------------ Laden und Schreiben
    def _file(self, pid: str) -> str:
        return os.path.join(self.root, f"{pid}.json")

    @property
    def index(self) -> dict:
        if self._index is None:
            try:
                with open(os.path.join(self.root, "index.json"), encoding="utf-8") as fh:
                    d = json.load(fh)
            except (OSError, ValueError):
                d = {}
            d = d if isinstance(d, dict) else {}
            d.setdefault("format", FORMAT)
            for k, typ in (("folders", list), ("recent", list), ("written", dict), ("ignored", list), ("migrated", dict)):
                if not isinstance(d.get(k), typ):
                    d[k] = typ()
            self._index = d
        return self._index

    def save_index(self):
        _write_json(os.path.join(self.root, "index.json"), self.index)

    def _all(self) -> dict[str, dict]:
        if self._pls is None:
            out = {}
            try:
                names = os.listdir(self.root)
            except OSError:
                names = []
            for n in names:
                if not (n.startswith("pl_") and n.endswith(".json")):
                    continue
                try:
                    with open(os.path.join(self.root, n), encoding="utf-8") as fh:
                        d = json.load(fh)
                except (OSError, ValueError):
                    continue
                if isinstance(d, dict) and d.get("id") == n[:-5]:
                    d["items"] = [y for y in (clean_item(x) for x in d.get("items") or []) if y]
                    out[d["id"]] = d
            self._pls = out
        return self._pls

    def _put(self, pl: dict):
        pl["modified"] = int(time.time())
        self._all()[pl["id"]] = pl
        _write_json(self._file(pl["id"]), pl)

    def _drop(self, pid: str):
        self._all().pop(pid, None)
        try:
            os.remove(self._file(pid))
        except OSError:
            pass

    # ------------------------------------------------------------------ Abfragen
    def get(self, pid) -> dict:
        pl = self._all().get(str(pid or ""))
        if pl is None:
            raise ValueError("Playlist nicht gefunden.")
        return pl

    def exists(self, pid) -> bool:
        return str(pid or "") in self._all()

    def active(self) -> list[dict]:
        return sorted((p for p in self._all().values() if not p.get("archived")),
                      key=lambda p: (p.get("folder", "").lower(), p["name"].lower(), p["id"]))

    def archived(self) -> list[dict]:
        return sorted((p for p in self._all().values() if p.get("archived")), key=lambda p: -int(p["archived"]))

    def find(self, name, folder=None) -> dict | None:
        """Aktive Playlist mit diesem Namen (und Ordner, wenn angegeben)."""
        n = " ".join(str(name or "").split()).lower()
        for p in self.active():
            if p["name"].lower() == n and (folder is None or p.get("folder", "") == clean_folder(folder)):
                return p
        return None

    def find_source(self, plugin, sid) -> dict | None:
        for p in self.active():
            src = p.get("source") or {}
            if src.get("plugin") == plugin and str(src.get("id")) == str(sid):
                return p
        return None

    def meta(self, pl: dict) -> dict:
        return {"id": pl["id"], "name": pl["name"], "folder": pl.get("folder", ""), "kind": pl.get("kind", "manual"),
                "count": len(pl.get("items") or []), "modified": pl.get("modified", 0), "created": pl.get("created", 0),
                "archived": pl.get("archived") or 0, "color": pl.get("color", ""), "note": pl.get("note", ""),
                "source": pl.get("source") or None, "file": self.mirror_path(pl["id"]) if not pl.get("archived") else pl.get("archived_file", ""),
                "rules": pl.get("rules") or None, "refreshed": pl.get("refreshed") or 0, "pushed": pl.get("pushed") or {}}

    def folders(self) -> list[str]:
        """Alle Ordner: angelegte und die der aktiven Playlists (mit allen Elternordnern)."""
        out = set()
        for f in list(self.index["folders"]) + [p.get("folder", "") for p in self.active()]:
            parts = clean_folder(f).split("/") if f else []
            for k in range(1, len(parts) + 1):
                out.add("/".join(parts[:k]))
        return sorted(out, key=lambda s: [x.lower() for x in s.split("/")])

    def recent(self) -> list[str]:
        return [i for i in self.index["recent"] if self.exists(i) and not self.get(i).get("archived")][:RECENT_MAX]

    def touch(self, pid):
        r = [x for x in self.index["recent"] if x != pid]
        self.index["recent"] = [pid] + r[:RECENT_MAX * 2]
        self.save_index()

    # ------------------------------------------------------------------ Rückgängig
    def _snap(self, ids, label: str) -> dict:
        return {"label": label, "pls": {i: copy.deepcopy(self._all().get(i)) for i in ids},
                "folders": list(self.index["folders"])}

    def _record(self, rec: dict):
        self.undo_stack.append(rec)
        del self.undo_stack[:-UNDO_MAX]
        self.redo_stack.clear()

    def _swap(self, rec: dict) -> dict:
        back = self._snap(list(rec["pls"]), rec["label"])
        for pid, pl in rec["pls"].items():
            if pl is None:
                self._drop(pid)
            else:
                self._all()[pid] = copy.deepcopy(pl)
                _write_json(self._file(pid), pl)
        self.index["folders"] = list(rec["folders"])
        self.save_index()
        self.sync(list(rec["pls"]))
        return back

    def undo(self) -> str:
        if not self.undo_stack:
            raise ValueError("Nichts rückgängig zu machen.")
        rec = self.undo_stack.pop()
        self.redo_stack.append(self._swap(rec))
        return rec["label"]

    def redo(self) -> str:
        if not self.redo_stack:
            raise ValueError("Nichts zu wiederholen.")
        rec = self.redo_stack.pop()
        self.undo_stack.append(self._swap(rec))
        return rec["label"]

    def _change(self, ids, label, fn):
        """Änderung mit Rückgängig-Eintrag und nachgeführtem Playlist-Ordner."""
        rec = self._snap(ids, label)
        out = fn()
        self._record(rec)
        self.sync(ids)
        return out

    # ------------------------------------------------------------------ Ändern
    def _check_free(self, name, folder, skip=None):
        for p in self.active():
            if p["id"] != skip and p.get("folder", "") == folder and p["name"].lower() == name.lower():
                if folder:
                    raise ValueError(f"Eine Playlist „{name}“ gibt es im Ordner „{folder}“ schon.")
                raise ValueError(f"Eine Playlist „{name}“ gibt es schon.")

    def unique_name(self, name, folder, suffix="") -> str:
        name, folder = clean_name(name), clean_folder(folder)
        taken = {p["name"].lower() for p in self.active() if p.get("folder", "") == folder}
        if name.lower() not in taken and not suffix:
            return name
        k = 1
        while True:
            cand = f"{name} ({suffix}{'' if k == 1 else ' ' + str(k)})" if suffix else f"{name} ({k + 1})"
            if cand.lower() not in taken:
                return cand
            k += 1

    def create(self, name, folder="", kind="manual", items=None, **extra) -> dict:
        name, folder = clean_name(name), clean_folder(folder)
        self._check_free(name, folder)
        pid = "pl_" + secrets.token_hex(6)
        now = int(time.time())
        pl = {"format": FORMAT, "id": pid, "name": name, "folder": folder, "kind": kind if kind in KINDS else "manual",
              "created": now, "items": [y for y in (clean_item(x) for x in items or []) if y]}
        for k in ("color", "note", "source", "djset", "rules", "refreshed"):
            if extra.get(k):
                pl[k] = extra[k]
        self._change([pid], "Playlist anlegen", lambda: self._put(pl))
        return pl

    def update(self, pid, label="Playlist ändern", **fields) -> dict:
        pl = copy.deepcopy(self.get(pid))
        if pl.get("archived"):
            raise ValueError("Archivierte Playlists lassen sich nicht ändern – zuerst zurückholen.")
        if "name" in fields or "folder" in fields:
            name = clean_name(fields.get("name", pl["name"]))
            folder = clean_folder(fields.get("folder", pl.get("folder", "")))
            self._check_free(name, folder, skip=pid)
            pl["name"], pl["folder"] = name, folder
        if "items" in fields:
            pl["items"] = [y for y in (clean_item(x) for x in fields["items"] or []) if y]
        for k in ("color", "note", "kind", "source", "djset", "rules", "refreshed"):
            if k in fields:
                if fields[k] in (None, "", {}):
                    pl.pop(k, None)
                else:
                    pl[k] = fields[k]
        self._change([pid], label, lambda: self._put(pl))
        return pl

    def rename(self, pid, name) -> dict:
        return self.update(pid, "Umbenennen", name=name)

    def move(self, pid, folder) -> dict:
        return self.update(pid, "Verschieben", folder=folder)

    def duplicate(self, pid) -> dict:
        src = self.get(pid)
        name = self.unique_name(src["name"], src.get("folder", ""), "Kopie")
        extra = {k: copy.deepcopy(src[k]) for k in ("color", "note", "djset", "rules") if src.get(k)}
        return self.create(name, src.get("folder", ""), src.get("kind", "manual") if src.get("kind") != "queue" else "manual",
                           copy.deepcopy(src.get("items") or []), **extra)

    def merge(self, ids, name, folder="") -> dict:
        items = []
        for pid in ids:
            items += copy.deepcopy(self.get(pid).get("items") or [])
        return self.create(name, folder, "manual", items)

    def _hand(self, pid) -> dict:
        """Playlist, die sich von Hand ändern lässt – Smartlists füllen sich über ihre Regeln (#272)."""
        pl = self.get(pid)
        if pl.get("kind") == "smart":
            raise ValueError("Smartlists füllen sich über ihre Regeln – zuerst „Einfrieren“, um sie von Hand zu ändern.")
        return pl

    def add(self, pid, items, dupes="ask") -> dict:
        """Einträge anhängen. dupes: "ask" (bei Doppelten nichts ändern, nur melden), "add", "skip"."""
        pl = self._hand(pid)
        new = [y for y in (clean_item(x) for x in items or []) if y]
        have = {nk(x["path"]) for x in pl.get("items") or [] if x.get("path")}
        dup = 0
        seen = set(have)
        for x in new:
            if x.get("path") and nk(x["path"]) in seen:
                dup += 1
            if x.get("path"):
                seen.add(nk(x["path"]))
        if dup and dupes == "ask":
            return {"ask": True, "dupes": dup, "new": len(new) - dup, "added": 0}
        if dupes == "skip":
            keep, seen = [], set(have)
            for x in new:
                if x.get("path") and nk(x["path"]) in seen:
                    continue
                if x.get("path"):
                    seen.add(nk(x["path"]))
                keep.append(x)
            new = keep
        now = int(time.time())
        for x in new:
            x.setdefault("added", now)
        if new:
            self.update(pid, "Titel hinzufügen", items=list(pl.get("items") or []) + new)
        self.touch(pid)
        return {"ask": False, "dupes": dup, "added": len(new)}

    def remove(self, pid, indices) -> int:
        pl = self._hand(pid)
        drop = {int(i) for i in indices or [] if isinstance(i, int)}
        items = [x for k, x in enumerate(pl.get("items") or []) if k not in drop]
        n = len(pl.get("items") or []) - len(items)
        if n:
            self.update(pid, "Titel entfernen", items=items)
        return n

    def order(self, pid, perm) -> dict:
        """Neue Reihenfolge als Liste der bisherigen Positionen (fehlende hängen hinten an)."""
        pl = self._hand(pid)
        items = pl.get("items") or []
        seen, out = set(), []
        for i in perm or []:
            if isinstance(i, int) and 0 <= i < len(items) and i not in seen:
                out.append(items[i])
                seen.add(i)
        out += [x for k, x in enumerate(items) if k not in seen]
        return self.update(pid, "Reihenfolge", items=out)

    # ------------------------------------------------------------------ Smartlists (#272)
    def smart_fill(self, pid, items) -> bool:
        """Einträge einer Smartlist neu setzen (M3U8 wird mitgeschrieben). Rückgängig nur bei echter Änderung.
        → True, wenn sich die Titel geändert haben."""
        pl = self.get(pid)
        if pl.get("kind") != "smart" or pl.get("archived"):
            raise ValueError("Keine aktive Smartlist.")
        old = [nk(x["path"]) for x in pl.get("items") or [] if x.get("path")]
        new = [y for y in (clean_item(x) for x in items or []) if y]
        now = int(time.time())
        if old == [nk(x["path"]) for x in new if x.get("path")]:
            pl = copy.deepcopy(pl)
            pl["refreshed"] = now
            self._put(pl)                                    # nur Zeitpunkt – kein Rückgängig-Eintrag
            return False
        added = {nk(x["path"]): x.get("added") for x in pl.get("items") or [] if x.get("path")}
        for x in new:
            x["added"] = added.get(nk(x["path"])) or now
        self.update(pid, "Smartlist aktualisieren", items=new, refreshed=now)
        return True

    def set_pushed(self, pid, plugin, info: dict):
        """#273: Ziel im anderen Programm merken (ID, Zeitpunkt) – ohne Rückgängig-Eintrag."""
        pl = copy.deepcopy(self.get(pid))
        pushed = pl.get("pushed") if isinstance(pl.get("pushed"), dict) else {}
        pushed[str(plugin)] = {"id": info.get("id"), "at": int(time.time())}
        pl["pushed"] = pushed
        self._put(pl)

    def freeze(self, pid) -> dict:
        """Smartlist → normale Playlist mit den aktuellen Titeln (Regeln fallen weg)."""
        pl = self.get(pid)
        if pl.get("kind") != "smart":
            raise ValueError("Nur Smartlists lassen sich einfrieren.")
        return self.update(pid, "Smartlist einfrieren", kind="manual", rules=None, refreshed=None)

    def relink(self, pid, picks, label="Titel verknüpfen") -> int:
        """Einträgen einen (neuen) Pfad geben: picks = [{"k": Position, "path": Datei}] – Angaben „ref“ bleiben."""
        items = copy.deepcopy(self.get(pid).get("items") or [])
        n = 0
        for p in picks or []:
            k, path = (p.get("k"), p.get("path")) if isinstance(p, dict) else (None, None)
            if isinstance(k, int) and 0 <= k < len(items) and isinstance(path, str) and path:
                items[k]["path"] = path
                n += 1
        if n:
            self.update(pid, label, items=items)
        return n

    # ------------------------------------------------------------------ Ordner
    def folder_create(self, path) -> str:
        f = clean_folder(path)
        if not f:
            raise ValueError("Bitte einen Ordnernamen eingeben.")
        if f not in self.index["folders"]:
            rec = self._snap([], "Ordner anlegen")
            self.index["folders"].append(f)
            self.save_index()
            self._record(rec)
        return f

    def _under(self, folder, prefix) -> bool:
        return folder == prefix or folder.startswith(prefix + "/")

    def folder_rename(self, old, new) -> str:
        old, new = clean_folder(old), clean_folder(new)
        if not old or not new:
            raise ValueError("Bitte einen Ordnernamen eingeben.")
        if old == new:
            return new
        if self._under(new, old):
            raise ValueError("Ein Ordner lässt sich nicht in sich selbst verschieben.")
        pls = [p for p in self.active() if self._under(p.get("folder", ""), old)]
        for p in pls:
            nf = new + p.get("folder", "")[len(old):]
            self._check_free(p["name"], nf, skip=p["id"])
        rec = self._snap([p["id"] for p in pls], "Ordner umbenennen")
        for p in pls:
            q = copy.deepcopy(p)
            q["folder"] = new + p.get("folder", "")[len(old):]
            self._put(q)
        self.index["folders"] = sorted({(new + f[len(old):]) if self._under(f, old) else f for f in self.index["folders"]})
        self.save_index()
        self._record(rec)
        self.sync([p["id"] for p in pls])
        return new

    def folder_remove(self, path):
        """Leeren Ordner entfernen (Ordner mit Playlists: diese zuerst archivieren oder verschieben)."""
        f = clean_folder(path)
        if any(self._under(p.get("folder", ""), f) for p in self.active()):
            raise ValueError("Der Ordner enthält noch Playlists – zuerst archivieren oder verschieben.")
        rec = self._snap([], "Ordner entfernen")
        self.index["folders"] = [x for x in self.index["folders"] if not self._under(x, f)]
        self.save_index()
        self._record(rec)

    # ------------------------------------------------------------------ Archiv
    def _archive_root(self) -> str:
        if self.archive_dir:
            return os.path.join(self.archive_dir, ARCHIVE_SUB)
        return os.path.join(self.mirror, MIRROR_ARCHIVE) if self.mirror else ""

    def _log_dir(self) -> str:
        return self.archive_dir or (os.path.join(self.mirror, MIRROR_ARCHIVE) if self.mirror else "")

    def _log(self, src, dst):
        d = self._log_dir()
        if not d:
            return
        os.makedirs(d, exist_ok=True)
        log = os.path.join(d, archive.LOG)
        new = not os.path.exists(log)
        with open(log, "a", encoding="utf-8-sig" if new else "utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            if new:
                w.writerow(archive.HEAD)
            w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), src, dst, AREA, ""])

    def _log_restored(self, dst):
        log = os.path.join(self._log_dir() or "", archive.LOG)
        if not self._log_dir() or not os.path.isfile(log):
            return
        with open(log, encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh, delimiter=";"))
        for r in reversed(rows[1:]):
            r += [""] * (5 - len(r))
            if os.path.normcase(r[2]) == os.path.normcase(dst) and not r[4]:
                r[4] = time.strftime("%Y-%m-%d %H:%M:%S")
                break
        with open(log, "w", encoding="utf-8-sig", newline="") as fh:
            csv.writer(fh, delimiter=";").writerows(rows)

    def archive(self, pid) -> dict:
        """Archivieren: Playlist bleibt erhalten (Archiv-Bereich), ihre M3U8 wandert ins Archiv."""
        pl = copy.deepcopy(self.get(pid))
        if pl.get("archived"):
            return pl
        pl["archived"] = int(time.time())
        info = self.index["written"].pop(pid, None)
        if info and self.mirror:
            src = os.path.join(self.mirror, *info["rel"].split("/"))
            root = self._archive_root()
            if os.path.isfile(src) and root:
                dst = _unique(os.path.join(root, *info["rel"].split("/")))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(src, dst)
                self._log(src, dst)
                pl["archived_file"] = dst
        self._put(pl)
        self.index["recent"] = [x for x in self.index["recent"] if x != pid]
        self.save_index()
        self.undo_stack = [r for r in self.undo_stack if pid not in r["pls"]]     # Archivieren ersetzt das Rückgängig
        self.redo_stack = [r for r in self.redo_stack if pid not in r["pls"]]
        return pl

    def archive_folder(self, path) -> int:
        f = clean_folder(path)
        pls = [p for p in self.active() if self._under(p.get("folder", ""), f)]
        for p in pls:
            self.archive(p["id"])
        self.index["folders"] = [x for x in self.index["folders"] if not self._under(x, f)]
        self.save_index()
        return len(pls)

    def restore(self, pid) -> dict:
        """Aus dem Archiv zurückholen (bei gleichem Namen im Ordner mit Zusatz „(2)“)."""
        pl = copy.deepcopy(self.get(pid))
        if not pl.get("archived"):
            return pl
        pl.pop("archived", None)
        try:
            self._check_free(pl["name"], pl.get("folder", ""), skip=pid)
        except ValueError:
            pl["name"] = self.unique_name(pl["name"], pl.get("folder", ""))
        old = pl.pop("archived_file", "")
        self._put(pl)
        if old and os.path.isfile(old) and self.mirror:
            rel = self.desired().get(pid)
            dst = os.path.join(self.mirror, *rel.split("/")) if rel else ""
            if dst and not os.path.exists(dst):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(old, dst)
                self._log_restored(old)
                self.index["written"][pid] = {"rel": rel, "sha": sha_file(dst)}
                self.save_index()
        self.sync([pid])
        return pl

    def delete(self, pid):
        """Endgültig löschen – nur archivierte Playlists (die Oberfläche fragt vorher)."""
        pl = self.get(pid)
        if not pl.get("archived"):
            raise ValueError("Nur archivierte Playlists lassen sich endgültig löschen.")
        f = pl.get("archived_file", "")
        if f and os.path.isfile(f):
            os.remove(f)
        self._drop(pid)
        self.index["written"].pop(pid, None)
        self.save_index()

    # ------------------------------------------------------------------ Playlist-Ordner (M3U8)
    def desired(self) -> dict[str, str]:
        """Aktive Playlist → relativer Pfad ihrer M3U8 im Playlist-Ordner (Trenner „/“, eindeutig)."""
        out, used = {}, set()
        for p in self.active():
            parts = [safe_part(x) for x in p.get("folder", "").split("/") if x]
            stem = safe_part(p["name"])
            rel = "/".join(parts + [stem + MIRROR_EXT])
            k = 1
            while rel.lower() in used:
                k += 1
                rel = "/".join(parts + [f"{stem} ({k}){MIRROR_EXT}"])
            used.add(rel.lower())
            out[p["id"]] = rel
        return out

    def mirror_path(self, pid) -> str:
        if not self.mirror:
            return ""
        rel = self.desired().get(pid)
        return os.path.join(self.mirror, *rel.split("/")) if rel else ""

    def sync(self, ids=None) -> dict:
        """M3U8 der genannten (None = aller) Playlists schreiben, umbenennen bzw. entfernen. Von anderen Programmen
        geänderte oder fremde Dateien bleiben unangetastet (→ external_changes)."""
        if not self.mirror:
            return {"written": 0, "conflicts": []}
        want = self.desired()
        ids = set(want) | set(self.index["written"]) if ids is None else set(ids)
        written = self.index["written"]
        n, conflicts = 0, []
        for pid in sorted(ids):
            rel, info = want.get(pid), written.get(pid)
            path = os.path.join(self.mirror, *rel.split("/")) if rel else ""
            if info and info["rel"] != rel:                          # umbenannt, verschoben, entfernt
                old = os.path.join(self.mirror, *info["rel"].split("/"))
                if os.path.isfile(old) and sha_file(old) != info["sha"]:
                    conflicts.append(info["rel"])                    # von aussen geändert: bleibt liegen (→ „neu“)
                    written.pop(pid, None)
                    info = None
                elif os.path.isfile(old):
                    if not rel:
                        os.remove(old)                               # eigene, unveränderte Datei einer entfernten Playlist
                        written.pop(pid, None)
                        continue
                    if os.path.exists(path):                         # Ziel belegt (fremde Datei)
                        conflicts.append(rel)
                        continue
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    os.replace(old, path)
                    info = written[pid] = {"rel": rel, "sha": info["sha"]}
                else:
                    written.pop(pid, None)
                    info = None
            if not rel:
                written.pop(pid, None)
                continue
            text = m3u_text(self.get(pid), os.path.dirname(path))
            sha = sha_text(text)
            if os.path.isfile(path):
                cur = sha_file(path)
                if cur == sha:
                    written[pid] = {"rel": rel, "sha": sha}
                    continue
                if not info or info.get("sha") != cur:               # fremd oder von aussen geändert
                    conflicts.append(rel)
                    continue
            _write_text(path, text)
            written[pid] = {"rel": rel, "sha": sha}
            n += 1
        self.save_index()
        return {"written": n, "conflicts": conflicts}

    def external_changes(self) -> list[dict]:
        """Änderungen im Playlist-Ordner durch andere Programme: geändert, entfernt, neu."""
        if not self.mirror or not os.path.isdir(self.mirror):
            return []
        out, known = [], set()
        for pid, info in self.index["written"].items():
            if not self.exists(pid):
                continue
            known.add(info["rel"].lower())
            path = os.path.join(self.mirror, *info["rel"].split("/"))
            if not os.path.isfile(path):
                out.append({"kind": "removed", "id": pid, "rel": info["rel"], "name": self.get(pid)["name"]})
            elif sha_file(path) != info["sha"]:
                out.append({"kind": "changed", "id": pid, "rel": info["rel"], "name": self.get(pid)["name"]})
        ignored = {x.lower() for x in self.index["ignored"]}
        for dp, dns, fns in os.walk(self.mirror):
            dns[:] = [d for d in dns if d != MIRROR_ARCHIVE and not d.startswith(".")]
            for fn in fns:
                if not fn.lower().endswith((".m3u8", ".m3u")):
                    continue
                rel = os.path.relpath(os.path.join(dp, fn), self.mirror).replace(os.sep, "/")
                if rel.lower() in known or rel.lower() in ignored:
                    continue
                out.append({"kind": "new", "id": "", "rel": rel, "name": os.path.splitext(fn)[0]})
        return sorted(out, key=lambda x: x["rel"].lower())

    def read_mirror(self, rel) -> list[dict]:
        path = os.path.join(self.mirror, *rel.split("/"))
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            return parse_m3u(fh.read(), os.path.dirname(path))

    def apply_external(self, rel, action) -> dict:
        """Eine Änderung von aussen übernehmen ("take"), die TagStudio-Fassung behalten ("keep"; bei neuen Dateien:
        ignorieren) oder – bei entfernten Dateien – die Playlist archivieren ("archive")."""
        ch = next((c for c in self.external_changes() if c["rel"] == rel), None)
        if ch is None:
            raise ValueError("Diese Änderung gibt es nicht mehr.")
        path = os.path.join(self.mirror, *rel.split("/"))
        if ch["kind"] == "new":
            if action == "take":
                folder = "/".join(rel.split("/")[:-1])
                name = self.unique_name(os.path.splitext(rel.split("/")[-1])[0], folder)
                items = [{"path": e["path"], "dur": e["dur"], **self._split_label(e["label"])} for e in self.read_mirror(rel)]
                pl = self.create(name, folder, "import", items, source={"plugin": "file", "id": rel})
                if self.desired().get(pl["id"]) == rel:
                    self.index["written"][pl["id"]] = {"rel": rel, "sha": sha_file(path)}
                else:                                                   # z. B. .m3u → eigene .m3u8 daneben
                    self.index["ignored"].append(rel)
                self.save_index()
                self.sync([pl["id"]])
                return {"id": pl["id"]}
            self.index["ignored"].append(rel)
            self.save_index()
            return {"id": ""}
        pid = ch["id"]
        if ch["kind"] == "changed" and action == "take":
            old = {nk(x["path"]): x for x in self.get(pid).get("items") or [] if x.get("path")}
            items = []
            for e in self.read_mirror(rel):
                x = dict(old.get(nk(e["path"])) or {"path": e["path"], **self._split_label(e["label"])})
                x["path"] = e["path"]
                if e["dur"]:
                    x["dur"] = e["dur"]
                items.append(x)
            self.index["written"][pid]["sha"] = sha_file(path)
            self.save_index()
            self.update(pid, "Änderung übernehmen", items=items)
        elif ch["kind"] == "changed":                                   # TagStudio-Fassung behalten
            self.index["written"][pid]["sha"] = sha_file(path)
            self.save_index()
            self.sync([pid])
        elif action == "archive":                                       # Datei entfernt → Playlist archivieren
            self.index["written"].pop(pid, None)
            self.save_index()
            self.archive(pid)
        else:                                                           # Datei entfernt → neu schreiben
            self.index["written"].pop(pid, None)
            self.save_index()
            self.sync([pid])
        return {"id": pid}

    @staticmethod
    def _split_label(label) -> dict:
        a, sep, t = str(label or "").partition(" - ")
        return {"artist": a.strip(), "title": t.strip()} if sep else ({"title": label.strip()} if label else {})

    # ------------------------------------------------------------------ Übernahme (DJ-Set-Listen, #269)
    def migrate_djset(self, saved: dict, current: str = "", folder: str = "DJ-Sets") -> dict:
        """Gespeicherte DJ-Set-Listen (cfg „djset_saved“) einmalig übernehmen → {alter Name: id}."""
        if self.index["migrated"].get("djset"):
            return {}
        out = {}
        for name, v in sorted((saved or {}).items()):
            if not isinstance(v, dict):
                continue
            items = [{"path": x["path"], **({"lock": True} if x.get("lock") else {})}
                     for x in v.get("items") or [] if isinstance(x, dict) and isinstance(x.get("path"), str)]
            src, f, n, kind = v.get("source"), folder, name, "djset"
            if src and ": " in name:                                  # „Lexicon: Freitag“ → Ordner Lexicon
                f, n = name.split(": ", 1)
                kind = "import"
            try:
                n = self.unique_name(n, f)
                pl = self.create(n, f, kind, items, djset={"opts": v["opts"]} if isinstance(v.get("opts"), dict) else None,
                                 source={"plugin": src, "id": ""} if src else None)
            except ValueError:
                continue
            out[name] = pl["id"]
        self.index["migrated"]["djset"] = int(time.time())
        self.save_index()
        self.undo_stack.clear()
        return out
