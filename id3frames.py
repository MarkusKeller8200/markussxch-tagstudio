"""MarKusSXCH TagStudio – Katalog aller ID3v2-Frames (#98) und lesbare Kurzfassungen für Binär-Frames.

SPEC enthält jeden Frame aus ID3v2.3 und ID3v2.4 (inkl. Kapitel-Erweiterung CHAP/CTOC) sowie verbreitete
inoffizielle Frames (iTunes, Podcasts). Daraus entstehen die v2.2-Zuordnung, die Übersicht docs/ID3-FELDER.md
(`python tools/id3_frames_doc.py`) und die Tests. `describe()` liefert für Binär-Frames einen lesbaren Text,
den TagStudio statt „n Bytes · Prüfsumme“ anzeigt. Geschrieben wird immer byte-genau (siehe id3tags.Item.to_frames).
Nur Standardbibliothek.
"""
from __future__ import annotations

import struct

# Frame → (v2.2-ID oder "", Versionen, Bezeichnung)   Versionen: "3" = ID3v2.3, "4" = ID3v2.4, "x" = inoffiziell
SPEC = {
    # ---- Text
    "TALB": ("TAL", "34", "Album"), "TBPM": ("TBP", "34", "Beats pro Minute"), "TCOM": ("TCM", "34", "Komponist"),
    "TCON": ("TCO", "34", "Genre"), "TCOP": ("TCR", "34", "Copyright"), "TDAT": ("TDA", "3", "Datum (TTMM)"),
    "TDEN": ("", "4", "Kodierungsdatum"), "TDLY": ("TDY", "34", "Verzögerung"),
    "TDOR": ("", "4", "Originalveröffentlichungsdatum"), "TDRC": ("", "4", "Aufnahmedatum"),
    "TDRL": ("", "4", "Veröffentlichungsdatum"), "TDTG": ("", "4", "Tagging-Datum"), "TENC": ("TEN", "34", "Kodiert von"),
    "TEXT": ("TXT", "34", "Texter"), "TFLT": ("TFT", "34", "Dateityp"), "TIME": ("TIM", "3", "Uhrzeit (HHMM)"),
    "TIPL": ("", "4", "Beteiligte Personen"), "TIT1": ("TT1", "34", "Inhaltliche Gruppierung"),
    "TIT2": ("TT2", "34", "Titel"), "TIT3": ("TT3", "34", "Untertitel"), "TKEY": ("TKE", "34", "Tonart"),
    "TLAN": ("TLA", "34", "Sprache"), "TLEN": ("TLE", "34", "Länge (ms)"), "TMCL": ("", "4", "Musiker"),
    "TMED": ("TMT", "34", "Medientyp"), "TMOO": ("", "4", "Stimmung"), "TOAL": ("TOT", "34", "Originalalbum"),
    "TOFN": ("TOF", "34", "Originaldateiname"), "TOLY": ("TOL", "34", "Originaltexter"),
    "TOPE": ("TOA", "34", "Originalkünstler"), "TORY": ("TOR", "3", "Originaljahr"), "TOWN": ("", "34", "Eigentümer"),
    "TPE1": ("TP1", "34", "Künstler"), "TPE2": ("TP2", "34", "Album-Künstler"), "TPE3": ("TP3", "34", "Dirigent"),
    "TPE4": ("TP4", "34", "Remix / Bearbeitung"), "TPOS": ("TPA", "34", "Disknummer"),
    "TPRO": ("", "4", "Produktionshinweis"), "TPUB": ("TPB", "34", "Herausgeber / Label"),
    "TRCK": ("TRK", "34", "Spurnummer"), "TRDA": ("TRD", "3", "Aufnahmedaten"),
    "TRSN": ("", "34", "Internetradio-Name"), "TRSO": ("", "34", "Internetradio-Eigentümer"),
    "TSIZ": ("TSI", "3", "Grösse (Bytes)"), "TSOA": ("TSA", "4", "Album einsortieren als"),
    "TSOP": ("TSP", "4", "Künstler einsortieren als"), "TSOT": ("TST", "4", "Titel einsortieren als"),
    "TSRC": ("TRC", "34", "ISRC"), "TSSE": ("TSS", "34", "Kodierung Einstellungen"),
    "TSST": ("", "4", "Disc-Untertitel"), "TYER": ("TYE", "3", "Jahr"), "TXXX": ("TXX", "34", "Benutzertext"),
    # ---- URL
    "WCOM": ("WCM", "34", "Kauf-Internetseite"), "WCOP": ("WCP", "34", "Copyright-Internetseite"),
    "WOAF": ("WAF", "34", "Audiodatei Internetseite"), "WOAR": ("WAR", "34", "Künstler Internetseite"),
    "WOAS": ("WAS", "34", "Audioquelle Internetseite"), "WORS": ("", "34", "Internetradio Internetseite"),
    "WPAY": ("", "34", "Bezahlung Internetseite"), "WPUB": ("WPB", "34", "Herausgeber Internetseite"),
    "WXXX": ("WXX", "34", "Benutzer-Link"),
    # ---- Kommentare, Texte, Bilder
    "COMM": ("COM", "34", "Kommentar"), "USLT": ("ULT", "34", "Liedtext"), "SYLT": ("SLT", "34", "Synchronisierter Liedtext"),
    "APIC": ("PIC", "34", "Bild / Cover"), "USER": ("", "34", "Nutzungsbedingungen"),
    # ---- Binär
    "AENC": ("CRA", "34", "Audio-Verschlüsselung"), "ASPI": ("", "4", "Audio-Suchindex"), "COMR": ("", "34", "Kommerziell"),
    "ENCR": ("", "34", "Verschlüsselungsmethode"), "EQUA": ("EQU", "3", "Equalizer"), "EQU2": ("", "4", "Equalizer"),
    "ETCO": ("ETC", "34", "Ereignis-Zeitpunkte"), "GEOB": ("GEO", "34", "Eingebettete Daten"),
    "GRID": ("", "34", "Gruppen-ID"), "IPLS": ("IPL", "3", "Beteiligte Personen"), "LINK": ("LNK", "34", "Verknüpfung"),
    "MCDI": ("MCI", "34", "CD-Inhaltsverzeichnis"), "MLLT": ("MLL", "34", "MPEG-Lookup-Tabelle"),
    "OWNE": ("", "34", "Besitzer"), "PCNT": ("CNT", "34", "Wiedergabezähler"), "POPM": ("POP", "34", "Bewertung"),
    "POSS": ("", "34", "Positions-Synchronisation"), "PRIV": ("", "34", "Private Daten"), "RBUF": ("BUF", "34", "Puffergrösse"),
    "RVAD": ("RVA", "3", "Lautstärke-Anpassung"), "RVA2": ("", "4", "Lautstärke-Anpassung"), "RVRB": ("REV", "34", "Hall"),
    "SEEK": ("", "4", "Suchmarke"), "SIGN": ("", "4", "Signatur"), "SYTC": ("STC", "34", "Tempo-Code"),
    "UFID": ("UFI", "34", "Eindeutige Datei-ID"),
    # ---- Kapitel-Erweiterung (id3v2-chapters-1.0, für v2.3 und v2.4)
    "CHAP": ("", "34", "Kapitel"), "CTOC": ("", "34", "Inhaltsverzeichnis (Kapitel)"),
    # ---- inoffiziell, aber verbreitet (iTunes, Podcasts, Mp3tag)
    "TCMP": ("TCP", "x", "Zusammenstellung (iTunes)"), "TSO2": ("TS2", "x", "Album-Künstler einsortieren als (iTunes)"),
    "TSOC": ("TSC", "x", "Komponist einsortieren als (iTunes)"), "GRP1": ("GP1", "x", "Gruppierung (iTunes)"),
    "MVNM": ("MVN", "x", "Satzname (iTunes)"), "MVIN": ("MVI", "x", "Satznummer (iTunes)"),
    "PCST": ("PCS", "x", "Podcast-Kennzeichen (iTunes)"), "TCAT": ("TCT", "x", "Podcast-Kategorie (iTunes)"),
    "TDES": ("TDS", "x", "Podcast-Beschreibung (iTunes)"), "TGID": ("TID", "x", "Podcast-ID (iTunes)"),
    "TKWD": ("TKW", "x", "Podcast-Schlüsselwörter (iTunes)"), "WFED": ("WFD", "x", "Podcast-Feed (iTunes)"),
    "XSOA": ("", "x", "Album einsortieren als (v2.3, iTunes)"), "XSOP": ("", "x", "Künstler einsortieren als (v2.3, iTunes)"),
    "XSOT": ("", "x", "Titel einsortieren als (v2.3, iTunes)"),
}
# v2.2-Frames ohne Gegenstück in v2.3/v2.4 (werden beim Umwandeln nach v2.3 verworfen)
V22_DROPPED = {"CRM": "Verschlüsselte Meta-Daten (nur ID3v2.2)"}

V22_TO_V23 = {v22: fid for fid, (v22, _v, _l) in SPEC.items() if v22}
V23_ONLY = sorted(f for f, (_a, v, _l) in SPEC.items() if v == "3")
V24_ONLY = sorted(f for f, (_a, v, _l) in SPEC.items() if v == "4")

EVENTS = {0x00: "Polsterung", 0x01: "Ende der Stille", 0x02: "Beginn Intro", 0x03: "Beginn Hauptteil",
          0x04: "Beginn Outro", 0x05: "Ende Outro", 0x06: "Beginn Vers", 0x07: "Beginn Refrain", 0x08: "Beginn Bridge",
          0x09: "Beginn Instrumental", 0x0A: "Beginn Solo", 0x0D: "Tonartwechsel", 0x0E: "Tempowechsel",
          0x0F: "Hauptteil Ende", 0x10: "Profanität", 0x11: "Profanität Ende", 0xFD: "Audio-Ende", 0xFE: "Datei-Ende"}
CHANNELS = {0: "Andere", 1: "Master", 2: "Vorne rechts", 3: "Vorne links", 4: "Hinten rechts", 5: "Hinten links",
            6: "Vorne Mitte", 7: "Hinten Mitte", 8: "Subwoofer"}


def label(fid: str) -> str:
    s = SPEC.get(fid)
    return s[2] if s else ""


# --------------------------------------------------------------------------- Hilfen
def _term(b: bytes, enc: int = 0):
    """bis zum Nullbyte (UTF-16: zwei Nullbytes) → (Teil, Rest)"""
    if enc in (1, 2):
        i = 0
        while i + 1 < len(b):
            if b[i] == 0 and b[i + 1] == 0:
                return b[:i], b[i + 2:]
            i += 2
        return b, b""
    i = b.find(b"\x00")
    return (b, b"") if i < 0 else (b[:i], b[i + 1:])


def _txt(b: bytes, enc: int = 0) -> str:
    try:
        if enc == 0:
            s = b.decode("latin-1")
        elif enc == 1:
            s = b.decode("utf-16") if b[:2] in (b"\xff\xfe", b"\xfe\xff") else b.decode("utf-16-le")
        elif enc == 2:
            s = b.decode("utf-16-be")
        else:
            s = b.decode("utf-8")
    except UnicodeDecodeError:
        s = b.decode("latin-1", "replace")
    return s.replace("﻿", "").strip()


def _ms(ms: int) -> str:
    s = ms / 1000
    return f"{int(s // 60)}:{s % 60:04.1f}"


def _date8(b: bytes) -> str:
    d = b.decode("latin-1", "replace")
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 and d.isdigit() else d


def _int(b: bytes) -> int:
    return int.from_bytes(b, "big") if b else 0


def _short(s: str, n: int = 120) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n - 1] + "…"


# --------------------------------------------------------------------------- Kurzfassungen
def describe(fid: str, p: bytes | None, ver: int = 4) -> str | None:
    """Lesbare Kurzfassung eines Binär-Frames oder None (dann zeigt TagStudio Grösse und Prüfsumme)."""
    if p is None:
        return None
    try:
        fn = _DESCRIBE.get(fid)
        return fn(p, ver) if fn else None
    except (IndexError, ValueError, struct.error, UnicodeError):
        return None


def _pcnt(p, _v):
    return f"{_int(p)} Wiedergabe(n)"


def _sylt(p, _v):
    enc, lang, fmt, ctype = p[0], p[1:4].decode("latin-1", "replace"), p[4], p[5]
    desc, rest = _term(p[6:], enc)
    lines = []
    while rest:
        t, rest = _term(rest, enc)
        if len(rest) < 4:
            break
        stamp, rest = _int(rest[:4]), rest[4:]
        lines.append((stamp, _txt(t, enc)))
    kind = {0: "Sonstiges", 1: "Liedtext", 2: "Text-Umschrift", 3: "Satz/Teil", 4: "Ereignisse", 5: "Akkorde",
            6: "Wissenswertes", 7: "Web-Adressen", 8: "Bild-Adressen"}.get(ctype, "Inhalt")
    unit = "ms" if fmt == 2 else "Frames"
    first = " · ".join(f"[{_ms(s) if fmt == 2 else s}] {t}" for s, t in lines[:3] if t)
    return _short(f"{kind} ({lang}{', ' + _txt(desc, enc) if desc else ''}): {len(lines)} Zeile(n), Zeit in {unit}"
                  + (f" – {first}" if first else ""))


def _etco(p, _v):
    fmt, rest, ev = p[0], p[1:], []
    while len(rest) >= 5:
        ev.append((rest[0], _int(rest[1:5])))
        rest = rest[5:]
    unit = "ms" if fmt == 2 else "Frames"
    return _short(f"{len(ev)} Ereignis(se), Zeit in {unit}: "
                  + ", ".join(f"{EVENTS.get(t, hex(t))} @ {_ms(s) if fmt == 2 else s}" for t, s in ev[:4]))


def _mllt(p, _v):
    return (f"alle {_int(p[0:2])} MPEG-Frames · {_int(p[2:5])} Bytes · {_int(p[5:8])} ms "
            f"({p[8]}/{p[9]} Bit Abweichung)")


def _sytc(p, _v):
    return f"Tempo-Code, Zeit in {'ms' if p[0] == 2 else 'Frames'}, {len(p) - 1} Bytes"


def _rva2(p, _v):
    ident, rest = _term(p)
    parts = []
    while len(rest) >= 4:
        ch, adj, bits = rest[0], struct.unpack(">h", rest[1:3])[0] / 512, rest[3]
        rest = rest[4 + (bits + 7) // 8:]
        parts.append(f"{CHANNELS.get(ch, ch)} {adj:+.2f} dB")
    return _short(f"{_txt(ident) or '(ohne Kennung)'}: " + ", ".join(parts))


def _rvad(p, _v):
    return f"Lautstärke-Anpassung (ID3v2.3), {p[1]} Bit je Wert, {len(p)} Bytes"


def _equ2(p, _v):
    ident, rest = _term(p[1:])
    pts = len(rest) // 4
    return f"{_txt(ident) or '(ohne Kennung)'}: {pts} Punkt(e), {'linear' if p[0] else 'Stufen'}"


def _equa(p, _v):
    return f"Equalizer (ID3v2.3), {p[0]} Bit je Wert, {(len(p) - 1) // (2 + (p[0] + 7) // 8)} Punkt(e)"


def _rvrb(p, _v):
    return f"Hall links {_int(p[0:2])} ms, rechts {_int(p[2:4])} ms"


def _user(p, _v):
    return _short(f"{p[1:4].decode('latin-1', 'replace')}: {_txt(p[4:], p[0])}")


def _owne(p, _v):
    enc = p[0]
    price, rest = _term(p[1:])
    return _short(f"Preis {_txt(price)} · gekauft {_date8(rest[:8])} · Verkäufer {_txt(rest[8:], enc)}")


def _comr(p, _v):
    enc = p[0]
    price, rest = _term(p[1:])
    until, rest = rest[:8], rest[8:]
    url, rest = _term(rest)
    seller, rest = _term(rest[1:], enc)
    desc, _rest = _term(rest, enc)
    return _short(f"Preis {_txt(price)} · gültig bis {_date8(until)} · Verkäufer {_txt(seller, enc)}"
                  + (f" · {_txt(desc, enc)}" if desc else "") + (f" · {_txt(url)}" if url else ""))


def _encr(p, _v):
    owner, rest = _term(p)
    return f"{_txt(owner)} · Methode 0x{rest[0]:02X}" if rest else _txt(owner)


def _grid(p, _v):
    owner, rest = _term(p)
    return f"Gruppe 0x{rest[0]:02X} · {_txt(owner)}" if rest else _txt(owner)


def _sign(p, _v):
    return f"Signatur Gruppe 0x{p[0]:02X}, {len(p) - 1} Bytes"


def _link(p, ver):
    n = 3 if ver == 2 else 4
    fid, rest = p[:n].decode("latin-1", "replace"), p[n:]
    url, rest = _term(rest)
    extra = rest.replace(b"\x00", b" ").decode("latin-1", "replace").strip()
    return _short(f"Verweis auf {fid}: {_txt(url)}" + (f" ({extra})" if extra else ""))


def _poss(p, _v):
    return f"Position {_int(p[1:])} {'ms' if p[0] == 2 else 'Frames'}"


def _seek(p, _v):
    return f"nächstes Tag nach {_int(p[0:4])} Bytes"


def _aspi(p, _v):
    return f"Suchindex: {_int(p[8:10])} Punkte über {_int(p[4:8])} Bytes ab {_int(p[0:4])}"


def _rbuf(p, _v):
    off = f", nächstes Tag nach {_int(p[4:8])} Bytes" if len(p) >= 8 else ""
    return f"Puffer {_int(p[0:3])} Bytes{', eingebettete Info' if p[3] & 1 else ''}{off}"


def _aenc(p, _v):
    owner, rest = _term(p)
    return f"{_txt(owner)} · Vorschau ab Frame {_int(rest[0:2])}, {_int(rest[2:4])} Frames"


def _mcdi(p, _v):
    return f"CD-Inhaltsverzeichnis, {max(0, (len(p) - 4) // 8 - 1)} Spur(en), {len(p)} Bytes"


def _subtitle(rest: bytes, ver: int) -> str:
    """TIT2 aus den Unter-Frames eines CHAP/CTOC"""
    while len(rest) >= 10:
        fid, size = rest[:4], (int.from_bytes(rest[4:8], "big") if ver == 3 else
                               ((rest[4] << 21) | (rest[5] << 14) | (rest[6] << 7) | rest[7]))
        data = rest[10:10 + size]
        if fid == b"TIT2" and data:
            return _txt(data[1:], data[0])
        rest = rest[10 + size:]
    return ""


def _chap(p, ver):
    eid, rest = _term(p)
    start, end = _int(rest[0:4]), _int(rest[4:8])
    t = _subtitle(rest[16:], ver)
    return _short(f"{_txt(eid)}: {_ms(start)}–{_ms(end)}" + (f" „{t}“" if t else ""))


def _ctoc(p, ver):
    eid, rest = _term(p)
    flags, n, rest = rest[0], rest[1], rest[2:]
    for _ in range(n):
        _e, rest = _term(rest)
    t = _subtitle(rest, ver)
    return _short(f"{_txt(eid)}: {n} Eintrag/Einträge{' · oberste Ebene' if flags & 2 else ''}"
                  + (f" „{t}“" if t else ""))


def _pcst(p, _v):
    return "Podcast"


_DESCRIBE = {"PCNT": _pcnt, "SYLT": _sylt, "ETCO": _etco, "MLLT": _mllt, "SYTC": _sytc, "RVA2": _rva2, "RVAD": _rvad,
             "EQU2": _equ2, "EQUA": _equa, "RVRB": _rvrb, "USER": _user, "OWNE": _owne, "COMR": _comr, "ENCR": _encr,
             "GRID": _grid, "SIGN": _sign, "LINK": _link, "POSS": _poss, "SEEK": _seek, "ASPI": _aspi,
             "RBUF": _rbuf, "AENC": _aenc, "MCDI": _mcdi, "CHAP": _chap, "CTOC": _ctoc, "PCST": _pcst}


# --------------------------------------------------------------------------- Übersicht
def capabilities(fid: str) -> dict:
    """Was TagStudio mit dem Frame kann: lesen, anzeigen, bearbeiten, schreiben (+ Hinweis)."""
    from id3tags import _kind_of
    k = _kind_of(fid)
    if fid == "IPLS":
        k = "text"
    if k in ("text", "url", "txxx", "wxxx", "comment", "lyrics"):
        return {"read": True, "show": "Text", "edit": "Text", "write": True}
    if k == "picture":
        return {"read": True, "show": "Bild", "edit": "Cover-Werkzeuge", "write": True}
    show = "lesbar" if fid in _DESCRIBE or fid in ("POPM", "UFID", "PRIV", "GEOB") else "Grösse + Prüfsumme"
    edit = {"GEOB": "Binärfeld-Editor", "PRIV": "Binärfeld-Editor", "POPM": "Bewertung (Sterne)"}.get(fid, "–")
    return {"read": True, "show": show, "edit": edit, "write": True}
