"""Mehrsprachigkeit (#157): Sprachen und Kataloge der Oberfläche.

Ausgangssprache ist Schweizer Hochdeutsch (``de-CH``) – so steht der Text im Code. Die Kataloge liegen je Modul in
``web/i18n/<modul>.json``: deutscher Text (Schlüssel) → ``[Englisch, Zürichdeutsch]`` (Reihenfolge wie ``COLUMNS``) –
so steht jeder Text mit allen Übersetzungen beisammen. Platzhalter: ``{n}`` Zahl, ``{q}`` Text in
Anführungszeichen, ``{x}`` beliebiger eingesetzter Text (wird seinerseits übersetzt). Übersetzt wird in der Oberfläche
(``web/i18n.js``); MP3-Tags werden nie übersetzt. Nur Standardbibliothek.
"""
from __future__ import annotations

import json
import os
import threading

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
DIR = os.path.join(WEB, "i18n")
SOURCE = "de-CH"
# (Code nach BCP 47, Name in der eigenen Sprache, Flagge, Name auf Deutsch)
LANGS = [
    ("de-CH", "Deutsch (Schweiz)", "🇨🇭", "Hochdeutsch (Schweiz)"),
    ("en", "English", "🇬🇧", "Englisch"),
    ("gsw-u-sd-chzh", "Züritüütsch", "🦁", "Zürichdeutsch"),
]
CODES = tuple(c for c, *_ in LANGS)
COLUMNS = ("en", "gsw-u-sd-chzh")            # Spalten in den Katalogdateien
_lock = threading.Lock()
_cache: dict[str, tuple[tuple, dict]] = {}


def _files() -> list[str]:
    try:
        return sorted(os.path.join(DIR, f) for f in os.listdir(DIR) if f.endswith(".json") and not f.startswith("_")
                      and f != "ignore.json")
    except OSError:
        return []


def catalog(lang: str) -> dict[str, str]:
    """Mitgelieferter Katalog einer Sprache (alle Dateien zusammengeführt, zwischengespeichert je Änderungszeit)."""
    if lang not in CODES or lang == SOURCE:
        return {}
    files, col = _files(), COLUMNS.index(lang)
    stamp = tuple((f, os.path.getmtime(f)) for f in files)
    with _lock:
        hit = _cache.get(lang)
        if hit and hit[0] == stamp:
            return hit[1]
    out: dict[str, str] = {}
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        for k, v in d.items():
            if isinstance(k, str) and isinstance(v, list) and len(v) > col and isinstance(v[col], str) and v[col]:
                out[k] = v[col]
    with _lock:
        _cache[lang] = (stamp, out)
    return out


def detect(accept: str | None) -> str:
    """Sprache aus der System-/Browsersprache (erster Start): en… → en, gsw… → Zürichdeutsch, sonst de-CH."""
    a = (accept or "").strip().lower()
    if a.startswith("gsw"):
        return "gsw-u-sd-chzh"
    if a.startswith("de") or not a:
        return SOURCE
    return "en"


def langs() -> list[dict]:
    return [{"code": c, "name": n, "flag": f, "de": d} for c, n, f, d in LANGS]
