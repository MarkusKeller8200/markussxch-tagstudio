"""App-Protokoll (4.1.0, #133): Start/Ende, Fehler und Warnungen nach ~/TagStudio/Logs/app.log.

Bewusst klein: eine Datei, bei 1 MB wird sie zu app.log.1 (eine Vorgängerdatei). Es werden nie Argumente von
Aufrufen protokolliert – nur Name und Fehlermeldung –, damit keine Schlüssel oder Pfade mit Passwörtern hineingeraten.
"""
from __future__ import annotations

import datetime
import os
import paths
import sys
import threading
import traceback

MAX_BYTES = 1_000_000
NAME = "app.log"
_lock = threading.Lock()
_SECRET_WORDS = ("token", "password", "passwort", "secret", "api_key", "apikey", "authorization", "bearer", "cookie")


def log_dir() -> str:
    d = paths.sub("Logs")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


def path() -> str:
    return os.path.join(log_dir(), NAME)


def _clean(text: str) -> str:
    """Zeilen, die nach Zugangsdaten aussehen, unkenntlich machen."""
    out = []
    for ln in str(text).splitlines():
        low = ln.lower()
        out.append(ln.split(":", 1)[0] + ": •••" if any(w in low for w in _SECRET_WORDS) and ":" in ln else ln)
    return "\n".join(out)


def write(level: str, msg: str):
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {level.upper():5} {_clean(msg).rstrip()}\n"
    with _lock:
        try:
            p = path()
            if os.path.isfile(p) and os.path.getsize(p) > MAX_BYTES:
                os.replace(p, p + ".1")
            with open(p, "a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError:
            pass


def info(msg):
    write("INFO", msg)


def warn(msg):
    write("WARN", msg)


def error(msg, exc: BaseException | None = None):
    if exc is not None:
        msg = f"{msg}\n" + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-4000:]
    write("ERROR", msg)


def install_hooks():
    """Unbehandelte Ausnahmen (Hauptfaden und Hintergrund-Fäden) mitschreiben."""
    old = sys.excepthook

    def hook(t, v, tb):
        error("Unbehandelter Fehler", v.with_traceback(tb) if v is not None else None)
        old(t, v, tb)
    sys.excepthook = hook
    if hasattr(threading, "excepthook"):
        old_t = threading.excepthook

        def thook(args):
            if args.exc_type is not SystemExit:
                error(f"Unbehandelter Fehler im Faden {getattr(args.thread, 'name', '?')}", args.exc_value)
            old_t(args)
        threading.excepthook = thook


def files() -> list[dict]:
    """Alle Protokolle im Log-Ordner (App und Plugins), neueste zuerst – Name, Pfad, Grösse, Änderungszeit."""
    d = log_dir()
    out = []
    try:
        for n in os.listdir(d):
            fp = os.path.join(d, n)
            if os.path.isfile(fp) and not n.startswith("."):
                st = os.stat(fp)
                out.append({"name": n, "path": fp, "size": st.st_size, "mtime": st.st_mtime})
    except OSError:
        pass
    return sorted(out, key=lambda x: -x["mtime"])


def read_from(name: str = "", offset: int = -1, limit: int = 200_000) -> dict:
    """#327: Protokoll fortlaufend lesen (Live-Fenster) – ab Byte offset (-1 = die letzten limit Bytes).
    name: Dateiname im Log-Ordner (Standard app.log). → {name, files, size, offset, text, reset, mtime}"""
    fs = {f["name"]: f for f in files()}
    name = os.path.basename(str(name or ""))
    name = name if name in fs else (NAME if NAME in fs else next(iter(fs), ""))
    res = {"name": name, "files": sorted(fs, key=lambda n: (n != NAME, n.lower())), "size": 0, "offset": 0, "text": "",
           "reset": offset < 0, "mtime": 0.0}
    if name:
        f = fs[name]
        size, res["mtime"] = f["size"], f["mtime"]
        if offset < 0 or offset > size:
            res["reset"] = True
            offset = max(0, size - limit)
        try:
            with open(f["path"], "rb") as fh:
                fh.seek(offset)
                data = fh.read(max(0, size - offset))
        except OSError:
            data = b""
        res.update(size=offset + len(data), offset=offset, text=data.decode("utf-8", "replace"))
    return res


def clear(name: str) -> bool:
    """#329: Protokoll im Log-Ordner leeren (nicht löschen) – nur Dateien direkt im Log-Ordner."""
    fs = {f["name"]: f for f in files()}
    name = os.path.basename(str(name or ""))
    if name not in fs:
        return False
    with _lock:
        try:
            with open(fs[name]["path"], "w", encoding="utf-8"):
                pass
        except OSError:
            return False
    return True


CLEARED_NOTE = "Protokoll beim letzten Beenden geleert (Entwicklermodus)"


def clear_on_exit(plugins: bool = False) -> list[str]:
    """#332 (Entwicklung): beim Beenden/Neustart app.log und app.log.1 leeren (nicht löschen), auf Wunsch auch die
    Plugin-Protokolle. Update-Protokolle (update*) bleiben – sie schreibt der Installer nach dem Beenden weiter.
    Danach steht als erste Zeile der Hinweis CLEARED_NOTE, damit beim nächsten Start klar ist, warum es kurz ist.
    → Namen der geleerten Dateien"""
    names = []
    for f in files():
        n = f["name"]
        if n == NAME or n.startswith(NAME + "."):
            names.append(n)
        elif plugins and n.endswith(".log") and not n.lower().startswith("update"):
            names.append(n)
    done = [n for n in names if clear(n)]
    write("INFO", CLEARED_NOTE)
    return done


def tail(p: str, limit: int = 200_000) -> str:
    """Ende einer Textdatei (höchstens `limit` Bytes)."""
    try:
        with open(p, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - limit))
            data = fh.read()
    except OSError as ex:
        return f"(nicht lesbar: {ex})"
    text = data.decode("utf-8", errors="replace")
    if size > limit:
        text = "… (gekürzt, nur das Ende)\n" + text.split("\n", 1)[-1]
    return text
