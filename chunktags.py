"""WAV und AIFF: Tags im ID3-Chunk lesen und schreiben (#156, #263, Release 4.16.0 „Audioformate“).

Beide Formate sind Container aus Chunks (WAV: RIFF, Grössen Little-Endian; AIFF/AIFC: IFF „FORM“, Big-Endian). Die
Tags stehen als vollständiges ID3v2-Tag in einem eigenen Chunk (`id3 ` bzw. `ID3 `) – also mit denselben Feldern wie
bei MP3. `ChunkFile` ist deshalb eine Unterklasse von `id3tags.MP3File`: Felder, Cover, Bewertung, Serato-GEOB usw.
laufen über denselben Code; nur **Laden** und **Speichern** sind eigen.

Getrennt vom MP3-Weg: Für `.mp3` ändert sich nichts. `MP3File(pfad)` liefert für `.wav`, `.aif`, `.aiff` automatisch
ein `ChunkFile` (damit nie ein ID3-Kopf vor eine WAV-Datei geschrieben wird). In Tagger und Vergleich erscheinen
WAV/AIFF nur mit der Einstellung `chunk_formats` (Standard aus).

Grundsätze:
- Alle anderen Chunks (Audio, INFO, bext, cue, Serato …) werden **byte-genau** übernommen; nur der ID3-Chunk wird
  ersetzt bzw. am Ende angehängt. INFO/NAME/AUTH bleiben unverändert (Abgleich erst nach der Messreihe #446).
- Schreiben immer über eine temporäre Datei; vor dem Ersetzen wird geprüft, dass die Audiodaten (SHA-256 von
  `data` bzw. `SSND`) gleich geblieben sind.
- RF64 (WAV über 4 GB) und beschädigte Container: nur lesen.
- Gibt es keinen ID3-Chunk, werden INFO (WAV) bzw. NAME/AUTH/ANNO (AIFF) als Felder angezeigt; gespeichert wird dann
  ein neuer ID3-Chunk.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import struct
import tempfile

from id3tags import MP3File, Item, _syncsafe, _to_syncsafe

WAV_EXTS = (".wav",)
AIFF_EXTS = (".aif", ".aiff", ".aifc")
EXTS = WAV_EXTS + AIFF_EXTS
TAG_IDS = (b"id3 ", b"ID3 ")
# Felder aus RIFF-INFO bzw. AIFF-Textchunks, wenn kein ID3-Chunk da ist (nur lesen)
INFO_MAP = {b"INAM": "TIT2", b"IART": "TPE1", b"IPRD": "TALB", b"ICRD": "TDRC", b"IGNR": "TCON", b"ICMT": "COMM:",
            b"ITRK": "TRCK", b"IPRT": "TRCK", b"ICOP": "TCOP", b"ISFT": "TSSE"}
AIFF_TEXT = {b"NAME": "TIT2", b"AUTH": "TPE1", b"(c) ": "TCOP", b"ANNO": "COMM:"}


def is_chunk_path(path) -> bool:
    """Ist der Pfad eine WAV- oder AIFF-Datei (nach der Endung)?"""
    return str(path or "").lower().endswith(EXTS)


class ChunkError(ValueError):
    """Container nicht lesbar bzw. nicht sicher schreibbar."""


# --------------------------------------------------------------------------- Container lesen
def _ext80(b: bytes) -> float:
    """IEEE-754 80-Bit-Gleitkommazahl (Abtastrate im AIFF-COMM-Chunk)."""
    if len(b) < 10:
        return 0.0
    exp = ((b[0] & 0x7F) << 8) | b[1]
    mant = int.from_bytes(b[2:10], "big")
    if exp == 0 and mant == 0:
        return 0.0
    v = mant * 2.0 ** (exp - 16383 - 63)
    return -v if b[0] & 0x80 else v


def read_layout(path: str) -> dict:
    """Aufbau einer WAV-/AIFF-Datei → {"kind": "wav"|"aiff", "form": b"WAVE"|b"AIFF"|b"AIFC", "rf64", "le",
    "chunks": [{"id", "start", "size", "data_start", "end"}], "body_end", "size"}.
    `end` schliesst das Füllbyte ein (nicht über das Dateiende hinaus). Wirft ChunkError bei fremdem Format."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(12)
        if len(head) < 12:
            raise ChunkError("Datei zu kurz – kein WAV/AIFF")
        magic, form = head[:4], head[8:12]
        if magic in (b"RIFF", b"RF64") and form == b"WAVE":
            kind, le = "wav", True
        elif magic == b"FORM" and form in (b"AIFF", b"AIFC"):
            kind, le = "aiff", False
        else:
            raise ChunkError("kein gültiger WAV-/AIFF-Kopf")
        declared = struct.unpack("<I" if le else ">I", head[4:8])[0]
        rf64 = magic == b"RF64"
        body_end = size if rf64 or declared == 0xFFFFFFFF else min(size, 8 + declared)
        ds64 = {}
        chunks, pos = [], 12
        while pos + 8 <= body_end:
            f.seek(pos)
            h = f.read(8)
            cid = h[:4]
            csize = struct.unpack("<I" if le else ">I", h[4:8])[0]
            if rf64 and cid == b"ds64":
                d = f.read(min(csize, 28))
                if len(d) >= 16:
                    ds64 = {"riff": struct.unpack("<Q", d[0:8])[0], "data": struct.unpack("<Q", d[8:16])[0]}
            if rf64 and cid == b"data" and csize == 0xFFFFFFFF and ds64.get("data"):
                csize = ds64["data"]
            data_start = pos + 8
            end = min(data_start + csize + (csize & 1), size)
            chunks.append({"id": cid, "start": pos, "size": csize, "data_start": data_start,
                           "end": end, "short": data_start + csize > size})
            pos = data_start + csize + (csize & 1)
        return {"kind": kind, "form": form, "rf64": rf64, "le": le, "chunks": chunks,
                "body_end": body_end, "size": size}


def _find(lay: dict, *ids) -> dict | None:
    for c in lay["chunks"]:
        if c["id"] in ids:
            return c
    return None


def _read(path: str, c: dict) -> bytes:
    with open(path, "rb") as f:
        f.seek(c["data_start"])
        return f.read(min(c["size"], max(0, c["end"] - c["data_start"])))


def _audio_chunk(lay: dict) -> dict | None:
    return _find(lay, b"data") if lay["kind"] == "wav" else _find(lay, b"SSND")


def audio_hash(path: str, lay: dict | None = None) -> str:
    """SHA-256 der Audiodaten (`data` bzw. `SSND`) – zum Nachweis, dass Speichern das Audio nicht anfasst."""
    lay = lay or read_layout(path)
    c = _audio_chunk(lay)
    h = hashlib.sha256()
    if c is None:
        return ""
    with open(path, "rb") as f:
        f.seek(c["data_start"])
        left = max(0, min(c["size"], c["end"] - c["data_start"]))
        while left:
            b = f.read(min(left, 1 << 20))
            if not b:
                break
            h.update(b)
            left -= len(b)
    return h.hexdigest()


def read_tag_bytes(path: str) -> bytes:
    """Das rohe ID3-Tag aus dem Chunk (b"" ohne ID3-Chunk) – für Sicherungen und Snapshots."""
    lay = read_layout(path)
    c = _find(lay, *TAG_IDS)
    if c is None:
        return b""
    d = _read(path, c)
    if len(d) >= 10 and d[:3] == b"ID3":
        return d[:10 + _syncsafe(d[6:10])]
    return b""


def disk_sig(path: str) -> str:
    """Fingerabdruck der Tag-Bytes (wie id3tags.disk_sig, aber aus dem ID3-Chunk)."""
    h = hashlib.sha1()
    try:
        h.update(read_tag_bytes(path))
    except ChunkError:
        pass
    h.update(str(os.path.getsize(path)).encode())
    return h.hexdigest()


# --------------------------------------------------------------------------- Container schreiben
def write_tag_bytes(path: str, tag: bytes) -> None:
    """Ersetzt den ID3-Chunk (bzw. hängt einen an) – `tag` = vollständiges ID3v2-Tag oder b"" (Chunk entfernen).
    Alle anderen Chunks byte-genau; atomar über eine temporäre Datei; Audio-Prüfsumme vorher = nachher."""
    lay = read_layout(path)
    if lay["rf64"]:
        raise ChunkError("RF64 (WAV über 4 GB) wird nur gelesen – nicht gespeichert.")
    if any(c["short"] for c in lay["chunks"]) or _audio_chunk(lay) is None:
        raise ChunkError("Datei unvollständig oder ohne Audiodaten – nicht gespeichert, damit nichts verloren geht.")
    le = lay["le"]
    pack = (lambda n: struct.pack("<I", n)) if le else (lambda n: struct.pack(">I", n))
    before = audio_hash(path, lay)
    tag_c = _find(lay, *TAG_IDS)
    cid = tag_c["id"] if tag_c else (b"id3 " if lay["kind"] == "wav" else b"ID3 ")
    new_chunk = b""
    if tag:
        new_chunk = cid + pack(len(tag)) + tag + (b"\x00" if len(tag) & 1 else b"")
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".tagstudio_chunk_", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "wb") as out, open(path, "rb") as src:
            out.write(b"RIFF" if le else b"FORM")
            out.write(b"\x00\x00\x00\x00")                 # Grösse folgt
            out.write(lay["form"])
            done = False
            for c in lay["chunks"]:
                if c is tag_c:
                    out.write(new_chunk)
                    done = True
                    continue
                src.seek(c["start"])
                left = c["end"] - c["start"]
                while left:
                    b = src.read(min(left, 1 << 20))
                    if not b:
                        break
                    out.write(b)
                    left -= len(b)
                if c["size"] & 1 and c["end"] < c["data_start"] + c["size"] + 1:
                    out.write(b"\x00")                     # fehlendes Füllbyte am Dateiende ergänzen
            if not done:
                out.write(new_chunk)
            body = out.tell()
            if lay["body_end"] < lay["size"]:              # Bytes hinter dem Container (selten) unverändert anhängen
                src.seek(lay["body_end"])
                shutil.copyfileobj(src, out, 1 << 20)
            out.seek(4)
            out.write(pack(body - 8))
        check = read_layout(tmp)
        if audio_hash(tmp, check) != before:
            raise ChunkError("Prüfung fehlgeschlagen: Audiodaten wären verändert worden – nicht gespeichert.")
        if tag and read_tag_bytes(tmp) != tag:
            raise ChunkError("Prüfung fehlgeschlagen: ID3-Chunk nicht lesbar – nicht gespeichert.")
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


# --------------------------------------------------------------------------- Datei-Klasse
class ChunkFile(MP3File):
    """WAV/AIFF mit denselben Feldern wie MP3File. Kein ID3v1, kein Listen-Cache."""

    MPEG_ATTRS = MP3File.MPEG_ATTRS

    def load(self, cached: dict | None = None, keep_raw: bool = False):  # noqa: ARG002 – kein Listen-Cache
        self.items = {}
        self.version = 3
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
        self.container = "wav" if self.path.lower().endswith(WAV_EXTS) else "aiff"
        self.rf64 = False
        self.tag_chunk = ""
        st = os.stat(self.path)
        self.size, self.mtime = st.st_size, st.st_mtime
        tag = b""
        try:
            lay = read_layout(self.path)
            self.container = lay["kind"]
            self.rf64 = lay["rf64"]
            self._audio_info(lay)
            c = _find(lay, *TAG_IDS)
            if c is not None:
                self.tag_chunk = c["id"].decode("ascii")
                d = _read(self.path, c)
                if len(d) >= 10 and d[:3] == b"ID3" and d[3] in (2, 3, 4):
                    ver, flags, size = d[3], d[5], _syncsafe(d[6:10])
                    tag = d[:10 + size]
                    self.had_v2 = True
                    self.tag_desc = f"ID3v2.{ver} ({self.tag_chunk.strip()}-Chunk)"
                    self.tag_damaged = any(b >= 0x80 for b in d[6:10]) or 10 + size > len(d)
                    self._parse_v2(ver, flags, d[10:10 + size])
                else:
                    self.tag_damaged = True
                    self.tag_desc = "ID3-Chunk beschädigt"
            if not self.had_v2:
                self._read_text_chunks(lay)
            if any(x["short"] for x in lay["chunks"]):
                self.tag_damaged = True
        except ChunkError:
            self.tag_damaged = True
            self.tag_desc = "kein gültiger WAV-/AIFF-Container"
        h = hashlib.sha1()
        h.update(tag)
        h.update(str(self.size).encode())
        self.disk_sig = h.hexdigest()
        self._snapshot()

    def _audio_info(self, lay):
        if lay["kind"] == "wav":
            c = _find(lay, b"fmt ")
            data = _find(lay, b"data")
            if c is None:
                return
            d = _read(self.path, c)
            if len(d) < 16:
                return
            _fmt, ch, sr, byterate, _align, bits = struct.unpack("<HHIIHH", d[:16])
            self.samplerate, self.bits = sr, bits
            self.channels = {1: "Mono", 2: "Stereo"}.get(ch, f"{ch} Kanäle")
            self.bitrate = round(byterate * 8 / 1000) if byterate else 0
            if data is not None and byterate:
                self.duration = data["size"] / byterate
        else:
            c = _find(lay, b"COMM")
            if c is None:
                return
            d = _read(self.path, c)
            if len(d) < 18:
                return
            ch, frames, bits = struct.unpack(">HIH", d[:8])
            sr = _ext80(d[8:18])
            self.samplerate, self.bits = int(round(sr)), bits
            self.channels = {1: "Mono", 2: "Stereo"}.get(ch, f"{ch} Kanäle")
            if sr:
                self.duration = frames / sr
                self.bitrate = round(sr * ch * bits / 1000)

    def _read_text_chunks(self, lay):
        """Ohne ID3-Chunk: INFO (WAV) bzw. NAME/AUTH/(c)/ANNO (AIFF) als Felder anzeigen."""
        vals = {}
        if lay["kind"] == "wav":
            for c in lay["chunks"]:
                if c["id"] != b"LIST":
                    continue
                d = _read(self.path, c)
                if d[:4] != b"INFO":
                    continue
                p = 4
                while p + 8 <= len(d):
                    sid = d[p:p + 4]
                    n = struct.unpack("<I", d[p + 4:p + 8])[0]
                    v = d[p + 8:p + 8 + n].split(b"\x00")[0]
                    key = INFO_MAP.get(sid)
                    if key and v and key not in vals:
                        vals[key] = _text(v)
                    p += 8 + n + (n & 1)
            desc = "RIFF INFO"
        else:
            for c in lay["chunks"]:
                key = AIFF_TEXT.get(c["id"])
                if key and key not in vals:
                    v = _read(self.path, c).split(b"\x00")[0]
                    if v:
                        vals[key] = _text(v)
            desc = "AIFF-Text"
        for k, v in vals.items():
            v = v.strip()
            if v:
                self.items[k] = Item.new_text(k, v)
        if vals:
            self.tag_desc = desc

    def external_change(self) -> bool:
        try:
            return disk_sig(self.path) != getattr(self, "disk_sig", None)
        except OSError:
            return True

    def v1_pending(self) -> bool:
        return False                                   # WAV/AIFF kennen kein ID3v1

    def info(self) -> str:
        import time
        from id3tags import fmt_bytes
        parts = [time.strftime("%d.%m.%Y %H:%M:%S", time.localtime(self.mtime)),
                 f"{fmt_bytes(self.size)} Bytes", f"{self.container.upper()} · {self.tag_desc}"]
        if self.duration:
            m, s = divmod(int(round(self.duration)), 60)
            parts.append(f"{m}:{s:02d}")
        if self.samplerate:
            parts.append(f"{self.samplerate / 1000:g} kHz")
        if self.bits:
            parts.append(f"{self.bits} bit")
        if self.channels:
            parts.append(self.channels)
        return "   ".join(parts)

    def save(self):
        if not self.is_modified():
            return
        if self.rf64:
            raise ValueError("RF64 (WAV über 4 GB) wird nur gelesen – nicht gespeichert.")
        if self.tag_damaged:
            raise ValueError("WAV-/AIFF-Datei bzw. ID3-Chunk beschädigt – nicht gespeichert, damit keine Audiodaten "
                             "verloren gehen.")
        ver = self.version
        body = b"".join(b for it in self.items.values() for b in it.to_frames(ver))
        tag = b"ID3" + bytes([ver, 0, 0]) + _to_syncsafe(len(body)) + body if body else b""
        try:
            write_tag_bytes(self.path, tag)
        except ChunkError as ex:
            raise ValueError(str(ex)) from ex
        self.load()


def _text(b: bytes) -> str:
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("latin-1")
