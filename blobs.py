"""MarKusSXCH TagStudio – Binärfelder (GEOB, PRIV) ansehen und bearbeiten.

Ein Binärfeld besteht aus einem Kopf (GEOB: Kodierung, MIME-Typ, Dateiname, Beschreibung; PRIV: Besitzer) und
den eigentlichen Daten. Die Daten werden erkannt als
  xml     – XML-Abschnitt (auch mitten in anderen Bytes, UTF-8/UTF-16) → XML-Editor
  text    – lesbarer Text (UTF-8 bzw. UTF-16 mit BOM), Null-Bytes am Ende bleiben erhalten
  base64  – Base64, das Text/JSON/XML enthält (z. B. Mixed In Key) → bearbeitet wird der entschlüsselte Text
  binary  – sonst: nur Hex-Ansicht
Beim Speichern wird nur geändert, was bearbeitet wurde; der Rest bleibt byte-genau.
Nur Standardbibliothek.
"""
from __future__ import annotations

import base64
import binascii
import json
import re

import xmltools

BLOB_FIDS = ("GEOB", "PRIV")
_B64_RE = re.compile(rb"^[A-Za-z0-9+/\r\n]+={0,2}[\r\n]*$")
HEX_LIMIT = 64 * 1024


def is_blob(it) -> bool:
    return it is not None and it.kind == "raw" and it.fid in BLOB_FIDS and it.payload is not None


# --------------------------------------------------------------------------- Kopf
def split(it) -> dict:
    """Kopf und Daten trennen."""
    from id3tags import _decode, _split_term
    p = it.payload
    if it.fid == "GEOB":
        e = p[0] if p else 0
        i = p.find(b"\x00", 1)
        mime = p[1:i].decode("latin-1", "replace") if i > 0 else ""
        fname, rest = _split_term(e, p[i + 1:]) if i > 0 else (b"", b"")
        desc, data = _split_term(e, rest)
        return {"fid": "GEOB", "enc": e, "mime": mime, "filename": _decode(e, fname), "desc": _decode(e, desc),
                "data": data, "hdr": len(p) - len(data)}
    i = p.find(b"\x00")
    owner = p[:i].decode("latin-1", "replace") if i >= 0 else ""
    data = p[i + 1:] if i >= 0 else p
    return {"fid": it.fid, "owner": owner, "data": data, "hdr": len(p) - len(data)}


def _geob_header(enc: int, mime: str, filename: str, desc: str) -> bytes:
    from id3tags import _enc, _term
    if enc not in (0, 1, 2, 3):
        enc = 3
    try:
        fn, ds = _enc(enc, filename), _enc(enc, desc)
    except UnicodeEncodeError:       # Latin-1 reicht nicht → UTF-16 mit BOM
        enc = 1
        fn, ds = _enc(enc, filename), _enc(enc, desc)
    return bytes([enc]) + mime.encode("latin-1", "replace") + b"\x00" + fn + _term(enc) + ds + _term(enc)


# --------------------------------------------------------------------------- Inhalt erkennen
def _text_of(data: bytes):
    """Lesbarer Text? → (text, codec, nul_suffix) oder None."""
    body = data.rstrip(b"\x00")
    tail = data[len(body):]
    if not body:
        return None
    for bom, codec in ((b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be")):
        if body.startswith(bom):
            if len(data) % 2:
                return None
            try:
                t = data[len(bom):].decode(codec).rstrip("\x00")
            except UnicodeDecodeError:
                return None
            return (t, codec, None) if _readable(t) else None
    try:
        t = body.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return (t, "utf-8", tail) if _readable(t) else None


def _readable(t: str) -> bool:
    if not t:
        return False
    bad = sum(1 for c in t if (ord(c) < 32 and c not in "\t\r\n") or c in "�")
    return bad == 0


def _inner(text: str) -> str:
    s = text.strip()
    if xmltools.looks_like_xml(s):
        return "xml"
    if s[:1] in "{[":
        try:
            json.loads(s)
            return "json"
        except ValueError:
            pass
    return "text"


def analyze(data: bytes) -> dict:
    """Art der Daten bestimmen (siehe Modulbeschreibung)."""
    xml = xmltools.find_xml(data)
    if xml is not None and xml["text"].encode(xml["codec"]) == data[xml["start"]:xml["end"]]:
        return {"kind": "xml", "text": xml["text"], "codec": xml["codec"], "start": xml["start"], "end": xml["end"],
                "inner": "xml"}
    tx = _text_of(data)
    if tx is not None:
        text, codec, tail = tx
        body = data.rstrip(b"\x00")
        if codec == "utf-8" and len(body) >= 8 and _B64_RE.match(body) and not body.isdigit():
            clean = re.sub(rb"[\r\n]", b"", body)
            try:
                raw = base64.b64decode(clean + b"=" * (-len(clean) % 4), validate=True)
            except (binascii.Error, ValueError):
                raw = None
            inner = _text_of(raw) if raw else None
            if inner is not None:
                return {"kind": "base64", "text": inner[0], "codec": inner[1], "tail": tail,
                        "pad": body.rstrip(b"\r\n").endswith(b"="), "nl": b"\n" in body,
                        "inner_tail": inner[2] or b"", "inner": _inner(inner[0])}
        return {"kind": "text", "text": text, "codec": codec, "tail": tail or b"", "inner": _inner(text)}
    return {"kind": "binary", "inner": "binary"}


def _hexdump(data: bytes, limit: int = HEX_LIMIT) -> str:
    out = []
    for o in range(0, min(len(data), limit), 16):
        chunk = data[o:o + 16]
        hx = " ".join(f"{b:02x}" for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "·" for b in chunk)
        out.append(f"{o:08x}  {hx:<47}  {asc}")
    if len(data) > limit:
        out.append(f"… ({len(data) - limit} weitere Bytes)")
    return "\n".join(out)


# --------------------------------------------------------------------------- Für die Oberfläche
KIND_LABEL = {"xml": "XML", "text": "Text", "base64": "Base64-kodierter Text", "binary": "Binärdaten"}
INNER_LABEL = {"xml": "XML", "json": "JSON", "text": "Text", "binary": ""}


def view(it) -> dict:
    s = split(it)
    a = analyze(s["data"])
    d = {"fid": s["fid"], "size": len(s["data"]), "kind": a["kind"], "inner": a["inner"],
         "kind_label": KIND_LABEL[a["kind"]] + (f" ({INNER_LABEL[a['inner']]})" if a["kind"] == "base64" else ""),
         "editable": a["kind"] != "binary", "text": a.get("text", ""),
         "codec": {"utf-8": "UTF-8", "utf-16-le": "UTF-16 LE", "utf-16-be": "UTF-16 BE"}.get(a.get("codec"), ""),
         "hex": _hexdump(s["data"]) if a["kind"] == "binary" else ""}
    if a["kind"] == "xml":
        d["note"] = xmltools.blob_info(it)
    if s["fid"] == "GEOB":
        d.update(mime=s["mime"], filename=s["filename"], desc=s["desc"])
    else:
        d["owner"] = s["owner"]
    return d


def update(it, text=None, mime=None, filename=None):
    """Neues Feld mit geändertem Inhalt und/oder Kopf (GEOB: MIME, Dateiname). Unverändertes bleibt byte-genau."""
    from id3tags import Item
    s = split(it)
    data = s["data"]
    if text is not None:
        a = analyze(data)
        if a["kind"] == "binary":
            raise ValueError("Binärdaten können nicht als Text bearbeitet werden.")
        if text != a["text"]:
            if a["kind"] == "xml":
                data = data[:a["start"]] + text.encode(a["codec"]) + data[a["end"]:]
            elif a["kind"] == "text":
                bom = {"utf-16-le": b"\xff\xfe", "utf-16-be": b"\xfe\xff"}.get(a["codec"], b"")
                data = bom + text.encode(a["codec"]) + a["tail"]
            else:   # base64
                inner = text.encode(a["codec"]) + a["inner_tail"]
                if a["codec"] != "utf-8":
                    inner = {"utf-16-le": b"\xff\xfe", "utf-16-be": b"\xfe\xff"}[a["codec"]] + inner
                enc = base64.encodebytes(inner) if a["nl"] else base64.b64encode(inner)
                if not a["pad"]:
                    enc = enc.replace(b"=", b"")
                data = enc + a["tail"]
    head = it.payload[:s["hdr"]]
    if s["fid"] == "GEOB" and (mime is not None or filename is not None):
        m = s["mime"] if mime is None else mime.strip()
        fn = s["filename"] if filename is None else filename
        if (m, fn) != (s["mime"], s["filename"]):
            head = _geob_header(s["enc"], m, fn, s["desc"])
    payload = head + data
    if payload == it.payload:
        return it
    return Item(it.fid, it.key, desc=it.desc, lang=it.lang, payload=payload)


def pretty(text: str, inner: str) -> str:
    """JSON hübsch formatieren (für den Editor)."""
    if inner == "json":
        return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
    return text
