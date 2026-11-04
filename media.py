"""MarKusSXCH TagStudio – Audio für den Vorschau-Player bereitstellen.

Ein kleiner lokaler HTTP-Server (nur 127.0.0.1) liefert Audiodateien mit Range-Anfragen aus, damit das
<audio>-Element der Oberfläche spulen kann, ohne die ganze Datei zu laden. Ausgeliefert werden nur Dateien, die
vorher registriert wurden (Dateien aus Tagger bzw. Vergleich); jede Adresse enthält ein zufälliges Sitzungs-Token.
Nur Standardbibliothek.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import struct
import threading

from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Eigene Oberfläche: Browser-Modus (http://127.0.0.1:…) oder Desktop-Fenster mit lokaler Datei (Origin „null“)
_LOOPBACK_ORIGIN = re.compile(r"null|http://(127\.0\.0\.1|localhost|\[::1\])(?::(\d{1,5}))?")
_LOOPBACK_HOSTS = {"127.0.0.1": "127.0.0.1", "localhost": "localhost", "[::1]": "[::1]"}


def _allowed_origin(origin: str) -> str:
    """Origin der eigenen Oberfläche → Wert für Access-Control-Allow-Origin, neu zusammengesetzt aus festen Teilen
    (nie die Eingabe selbst – keine Steuerzeichen in der Antwort); sonst leer."""
    m = _LOOPBACK_ORIGIN.fullmatch(origin)
    if not m:
        return ""
    if origin == "null":
        return "null"
    host = _LOOPBACK_HOSTS[m.group(1)]
    return f"http://{host}:{int(m.group(2))}" if m.group(2) else f"http://{host}"

AUDIO_TYPES = {".mp3": "audio/mpeg", ".flac": "audio/flac", ".wav": "audio/wav", ".m4a": "audio/mp4",
               ".aac": "audio/aac", ".ogg": "audio/ogg", ".opus": "audio/ogg", ".aif": "audio/aiff", ".aiff": "audio/aiff",
               ".aifc": "audio/aiff"}
AIFF_EXTS = (".aif", ".aiff", ".aifc")      # #448: Browser spielen AIFF nicht – wird als WAV ausgeliefert
CHUNK = 256 * 1024
MAX_FILES = 300          # nur die zuletzt genutzten Dateien bleiben freigegeben (#44)
_RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")


class MediaServer:
    def __init__(self):
        self.token = secrets.token_urlsafe(18)
        self.files: OrderedDict[str, str] = OrderedDict()
        self.lock = threading.Lock()
        self.srv = None

    # ---------------------------------------------------------------- Registrierung
    def register(self, path: str) -> str:
        """Datei freigeben → Adresse für das <audio>-Element."""
        path = os.path.abspath(path)
        ext = os.path.splitext(path)[1].lower()
        if ext not in AUDIO_TYPES:
            raise ValueError(f"Kein unterstütztes Audioformat: {ext or '(ohne Endung)'}")
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        fid = hashlib.sha1(path.encode("utf-8", "surrogatepass")).hexdigest()[:20]
        if ext in AIFF_EXTS:                       # #448: als WAV ausliefern (vorher prüfen, ob es geht)
            aiff_view(path)
            ext = ".wav"
        with self.lock:
            self.files[fid] = path
            self.files.move_to_end(fid)
            while len(self.files) > MAX_FILES:
                self.files.popitem(last=False)
        self.start()
        return f"http://127.0.0.1:{self.srv.server_address[1]}/m/{self.token}/{fid}{ext}"

    # ---------------------------------------------------------------- Server
    def start(self):
        with self.lock:
            if self.srv is not None:
                return
            media = self

            class Handler(BaseHTTPRequestHandler):
                protocol_version = "HTTP/1.1"

                def log_message(self, *a):  # ruhig bleiben
                    pass

                def do_HEAD(self):  # noqa: N802
                    media.serve(self, head=True)

                def do_GET(self):  # noqa: N802
                    media.serve(self)

            self.srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            self.srv.daemon_threads = True
            threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def stop(self):
        if self.srv is not None:
            self.srv.shutdown()
            self.srv.server_close()
            self.srv = None

    def lookup(self, url_path: str):
        """'/m/<token>/<id>.<ext>' → Dateipfad oder None."""
        parts = url_path.split("/")
        if len(parts) != 4 or parts[1] != "m" or not secrets.compare_digest(parts[2], self.token):
            return None
        fid = os.path.splitext(parts[3])[0]
        with self.lock:
            return self.files.get(fid)

    def serve(self, h: BaseHTTPRequestHandler, head=False):
        path = self.lookup(h.path.split("?", 1)[0])
        if path is None or not os.path.isfile(path):
            return _plain(h, 404, "not found")
        view = None
        if path.lower().endswith(AIFF_EXTS):
            try:
                view = aiff_view(path)
            except (OSError, ValueError):
                return _plain(h, 415, "unsupported")
        size = view["size"] if view else os.path.getsize(path)
        ctype = "audio/wav" if view else AUDIO_TYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
        start, end, status = 0, size - 1, 200
        rng = h.headers.get("Range")
        if rng:
            m = _RANGE.match(rng.strip())
            if not m or (not m.group(1) and not m.group(2)):
                return _range_error(h, size)
            if m.group(1):
                start = int(m.group(1))
                end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
            else:                               # „bytes=-500“ = die letzten 500 Bytes
                start = max(0, size - int(m.group(2)))
            if start >= size or start > end:
                return _range_error(h, size)
            status = 206
        length = end - start + 1
        h.send_response(status)
        h.send_header("Content-Type", ctype)
        h.send_header("Accept-Ranges", "bytes")
        h.send_header("Content-Length", str(length))
        h.send_header("Cache-Control", "no-store")
        allow = _allowed_origin(h.headers.get("Origin") or "")
        if allow:                                          # nur die eigene Oberfläche darf die Daten lesen (Wellenform)
            h.send_header("Access-Control-Allow-Origin", allow)
            h.send_header("Vary", "Origin")
        if status == 206:
            h.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        h.end_headers()
        if head:
            return
        if view:
            try:
                pos = start
                while pos <= end:
                    part = aiff_read(path, view, pos, min(end, pos + CHUNK - 1))
                    if not part:
                        break
                    h.wfile.write(part)
                    pos += len(part)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            return
        try:
            with open(path, "rb") as fh:
                fh.seek(start)
                left = length
                while left > 0:
                    chunk = fh.read(min(CHUNK, left))
                    if not chunk:
                        break
                    h.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass   # Wiedergabe abgebrochen/gespult – normal


# --------------------------------------------------------------------------- AIFF als WAV (#448)
# AIFF/AIFC enthält unkomprimiertes PCM in Big-Endian (AIFC „sowt“: Little-Endian). Für den Browser wird daraus eine
# virtuelle WAV-Datei: 44-Byte-Kopf + Audiodaten mit umgedrehter Byte-Reihenfolge (8 bit: vorzeichenbehaftet →
# vorzeichenlos). Nichts wird auf die Platte geschrieben; Spulen (Range) funktioniert wie bei echten Dateien.
_AIFC = {b"NONE": ("be", 1), b"twos": ("be", 1), b"sowt": ("le", 1), b"raw ": ("u8", 1),
         b"fl32": ("be", 3), b"FL32": ("be", 3), b"fl64": ("be", 3), b"FL64": ("be", 3)}
_VIEWS: dict = {}


def aiff_view(path: str) -> dict:
    """Aufbau der virtuellen WAV-Datei → {"header", "off", "len", "width", "mode", "size"}. ValueError, wenn die
    Datei nicht abspielbar ist (komprimiertes AIFC, kein Audio)."""
    import chunktags
    st = os.stat(path)
    sig = (os.path.abspath(path), st.st_size, st.st_mtime_ns)
    v = _VIEWS.get(sig[0])
    if v and v["sig"] == sig:
        return v
    try:
        lay = chunktags.read_layout(path)
    except chunktags.ChunkError as ex:
        raise ValueError(str(ex)) from ex
    if lay["kind"] != "aiff":
        raise ValueError("keine AIFF-Datei")
    comm, ssnd = chunktags._find(lay, b"COMM"), chunktags._find(lay, b"SSND")
    if comm is None or ssnd is None:
        raise ValueError("AIFF ohne Audiodaten")
    d = chunktags._read(path, comm)
    ch, frames, bits = struct.unpack(">HIH", d[:8])
    rate = int(round(chunktags._ext80(d[8:18])))
    comp = d[18:22] if lay["form"] == b"AIFC" and len(d) >= 22 else b"NONE"
    if comp not in _AIFC:
        raise ValueError(f"AIFC-Kompression {comp.decode('latin-1').strip()} wird nicht abgespielt")
    order, fmt = _AIFC[comp]
    if comp in (b"fl32", b"FL32"):
        bits = 32
    elif comp in (b"fl64", b"FL64"):
        bits = 64
    width = (bits + 7) // 8
    if not (ch and rate and width):
        raise ValueError("AIFF-Angaben unvollständig")
    with open(path, "rb") as fh:
        fh.seek(ssnd["data_start"])
        offset = struct.unpack(">I", fh.read(4))[0]
    off = ssnd["data_start"] + 8 + offset
    avail = max(0, min(ssnd["data_start"] + ssnd["size"], ssnd["end"]) - off)
    block = ch * width
    n = min(avail, frames * block) // block * block
    mode = "u8" if width == 1 and order != "u8" else "copy" if order in ("le", "u8") or width == 1 else "swap"
    header = (b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE" + b"fmt " + struct.pack("<IHHIIHH", 16, fmt, ch, rate,
              rate * block, block, width * 8) + b"data" + struct.pack("<I", n))
    v = {"sig": sig, "header": header, "off": off, "len": n, "width": width, "mode": mode, "size": len(header) + n}
    _VIEWS[sig[0]] = v
    if len(_VIEWS) > 50:
        _VIEWS.pop(next(iter(_VIEWS)))
    return v


_U8 = bytes((i + 128) & 255 for i in range(256))


def aiff_read(path: str, v: dict, start: int, end: int) -> bytes:
    """Bytes start..end (einschliesslich) der virtuellen WAV-Datei."""
    out = b""
    hl = len(v["header"])
    if start < hl:
        out = v["header"][start:min(end + 1, hl)]
        start = hl
    if start > end or start >= v["size"]:
        return out
    w = v["width"]
    a, b = start - hl, min(end, v["size"] - 1) - hl + 1          # Bereich in den Audiodaten
    a0 = a - a % w                                               # auf ganze Samples ausrichten
    b0 = min(v["len"], b + (-b % w))
    with open(path, "rb") as fh:
        fh.seek(v["off"] + a0)
        raw = fh.read(b0 - a0)
    if v["mode"] == "swap":
        buf = bytearray(len(raw))
        for i in range(w):
            buf[i::w] = raw[w - 1 - i::w]
        raw = bytes(buf)
    elif v["mode"] == "u8":
        raw = raw.translate(_U8)
    return out + raw[a - a0:b - a0]


def _plain(h, code, text):
    body = text.encode()
    h.send_response(code)
    h.send_header("Content-Type", "text/plain")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def _range_error(h, size):
    h.send_response(416)
    h.send_header("Content-Range", f"bytes */{size}")
    h.send_header("Content-Length", "0")
    h.end_headers()


SERVER = MediaServer()
