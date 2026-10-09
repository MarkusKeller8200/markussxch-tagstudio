"""
id3tags.py – abhängigkeitsfreie ID3-Bibliothek (nur Python-Standardbibliothek).

* Liest ID3v2.2 / v2.3 / v2.4 (+ ID3v1 als Rückfall) und schreibt v2.3 bzw. v2.4.
* Jeder Frame wird als "Item" mit stabilem Schlüssel dargestellt (z. B. "TIT2",
  "TXXX:Acoustid Id", "COMM:iTunNORM", "APIC:3"), damit zwei Dateien zeilenweise
  verglichen und einzelne Felder hin- und herkopiert werden können.
* Unveränderte Frames werden byte-genau zurückgeschrieben. Audio wird nie verändert.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import struct
import tempfile
import zlib

# =========================================================================== Labels
TEXT_LABELS = {
    "TIT1": "Inhaltliche Gruppierung", "TIT2": "Titel", "TIT3": "Untertitel",
    "TALB": "Album", "TOAL": "Originalalbum", "TRCK": "Spurnummer", "TPOS": "Disknummer",
    "TSST": "Disc-Untertitel", "TSRC": "ISRC", "TPE1": "Künstler", "TPE2": "Album-Künstler",
    "TPE3": "Dirigent", "TPE4": "Remix / Bearbeitung", "TOPE": "Originalkünstler",
    "TEXT": "Texter", "TOLY": "Originaltexter", "TCOM": "Komponist", "TMCL": "Musiker",
    "TIPL": "Beteiligte Personen", "TENC": "Kodiert von", "TBPM": "Beats pro Minute",
    "TLEN": "Länge", "TKEY": "Tonart", "TLAN": "Sprache", "TCON": "Genre",
    "TFLT": "Dateityp", "TMED": "Medientyp", "TMOO": "Stimmung", "TCOP": "Copyright",
    "TPRO": "Produktionshinweis", "TPUB": "Herausgeber", "TOWN": "Eigentümer",
    "TRSN": "Internetradio-Name", "TRSO": "Internetradio-Eigentümer",
    "TOFN": "Originaldateiname", "TDLY": "Verzögerung", "TDEN": "Kodierungsdatum",
    "TDOR": "Originalveröffentlichungsdatum", "TDRC": "Aufnahmedatum",
    "TDRL": "Veröffentlichungsdatum", "TDTG": "Tagging-Datum",
    "TSSE": "Kodierung Einstellungen", "TSOA": "Album einsortieren als",
    "TSOP": "Künstler einsortieren als", "TSOT": "Titel einsortieren als",
    "TSO2": "Album-Künstler einsortieren als", "TSOC": "Komponist einsortieren als",
    "TCMP": "Zusammenstellung", "GRP1": "Gruppierung", "MVNM": "Satzname",
    "MVIN": "Satznummer", "TCAT": "Podcast-Kategorie", "TDES": "Podcast-Beschreibung",
    "TGID": "Podcast-ID", "TKWD": "Podcast-Schlüsselwörter", "TIME": "Uhrzeit",
    "TRDA": "Aufnahmedaten", "TSIZ": "Größe",
    "WCOM": "Kauf-Internetseite", "WCOP": "Copyright-Internetseite",
    "WOAF": "Audiodatei Internetseite", "WOAR": "Künstler Internetseiten",
    "WOAS": "Audioquelle Internetseite", "WORS": "Internetradio Internetseite",
    "WPAY": "Bezahlung Internetseite", "WPUB": "Herausgeber Internetseite",
    "WFED": "Podcast-Feed",
}
PIC_TYPES = [
    "Anderes", "Datei-Icon", "Anderes Icon", "Cover vorne", "Cover hinten", "Booklet",
    "Medium", "Solist", "Künstler", "Dirigent", "Band", "Komponist", "Texter",
    "Aufnahmeort", "Während der Aufnahme", "Während der Aufführung", "Video-Standbild",
    "Fisch", "Illustration", "Band-Logo", "Verlags-Logo",
]
RAW_LABELS = {
    "POPM": "Bewertung", "PRIV": "Privat", "UFID": "Eindeutige Datei-ID", "GEOB": "Eingebettete Daten",
    "MCDI": "CD-Inhaltsverzeichnis", "PCNT": "Wiedergabezähler", "SYLT": "Synchronisierter Liedtext",
    "RVA2": "Lautstärke-Anpassung", "RVAD": "Lautstärke-Anpassung", "EQU2": "Equalizer",
    "USER": "Nutzungsbedingungen", "OWNE": "Besitzer", "COMR": "Kommerziell", "ETCO": "Ereignis-Timing",
    "CHAP": "Kapitel", "CTOC": "Inhaltsverzeichnis", "SEEK": "Suchmarke", "ASPI": "Audio-Suchindex",
    "LINK": "Verknüpfung", "AENC": "Audio-Verschlüsselung", "ENCR": "Verschlüsselung",
    "GRID": "Gruppen-ID", "SIGN": "Signatur", "RBUF": "Puffergröße", "MLLT": "MPEG-Lookup",
    "SYTC": "Tempo-Code", "POSS": "Position", "PCST": "Podcast",
}

# Reihenfolge der Anzeige (angelehnt an Beyond Compare); Rest folgt alphabetisch
ORDER = [
    "TIT2", "TPE1", "TALB", "TCON", "TRCK", "TDRC", "TPE2", "TSO2", "TSOA", "TSOP", "TSOT",
    "TCOM", "TEXT", "TPE3", "TPE4", "WOAR", "WOAF", "TBPM", "TKEY", "COMM:", "TCMP", "TIT1",
    "GRP1", "TPOS", "TENC", "TSSE", "TFLT", "TSRC", "TLAN", "TLEN", "TDOR", "TDRL",
    "WPAY", "WCOM", "TPUB", "WPUB", "TCOP", "POPM:", "TIT3", "TMOO", "TDTG", "USLT:",
    "APIC:", "TXXX:", "WXXX:",
]

STANDARD_KEYS = ["TIT2", "TPE1", "TALB", "TPE2", "TDRC", "TRCK", "TPOS", "TCON", "TCOM", "COMM:", "APIC:3"]

# Mehrfachwerte: intern wie ID3v2.4 null-getrennt; Anzeige mit sichtbarem Trenner
MV = "\x00"
MV_SHOW = " ¦ "
V23_JOIN = " / "  # ID3v2.3 kennt keine Null-Trennung → beim Schreiben in v2.3 so verbinden

# Felder, die die Standards vorsehen (für "leere Felder einblenden")
_URLS = ["WCOM", "WCOP", "WOAF", "WOAR", "WOAS", "WORS", "WPAY", "WPUB"]
FIELDSETS = {
    "v1": ["TIT2", "TPE1", "TALB", "TDRC", "COMM:", "TRCK", "TCON"],
    "v23": ["TALB", "TBPM", "TCOM", "TCON", "TCOP", "TDLY", "TENC", "TEXT", "TFLT", "TIME", "TIT1",
            "TIT2", "TIT3", "TKEY", "TLAN", "TLEN", "TMED", "TOAL", "TOFN", "TOLY", "TOPE", "TDOR",
            "TOWN", "TPE1", "TPE2", "TPE3", "TPE4", "TPOS", "TPUB", "TRCK", "TRDA", "TRSN", "TRSO",
            "TSIZ", "TSRC", "TSSE", "TDRC"] + _URLS + ["WXXX:", "COMM:", "USLT:", "APIC:3"],
    "v24": ["TALB", "TBPM", "TCOM", "TCON", "TCOP", "TDEN", "TDLY", "TDOR", "TDRC", "TDRL", "TDTG",
            "TENC", "TEXT", "TFLT", "TIPL", "TIT1", "TIT2", "TIT3", "TKEY", "TLAN", "TLEN", "TMCL",
            "TMED", "TMOO", "TOAL", "TOFN", "TOLY", "TOPE", "TOWN", "TPE1", "TPE2", "TPE3", "TPE4",
            "TPOS", "TPRO", "TPUB", "TRCK", "TRSN", "TRSO", "TSOA", "TSOP", "TSOT", "TSRC", "TSSE",
            "TSST"] + _URLS + ["WXXX:", "COMM:", "USLT:", "APIC:3"],
}
FIELDSETS["all"] = sorted(set(FIELDSETS["v1"]) | set(FIELDSETS["v23"]) | set(FIELDSETS["v24"]))

GENRES = [
    "Blues", "Classic Rock", "Country", "Dance", "Disco", "Funk", "Grunge", "Hip-Hop", "Jazz",
    "Metal", "New Age", "Oldies", "Other", "Pop", "R&B", "Rap", "Reggae", "Rock", "Techno",
    "Industrial", "Alternative", "Ska", "Death Metal", "Pranks", "Soundtrack", "Euro-Techno",
    "Ambient", "Trip-Hop", "Vocal", "Jazz+Funk", "Fusion", "Trance", "Classical", "Instrumental",
    "Acid", "House", "Game", "Sound Clip", "Gospel", "Noise", "AlternRock", "Bass", "Soul",
    "Punk", "Space", "Meditative", "Instrumental Pop", "Instrumental Rock", "Ethnic", "Gothic",
    "Darkwave", "Techno-Industrial", "Electronic", "Pop-Folk", "Eurodance", "Dream",
    "Southern Rock", "Comedy", "Cult", "Gangsta", "Top 40", "Christian Rap", "Pop/Funk",
    "Jungle", "Native American", "Cabaret", "New Wave", "Psychadelic", "Rave", "Showtunes",
    "Trailer", "Lo-Fi", "Tribal", "Acid Punk", "Acid Jazz", "Polka", "Retro", "Musical",
    "Rock & Roll", "Hard Rock",
]


def key_label(key: str) -> str:
    """Deutscher Anzeigename eines Schlüssels."""
    base = key.split("#")[0]
    fid, _, desc = base.partition(":")
    if fid == "TXXX":
        return f"Benutzertext ({desc})"
    if fid == "WXXX":
        return f"Benutzer-URL ({desc})" if desc else "Benutzer-URL"
    if fid == "COMM":
        return f"Kommentar ({desc})" if desc else "Kommentar"
    if fid == "USLT":
        return f"Liedtext ({desc})" if desc else "Liedtext"
    if fid == "APIC":
        try:
            n = int(desc)
            name = PIC_TYPES[n] if n < len(PIC_TYPES) else f"Typ {n}"
        except ValueError:
            name = desc
        lbl = f"Bild ({name})"
    elif fid in TEXT_LABELS:
        lbl = TEXT_LABELS[fid]
    elif fid in RAW_LABELS:
        lbl = RAW_LABELS[fid] + (f" ({desc})" if desc else "")
    else:
        lbl = fid + (f" ({desc})" if desc else "")
    if "#" in key:
        lbl += " " + key.split("#")[1]
    return lbl


def sort_key(key: str):
    fid = key.split(":")[0].split("#")[0]
    for i, k in enumerate(ORDER):
        if k.endswith(":"):
            if key.startswith(k):
                return (i, key.lower())
        elif k == fid:
            return (i, key.lower())
    return (len(ORDER), key_label(key).lower())


class ID3Error(Exception):
    pass


# =========================================================================== Byte-Helfer
def _syncsafe(b: bytes) -> int:
    return (b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3]


def _to_syncsafe(n: int) -> bytes:
    return bytes([(n >> 21) & 0x7F, (n >> 14) & 0x7F, (n >> 7) & 0x7F, n & 0x7F])


def _deunsync(b: bytes) -> bytes:
    return b.replace(b"\xff\x00", b"\xff")


def _valid_id(fid: bytes) -> bool:
    return len(fid) > 0 and all((48 <= c <= 57) or (65 <= c <= 90) for c in fid)


def _decode(enc: int, b: bytes) -> str:
    if enc == 0:
        s = b.decode("latin-1")
    elif enc in (1, 2):
        if len(b) % 2:
            b = b[:-1]
        if enc == 1 and b[:2] in (b"\xff\xfe", b"\xfe\xff"):
            s = b.decode("utf-16", "replace")
        elif enc == 1:
            s = b.decode("utf-16-le", "replace")
        else:
            s = b.decode("utf-16-be", "replace")
    else:
        s = b.decode("utf-8", "replace")
    # manche Tagger setzen vor jeden Einzelwert ein BOM – auch in Latin-1/UTF-8 – unsichtbar, also entfernen
    return s.replace("\ufeff", "").replace("\ufffe", "")


def _split_term(enc: int, b: bytes):
    if enc in (1, 2):
        i = 0
        while i + 1 < len(b):
            if b[i] == 0 and b[i + 1] == 0:
                return b[:i], b[i + 2:]
            i += 2
        return b, b""
    i = b.find(b"\x00")
    return (b, b"") if i < 0 else (b[:i], b[i + 1:])


def _pick_enc(version: int, *strings: str) -> int:
    if version == 4:
        return 3
    try:
        for s in strings:
            s.encode("latin-1")
        return 0
    except UnicodeEncodeError:
        return 1


def _enc(enc: int, s: str) -> bytes:
    if enc == 0:
        return s.encode("latin-1")
    if enc == 1:
        return s.encode("utf-16")
    if enc == 2:
        return s.encode("utf-16-be")
    return s.encode("utf-8")


def _term(enc: int) -> bytes:
    return b"\x00\x00" if enc in (1, 2) else b"\x00"


def _frame_bytes(fid: str, payload: bytes, version: int, flags: int = 0) -> bytes:
    size = _to_syncsafe(len(payload)) if version == 4 else struct.pack(">I", len(payload))
    return fid.encode("ascii") + size + struct.pack(">H", flags) + payload


def genre_from_raw(s: str) -> str:
    s = s.strip()
    if s.startswith("(") and ")" in s:
        num, rest = s[1:s.index(")")], s[s.index(")") + 1:]
        if rest:
            return rest
        s = num
    if s.isdigit() and int(s) < len(GENRES):
        return GENRES[int(s)]
    return s


def fmt_bytes(n: int) -> str:
    return f"{n:,}".replace(",", "'")


def _geob_parts(p: bytes):
    """GEOB: enc, MIME\\0, Dateiname\\0, Beschreibung\\0, Daten → (mime, dateiname, beschreibung, daten)."""
    try:
        e = p[0]
        i = p.find(b"\x00", 1)
        mime = p[1:i].decode("latin-1", "replace")
        fname, rest = _split_term(e, p[i + 1:])
        desc, data = _split_term(e, rest)
        return mime, _decode(e, fname), _decode(e, desc), data
    except (IndexError, ValueError):
        return "", "", "", p


# =========================================================================== Cover
class Cover:
    def __init__(self, data: bytes, mime: str = "", ptype: int = 3, desc: str = ""):
        self.data = data
        self.mime = mime if mime and "/" in mime else self.guess_mime(data)
        self.ptype = ptype
        self.desc = desc

    @staticmethod
    def guess_mime(data: bytes) -> str:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        if data[:6] in (b"GIF87a", b"GIF89a"):
            return "image/gif"
        return "image/jpeg"

    @property
    def ext(self) -> str:
        return {"image/png": ".png", "image/gif": ".gif"}.get(self.mime.lower(), ".jpg")

    def dimensions(self):
        d = self.data
        try:
            if d[:8] == b"\x89PNG\r\n\x1a\n":
                return struct.unpack(">II", d[16:24])
            if d[:6] in (b"GIF87a", b"GIF89a"):
                return struct.unpack("<HH", d[6:10])
            if d[:2] == b"\xff\xd8":
                i = 2
                while i + 9 < len(d):
                    if d[i] != 0xFF:
                        i += 1
                        continue
                    m = d[i + 1]
                    if m == 0xFF:
                        i += 1
                        continue
                    if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
                        i += 2
                        continue
                    seglen = struct.unpack(">H", d[i + 2:i + 4])[0]
                    if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
                        h, w = struct.unpack(">HH", d[i + 5:i + 9])
                        return w, h
                    i += 2 + seglen
        except struct.error:
            pass
        return None

    def describe(self) -> str:
        fmt = self.mime.split("/")[-1].upper().replace("JPG", "JPEG")
        dims = self.dimensions()
        s = fmt + (f" {dims[0]}×{dims[1]}" if dims else "")
        return f"{s} · {len(self.data) / 1024:.0f} KB" + (f" · {self.desc}" if self.desc else "")

    def __eq__(self, other):
        return isinstance(other, Cover) and self.data == other.data and self.ptype == other.ptype

    def __hash__(self):
        return hash(hashlib.md5(self.data).hexdigest())


# =========================================================================== Item
EDITABLE_KINDS = ("text", "url", "txxx", "wxxx", "comment", "lyrics")


def _kind_of(fid: str) -> str:
    if fid == "TXXX":
        return "txxx"
    if fid == "WXXX":
        return "wxxx"
    if fid == "COMM":
        return "comment"
    if fid == "USLT":
        return "lyrics"
    if fid == "APIC":
        return "picture"
    if fid[0] == "T" or fid in ("GRP1", "MVNM", "MVIN"):
        return "text"
    if fid[0] == "W":
        return "url"
    return "raw"


class Item:
    """Ein Feld (ein oder mehrere Frames mit gleichem Schlüssel)."""

    def __init__(self, fid: str, key: str, text: str = "", desc: str = "", lang: str = "eng",
                 cover: Cover | None = None, payload: bytes | None = None):
        self.fid = fid
        self.key = key
        self.kind = _kind_of(fid)
        self.text = text
        self.desc = desc
        self.lang = lang
        self.cover = cover
        self.payload = payload
        self.orig: list[bytes] | None = None  # Original-Framebytes (byte-genau)
        self.orig_ver = 0

    # ------------------------------------------------------------------ Erzeugen
    @classmethod
    def new_text(cls, key: str, text: str, lang: str = "eng") -> "Item":
        fid, _, desc = key.split("#")[0].partition(":")
        return cls(fid, key, text=text, desc=desc, lang=lang)

    @classmethod
    def new_cover(cls, cover: Cover) -> "Item":
        return cls("APIC", f"APIC:{cover.ptype}", cover=cover)

    def clone(self) -> "Item":
        it = Item(self.fid, self.key, self.text, self.desc, self.lang, self.cover, self.payload)
        it.orig, it.orig_ver = self.orig, self.orig_ver
        return it

    def with_text(self, text: str) -> "Item":
        it = Item(self.fid, self.key, text, self.desc, self.lang, None, None)
        return it

    # ------------------------------------------------------------------ Eigenschaften
    @property
    def editable(self) -> bool:
        return self.kind in EDITABLE_KINDS

    @property
    def label(self) -> str:
        return key_label(self.key)

    def display(self) -> str:
        if self.kind == "picture":
            return self.cover.describe() if self.cover else ""
        if self.kind == "raw":
            p = self.payload
            if p is None:
                return "(verschlüsselt/komprimiert – nicht lesbar)"
            if self.fid == "POPM":
                rest = p.split(b"\x00", 1)[1] if b"\x00" in p else b""
                if rest:
                    r = rest[0]
                    stars = 0 if r == 0 else 1 if r < 64 else 2 if r < 128 else 3 if r < 196 else 4 if r < 255 else 5
                    return "★" * stars + "☆" * (5 - stars) + f"  ({r})"
                return "–"
            if self.fid == "GEOB":
                mime, fname, desc, data = _geob_parts(p)
                if mime.endswith("json") and data:
                    try:
                        txt = data.decode("utf-8").strip()
                        if txt[:1] not in "{[":  # Mixed In Key: Base64-kodiertes JSON
                            import base64
                            txt = base64.b64decode(txt + "=" * (-len(txt) % 4)).decode("utf-8").strip()
                        if txt.isprintable():
                            return txt[:300]
                    except (UnicodeDecodeError, ValueError):
                        pass
                return f"{mime or 'binär'} · {fmt_bytes(len(data))} Bytes · {hashlib.md5(data).hexdigest()[:8]}"
            if self.fid in ("PRIV", "UFID"):
                data = p.split(b"\x00", 1)[1] if b"\x00" in p else p
                if data and all(32 <= c < 127 for c in data[:200]):
                    return data.decode("ascii")[:300]
                return f"{fmt_bytes(len(data))} Bytes · {hashlib.md5(data).hexdigest()[:8]}"
            return f"{fmt_bytes(len(p))} Bytes · {hashlib.md5(p).hexdigest()[:8]}"
        if self.fid in ("TIPL", "TMCL") and MV in self.text:
            parts = self.text.split(MV)
            if len(parts) % 2 == 0:  # Paare Rolle/Name
                return "; ".join(f"{parts[i]}: {parts[i + 1]}" for i in range(0, len(parts), 2))
        return self.text.replace(MV, MV_SHOW)

    @property
    def values(self) -> list[str]:
        """Einzelwerte eines Mehrfachfeldes (ID3v2.4: null-getrennt)."""
        return [v for v in self.text.split(MV)] if self.kind != "picture" else []

    def compare_value(self):
        if self.kind == "picture":
            return ("pic", self.cover.data if self.cover else b"")
        if self.kind == "raw":
            return ("raw", self.payload if self.payload is not None else b"".join(self.orig or []))
        return ("txt", self.text.strip())

    def __eq__(self, other):
        return isinstance(other, Item) and self.key == other.key and self.compare_value() == other.compare_value()

    def __hash__(self):
        return hash(self.key)

    # ------------------------------------------------------------------ Schreiben
    def frame_ids(self, ver: int) -> list[str]:
        """Original-Frame-IDs (bzw. die IDs, die beim Speichern geschrieben würden)."""
        ids = []
        for b in self.to_frames(ver):
            fid = b[:4].decode("ascii", "replace")
            if fid not in ids:
                ids.append(fid)
        return ids or [self.fid]

    def details(self) -> list[tuple[str, str]]:
        """Zusatzinfos für den Tooltip."""
        out = []
        if self.kind in ("txxx", "wxxx", "comment", "lyrics"):
            out.append(("Beschreibung", self.desc or "(leer)"))
        if self.kind in ("comment", "lyrics"):
            out.append(("Sprache", self.lang))
        if self.kind == "picture" and self.cover:
            t = self.cover.ptype
            out.append(("Bildtyp", f"{t} – {PIC_TYPES[t] if t < len(PIC_TYPES) else '?'}"))
            out.append(("MIME", self.cover.mime))
        if self.kind == "raw" and self.fid == "GEOB" and self.payload:
            mime, fname, desc, data = _geob_parts(self.payload)
            out.append(("Beschreibung", desc or "(leer)"))
            out.append(("MIME", mime or "–"))
            if fname:
                out.append(("Dateiname", fname))
            out.append(("Größe", f"{fmt_bytes(len(data))} Bytes"))
            if desc.lower().startswith("serato"):
                out.append(("", "Serato-DJ-Daten (Cue-Punkte/Beatgrid) – gehören zu genau diesem Track"))
        elif self.kind == "raw" and self.desc:
            out.append(("Eigentümer", self.desc))
        return out

    def to_frames(self, ver: int) -> list[bytes]:
        if self.orig is not None and self.orig_ver == ver:
            return list(self.orig)
        k, fid = self.kind, self.fid
        out = []
        if k == "text":
            text = self.text.strip()
            if not text:
                return []
            if ver == 4 and fid in ("TYER", "TDAT", "TIME", "TRDA", "TSIZ", "TORY"):
                return []
            if ver == 3 and fid == "TDRC":
                year = text[:4]
                e = _pick_enc(3, year)
                out.append(_frame_bytes("TYER", bytes([e]) + _enc(e, year), 3))
                m = re.match(r"^\d{4}-(\d{2})-(\d{2})", text)
                if m:
                    out.append(_frame_bytes("TDAT", b"\x00" + (m.group(2) + m.group(1)).encode(), 3))
                return out
            if ver == 3 and fid == "TDOR":
                return [_frame_bytes("TORY", b"\x00" + text[:4].encode("latin-1", "replace"), 3)]
            if ver != 4 and MV in text:  # v2.3 kennt keine Null-Trennung
                text = V23_JOIN.join(x.strip() for x in text.split(MV) if x.strip())
            e = _pick_enc(ver, text)
            return [_frame_bytes(fid, bytes([e]) + _enc(e, text), ver)]
        if k == "url":
            for part in [p.strip() for p in self.text.split(" | ") if p.strip()]:
                out.append(_frame_bytes(fid, part.encode("latin-1", "replace"), ver))
            return out
        if k == "txxx":
            if not self.text.strip():
                return []
            val = self.text.strip()
            if ver != 4 and MV in val:
                val = V23_JOIN.join(x.strip() for x in val.split(MV) if x.strip())
            e = _pick_enc(ver, self.desc, val)
            return [_frame_bytes(fid, bytes([e]) + _enc(e, self.desc) + _term(e) + _enc(e, val), ver)]
        if k == "wxxx":
            if not self.text.strip():
                return []
            e = _pick_enc(ver, self.desc)
            return [_frame_bytes(fid, bytes([e]) + _enc(e, self.desc) + _term(e)
                                 + self.text.strip().encode("latin-1", "replace"), ver)]
        if k in ("comment", "lyrics"):
            if not self.text.strip():
                return []
            e = _pick_enc(ver, self.desc, self.text)
            lang = (self.lang or "eng").encode("latin-1", "replace")[:3].ljust(3, b" ")
            return [_frame_bytes(fid, bytes([e]) + lang + _enc(e, self.desc) + _term(e) + _enc(e, self.text), ver)]
        if k == "picture":
            c = self.cover
            if c is None:
                return []
            e = _pick_enc(ver, c.desc)
            payload = (bytes([e]) + c.mime.encode("latin-1") + b"\x00" + bytes([c.ptype])
                       + _enc(e, c.desc) + _term(e) + c.data)
            return [_frame_bytes("APIC", payload, ver)]
        # raw
        if self.payload is None:
            return []
        return [_frame_bytes(fid, self.payload, ver)]


# =========================================================================== Frame-Parsing
class _Frame:
    __slots__ = ("id", "flags", "data")

    def __init__(self, fid, flags, data):
        self.id, self.flags, self.data = fid, flags, data

    def raw(self, ver):
        return _frame_bytes(self.id, self.data, ver, self.flags)


def _frame_payload(fr: _Frame, version: int):
    data, f = fr.data, fr.flags
    if version == 3:
        if f & 0x0040:
            return None
        if f & 0x0080:
            try:
                data = zlib.decompress(data[4:])
            except zlib.error:
                return None
        if f & 0x0020:
            data = data[1:]
        return data
    if version == 4:
        if f & 0x0004:
            return None
        if f & 0x0040:
            data = data[1:]
        if f & 0x0001:
            data = data[4:]
        if f & 0x0002:
            data = _deunsync(data)
        if f & 0x0008:
            try:
                data = zlib.decompress(data)
            except zlib.error:
                return None
        return data
    return data


V22_TO_V23 = {
    "TT1": "TIT1", "TT2": "TIT2", "TT3": "TIT3", "TP1": "TPE1", "TP2": "TPE2", "TP3": "TPE3",
    "TP4": "TPE4", "TAL": "TALB", "TYE": "TYER", "TRK": "TRCK", "TPA": "TPOS", "TCO": "TCON",
    "TCM": "TCOM", "TXT": "TEXT", "TBP": "TBPM", "TEN": "TENC", "TSS": "TSSE", "TLE": "TLEN",
    "TKE": "TKEY", "TLA": "TLAN", "TPB": "TPUB", "TCR": "TCOP", "TRC": "TSRC", "TOR": "TORY",
    "TDA": "TDAT", "TXX": "TXXX", "WXX": "WXXX", "WAR": "WOAR", "WAF": "WOAF", "WPB": "WPUB",
    "COM": "COMM", "ULT": "USLT", "PIC": "APIC", "POP": "POPM", "UFI": "UFID", "TCP": "TCMP",
    "TS2": "TSO2", "TSA": "TSOA", "TSP": "TSOP", "TST": "TSOT", "TSC": "TSOC",
}

# MPEG-Tabellen
_BITRATES = {
    (1, 3): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
    (2, 3): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
}
_SRATES = {1: [44100, 48000, 32000], 2: [22050, 24000, 16000], 25: [11025, 12000, 8000]}


# =========================================================================== MP3File
def disk_sig(path: str) -> str:
    """Fingerabdruck der Tag-Bytes einer Datei (ID3v2-Bereich und ID3v1) – ohne Audio."""
    import hashlib
    h = hashlib.sha1()
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(10)
        tag_len = 0
        if len(head) == 10 and head[:3] == b"ID3" and head[3] in (2, 3, 4):
            tag_len = 10 + _syncsafe(head[6:10])
            f.seek(0)
            h.update(f.read(tag_len))
        if size - tag_len >= 128:
            f.seek(-128, os.SEEK_END)
            t = f.read(128)
            if t[:3] == b"TAG":
                h.update(t)
    h.update(str(size).encode())
    return h.hexdigest()


class MP3File:
    def __init__(self, path: str):
        self.path = path
        self.load()

    # ------------------------------------------------------------------ Laden
    MPEG_ATTRS = ("bitrate", "samplerate", "duration", "channels", "vbr")

    def load(self, cached: dict | None = None, keep_raw: bool = False):
        """Datei einlesen. `cached` (#70, Listen-Cache): {"head", "body", "v1", "mpeg", "size", "mtime"} – dann wird
        die Datei selbst nicht geöffnet (Tag-Bytes und MPEG-Angaben stammen aus dem Cache)."""
        import hashlib
        self.items: dict[str, Item] = {}
        self.version = 3
        self.tag_desc = "kein Tag"
        self.had_v2 = self.had_v1 = False
        self.audio_start = 0
        self.tag_space = 0
        self.has_footer = False
        self.v1_genre = 255
        if cached is not None:
            head, body, v1, mpeg_head = cached["head"], cached["body"], cached["v1"], None
            self.size, self.mtime = cached["size"], cached["mtime"]
        else:
            st = os.stat(self.path)
            self.size, self.mtime = st.st_size, st.st_mtime
            body, v1 = b"", b""
            with open(self.path, "rb") as f:
                head = f.read(10)
                if len(head) == 10 and head[:3] == b"ID3" and head[3] in (2, 3, 4):
                    body = f.read(_syncsafe(head[6:10]))
                    audio_start = 10 + len(body) + (10 if head[3] == 4 and head[5] & 0x10 else 0)
                else:
                    audio_start = 0
                f.seek(audio_start)
                mpeg_head = f.read(65536)
                if self.size >= 128:
                    f.seek(-128, os.SEEK_END)
                    v1 = f.read(128)
        sig = hashlib.sha1()
        tag_len = 0
        if len(head) == 10 and head[:3] == b"ID3" and head[3] in (2, 3, 4):
            ver, flags = head[3], head[5]
            size = _syncsafe(head[6:10])
            self.had_v2 = True
            self.has_footer = ver == 4 and bool(flags & 0x10)
            self.audio_start = 10 + size + (10 if self.has_footer else 0)
            self.tag_space = 0 if self.has_footer else size
            self.tag_desc = f"ID3v2.{ver}"
            tag_len = 10 + size
            sig.update(head + body)
            self._parse_v2(ver, flags, body)
        if v1[:3] == b"TAG" and len(v1) == 128:
            if self.size - tag_len >= 128:
                sig.update(v1)
            self.had_v1 = True
            self.v1_genre = v1[127]
            if not self.had_v2:
                self.tag_desc = "ID3v1"
                self._parse_v1(v1)
        else:
            v1 = b""
        if cached is not None:
            for k in self.MPEG_ATTRS:
                setattr(self, k, cached["mpeg"].get(k, 0 if k != "channels" else ""))
        else:
            self._parse_mpeg(mpeg_head)
        sig.update(str(self.size).encode())
        self.disk_sig = sig.hexdigest()          # wie disk_sig(path), ohne die Datei ein zweites Mal zu lesen
        if keep_raw:
            self._raw = (head, body, v1)         # für den Listen-Cache (#70) – der Aufrufer nimmt es gleich wieder weg
        self._snapshot()

    def mpeg_state(self) -> dict:
        return {k: getattr(self, k, 0) for k in self.MPEG_ATTRS}

    def external_change(self) -> bool:
        """Hat ein anderes Programm die Tags geändert, seit diese Datei eingelesen wurde? (#55)
        Vergleicht die Tag-Bytes (ID3v2 + ID3v1) – erkennt auch Programme, die die Änderungszeit erhalten."""
        try:
            return disk_sig(self.path) != getattr(self, "disk_sig", None)
        except OSError:
            return True

    def _parse_v2(self, ver, flags, body):
        if ver in (2, 3) and flags & 0x80:
            body = _deunsync(body)
        if ver == 2 and flags & 0x40:
            return
        pos = 0
        if ver == 3 and flags & 0x40 and len(body) >= 4:
            pos = 4 + struct.unpack(">I", body[:4])[0]
        elif ver == 4 and flags & 0x40 and len(body) >= 4:
            pos = _syncsafe(body[:4])
        end, frames = len(body), []
        while pos < end:
            hdr = 6 if ver == 2 else 10
            if pos + hdr > end:
                break
            fid = body[pos:pos + (3 if ver == 2 else 4)]
            if not _valid_id(fid):
                break
            if ver == 2:
                fsize, fflags = int.from_bytes(body[pos + 3:pos + 6], "big"), 0
            else:
                fsize = self._v4_size(body, pos, end) if ver == 4 else struct.unpack(">I", body[pos + 4:pos + 8])[0]
                fflags = struct.unpack(">H", body[pos + 8:pos + 10])[0]
            frames.append(_Frame(fid.decode("ascii"), fflags, body[pos + hdr:pos + hdr + fsize]))
            pos += hdr + fsize

        if ver == 2:
            conv = []
            for fr in frames:
                nid = V22_TO_V23.get(fr.id)
                if not nid:
                    continue
                data = fr.data
                if nid == "APIC" and len(data) >= 5:
                    fmt = data[1:4].decode("latin-1").upper()
                    mime = {"PNG": "image/png", "GIF": "image/gif"}.get(fmt, "image/jpeg")
                    data = data[:1] + mime.encode() + b"\x00" + data[4:]
                conv.append(_Frame(nid, 0, data))
            frames, self.version, src_ver = conv, 3, 2
        else:
            self.version = src_ver = ver
        self._frames_to_items(frames, src_ver)

    @staticmethod
    def _v4_size(body, pos, end):
        raw = body[pos + 4:pos + 8]
        ss, plain = _syncsafe(raw), struct.unpack(">I", raw)[0]
        if ss == plain:
            return ss

        def ok(n):
            nxt = pos + 10 + n
            if nxt == end:
                return True
            if nxt > end:
                return False
            if nxt + 4 > end:
                return body[nxt:end].strip(b"\x00") == b""
            fid = body[nxt:nxt + 4]
            return fid == b"\x00\x00\x00\x00" or _valid_id(fid)

        if any(c & 0x80 for c in raw):
            return plain
        if ok(ss):
            return ss
        return plain if ok(plain) else ss

    def _add(self, item: Item, raw: bytes, ver: int, mergeable: bool):
        key = item.key
        if key in self.items:
            ex = self.items[key]
            if mergeable and ex.kind == item.kind:
                sep = " | " if item.kind == "url" else MV
                if item.text and item.text not in ex.text.split(sep):
                    ex.text = ex.text + sep + item.text if ex.text else item.text
                ex.orig.append(raw)
                return
            n = 2
            while f"{key}#{n}" in self.items:
                n += 1
            item.key = f"{key}#{n}"
        item.orig, item.orig_ver = [raw], ver
        self.items[item.key] = item

    def _frames_to_items(self, frames, src_ver):
        ver = self.version  # Zielversion für die Rohbytes (2.2 → 2.3 wird neu erzeugt)
        tdat = None
        for fr in frames:
            raw = fr.raw(ver) if src_ver != 2 else None
            p = _frame_payload(fr, ver)
            fid = fr.id
            kind = _kind_of(fid)
            if p is None:
                it = Item(fid, fid, payload=None)
                it.kind = "raw"
                self._add(it, raw or b"", ver, False)
                continue
            try:
                if kind == "text":
                    if not p:
                        continue
                    parts = [x for x in _decode(p[0], p[1:]).split("\x00") if x.strip()]
                    if fid == "TCON":
                        parts = [genre_from_raw(x) for x in parts]
                    text = MV.join(p.strip() for p in parts)
                    if fid == "TDAT":
                        tdat = (text, raw)
                        continue
                    key = {"TYER": "TDRC", "TORY": "TDOR"}.get(fid, fid)
                    if key in self.items and fid in ("TYER", "TORY"):
                        continue  # TDRC/TDOR hat Vorrang
                    it = Item(key, key, text=text)
                    self._add(it, raw, ver, True)
                elif kind == "url":
                    it = Item(fid, fid, text=p.split(b"\x00")[0].decode("latin-1").strip())
                    self._add(it, raw, ver, True)
                elif kind in ("txxx", "wxxx"):
                    e = p[0]
                    d, v = _split_term(e, p[1:])
                    desc = _decode(e, d)
                    if kind == "txxx":
                        val = MV.join(x.strip() for x in _decode(e, v).split("\x00") if x.strip())
                    else:
                        val = v.split(b"\x00")[0].decode("latin-1").strip()
                    it = Item(fid, f"{fid}:{desc}", text=val, desc=desc)
                    self._add(it, raw, ver, False)
                elif kind in ("comment", "lyrics"):
                    e, lang = p[0], p[1:4].decode("latin-1", "replace")
                    d, v = _split_term(e, p[4:])
                    desc = _decode(e, d)
                    it = Item(fid, f"{fid}:{desc}", text=_decode(e, v).rstrip("\x00"), desc=desc, lang=lang)
                    self._add(it, raw, ver, False)
                elif kind == "picture":
                    cov = self._parse_apic(p)
                    if cov is None:
                        continue
                    it = Item("APIC", f"APIC:{cov.ptype}", cover=cov)
                    self._add(it, raw, ver, False)
                else:
                    desc = ""
                    if fid in ("PRIV", "UFID", "POPM") and b"\x00" in p:
                        desc = p.split(b"\x00")[0].decode("latin-1", "replace")
                    elif fid == "GEOB" and len(p) > 2:
                        desc = _geob_parts(p)[2]
                    it = Item(fid, f"{fid}:{desc}" if desc else fid, desc=desc, payload=p)
                    self._add(it, raw, ver, False)
            except (IndexError, ValueError, UnicodeError):
                it = Item(fid, fid, payload=p)
                it.kind = "raw"
                self._add(it, raw or b"", ver, False)

        if tdat:
            text, raw = tdat
            yr = self.items.get("TDRC")
            if yr and len(text) == 4 and text.isdigit() and re.fullmatch(r"\d{4}", yr.text or ""):
                yr.text = f"{yr.text}-{text[2:]}-{text[:2]}"
                if yr.orig is not None and raw is not None:
                    yr.orig.append(raw)
        if src_ver == 2:
            for it in self.items.values():
                it.orig = None

    @staticmethod
    def _parse_apic(p):
        e = p[0]
        i = p.find(b"\x00", 1)
        if i < 0 or i + 1 >= len(p):
            return None
        mime = p[1:i].decode("latin-1", "replace")
        ptype = p[i + 1]
        d, data = _split_term(e, p[i + 2:])
        if not data:
            return None
        return Cover(data, mime, ptype, _decode(e, d))

    def _parse_v1(self, v1):
        def s(b):
            return b.split(b"\x00")[0].decode("latin-1").strip()
        vals = {"TIT2": s(v1[3:33]), "TPE1": s(v1[33:63]), "TALB": s(v1[63:93]), "TDRC": s(v1[93:97])}
        if v1[125] == 0 and v1[126] != 0:
            vals["COMM:"] = s(v1[97:125])
            vals["TRCK"] = str(v1[126])
        else:
            vals["COMM:"] = s(v1[97:127])
        if v1[127] < len(GENRES):
            vals["TCON"] = GENRES[v1[127]]
        for k, v in vals.items():
            if v:
                self.items[k] = Item.new_text(k, v)

    def _parse_mpeg(self, d: bytes):
        self.bitrate = self.samplerate = 0
        self.duration = 0.0
        self.channels = ""
        self.vbr = False
        i = 0
        while i < len(d) - 4:
            if d[i] == 0xFF and (d[i + 1] & 0xE0) == 0xE0:
                b1, b2, b3 = d[i + 1], d[i + 2], d[i + 3]
                vbits, layer = (b1 >> 3) & 3, (b1 >> 1) & 3
                bri, sri = b2 >> 4, (b2 >> 2) & 3
                if vbits != 1 and layer == 1 and 0 < bri < 15 and sri < 3:
                    mpeg = {3: 1, 2: 2, 0: 25}[vbits]
                    br = _BITRATES[(1 if mpeg == 1 else 2, 3)][bri]
                    sr = _SRATES[mpeg][sri]
                    mode = b3 >> 6
                    spf = 1152 if mpeg == 1 else 576
                    self.samplerate, self.bitrate = sr, br
                    self.channels = ["Stereo", "Joint Stereo", "Dual", "Mono"][mode]
                    side = (32 if mode != 3 else 17) if mpeg == 1 else (17 if mode != 3 else 9)
                    xo = i + 4 + side
                    frames = 0
                    if d[xo:xo + 4] in (b"Xing", b"Info") and len(d) >= xo + 12:
                        if struct.unpack(">I", d[xo + 4:xo + 8])[0] & 1:
                            frames = struct.unpack(">I", d[xo + 8:xo + 12])[0]
                        self.vbr = d[xo:xo + 4] == b"Xing"
                    elif d[i + 36:i + 40] == b"VBRI" and len(d) >= i + 54:
                        frames = struct.unpack(">I", d[i + 50:i + 54])[0]
                        self.vbr = True
                    audio = self.size - self.audio_start - (128 if self.had_v1 else 0)
                    if frames:
                        self.duration = frames * spf / sr
                        if self.duration:
                            self.bitrate = round(audio * 8 / self.duration / 1000)
                    elif br:
                        self.duration = audio * 8 / (br * 1000)
                    return
            i += 1

    # ------------------------------------------------------------------ Zugriff
    def _snapshot(self):
        self._orig = {k: v.clone() for k, v in self.items.items()}
        self._orig_version = self.version

    def set_version(self, ver: int):
        """Ziel-Version beim Speichern (3 oder 4). Felder werden dann neu kodiert."""
        if ver in (3, 4):
            self.version = ver

    def keys(self):
        return list(self.items.keys())

    def get(self, key):
        return self.items.get(key)

    def text(self, key) -> str:
        it = self.items.get(key)
        return it.text if it and it.kind != "picture" else ""

    def set(self, key, item: Item | None):
        if item is None:
            self.items.pop(key, None)
        else:
            it = item.clone()
            it.key = key
            self.items[key] = it

    def set_text(self, key, text: str):
        ex = self.items.get(key)
        if ex is not None:
            if ex.text == text:
                return
            self.items[key] = ex.with_text(text)
        else:
            self.items[key] = Item.new_text(key, text)

    def is_modified(self) -> bool:
        if self.version != self._orig_version:
            return True
        if self.items.keys() != self._orig.keys():
            return True
        return any(self.items[k] != self._orig[k] for k in self.items)

    def field_modified(self, key) -> bool:
        return self.items.get(key) != self._orig.get(key)

    def modified_keys(self):
        return [k for k in set(self.items) | set(self._orig) if self.field_modified(k)]

    def revert(self):
        self.items = {k: v.clone() for k, v in self._orig.items()}
        self.version = self._orig_version

    def info(self) -> str:
        import time
        parts = [time.strftime("%d.%m.%Y %H:%M:%S", time.localtime(self.mtime)),
                 f"{fmt_bytes(self.size)} Bytes", self.tag_desc]
        if self.duration:
            m, s = divmod(int(round(self.duration)), 60)
            parts.append(f"{m}:{s:02d}")
        if self.bitrate:
            parts.append(f"{self.bitrate} kbps" + (" VBR" if self.vbr else ""))
        if self.samplerate:
            parts.append(f"{self.samplerate / 1000:g} kHz")
        if self.channels:
            parts.append(self.channels)
        return "   ".join(parts)

    # ------------------------------------------------------------------ Speichern
    def save(self):
        """Schreibt nur, wenn etwas geändert wurde. Reihenfolge der Frames bleibt erhalten."""
        if not self.is_modified():
            return
        ver = self.version
        body = b"".join(b for it in self.items.values() for b in it.to_frames(ver))
        need = len(body)
        if self.had_v2 and need <= self.tag_space and not self.has_footer:
            padded = body + b"\x00" * (self.tag_space - need)
            header = b"ID3" + bytes([ver, 0, 0]) + _to_syncsafe(len(padded))
            with open(self.path, "r+b") as f:
                f.write(header + padded)
        else:
            padded = body + b"\x00" * 4096
            header = b"ID3" + bytes([ver, 0, 0]) + _to_syncsafe(len(padded))
            folder = os.path.dirname(os.path.abspath(self.path))
            fd, tmp = tempfile.mkstemp(prefix=".mp3tag_", suffix=".tmp", dir=folder)
            try:
                with os.fdopen(fd, "wb") as out, open(self.path, "rb") as src:
                    out.write(header + padded)
                    src.seek(self.audio_start)
                    shutil.copyfileobj(src, out, 1024 * 1024)
                shutil.copymode(self.path, tmp)
                os.replace(tmp, self.path)
            except BaseException:
                if os.path.exists(tmp):
                    os.remove(tmp)
                raise
        if self.had_v1:
            self._write_v1()
        self.load()

    def _write_v1(self):
        def fit(s, n):
            return s.encode("latin-1", "replace")[:n].ljust(n, b"\x00")
        t = self.text
        track = t("TRCK").split("/")[0].strip()
        track = min(int(track), 255) if track.isdigit() else 0
        genre = self.v1_genre
        g = t("TCON").strip().lower()
        for i, name in enumerate(GENRES):
            if name.lower() == g:
                genre = i
                break
        tag = (b"TAG" + fit(t("TIT2"), 30) + fit(t("TPE1"), 30) + fit(t("TALB"), 30)
               + fit(t("TDRC")[:4], 4) + fit(t("COMM:"), 28) + b"\x00" + bytes([track, genre]))
        with open(self.path, "r+b") as f:
            f.seek(-128, os.SEEK_END)
            f.write(tag)
