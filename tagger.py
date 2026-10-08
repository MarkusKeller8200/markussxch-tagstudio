"""
tagger.py – Logik des Taggers (unabhängig von der Oberfläche).

* Standardfelder mehrerer Dateien lesen („verschieden“, wenn sie sich unterscheiden) und gemeinsam setzen
* Tags aus dem Dateinamen gewinnen (Muster wie „%track% - %artist% - %title%“)
* Dateien nach Tags umbenennen (Vorschau, Kollisionen, ungültige Zeichen)
* Spurnummern automatisch vergeben
"""
from __future__ import annotations

import os
import re

from id3tags import MV, MV_SHOW, Cover, Item

# Standardfelder des Taggers: (Schlüssel, Anzeigename, Platzhalter im Muster)
FIELDS = [
    ("TIT2", "Titel", "title"),
    ("TPE1", "Künstler", "artist"),
    ("TALB", "Album", "album"),
    ("TPE2", "Album-Künstler", "albumartist"),
    ("TDRC", "Jahr", "year"),
    ("TRCK", "Spurnummer", "track"),
    ("TPOS", "Disknummer", "disc"),
    ("TCON", "Genre", "genre"),
    ("TCOM", "Komponist", "composer"),
    ("TBPM", "BPM", "bpm"),
    ("TKEY", "Tonart", "key"),
    ("COMM:", "Kommentar", "comment"),
]
PLACEHOLDERS = {ph: key for key, _l, ph in FIELDS}
INVALID = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


# =========================================================================== Felder
def text_of(f, key) -> str:
    it = f.get(key)
    if it is None or it.kind in ("picture", "raw"):
        return ""
    return it.text.replace(MV, MV_SHOW)


def common_values(files) -> dict:
    """Je Standardfeld: {"value": gemeinsamer Wert oder "", "mixed": bool}."""
    out = {}
    for key, _label, _ph in FIELDS:
        vals = {text_of(f, key) for f in files}
        out[key] = {"value": vals.pop() if len(vals) == 1 else "", "mixed": len(vals) > 1 if vals else False}
    return out


def set_field(files, key, value) -> int:
    """Setzt key in allen Dateien (leerer Wert entfernt das Feld). Liefert Anzahl geänderter Dateien."""
    from core import apply_value
    return sum(1 for f in files if apply_value(f, key, value))


def cover_summary(files) -> dict:
    """Vorderes Cover (APIC:3) der Auswahl: {"state": "none"|"same"|"mixed", "data", "mime", "desc"}."""
    covers = [f.get("APIC:3") for f in files]
    datas = {c.cover.data if c is not None and c.cover else b"" for c in covers}
    if datas == {b""}:
        return {"state": "none"}
    if len(datas) > 1:
        return {"state": "mixed"}
    c = covers[0]
    return {"state": "same", "data": c.cover.data, "mime": c.cover.mime or Cover.guess_mime(c.cover.data),
            "desc": c.cover.describe()}


def set_cover(files, data: bytes | None, ptype: int = 3) -> int:
    key = f"APIC:{ptype}"
    n = 0
    for f in files:
        if data is None:
            if f.get(key) is not None:
                f.set(key, None)
                n += 1
        else:
            new = Item.new_cover(Cover(data, ptype=ptype))
            if f.get(key) != new:
                f.set(key, new)
                n += 1
    return n


# =========================================================================== Muster
def _pattern_regex(pattern: str):
    """Muster → Regex mit benannten Gruppen. Unbekannte Platzhalter bzw. %dummy% werden übersprungen."""
    parts, pos, names = [], 0, []
    for m in re.finditer(r"%(\w+)%", pattern):
        parts.append(re.escape(pattern[pos:m.start()]))
        name = m.group(1).lower()
        if name in PLACEHOLDERS and name not in names:
            names.append(name)
            parts.append(rf"(?P<{name}>\d+)" if name in ("track", "disc", "year", "bpm") else rf"(?P<{name}>.+?)")
        else:
            parts.append(r".+?")
        pos = m.end()
    parts.append(re.escape(pattern[pos:]))
    return re.compile("^" + "".join(parts) + "$", re.I), names


def parse_filename(pattern: str, filename: str) -> dict | None:
    """Werte aus dem Dateinamen (ohne Endung) nach Muster; None, wenn es nicht passt."""
    rx, _ = _pattern_regex(pattern)
    m = rx.match(os.path.splitext(os.path.basename(filename))[0])
    if not m:
        return None
    return {PLACEHOLDERS[k]: v.strip() for k, v in m.groupdict().items() if v is not None and v.strip()}


def plan_from_filename(files, pattern: str) -> list[dict]:
    """Vorschau: [{"file", "values": {key: neu}, "changes": [(key, alt, neu)], "match": bool}]."""
    out = []
    for f in files:
        vals = parse_filename(pattern, f.path)
        changes = []
        if vals:
            for key, new in vals.items():
                old = text_of(f, key)
                if key == "TRCK" and "/" in old and "/" not in new:
                    new = f"{int(new)}/{old.split('/', 1)[1]}"
                elif key in ("TRCK", "TPOS") and new.isdigit():
                    new = str(int(new))
                if old != new:
                    changes.append((key, old, new))
        out.append({"file": f, "match": vals is not None, "changes": changes})
    return out


def format_name(f, pattern: str, pad: int = 2) -> str:
    """Neuer Dateiname (ohne Ordner, mit Endung) aus Tags nach Muster."""
    def val(m):
        name = m.group(1).lower()
        key = PLACEHOLDERS.get(name)
        if key is None:
            return m.group(0)
        v = text_of(f, key).replace(MV_SHOW, ", ")
        if name in ("track", "disc"):
            v = v.split("/")[0].strip()
            if v.isdigit():
                v = v.zfill(pad if name == "track" else 1)
        if name == "year":
            v = v[:4]
        return v
    base = re.sub(r"%(\w+)%", val, pattern)
    base = INVALID.sub("_", base).strip().rstrip(".")
    base = re.sub(r"\s{2,}", " ", base)
    return base + os.path.splitext(f.path)[1].lower()


def plan_rename(files, pattern: str) -> list[dict]:
    """Vorschau: [{"file", "old", "new", "problem"}]; problem: None | Text (leer, Kollision, existiert)."""
    plan, targets = [], {}
    for f in files:
        new = format_name(f, pattern)
        old = os.path.basename(f.path)
        problem = None
        stem = new[:-len(os.path.splitext(f.path)[1])] if os.path.splitext(f.path)[1] else new
        if not stem or re.fullmatch(r"[\s_\-.,]*", stem):
            problem = "Name wäre leer – fehlen Tags?"
        elif "%" in stem:
            problem = "Unbekannter Platzhalter im Muster"
        full = os.path.normcase(os.path.join(os.path.dirname(f.path), new))
        if problem is None and full in targets:
            problem = "Gleicher Name wie eine andere Datei"
        elif problem is None and new != old and os.path.exists(os.path.join(os.path.dirname(f.path), new)) \
                and os.path.normcase(os.path.abspath(f.path)) != full:
            problem = "Datei mit diesem Namen existiert schon"
        targets[full] = f
        plan.append({"file": f, "old": old, "new": new, "problem": problem})
    return plan


def do_rename(plan) -> list[dict]:
    """Benennt um (nur Einträge ohne Problem und mit neuem Namen). Aktualisiert f.path."""
    results = []
    for p in plan:
        f = p["file"]
        if p["problem"] or p["new"] == p["old"]:
            continue
        dst = os.path.join(os.path.dirname(f.path), p["new"])
        try:
            if os.path.normcase(f.path) == os.path.normcase(dst):  # nur Groß-/Kleinschreibung (Windows/macOS)
                tmp = dst + ".tagstudio_tmp"
                os.rename(f.path, tmp)
                os.rename(tmp, dst)
            else:
                os.rename(f.path, dst)
            results.append({"old": p["old"], "new": p["new"], "ok": True})
            f.path = dst
        except OSError as ex:
            results.append({"old": p["old"], "new": p["new"], "ok": False, "error": str(ex)})
    return results


def plan_numbering(files, with_total: bool = True, start: int = 1) -> list[tuple]:
    """Spurnummern in der gegebenen Reihenfolge: [(f, alt, neu)] nur bei Änderung."""
    n = len(files)
    out = []
    for i, f in enumerate(files, start):
        new = f"{i}/{n + start - 1}" if with_total else str(i)
        old = text_of(f, "TRCK")
        if old != new:
            out.append((f, old, new))
    return out
