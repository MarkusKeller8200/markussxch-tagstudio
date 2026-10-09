"""
xmltools.py – XML in Tag-Feldern erkennen, prüfen, formatieren und kompakt schreiben.

Nur Standardbibliothek (expat/minidom). Externe Entitäten werden nicht geladen.
Wird von beiden Oberflächen genutzt.
"""
from __future__ import annotations

import re
from xml.dom import minidom, Node
from xml.parsers import expat

_HEAD = re.compile(r"^\s*(?:<\?xml\b|<!DOCTYPE\b|<!--|<[A-Za-z_][\w:.\-]*(?:\s|/?>))", re.S)
_DECL = re.compile(r"^\s*(<\?xml\b[^>]*\?>)", re.S)

# häufige expat-Meldungen auf Deutsch
_DE = {
    "syntax error": "Syntaxfehler",
    "mismatched tag": "End-Tag passt nicht zum Start-Tag",
    "unclosed token": "Nicht abgeschlossenes Element",
    "no element found": "Kein Element gefunden (Dokument leer oder unvollständig)",
    "not well-formed (invalid token)": "Nicht wohlgeformt (ungültiges Zeichen)",
    "junk after document element": "Text nach dem Wurzelelement (nur ein Wurzelelement erlaubt)",
    "undefined entity": "Unbekannte Entität (z. B. & statt &amp;)",
    "duplicate attribute": "Attribut doppelt vorhanden",
    "unclosed CDATA section": "CDATA-Abschnitt nicht geschlossen",
    "XML or text declaration not at start of entity": "XML-Deklaration steht nicht am Anfang",
    "unbound prefix": "Unbekanntes Namensraum-Präfix",
}


def looks_like_xml(text: str) -> bool:
    """Sieht der Wert nach XML aus? (Beginnt mit einem Tag/Deklaration und endet mit '>')."""
    if not text or len(text) < 7:
        return False
    s = text.strip()
    return s.endswith(">") and bool(_HEAD.match(s)) and ("</" in s or "/>" in s or s.startswith("<?xml"))


def check(text: str) -> dict:
    """Wohlgeformt? → {"ok": True} oder {"ok": False, "error", "line", "col"} (Zeile/Spalte ab 1)."""
    p = expat.ParserCreate()
    p.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    try:
        p.Parse(text, True)
        return {"ok": True}
    except expat.ExpatError as ex:
        msg = expat.ErrorString(ex.code) if ex.code else str(ex)
        return {"ok": False, "error": _DE.get(msg, msg), "line": ex.lineno, "col": ex.offset + 1}


def _esc_text(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _esc_attr(s: str) -> str:
    return _esc_text(s).replace('"', "&quot;").replace("\n", "&#10;").replace("\t", "&#9;")


def _serialize(node, indent: str | None, level: int, out: list):
    nl = "\n" if indent is not None else ""
    pad = (indent or "") * level
    t = node.nodeType
    if t == Node.ELEMENT_NODE:
        attrs = "".join(f' {a.name}="{_esc_attr(a.value)}"' for a in node.attributes.values())
        kids = [c for c in node.childNodes
                if not (c.nodeType == Node.TEXT_NODE and not c.data.strip())]
        if not kids:
            out.append(f"{pad}<{node.tagName}{attrs}/>{nl}")
            return
        mixed = any(c.nodeType == Node.TEXT_NODE and c.data.strip() for c in kids) and \
            any(c.nodeType == Node.ELEMENT_NODE for c in kids)
        if mixed and indent is not None:  # Fließtext mit Elementen: Inhalt unverändert in einer Zeile lassen
            inline: list[str] = []
            _serialize(node, None, 0, inline)
            out.append(f"{pad}{''.join(inline)}{nl}")
            return
        if all(c.nodeType in (Node.TEXT_NODE, Node.CDATA_SECTION_NODE) for c in kids):
            inner = "".join(_esc_text(c.data) if c.nodeType == Node.TEXT_NODE else f"<![CDATA[{c.data}]]>"
                            for c in node.childNodes)
            if indent is not None:
                inner = inner.strip()
            out.append(f"{pad}<{node.tagName}{attrs}>{inner}</{node.tagName}>{nl}")
            return
        out.append(f"{pad}<{node.tagName}{attrs}>{nl}")
        for c in kids:
            _serialize(c, indent, level + 1, out)
        out.append(f"{pad}</{node.tagName}>{nl}")
    elif t == Node.TEXT_NODE:
        out.append(f"{pad}{_esc_text(node.data.strip() if indent is not None else node.data)}{nl}")
    elif t == Node.CDATA_SECTION_NODE:
        out.append(f"{pad}<![CDATA[{node.data}]]>{nl}")
    elif t == Node.COMMENT_NODE:
        out.append(f"{pad}<!--{node.data}-->{nl}")
    elif t == Node.PROCESSING_INSTRUCTION_NODE:
        out.append(f"{pad}<?{node.target} {node.data}?>{nl}")


def format_xml(text: str, compact: bool = False, indent: str = "  ") -> dict:
    """Formatiert (eingerückt) oder schreibt kompakt (eine Zeile, Leerraum zwischen Tags entfernt).
    → {"ok", "text"} bzw. {"ok": False, "error", "line", "col"}. Die XML-Deklaration bleibt erhalten."""
    chk = check(text)
    if not chk["ok"]:
        return chk
    dom = minidom.parseString(text.encode("utf-8") if not _DECL.match(text) else _utf8_decl(text))
    out: list[str] = []
    m = _DECL.match(text)
    if m:
        out.append(m.group(1) + ("" if compact else "\n"))
    for c in dom.childNodes:
        if c.nodeType == Node.DOCUMENT_TYPE_NODE:
            out.append(c.toxml() + ("" if compact else "\n"))
        else:
            _serialize(c, None if compact else indent, 0, out)
    res = "".join(out)
    return {"ok": True, "text": res if compact else res.rstrip("\n")}


def _utf8_decl(text: str) -> bytes:
    """Deklaration auf UTF-8 umstellen, damit minidom den (bereits dekodierten) Text richtig liest."""
    return re.sub(r'encoding\s*=\s*["\'][^"\']*["\']', 'encoding="UTF-8"', text, count=1).encode("utf-8")


# =========================================================================== XML in Binärfeldern (GEOB, PRIV …)
# XML kann in einem Binärfeld mitten in anderen Bytes stehen (Kopf, Längenangaben, Nullbytes am Ende).
# Gesucht wird ein XML-Abschnitt in UTF-8 oder UTF-16; beim Bearbeiten wird nur dieser Abschnitt ersetzt,
# alle übrigen Bytes (Frame-Kopf, Präfix, Suffix) bleiben byte-genau erhalten.
_START = {
    "utf-8": re.compile(rb"<\?xml|<[A-Za-z_]"),
    "utf-16-le": re.compile(rb"<\x00(?:\?\x00x\x00m\x00l\x00|[A-Za-z_]\x00)"),
    "utf-16-be": re.compile(rb"\x00<(?:\x00\?\x00x\x00m\x00l|\x00[A-Za-z_])"),
}
_END = {"utf-8": b">", "utf-16-le": b">\x00", "utf-16-be": b"\x00>"}
_BOMS = ((b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be"), (b"\xef\xbb\xbf", "utf-8"))


def _blob_header_len(it) -> int:
    """Länge des Frame-Kopfs vor den eigentlichen Daten (GEOB: Kodierung, MIME, Dateiname, Beschreibung)."""
    p = it.payload
    if it.fid == "GEOB":
        from id3tags import _geob_parts
        return len(p) - len(_geob_parts(p)[3])
    if it.fid == "PRIV":
        i = p.find(b"\x00")
        return i + 1 if i >= 0 else 0
    return 0


def find_xml(data: bytes):
    """XML-Abschnitt in Binärdaten → {"codec", "start", "end", "text", "valid"} oder None.
    Bevorzugt wohlgeformtes XML; sonst den ersten Abschnitt, der nach XML aussieht."""
    if not data or len(data) < 7:
        return None
    order = ["utf-8", "utf-16-le", "utf-16-be"]
    for bom, codec in _BOMS:   # BOM am Anfang der Daten entscheidet die Kodierung
        if data.startswith(bom):
            order.remove(codec)
            order.insert(0, codec)
            break
    fallback = None
    for codec in order:
        end = data.rfind(_END[codec])
        if end < 0:
            continue
        end += len(_END[codec])
        for n, m in enumerate(_START[codec].finditer(data, 0, end)):
            if n >= 20:
                break
            start = m.start()
            chunk = data[start:end]
            if codec != "utf-8" and len(chunk) % 2:
                continue
            try:
                text = chunk.decode(codec)
            except UnicodeDecodeError:
                continue
            if not looks_like_xml(text):
                continue
            hit = {"codec": codec, "start": start, "end": end, "text": text}
            if check(text)["ok"]:
                return dict(hit, valid=True)
            if fallback is None:
                fallback = dict(hit, valid=False)
    return fallback


def blob_xml(it):
    """XML in einem Binärfeld: dict wie find_xml plus "offset" (Beginn der Daten im Frame) oder None."""
    if it is None or it.kind != "raw" or not it.payload or it.fid in ("POPM", "APIC"):
        return None
    hdr = _blob_header_len(it)
    hit = find_xml(it.payload[hdr:])
    if hit is None:
        return None
    hit["offset"] = hdr
    hit["editable"] = hit["text"].encode(hit["codec"]) == it.payload[hdr + hit["start"]:hdr + hit["end"]]
    return hit


def replace_blob_xml(it, text: str):
    """Neues Feld mit ersetztem XML-Abschnitt (übrige Bytes unverändert) oder None, wenn kein XML gefunden."""
    hit = blob_xml(it)
    if hit is None or not hit["editable"]:
        return None
    from id3tags import Item
    p, a, b = it.payload, hit["offset"] + hit["start"], hit["offset"] + hit["end"]
    new = p[:a] + text.encode(hit["codec"]) + p[b:]
    return Item(it.fid, it.key, desc=it.desc, lang=it.lang, payload=new)


def xml_of_item(it):
    """XML-Inhalt eines Feldes: (text, bearbeitbar) oder None.
    Textfelder: bearbeitbar. Binärfelder (GEOB/PRIV …) mit XML-Abschnitt: bearbeitbar, wobei nur der
    XML-Teil ersetzt wird."""
    if it is None:
        return None
    if it.kind in ("text", "txxx", "comment", "lyrics"):
        return (it.text, True) if looks_like_xml(it.text) else None
    hit = blob_xml(it)
    if hit is not None:
        return hit["text"], hit["editable"]
    return None


def blob_info(it) -> str:
    """Kurzbeschreibung für den Editor, z. B. „GEOB · UTF-8 · 412 von 1024 Bytes“ ("" bei Textfeldern)."""
    hit = blob_xml(it)
    if hit is None:
        return ""
    data_len = len(it.payload) - hit["offset"]
    codec = {"utf-8": "UTF-8", "utf-16-le": "UTF-16 LE", "utf-16-be": "UTF-16 BE"}[hit["codec"]]
    part = hit["end"] - hit["start"]
    extra = " · weitere Bytes davor/danach bleiben unverändert" if part < data_len else ""
    return f"{it.fid} · {codec} · XML {part} von {data_len} Bytes{extra}"
