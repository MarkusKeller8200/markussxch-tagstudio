"""Eigene Wellenform im MP3 (#222, Entscheid W1): GEOB „TagStudio Overview“.

Nur auf Wunsch (Einstellung „Wellenform im MP3 speichern“, Standard aus): beim Speichern legt TagStudio die Wellenform
aus dem Cache (``waveform.py``) als eigenes GEOB in der Datei ab – dann reist sie mit der Datei und übersteht das
Leeren des Caches. Serato-Felder („Serato Overview“ & Co.) werden nie gelesen, verändert oder ersetzt.

Daten (binär, klein – rund 1.6 KB bei 800 Werten)::

    b"TSOV" · Version 1 · Anzahl n (2 Byte, big endian) · n Spitzenwerte · n RMS-Werte (je 0–255)

Nur Standardbibliothek.
"""
from __future__ import annotations

DESC = "TagStudio Overview"
KEY = f"GEOB:{DESC}"
MAGIC = b"TSOV"
VERSION = 1
MIME = "application/octet-stream"


def encode(peaks, rms) -> bytes:
    """Wellenform → Daten des GEOB (prüft Länge und Wertebereich wie der Cache)."""
    if not isinstance(peaks, (list, tuple, bytes)) or not isinstance(rms, (list, tuple, bytes)):
        raise ValueError("Spitzen- und RMS-Werte erwartet")
    p, r = bytes(peaks), bytes(rms)
    if len(p) != len(r) or not 16 <= len(p) <= 4000:
        raise ValueError("16–4000 Werte, Spitzen und RMS gleich lang")
    return MAGIC + bytes([VERSION]) + len(p).to_bytes(2, "big") + p + r


def decode(data: bytes) -> dict | None:
    """Daten des GEOB → {"peaks", "rms"} oder None (fremdes oder beschädigtes Format)."""
    if not data or len(data) < 7 or data[:4] != MAGIC or data[4] != VERSION:
        return None
    n = int.from_bytes(data[5:7], "big")
    if not 16 <= n <= 4000 or len(data) < 7 + 2 * n:
        return None
    return {"peaks": list(data[7:7 + n]), "rms": list(data[7 + n:7 + 2 * n])}


def _payload(data: bytes) -> bytes:
    """GEOB-Rahmen: Latin-1, MIME, leerer Dateiname, Beschreibung, Daten."""
    return b"\x00" + MIME.encode("latin-1") + b"\x00" + b"\x00" + DESC.encode("latin-1") + b"\x00" + data


def of_file(f) -> dict | None:
    """Gespeicherte Wellenform aus der geladenen Datei (MP3File) oder None."""
    it = f.get(KEY)
    if it is None or not getattr(it, "payload", None):
        return None
    import blobs
    try:
        return decode(blobs.split(it)["data"])
    except (ValueError, IndexError, KeyError):
        return None


def embed(f, wave: dict | None) -> bool:
    """Wellenform in die Datei übernehmen (noch nicht gespeichert). True = Feld neu bzw. geändert.

    Fasst nur das eigene Feld an; ohne Wellenform passiert nichts (ein vorhandenes Feld bleibt)."""
    if not wave or not wave.get("peaks") or not wave.get("rms"):
        return False
    try:
        data = encode(wave["peaks"], wave["rms"])
    except (ValueError, TypeError):
        return False
    old = f.get(KEY)
    payload = _payload(data)
    if old is not None and getattr(old, "payload", None) == payload:
        return False
    from id3tags import Item
    f.set(KEY, Item("GEOB", KEY, desc=DESC, payload=payload))
    return True


def embed_from_cache(f) -> bool:
    """Vor dem Speichern: Wellenform aus dem Cache in die Datei (nur Dateien, die ohnehin gespeichert werden)."""
    import waveform
    try:
        wave = waveform.load(waveform.key_for(f))
    except (OSError, ValueError):
        return False
    return embed(f, wave)
