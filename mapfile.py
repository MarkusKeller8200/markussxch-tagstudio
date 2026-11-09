"""Gemeinsame Grundlage für Formate ohne ID3 (#262): FLAC, OGG/Opus (Vorbis-Kommentare) und MP4/M4A (iTunes-Atome).

TagStudioSX arbeitet weiter mit seinen ID3-Feldschlüsseln (`TIT2`, `TXXX:ENERGY`, `APIC:3` …). `MappedFile` übersetzt
beim Laden die Felder des Formats in diese Schlüssel und beim Speichern zurück (Zuordnung siehe `formatmap.py` und die
Tabellen unten). Grundsätze:

- **Unveränderte Felder bleiben, wie sie waren** – gleicher Name, gleiche Reihenfolge; unbekannte Felder und Binärdaten
  (z. B. Serato) werden unverändert mitgeschrieben, auch wenn TagStudioSX sie nicht anzeigt.
- Felder ohne Gegenstück im Format (z. B. `POPM`, `GEOB`, Links) werden **nicht geschrieben**; `save()` meldet sie in
  `save_skipped` (der Tagger zeigt den Hinweis).
- Audio wird nie verändert (je Format geprüft), Schreiben über eine temporäre Datei bzw. nur im Tag-Bereich.
- Kein ID3v1, kein Listen-Cache.
"""
from __future__ import annotations

import hashlib
import os
import struct
import time

from id3tags import MP3File, Item, Cover, MV, fmt_bytes

READ_ONLY_MSG = "nur lesen"


class FormatError(ValueError):
    """Datei nicht lesbar bzw. nicht sicher schreibbar."""


class MappedFile(MP3File):
    """Basis: Unterklassen setzen `container`, `_parse()` → (Einträge, Tag-Bytes) und `_write(einträge)`."""

    FORMAT = "?"
    READ_ONLY = False

    def load(self, cached: dict | None = None, keep_raw: bool = False):  # noqa: ARG002 – kein Listen-Cache
        self.items = {}
        self.version = 4                    # Mehrfachwerte wie ID3v2.4 (null-getrennt); die Datei hat keine ID3-Version
        self.tag_desc = "kein Tag"
        self.had_v2 = self.had_v1 = False
        self.audio_start = 0
        self.tag_space = 0
        self.has_footer = False
        self.tag_damaged = False
        self.v1_genre = 255
        self.v1_mode = None
        self.bitrate = self.samplerate = 0
        self.duration = 0.0
        self.channels = ""
        self.vbr = False
        self.bits = 0
        self.codec = ""
        self.read_only = self.READ_ONLY
        self.save_skipped: list[str] = []
        self._native: list = []
        self._srcname: dict = {}
        st = os.stat(self.path)
        self.size, self.mtime = st.st_size, st.st_mtime
        raw = b""
        try:
            raw = self._parse()
            self._to_items()
        except (FormatError, ValueError, IndexError, KeyError, OSError, struct.error, StopIteration) as ex:
            if isinstance(ex, (FileNotFoundError, PermissionError)):
                raise
            self.items = {}
            self.tag_damaged = True
            self.tag_desc = f"{self.FORMAT}: nicht lesbar ({ex})"
        h = hashlib.sha1()
        h.update(raw or b"")
        h.update(str(self.size).encode())
        self.disk_sig = h.hexdigest()
        self._snapshot()

    # Unterklassen
    def _parse(self) -> bytes:
        raise NotImplementedError

    def _to_items(self):
        raise NotImplementedError

    def _write(self):
        raise NotImplementedError

    # Gemeinsames
    def external_change(self) -> bool:
        try:
            g = type(self).__new__(type(self))
            g.path = self.path
            g.load()
            return g.disk_sig != getattr(self, "disk_sig", None)
        except OSError:
            return True

    def v1_pending(self) -> bool:
        return False

    def set_version(self, ver: int):          # keine ID3-Version – Wahl im Tagger hat keine Wirkung
        return

    def info(self) -> str:
        parts = [time.strftime("%d.%m.%Y %H:%M:%S", time.localtime(self.mtime)),
                 f"{fmt_bytes(self.size)} Bytes", f"{self.format_name()} · {self.tag_desc}"]
        if self.duration:
            m, s = divmod(int(round(self.duration)), 60)
            parts.append(f"{m}:{s:02d}")
        if self.bitrate:
            parts.append(f"{self.bitrate} kbps")
        if self.samplerate:
            parts.append(f"{self.samplerate / 1000:g} kHz")
        if self.bits:
            parts.append(f"{self.bits} bit")
        if self.channels:
            parts.append(self.channels)
        return "   ".join(parts)

    def format_name(self) -> str:
        return self.FORMAT

    def save(self):
        if not self.is_modified():
            return
        if self.read_only:
            raise ValueError(f"{self.format_name()} wird nur gelesen – nicht gespeichert.")
        if self.tag_damaged:
            raise ValueError(f"{self.format_name()}-Datei beschädigt oder nicht lesbar – nicht gespeichert, damit keine "
                             "Audiodaten verloren gehen.")
        try:
            self._write()
        except FormatError as ex:
            raise ValueError(str(ex)) from ex
        skipped = list(self.save_skipped)
        self.load()
        self.save_skipped = skipped


def channels_text(n: int) -> str:
    return {1: "Mono", 2: "Stereo"}.get(n, f"{n} Kanäle")


# =========================================================================== Vorbis-Kommentare (FLAC, OGG, Opus)
# TagStudioSX-Schlüssel → Vorbis-Name (Schreiben); beim Lesen zusätzlich die Aliasse
VORBIS_MAP = {
    "TIT2": "TITLE", "TPE1": "ARTIST", "TALB": "ALBUM", "TPE2": "ALBUMARTIST", "TCOM": "COMPOSER", "TEXT": "LYRICIST",
    "TPE3": "CONDUCTOR", "TPE4": "REMIXER", "TCON": "GENRE", "TDRC": "DATE", "TDOR": "ORIGINALDATE",
    "TDRL": "RELEASEDATE", "TSST": "DISCSUBTITLE", "TBPM": "BPM", "TKEY": "INITIALKEY", "TSRC": "ISRC",
    "TPUB": "LABEL", "TCOP": "COPYRIGHT", "COMM:": "COMMENT", "USLT:": "LYRICS", "TIT1": "WORK", "GRP1": "GROUPING",
    "TIT3": "SUBTITLE", "TMOO": "MOOD", "TMED": "MEDIA", "TLAN": "LANGUAGE", "TENC": "ENCODEDBY", "TSSE": "ENCODING",
    "TSOT": "TITLESORT", "TSOP": "ARTISTSORT", "TSOA": "ALBUMSORT", "TSO2": "ALBUMARTISTSORT", "TSOC": "COMPOSERSORT",
    "TCMP": "COMPILATION", "MVNM": "MOVEMENTNAME", "MVIN": "MOVEMENTNUMBER", "TOPE": "ORIGINALARTIST",
    "TOAL": "ORIGINALALBUM",
}
VORBIS_ALIAS = {"KEY": "TKEY", "ORGANIZATION": "TPUB", "PUBLISHER": "TPUB", "DESCRIPTION": "COMM:",
                "ALBUM ARTIST": "TPE2", "ALBUM_ARTIST": "TPE2", "ENCODERSETTINGS": "TSSE", "ENCODER": "TSSE",
                "UNSYNCEDLYRICS": "USLT:", "YEAR": "TDRC", "TEMPO": "TBPM"}
VORBIS_TOTALS = {"TRACKTOTAL": "TRCK", "TOTALTRACKS": "TRCK", "DISCTOTAL": "TPOS", "TOTALDISCS": "TPOS"}
VORBIS_NUMS = {"TRACKNUMBER": "TRCK", "DISCNUMBER": "TPOS"}
VORBIS_HIDDEN = ("SERATO_", "METADATA_BLOCK_PICTURE", "COVERART", "COVERARTMIME")   # unverändert mitschreiben
_V_READ = {v: k for k, v in VORBIS_MAP.items()}
_V_READ.update(VORBIS_ALIAS)


def vorbis_key(name: str) -> str | None:
    """Vorbis-Name → TagStudioSX-Schlüssel (ohne Spur/Disk); None = verborgen (unverändert mitschreiben)."""
    u = name.upper()
    if u.startswith(VORBIS_HIDDEN):
        return None
    return _V_READ.get(u) or f"TXXX:{name}"


def _valid_vname(n: str) -> bool:
    return bool(n) and all(0x20 <= ord(c) <= 0x7D and c != "=" for c in n)


def parse_vorbis_comment(data: bytes, pos: int = 0) -> tuple[str, list[tuple[str, str]], int]:
    """→ (Hersteller, [(Name, Wert)], Ende)."""
    import struct
    n = struct.unpack_from("<I", data, pos)[0]
    vendor = data[pos + 4:pos + 4 + n].decode("utf-8", "replace")
    pos += 4 + n
    cnt = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    out = []
    for _ in range(cnt):
        ln = struct.unpack_from("<I", data, pos)[0]
        raw = data[pos + 4:pos + 4 + ln]
        if len(raw) != ln:
            raise FormatError("Vorbis-Kommentar abgeschnitten")
        pos += 4 + ln
        k, eq, v = raw.partition(b"=")
        if not eq:
            continue
        out.append((k.decode("ascii", "replace"), v.decode("utf-8", "replace")))
    return vendor, out, pos


def build_vorbis_comment(vendor: str, entries: list[tuple[str, str]]) -> bytes:
    import struct
    v = vendor.encode("utf-8")
    out = [struct.pack("<I", len(v)), v, struct.pack("<I", len(entries))]
    for k, val in entries:
        b = k.encode("ascii") + b"=" + val.encode("utf-8")
        out += [struct.pack("<I", len(b)), b]
    return b"".join(out)


def parse_picture(d: bytes) -> Cover:
    """FLAC-PICTURE-Block (auch Inhalt von METADATA_BLOCK_PICTURE) → Cover."""
    import struct
    p = 0
    ptype, ml = struct.unpack_from(">II", d, p)
    p += 8
    mime = d[p:p + ml].decode("ascii", "replace")
    p += ml
    dl = struct.unpack_from(">I", d, p)[0]
    p += 4
    desc = d[p:p + dl].decode("utf-8", "replace")
    p += dl + 16
    n = struct.unpack_from(">I", d, p)[0]
    data = d[p + 4:p + 4 + n]
    if len(data) != n:
        raise FormatError("Bild abgeschnitten")
    return Cover(data, mime, ptype, desc)


def build_picture(c: Cover) -> bytes:
    import struct
    m, d = (c.mime or "image/jpeg").encode("ascii", "replace"), (c.desc or "").encode("utf-8")
    return (struct.pack(">II", int(c.ptype or 3), len(m)) + m + struct.pack(">I", len(d)) + d
            + struct.pack(">IIIII", 0, 0, 0, 0, len(c.data)) + c.data)


class VorbisMixin:
    """Übersetzung Vorbis-Kommentare ↔ Items. Erwartet `self._native` = [(Name, Wert)] und `self._covers` = [Cover]."""

    def _vorbis_to_items(self):
        vals: dict[str, list[str]] = {}
        totals: dict[str, str] = {}
        for name, value in self._native:
            u = name.upper()
            if u in VORBIS_TOTALS:
                totals[VORBIS_TOTALS[u]] = value.strip()
                self._srcname.setdefault("#" + VORBIS_TOTALS[u], name)
                continue
            key = VORBIS_NUMS.get(u) or vorbis_key(name)
            if key is None:
                continue
            if key == "COMM:" and u == "DESCRIPTION" and any(n.upper() == "COMMENT" for n, _ in self._native):
                key = "TXXX:DESCRIPTION"                     # beides vorhanden: COMMENT gilt, DESCRIPTION frei
            self._srcname.setdefault(key, name)
            if key == "TCMP":
                value = "1" if value.strip() in ("1", "true", "yes") else "0"
            vals.setdefault(key, []).append(value)
        for key, total in totals.items():
            if total and key in vals and "/" not in vals[key][0]:
                vals[key][0] = f"{vals[key][0]}/{total}"
        for key, lst in vals.items():
            text = MV.join(v for v in lst if v.strip()) if key not in ("COMM:", "USLT:") else lst[0]
            if not text.strip():
                continue
            it = Item.new_text(key, text)
            self.items[key] = it
        for c in getattr(self, "_covers", []):
            key = f"APIC:{c.ptype}"
            n = 2
            while key in self.items:
                key = f"APIC:{c.ptype}#{n}"
                n += 1
            it = Item.new_cover(c)
            it.key = key
            self.items[key] = it

    def _items_to_vorbis(self) -> tuple[list[tuple[str, str]], list[Cover]]:
        """Neue Einträge: Original-Reihenfolge und -Namen behalten, neue Felder hinten; verborgene unverändert."""
        skipped, done, out = [], set(), []
        wanted: dict[str, list[tuple[str, str]]] = {}
        for key, it in self.items.items():
            if it.kind == "picture":
                continue
            base = key.split("#")[0]
            if it.kind == "raw" or it.fid in ("POPM", "GEOB", "PRIV", "UFID", "WXXX") or it.fid.startswith("W"):
                skipped.append(key)
                continue
            if base in ("COMM:", "USLT:", "TRCK", "TPOS") or base in VORBIS_MAP:
                name = self._srcname.get(base) or {"TRCK": "TRACKNUMBER", "TPOS": "DISCNUMBER"}.get(base) or VORBIS_MAP.get(base)
            elif it.fid == "TXXX" and _valid_vname(it.desc):
                name = it.desc
            elif it.fid in ("COMM", "USLT"):
                skipped.append(key)
                continue
            else:
                skipped.append(key)
                continue
            if base == "TXXX:MOOD" and "TMOO" in self.items:
                continue                                         # ID3v2.3-Stimmung = MOOD, TMOO hat Vorrang
            vals = [it.text] if base in ("COMM:", "USLT:") else [v for v in it.text.split(MV) if v.strip()]
            rows = []
            if base in ("TRCK", "TPOS"):
                num, _, tot = it.text.partition("/")
                rows.append((name, num.strip()))
                if tot.strip():
                    rows.append((self._srcname.get("#" + base) or ("TRACKTOTAL" if base == "TRCK" else "DISCTOTAL"),
                                 tot.strip()))
            elif base == "TCMP":
                rows.append((name, "1" if it.text.strip() in ("1", "true") else "0"))
            else:
                rows = [(name, v) for v in vals]
            wanted[base] = rows
        for name, value in self._native:
            u = name.upper()
            key = VORBIS_TOTALS.get(u) or VORBIS_NUMS.get(u) or vorbis_key(name)
            if key == "COMM:" and u == "DESCRIPTION" and any(n.upper() == "COMMENT" for n, _ in self._native):
                key = "TXXX:DESCRIPTION"
            if key is None:
                out.append((name, value))                        # verborgen: unverändert
                continue
            if key in done:
                continue
            done.add(key)
            out += wanted.pop(key, [])
        for rows in wanted.values():
            out += rows
        covers = [it.cover for it in self.items.values() if it.kind == "picture" and it.cover is not None]
        self.save_skipped = skipped
        return out, covers
