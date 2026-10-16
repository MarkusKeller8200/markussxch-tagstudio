"""Beatgrid der eigenen Analyse im MP3 (#221): ``TXXX:TAGSTUDIO_BEATGRID``.

Wert als lesbarer Text, z. B. ``bpm=124.998; first=0.1234; conf=0.87; src=analyse; date=2026-10-17`` – nur das Raster
(BPM, erster Schlag, Sicherheit), nicht die Wellenform. Geschrieben nur auf ausdrücklichen Befehl („Beatgrid in Tag
speichern …“); ein Serato-Raster hat immer Vorrang. Nur Standardbibliothek.
"""
from __future__ import annotations

import datetime
import re

KEY = "TXXX:TAGSTUDIO_BEATGRID"


def fmt(beat: dict, date: str | None = None) -> str:
    bpm, first = float(beat["bpm"]), float(beat["first"])
    if not (40 <= bpm <= 300 and 0 <= first < 60):
        raise ValueError("Raster ausserhalb des gültigen Bereichs")
    conf = beat.get("conf")
    parts = [f"bpm={bpm:.3f}", f"first={first:.4f}"]
    if conf is not None:
        parts.append(f"conf={float(conf):.2f}")
    parts += ["src=analyse", f"date={date or datetime.date.today().isoformat()}"]
    return "; ".join(parts)


def parse(text: str) -> dict | None:
    """Text → {"bpm", "first", "conf", "src", "date"} oder None (ungültig/leer)."""
    d = {}
    for m in re.finditer(r"(\w+)\s*=\s*([^;]+)", str(text or "")):
        d[m.group(1).lower()] = m.group(2).strip()
    try:
        bpm, first = float(d["bpm"]), float(d["first"])
        conf = float(d["conf"]) if "conf" in d else None
    except (KeyError, ValueError):
        return None
    if not (40 <= bpm <= 300 and 0 <= first < 60):
        return None
    return {"bpm": bpm, "first": first, "conf": conf, "src": d.get("src", ""), "date": d.get("date", "")}


def of_file(f) -> dict | None:
    return parse(f.text(KEY))
