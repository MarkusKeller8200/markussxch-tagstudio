"""Beatgrid-Status je Titel für die ganze Bibliothek (#191) – ohne Audio zu dekodieren.

Quellen, in dieser Reihenfolge:
- ``serato``  Raster aus Serato (GEOB „Serato BeatGrid“) – übernommen, nicht automatisch musikalisch geprüft
- ``analyse`` eigene Audioanalyse im Wellenform-Cache (BPM + erster Schlag, konstantes Tempo)
- ``bpm``     nur BPM-Tag (TBPM) – daraus geschätzt, **kein** Raster
- ``nobeat``  Audio wurde analysiert, aber kein Schlag gefunden (und kein BPM-Tag)
- ``none``    nichts davon
Nur lesen: weder Tags noch Raster werden geschrieben. Nur Standardbibliothek.
"""
from __future__ import annotations

import os

CODES = ("serato", "analyse", "bpm", "nobeat", "none")
LABEL = {"serato": "Serato", "analyse": "Analyse", "bpm": "nur BPM", "nobeat": "ohne Ergebnis", "none": "keins"}


def status(f) -> str:
    import serato
    import tagger
    import waveform
    try:
        bg = serato.of_file(f).get("BeatGrid")
    except Exception:  # noqa: BLE001 – fehlerhafte Serato-Daten zählen wie keine
        bg = None
    if bg and not bg.get("error") and bg.get("bpm") and bg.get("markers"):
        return "serato"
    wave = None
    try:
        key = waveform.key_for(f)
        if os.path.exists(waveform._file(key)):
            wave = waveform.load(key)
    except (OSError, ValueError):
        wave = None
    if wave and wave.get("beat"):
        return "analyse"
    try:
        bpm = float(tagger.text_of(f, "TBPM").replace(",", ".") or 0)
    except ValueError:
        bpm = 0
    if 40 <= bpm <= 300:
        return "bpm"
    return "nobeat" if wave else "none"
