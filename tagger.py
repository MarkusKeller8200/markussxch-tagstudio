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


# =========================================================================== Groß-/Kleinschreibung
CASE_MODES = {
    "title": "Jedes Wort groß („Golden Hour“)",
    "sentence": "Nur erster Buchstabe groß („Golden hour“)",
    "upper": "ALLES GROSS",
    "lower": "alles klein",
}
SMALL_WORDS = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into", "of", "on", "or", "the", "to",
               "vs", "feat", "ft", "with", "und", "oder", "von", "vom", "zu", "zum", "zur", "im", "am", "mit", "für",
               "de", "la", "le", "les", "du", "des", "del", "y", "e"}
_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*")


def change_case(text: str, mode: str, keep_upper: bool = True, small_words: bool = False) -> str:
    """Schreibweise ändern; Mehrfachwerte werden einzeln behandelt.
    keep_upper: Abkürzungen in Großbuchstaben (DJ, AC/DC, II) bleiben. small_words: and/of/the/feat. … klein (Titel)."""
    if mode not in CASE_MODES:
        raise ValueError(f"Unbekannte Schreibweise: {mode}")
    out = []
    for part in text.split(MV):
        if mode == "upper":
            out.append(part.upper())
        elif mode == "lower":
            out.append(part.lower())
        elif mode == "sentence":
            low = _WORD.sub(lambda m: m.group(0) if keep_upper and len(m.group(0)) > 1 and m.group(0).isupper()
                            else m.group(0).lower(), part)
            m = _WORD.search(low)
            out.append(low[:m.start()] + low[m.start()].upper() + low[m.start() + 1:] if m else low)
        else:
            first = [True]

            def cap(m):
                w = m.group(0)
                is_first = first[0]
                first[0] = False
                if keep_upper and len(w) > 1 and w.isupper():
                    return w
                if small_words and not is_first and w.lower() in SMALL_WORDS:
                    return w.lower()
                return w[0].upper() + w[1:].lower()
            out.append(_WORD.sub(cap, part))
    return MV.join(out)


def _text_items(f, keys):
    """(key, Item) der Textfelder; keys None = alle bearbeitbaren Textfelder."""
    for k, it in list(f.items.items()):
        if it.kind not in ("text", "txxx", "comment", "lyrics", "url", "wxxx") or not it.editable:
            continue
        if keys is not None and k not in keys:
            continue
        yield k, it


def plan_case(files, keys, mode, keep_upper=True, small_words=False) -> list[tuple]:
    plan = []
    for f in files:
        for k, it in _text_items(f, keys):
            new = change_case(it.text, mode, keep_upper, small_words)
            if new != it.text:
                plan.append((f, k, it.text, new))
    return plan


# =========================================================================== Suchen & Ersetzen
def plan_replace(files, keys, find, repl, case=False, regex=False, word=False) -> list[tuple]:
    """Suchen & Ersetzen in Textfeldern. keys None = alle Textfelder. Wirft ValueError bei ungültigem Muster.
    Bei regex sind Rückverweise \\1 … bzw. \\g<name> im Ersatz erlaubt."""
    if not find:
        return []
    pat = find if regex else re.escape(find)
    if word:
        pat = rf"\b(?:{pat})\b"
    try:
        rx = re.compile(pat, 0 if case else re.I)
    except re.error as ex:
        raise ValueError(f"Ungültiger regulärer Ausdruck: {ex}") from ex
    plan = []
    for f in files:
        for k, it in _text_items(f, keys):
            try:
                new = rx.sub(repl if regex else repl.replace("\\", "\\\\"), it.text)
            except (re.error, IndexError) as ex:
                raise ValueError(f"Ungültiger Ersatz: {ex}") from ex
            if new != it.text:
                plan.append((f, k, it.text, new))
    return plan


# =========================================================================== Cover aus dem Ordner
COVER_NAMES = ["cover", "folder", "front", "album", "albumart", "albumartlarge", "artwork"]
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".gif")


def find_folder_image(folder: str, cache: dict | None = None):
    """Bestes Bild im Ordner: bekannte Namen (cover/folder/front …), sonst das größte Bild. None, wenn keins."""
    if cache is not None and folder in cache:
        return cache[folder]
    best = None
    try:
        imgs = [e for e in os.scandir(folder) if e.is_file() and e.name.lower().endswith(IMAGE_EXT)]
    except OSError:
        imgs = []
    by_name = {os.path.splitext(e.name)[0].lower(): e.path for e in imgs}
    for n in COVER_NAMES:
        if n in by_name:
            best = by_name[n]
            break
    if best is None and imgs:
        best = max(imgs, key=lambda e: e.stat().st_size).path
    if cache is not None:
        cache[folder] = best
    return best


def plan_folder_cover(files, only_missing=True) -> list[dict]:
    """[{"file", "image": Pfad|None, "action": "set"|"skip", "reason"}]"""
    cache, out = {}, []
    for f in files:
        img = find_folder_image(os.path.dirname(f.path), cache)
        has = f.get("APIC:3") is not None
        if img is None:
            out.append({"file": f, "image": None, "action": "skip", "reason": "kein Bild im Ordner"})
        elif has and only_missing:
            out.append({"file": f, "image": img, "action": "skip", "reason": "hat schon ein Cover"})
        else:
            out.append({"file": f, "image": img, "action": "set", "reason": "ersetzen" if has else "neu"})
    return out


# =========================================================================== Export
def export_table(files, root: str = "") -> tuple[list[str], list[list]]:
    import keys
    head = ["Datei", "Ordner"] + [label for _k, label, _p in FIELDS] + ["Camelot", "Dauer", "Bitrate (kbps)", "ID3", "Cover",
                                                                       "Größe (Bytes)"]
    rows = []
    for f in files:
        dur = getattr(f, "duration", 0) or 0
        m, s = divmod(int(round(dur)), 60)
        rows.append([os.path.basename(f.path), os.path.dirname(f.path)]
                    + [text_of(f, k) for k, _l, _p in FIELDS]
                    + [keys.parse_key(text_of(f, "TKEY")) or ""]
                    + [f"{m}:{s:02d}" if dur else "", getattr(f, "bitrate", "") or "", f.tag_desc,
                       "ja" if f.get("APIC:3") is not None else "nein", f.size])
    return head, rows


def write_csv(path, head, rows):
    """CSV für Excel (UTF-8 mit BOM, Semikolon)."""
    import csv
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(head)
        w.writerows(rows)


_XML_BAD = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _xl(s) -> str:
    s = _XML_BAD.sub("", str(s))
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _col(n: int) -> str:
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def write_xlsx(path, head, rows, sheet="TagStudio"):
    """Minimales Excel-Dokument (ohne Zusatzpakete): eine Tabelle, fette Kopfzeile, Filter, fixierte Kopfzeile."""
    import zipfile

    def cell(r, c, v, style=0):
        ref = f"{_col(c)}{r}"
        st = f' s="{style}"' if style else ""
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return f'<c r="{ref}"{st}><v>{v}</v></c>'
        return f'<c r="{ref}" t="inlineStr"{st}><is><t xml:space="preserve">{_xl(v)}</t></is></c>'
    lines = [f'<row r="1">{"".join(cell(1, c, v, 1) for c, v in enumerate(head))}</row>']
    for r, row in enumerate(rows, 2):
        lines.append(f'<row r="{r}">{"".join(cell(r, c, v) for c, v in enumerate(row))}</row>')
    last = f"{_col(len(head) - 1)}{len(rows) + 1}"
    widths = [max([len(str(head[c]))] + [len(str(row[c])) for row in rows[:500] if c < len(row)]) for c in range(len(head))]
    cols = "".join(f'<col min="{c + 1}" max="{c + 1}" width="{min(60, max(8, w + 2))}" customWidth="1"/>'
                   for c, w in enumerate(widths))
    ws = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
          '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" '
          'state="frozen"/></sheetView></sheetViews>'
          f'<cols>{cols}</cols><sheetData>{"".join(lines)}</sheetData><autoFilter ref="A1:{last}"/></worksheet>')
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{_xl(sheet)}" sheetId="1" r:id="rId1"/></sheets><definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">\'{_xl(sheet)}\'!$A$1:${_col(len(head) - 1)}${len(rows) + 1}</definedName></definedNames></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        "xl/styles.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf/><xf fontId="1" applyFont="1"/></cellXfs></styleSheet>',
        "xl/worksheets/sheet1.xml": ws,
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
