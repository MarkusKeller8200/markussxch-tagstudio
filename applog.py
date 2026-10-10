"""App-Protokoll (4.1.0, #133): Start/Ende, Fehler und Warnungen nach ~/TagStudio/Logs/app.log.

Bewusst klein: eine Datei, bei 1 MB wird sie zu app.log.1 (eine Vorgängerdatei). Es werden nie Argumente von
Aufrufen protokolliert – nur Name und Fehlermeldung –, damit keine Schlüssel oder Pfade mit Passwörtern hineingeraten.
"""
from __future__ import annotations

import datetime
import os
import sys
import threading
import traceback

MAX_BYTES = 1_000_000
NAME = "app.log"
_lock = threading.Lock()
_SECRET_WORDS = ("token", "password", "passwort", "secret", "api_key", "apikey")


def log_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), "TagStudio", "Logs")
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
