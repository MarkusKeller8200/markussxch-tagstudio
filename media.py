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
import threading
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AUDIO_TYPES = {".mp3": "audio/mpeg", ".flac": "audio/flac", ".wav": "audio/wav", ".m4a": "audio/mp4",
               ".aac": "audio/aac", ".ogg": "audio/ogg", ".opus": "audio/ogg", ".aif": "audio/aiff", ".aiff": "audio/aiff"}
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
        size = os.path.getsize(path)
        ctype = AUDIO_TYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
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
        h.send_header("Access-Control-Allow-Origin", "*")
        if status == 206:
            h.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        h.end_headers()
        if head:
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
