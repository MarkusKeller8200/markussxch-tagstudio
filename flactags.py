"""FLAC: Vorbis-Kommentare und Bilder lesen und schreiben (#264).

Aufbau: (optional ein vorangestelltes ID3v2-Tag) · `fLaC` · Metadatenblöcke (STREAMINFO, PADDING, APPLICATION,
SEEKTABLE, VORBIS_COMMENT, CUESHEET, PICTURE) · Audio-Frames.

Schreiben: VORBIS_COMMENT und PICTURE werden ersetzt, alle anderen Blöcke byte-genau übernommen. Passen die neuen
Blöcke in den bisherigen Platz (inkl. PADDING), wird **nur der Metadatenbereich** an Ort und Stelle überschrieben – die
Audio-Frames werden nicht angefasst. Sonst wird die Datei über eine temporäre Datei neu geschrieben (mit 4 KB PADDING)
und vor dem Ersetzen geprüft, dass die Audio-Frames byte-gleich sind (SHA-256).
"""
from __future__ import annotations

import hashlib
import os
import shutil
import struct
import tempfile

from id3tags import _syncsafe
from mapfile import FormatError, MappedFile, VorbisMixin, build_picture, build_vorbis_comment, channels_text, \
    parse_picture, parse_vorbis_comment

EXTS = (".flac",)
STREAMINFO, PADDING, VORBIS_COMMENT, PICTURE = 0, 1, 4, 6
NEW_PADDING = 4096
MAX_BLOCK = (1 << 24) - 1


def read_layout(path: str) -> dict:
    """→ {"prefix": Länge eines vorangestellten ID3v2, "blocks": [{"type", "start", "len", "data"}],
    "audio_start", "size"}. Daten nur für kleine Blöcke (Bilder: auch), Audio nie."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(10)
        prefix = 0
        if len(head) == 10 and head[:3] == b"ID3":
            prefix = 10 + _syncsafe(head[6:10]) + (10 if head[5] & 0x10 else 0)
        f.seek(prefix)
        if f.read(4) != b"fLaC":
            raise FormatError("kein FLAC-Kopf")
        blocks, pos = [], prefix + 4
        while True:
            h = f.read(4)
            if len(h) < 4:
                raise FormatError("Metadaten abgeschnitten")
            last, typ = bool(h[0] & 0x80), h[0] & 0x7F
            ln = int.from_bytes(h[1:4], "big")
            data = f.read(ln) if typ != PADDING else b""
            if typ != PADDING and len(data) != ln:
                raise FormatError("Metadaten abgeschnitten")
            if typ == PADDING:
                f.seek(ln, os.SEEK_CUR)
            blocks.append({"type": typ, "start": pos, "len": ln, "data": data})
            pos += 4 + ln
            if pos > size:
                raise FormatError("Metadaten länger als die Datei")
            if last:
                break
            if typ == 127:
                raise FormatError("ungültiger Block")
    return {"prefix": prefix, "blocks": blocks, "audio_start": pos, "size": size}


def audio_hash(path: str, start: int) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        f.seek(start)
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _block(typ: int, data: bytes, last: bool) -> bytes:
    if len(data) > MAX_BLOCK:
        raise FormatError("Block zu gross (über 16 MB) – z. B. ein sehr grosses Cover")
    return bytes([(0x80 if last else 0) | typ]) + len(data).to_bytes(3, "big") + data


class FlacFile(VorbisMixin, MappedFile):
    FORMAT = "FLAC"

    def _parse(self) -> bytes:
        self.container = "flac"
        self.codec = "FLAC"
        lay = read_layout(self.path)
        self._lay = lay
        self.audio_start = lay["audio_start"]
        si = next((b for b in lay["blocks"] if b["type"] == STREAMINFO), None)
        if si is None or len(si["data"]) < 18:
            raise FormatError("STREAMINFO fehlt")
        d = si["data"]
        x = int.from_bytes(d[10:18], "big")
        rate, ch, bps, total = x >> 44, ((x >> 41) & 7) + 1, ((x >> 36) & 31) + 1, x & ((1 << 36) - 1)
        self.samplerate, self.bits, self.channels = rate, bps, channels_text(ch)
        if rate and total:
            self.duration = total / rate
            self.bitrate = round((lay["size"] - lay["audio_start"]) * 8 / self.duration / 1000)
        raw = b""
        self._native, self._covers, self._vendor = [], [], "TagStudio"
        for b in lay["blocks"]:
            if b["type"] == VORBIS_COMMENT and not raw:
                self._vendor, self._native, _end = parse_vorbis_comment(b["data"])
                raw += b["data"]
                self.tag_desc = "Vorbis-Kommentare"
            elif b["type"] == PICTURE:
                self._covers.append(parse_picture(b["data"]))
                raw += b["data"]
        self._raw = raw
        return raw

    def _to_items(self):
        self._vorbis_to_items()

    def _write(self):
        entries, covers = self._items_to_vorbis()
        lay = read_layout(self.path)
        if lay["audio_start"] != self._lay["audio_start"] or len(lay["blocks"]) != len(self._lay["blocks"]):
            raise FormatError("Datei wurde inzwischen verändert – bitte neu einlesen.")
        vc = build_vorbis_comment(getattr(self, "_vendor", "TagStudio") or "TagStudio", entries)
        pics = [build_picture(c) for c in covers]
        new, placed_vc, placed_pic = [], False, False
        for b in lay["blocks"]:
            t = b["type"]
            if t == PADDING:
                continue
            if t == VORBIS_COMMENT:
                if not placed_vc:
                    new.append((VORBIS_COMMENT, vc))
                    placed_vc = True
                continue
            if t == PICTURE:
                if not placed_pic:
                    new += [(PICTURE, p) for p in pics]
                    placed_pic = True
                continue
            new.append((t, b["data"]))
        if not placed_vc:
            new.insert(1, (VORBIS_COMMENT, vc))                 # nach STREAMINFO
        if not placed_pic and pics:
            i = next(i for i, (t, _d) in enumerate(new) if t == VORBIS_COMMENT) + 1
            new[i:i] = [(PICTURE, p) for p in pics]
        body = sum(4 + len(d) for _t, d in new)
        room = lay["audio_start"] - lay["prefix"] - 4            # bisheriger Platz für alle Blöcke
        free = room - body
        if free == 0 or free >= 4:                                # passt: nur den Metadatenbereich schreiben
            blocks = new + ([(PADDING, b"\x00" * (free - 4))] if free >= 4 else [])
            meta = b"fLaC" + b"".join(_block(t, d, i == len(blocks) - 1) for i, (t, d) in enumerate(blocks))
            if len(meta) != lay["audio_start"] - lay["prefix"]:
                raise FormatError("interner Fehler: Grösse passt nicht – nicht gespeichert")
            with open(self.path, "r+b") as f:
                f.seek(lay["prefix"])
                f.write(meta)
            chk = read_layout(self.path)
            if chk["audio_start"] != lay["audio_start"]:
                raise FormatError("Prüfung fehlgeschlagen: Audio-Anfang verschoben")
            return
        blocks = new + [(PADDING, b"\x00" * NEW_PADDING)]
        meta = b"fLaC" + b"".join(_block(t, d, i == len(blocks) - 1) for i, (t, d) in enumerate(blocks))
        before = audio_hash(self.path, lay["audio_start"])
        folder = os.path.dirname(os.path.abspath(self.path))
        fd, tmp = tempfile.mkstemp(prefix=".tagstudio_flac_", suffix=".tmp", dir=folder)
        try:
            with os.fdopen(fd, "wb") as out, open(self.path, "rb") as src:
                out.write(src.read(lay["prefix"]))
                out.write(meta)
                src.seek(lay["audio_start"])
                shutil.copyfileobj(src, out, 1 << 20)
            chk = read_layout(tmp)
            if audio_hash(tmp, chk["audio_start"]) != before:
                raise FormatError("Prüfung fehlgeschlagen: Audiodaten wären verändert worden – nicht gespeichert.")
            shutil.copymode(self.path, tmp)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise


def tag_bytes(path: str) -> bytes:
    """VORBIS_COMMENT- und PICTURE-Blöcke (für Sicherungen)."""
    lay = read_layout(path)
    return b"".join(_block(b["type"], b["data"], False) for b in lay["blocks"] if b["type"] in (VORBIS_COMMENT, PICTURE))


def write_tag_bytes(path: str, tag: bytes) -> None:
    """Gesicherte Blöcke zurückschreiben (Wiederherstellen)."""
    f = FlacFile.__new__(FlacFile)
    f.path = path
    f.load()
    blocks, p = [], 0
    while p + 4 <= len(tag):
        t, ln = tag[p] & 0x7F, int.from_bytes(tag[p + 1:p + 4], "big")
        blocks.append((t, tag[p + 4:p + 4 + ln]))
        p += 4 + ln
    vc = next((d for t, d in blocks if t == VORBIS_COMMENT), None)
    f._vendor, f._native = ("TagStudio", []) if vc is None else parse_vorbis_comment(vc)[:2]
    f._covers = [parse_picture(d) for t, d in blocks if t == PICTURE]
    f.items, f._srcname = {}, {}
    f._to_items()
    f._native_backup = f._native
    f._write()
