"""OGG Vorbis und Opus: Vorbis-Kommentare **lesen** (#266). Schreiben erst nach Freigabe (OGG-Seiten neu aufbauen).

Aufbau: OGG-Seiten („OggS“, Segmenttabelle). Paket 1 = Kennung (`\\x01vorbis` bzw. `OpusHead`), Paket 2 = Kommentare
(`\\x03vorbis` … Rahmenbit bzw. `OpusTags`). Cover als Base64-Feld `METADATA_BLOCK_PICTURE` (FLAC-PICTURE-Aufbau).
"""
from __future__ import annotations

import base64
import os
import struct

from mapfile import FormatError, MappedFile, VorbisMixin, channels_text, parse_picture, parse_vorbis_comment

EXTS = (".ogg", ".oga", ".opus")
MAX_HEAD = 16 << 20              # Kommentar-Paket höchstens 16 MB lesen


def _pages(f, serial=None):
    """OGG-Seiten ab der aktuellen Position → (Kopf, [Segmentlängen], Daten)."""
    while True:
        h = f.read(27)
        if len(h) < 27:
            return
        if h[:4] != b"OggS":
            raise FormatError("kein OGG-Seitenkopf")
        nseg = h[26]
        segs = f.read(nseg)
        data = f.read(sum(segs))
        yield h, list(segs), data


def read_packets(path: str, count: int = 2) -> tuple[list[bytes], int]:
    """Die ersten `count` Pakete des ersten logischen Datenstroms → (Pakete, Seriennummer)."""
    out, cur, serial, total = [], b"", None, 0
    with open(path, "rb") as f:
        for h, segs, data in _pages(f):
            s = struct.unpack_from("<I", h, 14)[0]
            if serial is None:
                serial = s
            if s != serial:
                continue
            p = 0
            for ln in segs:
                cur += data[p:p + ln]
                p += ln
                total += ln
                if total > MAX_HEAD:
                    raise FormatError("Kopfpakete zu gross")
                if ln < 255:
                    out.append(cur)
                    cur = b""
                    if len(out) >= count:
                        return out, serial
    raise FormatError("Kopfpakete unvollständig")


def last_granule(path: str, serial: int) -> int:
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        f.seek(max(0, size - 256 * 1024))
        tail = f.read()
    best, i = -1, tail.rfind(b"OggS")
    while i >= 0:
        if i + 27 <= len(tail) and struct.unpack_from("<I", tail, i + 14)[0] == serial:
            g = struct.unpack_from("<q", tail, i + 6)[0]
            if g >= 0:
                best = g
                break
        i = tail.rfind(b"OggS", 0, i)
    return best


class OggFile(VorbisMixin, MappedFile):
    FORMAT = "OGG"
    READ_ONLY = True

    def format_name(self) -> str:
        return "Opus" if getattr(self, "codec", "") == "Opus" else "OGG Vorbis"

    def _parse(self) -> bytes:
        self.container = "ogg"
        (ident, comm), serial = read_packets(self.path, 2)
        if ident[:7] == b"\x01vorbis":
            self.codec = "Vorbis"
            ch, rate = ident[11], struct.unpack_from("<I", ident, 12)[0]
            if comm[:7] != b"\x03vorbis":
                raise FormatError("Vorbis-Kommentar fehlt")
            body, pre = comm[7:], 0
        elif ident[:8] == b"OpusHead":
            self.codec = "Opus"
            ch, pre, rate = ident[9], struct.unpack_from("<H", ident, 10)[0], 48000
            if comm[:8] != b"OpusTags":
                raise FormatError("OpusTags fehlt")
            body = comm[8:]
        else:
            raise FormatError("weder Vorbis noch Opus")
        self.channels, self.samplerate = channels_text(ch), struct.unpack_from("<I", ident, 12)[0] if self.codec == "Opus" else rate
        self._vendor, self._native, _end = parse_vorbis_comment(body)
        self.tag_desc = "Vorbis-Kommentare (nur lesen)"
        g = last_granule(self.path, serial)
        if g > 0:
            self.duration = max(0, g - pre) / rate
            if self.duration:
                self.bitrate = round(self.size * 8 / self.duration / 1000)
        self._covers = []
        for name, value in self._native:
            if name.upper() == "METADATA_BLOCK_PICTURE":
                try:
                    self._covers.append(parse_picture(base64.b64decode(value + "=" * (-len(value) % 4))))
                except (ValueError, FormatError, struct.error):
                    pass
        self._raw = body
        return body

    def _to_items(self):
        self._vorbis_to_items()
