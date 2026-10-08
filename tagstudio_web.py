#!/usr/bin/env python3
"""
MarKusSXCH TagStudio – Web-Oberfläche.

Zeigt die Oberfläche aus dem Ordner web/ in einem eigenen App-Fenster (pywebview). Die Arbeit macht
derselbe Python-Kern wie bei der klassischen Oberfläche (session.py → core.py, id3tags.py …).

Ist pywebview nicht installiert (oder mit --browser), läuft die Oberfläche stattdessen im
Standard-Browser über einen lokalen Server (nur 127.0.0.1, mit Zugangsschlüssel).

    python tagstudio_web.py [links] [rechts] [--browser] [--port N] [--no-open]
"""
from __future__ import annotations

import json
import mimetypes
import os
import secrets
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, quote

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from session import Session  # noqa: E402

APP = "MarKusSXCH TagStudio"
WEB = os.path.join(HERE, "web")


class Api:
    """Alle Funktionen, die die Oberfläche aufrufen darf (öffentliche Methoden)."""

    def __init__(self, start_paths=None):
        self._s = Session()
        self._window = None
        self._start = start_paths or []

    # ---------- Sitzung
    def settings(self):
        st = self._s.settings()
        st["start_paths"] = self._start
        st["native"] = self._window is not None
        return st

    def set_option(self, name, value):
        return self._s.set_option(name, value)

    def set_ui(self, name, value):
        return self._s.set_ui(name, value)

    def unsaved(self):
        return self._s.unsaved()

    def start_load(self, lp, rp, recursive=False, mode="filename", keep_current=False):
        return self._s.start_load(lp, rp, bool(recursive), mode, bool(keep_current))

    def start_save(self):
        return self._s.start_save()

    def task_status(self):
        return self._s.task_status()

    def cancel_task(self):
        return self._s.cancel_task()

    def pair_rows(self):
        return self._s.pair_rows()

    def filter_pairs(self, query="", key=None, op="enthält", val="", side="links oder rechts"):
        return self._s.filter_pairs(query, key, op, val, side)

    def field_choices(self):
        return self._s.field_choices()

    def select(self, i):
        return self._s.select(None if i is None else int(i))

    def state(self):
        return self._s.state()

    # ---------- Ändern
    def copy_keys(self, keys, direction):
        return self._s.copy_keys(list(keys), direction)

    def copy_all(self, direction, delete_missing=None):
        return self._s.copy_all(direction, delete_missing)

    def copy_missing(self, direction):
        return self._s.copy_missing(direction)

    def remove(self, side, keys):
        return self._s.remove(side, list(keys))

    def set_value(self, side, key, text):
        return self._s.set_value(side, key, text)

    def revert_pair(self):
        return self._s.revert_pair()

    def undo(self):
        return self._s.do_undo()

    def redo(self):
        return self._s.do_redo()

    # ---------- System
    def pick_path(self, side, folder=True, start=""):
        """Ordner- bzw. Dateiauswahl des Betriebssystems. Liefert den Pfad oder ''."""
        start = start if start and os.path.isdir(start) else (os.path.dirname(start) if start else os.path.expanduser("~"))
        if self._window is not None:
            import webview
            kind = webview.FOLDER_DIALOG if folder else webview.OPEN_DIALOG
            types = () if folder else ("MP3-Dateien (*.mp3;*.MP3)", "Alle Dateien (*.*)")
            res = self._window.create_file_dialog(kind, directory=start, file_types=types)
            if not res:
                return ""
            return os.path.normpath(res[0] if isinstance(res, (list, tuple)) else res)
        return _tk_pick(folder, start)

    def open_url(self, url):
        if url.lower().startswith("www."):
            url = "https://" + url
        if url.lower().startswith(("http://", "https://")):
            webbrowser.open(url)
        return True

    def reveal(self, path):
        """Datei im Explorer/Finder zeigen."""
        if not path or not os.path.exists(path):
            return False
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])
        return True


def _tk_pick(folder, start):
    """Rückfall für den Browser-Modus: Dialog über tkinter (falls vorhanden)."""
    result = {"p": ""}

    def run():
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            if folder:
                p = filedialog.askdirectory(initialdir=start, title="Ordner wählen", parent=root)
            else:
                p = filedialog.askopenfilename(initialdir=start, title="MP3-Datei wählen", parent=root,
                                               filetypes=[("MP3-Dateien", "*.mp3 *.MP3"), ("Alle Dateien", "*")])
            root.destroy()
            result["p"] = os.path.normpath(p) if p else ""
        except Exception:  # noqa: BLE001
            result["p"] = ""
    if sys.platform == "darwin":  # Tk muss auf macOS im Hauptthread laufen – im Browser-Modus nicht möglich
        return ""
    t = threading.Thread(target=run)
    t.start()
    t.join()
    return result["p"]


# =========================================================================== Browser-Modus (lokaler Server)
def make_server(api: Api, port: int = 0):
    """Lokaler HTTP-Server: liefert web/ aus und nimmt API-Aufrufe unter POST /api/<name> entgegen."""
    token = secrets.token_urlsafe(24)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # ruhig bleiben
            pass

        def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            path = urlparse(self.path).path
            if path in ("", "/"):
                path = "/index.html"
            full = os.path.normpath(os.path.join(WEB, path.lstrip("/")))
            if not full.startswith(WEB + os.sep) or not os.path.isfile(full):
                return self._send(404, b"not found", "text/plain")
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript",):
                ctype += "; charset=utf-8"
            with open(full, "rb") as fh:
                self._send(200, fh.read(), ctype)

        def do_POST(self):  # noqa: N802
            path = urlparse(self.path).path
            if not path.startswith("/api/") or self.headers.get("X-Token") != token:
                return self._send(403, b'{"error":"forbidden"}')
            name = path[5:]
            fn = getattr(api, name, None)
            if name.startswith("_") or not callable(fn):
                return self._send(404, b'{"error":"unknown"}')
            try:
                n = int(self.headers.get("Content-Length") or 0)
                args = json.loads(self.rfile.read(n) or b"[]")
                res = fn(*args)
                body = json.dumps({"ok": True, "result": res}, ensure_ascii=False).encode("utf-8")
                self._send(200, body)
            except Exception as ex:  # noqa: BLE001
                self._send(500, json.dumps({"ok": False, "error": str(ex)}, ensure_ascii=False).encode("utf-8"))

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    return srv, token


def run_browser(api: Api, port=0, open_browser=True):
    srv, token = make_server(api, port)
    url = f"http://127.0.0.1:{srv.server_address[1]}/index.html#token={quote(token)}"
    print(f"{APP} läuft im Browser: {url}\n(Fenster offen lassen; Beenden mit Strg+C)")
    if open_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


# =========================================================================== App-Fenster (pywebview)
def run_window(api: Api):
    import webview
    win = webview.create_window(APP, url=os.path.join(WEB, "index.html"), js_api=api,
                                width=1440, height=920, min_size=(1000, 640), background_color="#121419")
    api._window = win

    def on_closing():
        n = api.unsaved()
        if not n:
            return True
        return win.create_confirmation_dialog(
            APP, f"{n} Datei(en) haben ungespeicherte Änderungen.\n\nTrotzdem beenden? (Änderungen gehen verloren)")
    try:
        win.events.closing += on_closing
    except Exception:  # noqa: BLE001 – ältere pywebview-Versionen
        pass
    webview.start()
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    browser = "--browser" in argv
    no_open = "--no-open" in argv
    port = 0
    if "--port" in argv:
        i = argv.index("--port")
        port = int(argv[i + 1])
        del argv[i:i + 2]
    paths = [a for a in argv if not a.startswith("--")][:2]
    api = Api(paths)
    if not browser:
        try:
            import webview  # noqa: F401
        except ImportError:
            print("pywebview ist nicht installiert – die Oberfläche öffnet sich im Browser.\n"
                  "Für ein eigenes Fenster: python -m pip install pywebview")
            browser = True
    if browser:
        return run_browser(api, port, not no_open)
    return run_window(api)


if __name__ == "__main__":
    sys.exit(main())
