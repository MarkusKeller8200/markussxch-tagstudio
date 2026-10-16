"""Beatgrid-Status je Titel für die ganze Bibliothek (#191) – ohne Audio zu dekodieren.

Quellen, in dieser Reihenfolge:
- ``serato``  Raster aus Serato (GEOB „Serato BeatGrid“) – übernommen, nicht automatisch musikalisch geprüft
- ``tag``     eigene Analyse, dauerhaft im MP3 gespeichert (TXXX:TAGSTUDIO_BEATGRID, #221)
- ``analyse`` eigene Audioanalyse im Wellenform-Cache (BPM + erster Schlag, konstantes Tempo)
- ``bpm``     nur BPM-Tag (TBPM) – daraus geschätzt, **kein** Raster
- ``nobeat``  Audio wurde analysiert, aber kein Schlag gefunden (und kein BPM-Tag)
- ``none``    nichts davon
Nur lesen: weder Tags noch Raster werden geschrieben. Nur Standardbibliothek.
"""
from __future__ import annotations

import os

CODES = ("serato_ok", "serato_diff", "serato", "tag", "analyse", "bpm", "nobeat", "none")
LABEL = {"serato_ok": "Serato ✓", "serato_diff": "Serato ≠ Analyse", "serato": "Serato", "tag": "Analyse (Tag)",
         "analyse": "Analyse", "bpm": "nur BPM", "nobeat": "ohne Ergebnis", "none": "keins"}
TEMPO_TOL = 0.001          # 0,1 %
OFFSET_TOL = 0.020         # 20 ms


def _de(x: float, nd: int = 1) -> str:
    return f"{x:.{nd}f}".replace(".", ",")


def compare(serato_grid: dict, own: dict) -> tuple[bool, str]:
    """#223: Serato-Raster mit eigener Analyse vergleichen → (stimmt überein, Hinweis). Nur der erste Serato-Marker;
    bei Tempowechseln mit Hinweis. Die eigene Analyse kennt nur konstantes Tempo und keinen Taktanfang."""
    s_bpm, s_first = float(serato_grid["bpm"]), float(serato_grid.get("first") or 0)
    o_bpm, o_first = float(own["bpm"]), float(own.get("first") or 0)
    if s_bpm <= 0 or o_bpm <= 0:
        return False, "kein Vergleich möglich"
    multi = len(serato_grid.get("markers") or []) > 1
    tail = " (Serato mit Tempowechsel – nur der Anfang verglichen)" if multi else ""
    r = o_bpm / s_bpm
    if abs(r - 2) <= 2 * TEMPO_TOL or abs(r - 0.5) <= 0.5 * TEMPO_TOL:
        return False, f"Serato {_de(s_bpm)} BPM, Analyse {_de(o_bpm)} BPM – {'halbes' if r > 1 else 'doppeltes'} Tempo in Serato{tail}"
    if abs(r - 1) > TEMPO_TOL:
        return False, f"Tempo weicht ab: Serato {_de(s_bpm, 2)} BPM, Analyse {_de(o_bpm, 2)} BPM{tail}"
    period = 60.0 / s_bpm
    d = (o_first - s_first) % period
    d = min(d, period - d)
    if d > OFFSET_TOL:
        return False, f"Tempo gleich ({_de(s_bpm, 2)} BPM), erster Schlag {round(d * 1000)} ms versetzt{tail}"
    return True, f"Serato und Analyse stimmen überein ({_de(s_bpm, 2)} BPM, Abstand {round(d * 1000)} ms){tail}"


def own_beat(f) -> dict | None:
    """Eigene Analyse: im MP3 (TXXX:TAGSTUDIO_BEATGRID) oder im Wellenform-Cache."""
    import beattag
    import waveform
    bt = beattag.of_file(f)
    if bt:
        return {**bt, "from": "tag"}
    try:
        key = waveform.key_for(f)
        wave = waveform.load(key) if os.path.exists(waveform._file(key)) else None
    except (OSError, ValueError):
        wave = None
    if wave and wave.get("beat"):
        return {**wave["beat"], "from": "cache"}
    return {"nobeat": True} if wave else None


def serato_grid(f) -> dict | None:
    import serato
    try:
        bg = serato.of_file(f).get("BeatGrid")
    except Exception:  # noqa: BLE001 – fehlerhafte Serato-Daten zählen wie keine
        bg = None
    return bg if bg and not bg.get("error") and bg.get("bpm") and bg.get("markers") else None


def detail(f) -> tuple[str, str]:
    """→ (Code, Hinweis). Liest nur Tags und Cache."""
    import tagger
    sg, own = serato_grid(f), own_beat(f)
    if sg:
        if own and own.get("bpm"):
            ok, note = compare(sg, own)
            return ("serato_ok" if ok else "serato_diff"), note
        return "serato", ""
    if own and own.get("bpm"):
        return ("tag" if own.get("from") == "tag" else "analyse"), ""
    try:
        bpm = float(tagger.text_of(f, "TBPM").replace(",", ".") or 0)
    except ValueError:
        bpm = 0
    if 40 <= bpm <= 300:
        return "bpm", ""
    return ("nobeat" if own else "none"), ""


def status(f) -> str:
    return detail(f)[0]
