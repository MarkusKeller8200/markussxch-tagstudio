"""MarKusSXCH TagStudio – Wellenform-Cache für den Vorschau-Player.

Die Oberfläche berechnet die Wellenform einmal (Web Audio, beim ersten Abspielen) und legt sie hier ab:
~/TagStudio/cache/wave/<xx>/<schlüssel>.json mit Spitzen- und RMS-Werten (je 0–255).
Der Schlüssel hängt nur am **Audioteil** der Datei (Länge + Anfang + Ende ohne Tags) – Tags bearbeiten,
Umbenennen oder Verschieben macht den Cache also nicht ungültig. Nur Standardbibliothek.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time

DIR = os.path.join(os.path.expanduser("~"), "TagStudio", "cache", "wave")
MAX_FILES = 20000
SAMPLE = 64 * 1024


def audio_key(path: str, audio_start: int = 0, audio_end: int | None = None) -> str:
    """Schlüssel aus Audiolänge, ersten und letzten 64 KB des Audioteils."""
    size = os.path.getsize(path)
    end = size if audio_end is None else min(audio_end, size)
    start = max(0, min(audio_start, end))
    h = hashlib.sha1(f"v1:{end - start}:".encode())
    with open(path, "rb") as fh:
        fh.seek(start)
        h.update(fh.read(min(SAMPLE, end - start)))
        if end - start > SAMPLE:
            fh.seek(max(start, end - SAMPLE))
            h.update(fh.read(min(SAMPLE, end - start)))
    return h.hexdigest()[:32]


def key_for(f) -> str:
    """Schlüssel für eine geladene MP3File (Tag am Ende – ID3v1 – bleibt außen vor)."""
    end = f.size - (128 if getattr(f, "had_v1", False) else 0)
    return audio_key(f.path, getattr(f, "audio_start", 0), end)


def _file(key: str) -> str:
    if not key or not all(c in "0123456789abcdef" for c in key):
        raise ValueError("ungültiger Schlüssel")
    return os.path.join(DIR, key[:2], key + ".json")


def load(key: str) -> dict | None:
    try:
        with open(_file(key), encoding="utf-8") as fh:
            d = json.load(fh)
        peaks, rms = base64.b64decode(d["peaks"]), base64.b64decode(d["rms"])
        if len(peaks) != len(rms) or not peaks:
            return None
        return {"peaks": list(peaks), "rms": list(rms)}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _bytes(vals, name) -> bytes:
    if not isinstance(vals, list) or not 16 <= len(vals) <= 4000:
        raise ValueError(f"{name}: 16–4000 Werte erwartet")
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 255 for v in vals):
        raise ValueError(f"{name}: nur ganze Zahlen 0–255")
    return bytes(vals)


def save(key: str, peaks, rms) -> None:
    p, r = _bytes(peaks, "peaks"), _bytes(rms, "rms")
    if len(p) != len(r):
        raise ValueError("peaks und rms unterschiedlich lang")
    fn = _file(key)
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    tmp = fn + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"v": 1, "n": len(p), "peaks": base64.b64encode(p).decode(), "rms": base64.b64encode(r).decode(),
                   "t": int(time.time())}, fh)
    os.replace(tmp, fn)
    if int(key[2:4], 16) == 0:         # ab und zu (1/256) aufräumen
        prune()


def prune(limit: int = MAX_FILES) -> int:
    files = []
    for root, _dirs, names in os.walk(DIR):
        files += [os.path.join(root, n) for n in names if n.endswith(".json")]
    if len(files) <= limit:
        return 0
    files.sort(key=lambda p: os.path.getmtime(p))
    gone = 0
    for p in files[:len(files) - limit]:
        try:
            os.remove(p)
            gone += 1
        except OSError:
            pass
    return gone
