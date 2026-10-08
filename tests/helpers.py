"""Hilfsfunktionen für die Tests: erzeugen gültige MP3-Dateien ohne externe Werkzeuge."""
import os
import random
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

FRAME_LEN = 417  # MPEG-1 Layer III, 128 kbps, 44.1 kHz, ohne Padding


def mpeg_audio(frames: int = 40, seed: int = 1) -> bytes:
    """Folge gültiger MPEG-1-Layer-III-Frames (128 kbps, 44.1 kHz, Joint Stereo) mit Zufallsinhalt."""
    rnd = random.Random(seed)
    head = b"\xff\xfb\x90\x40"
    return b"".join(head + bytes(rnd.getrandbits(8) for _ in range(FRAME_LEN - 4)) for _ in range(frames))


def syncsafe(n: int) -> bytes:
    return bytes([(n >> 21) & 0x7F, (n >> 14) & 0x7F, (n >> 7) & 0x7F, n & 0x7F])


def frame(fid: str, payload: bytes, ver: int = 4, flags: int = 0) -> bytes:
    size = syncsafe(len(payload)) if ver == 4 else struct.pack(">I", len(payload))
    return fid.encode() + size + struct.pack(">H", flags) + payload


def text(fid: str, value: str, ver: int = 4) -> bytes:
    if ver == 4:
        return frame(fid, b"\x03" + value.encode("utf-8"), 4)
    try:
        return frame(fid, b"\x00" + value.encode("latin-1"), 3)
    except UnicodeEncodeError:
        return frame(fid, b"\x01" + value.encode("utf-16"), 3)


def txxx(desc: str, value: str, ver: int = 4) -> bytes:
    return frame("TXXX", b"\x03" + desc.encode() + b"\x00" + value.encode(), ver)


def comm(desc: str, value: str, ver: int = 4) -> bytes:
    return frame("COMM", b"\x03eng" + desc.encode() + b"\x00" + value.encode(), ver)


def geob(desc: str, data: bytes, mime: str = "application/octet-stream", ver: int = 4) -> bytes:
    return frame("GEOB", b"\x00" + mime.encode() + b"\x00" + b"\x00" + desc.encode() + b"\x00" + data, ver)


def apic(data: bytes, ptype: int = 3, mime: str = "image/png", ver: int = 4) -> bytes:
    return frame("APIC", b"\x00" + mime.encode() + b"\x00" + bytes([ptype]) + b"\x00" + data, ver)


def tag(frames: list, ver: int = 4, padding: int = 256) -> bytes:
    body = b"".join(frames) + b"\x00" * padding
    return b"ID3" + bytes([ver, 0, 0]) + syncsafe(len(body)) + body


def id3v1(title="", artist="", album="", year="", comment="", track=0, genre=255) -> bytes:
    def fit(s, n):
        return s.encode("latin-1")[:n].ljust(n, b"\x00")
    return (b"TAG" + fit(title, 30) + fit(artist, 30) + fit(album, 30) + fit(year, 4)
            + fit(comment, 28) + b"\x00" + bytes([track, genre]))


def png(width: int = 300, height: int = 200, extra: bytes = b"") -> bytes:
    """Minimaler PNG-Kopf (reicht für Format- und Größenerkennung)."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00\x00\x00\x00" + extra


def write_mp3(path: str, frames: list = None, ver: int = 4, padding: int = 256, v1: bytes = b"",
              audio_seed: int = 1, audio_frames: int = 40) -> bytes:
    """Schreibt eine MP3-Datei; liefert die Audiobytes zurück (für Vergleiche)."""
    audio = mpeg_audio(audio_frames, audio_seed)
    with open(path, "wb") as fh:
        if frames is not None:
            fh.write(tag(frames, ver, padding))
        fh.write(audio)
        fh.write(v1)
    return audio


def audio_of(path: str) -> bytes:
    """Audiobytes einer Datei (ohne ID3v2 und ID3v1)."""
    with open(path, "rb") as fh:
        b = fh.read()
    start = 0
    if b[:3] == b"ID3":
        s = b[6:10]
        start = 10 + ((s[0] << 21) | (s[1] << 14) | (s[2] << 7) | s[3])
    end = len(b) - (128 if b[-128:-125] == b"TAG" else 0)
    return b[start:end]
