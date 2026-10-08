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


def xml_of_item(it):
    """XML-Inhalt eines Feldes: (text, bearbeitbar) oder None.
    Textfelder: bearbeitbar. Binärfelder (GEOB/PRIV) mit XML-Inhalt: nur ansehen."""
    if it is None:
        return None
    if it.kind in ("text", "txxx", "comment", "lyrics"):
        return (it.text, True) if looks_like_xml(it.text) else None
    if it.kind == "raw" and it.payload and it.fid in ("GEOB", "PRIV"):
        from id3tags import _geob_parts
        p = it.payload
        data = _geob_parts(p)[3] if it.fid == "GEOB" else (p.split(b"\x00", 1)[1] if b"\x00" in p else b"")
        for enc in ("utf-8", "utf-16"):
            try:
                txt = data.decode(enc).strip("\x00").strip()
            except UnicodeDecodeError:
                continue
            if looks_like_xml(txt):
                return txt, False
    return None
