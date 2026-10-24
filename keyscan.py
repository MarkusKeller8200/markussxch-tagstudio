"""MarKusSXCH TagStudio – Tonart-Erkennung mit OpenKeyScan (#217, #244, #245): gemeinsamer Teil beider Plugins.

Beide Wege liefern dasselbe Ergebnis – einen Camelot-Code je Datei:
  • Plugin „keyscan“ (#245): eigene Analyse in einer eigenen Python-Umgebung (MIT-Engine von Rekordcloud)
  • Plugin „openkeyscan“ (#244): über die lokale REST-API der OpenKeyScan-Desktop-App

Hier: Zwischenspeicher der Ergebnisse (je Datei mit Grösse und Änderungszeit), Vergleich mit schon vorhandenen
Tonarten und die Vorschläge für die Vorschau. Geschrieben wird nie direkt – nur nach Bestätigung in der Vorschau:
  TXXX:OPENKEYSCAN_KEY   Camelot (z. B. 09A), Herkunft „OpenKeyScan“
  TKEY                   optional, in der eingestellten Schreibweise; nur angehakt, wenn TKEY leer ist
Nur Standardbibliothek.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time

import keys

FIELD = "TXXX:OPENKEYSCAN_KEY"
SOURCE = "OpenKeyScan"
_KEY_START = re.compile(r"^\s*(0?(?:1[0-2]|[1-9])\s*[ABab]|[A-G][#b]?m?)\b")

# Bezeichnungen für die Vorschau
REL_TEXT = {"same": "gleich", "related": "verwandt", "different": "abweichend"}


def notation() -> str:
    try:
        import core
        return core.load_config().get("key_notation", "camelot") or "camelot"
    except Exception:  # noqa: BLE001
        return "camelot"


def code_of(value) -> str | None:
    """Camelot-Code ('9A') aus einer Engine-Antwort (Camelot, Open Key oder Tonartname) – sonst None."""
    if value is None:
        return None
    if isinstance(value, dict):
        for k in ("camelot", "openkey", "analyzedKey", "analyzed_key", "detectedKey", "detected_key", "key", "result"):
            c = code_of(value.get(k))
            if c:
                return c
        return None
    s = str(value).strip()
    if not s:
        return None
    s = re.sub(r"\s+(major|dur)$", "", s, flags=re.I)                 # „C major“ → „C“
    s = re.sub(r"\s+(minor|moll)$", "m", s, flags=re.I)              # „E minor“ → „Em“
    return keys.parse_key(s.split("/")[0].strip())


# =========================================================================== Zwischenspeicher
class Cache:
    """Ergebnisse je Datei (Pfad + Grösse + Änderungszeit) – damit ein zweiter Lauf nicht neu analysiert."""

    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
            self.data = d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            self.data = {}

    @staticmethod
    def _id(path):
        return os.path.normcase(os.path.abspath(path))

    @staticmethod
    def _stamp(path):
        try:
            st = os.stat(path)
            return st.st_size, int(st.st_mtime)
        except OSError:
            return None

    def get(self, path) -> dict | None:
        e = self.data.get(self._id(path))
        stamp = self._stamp(path)
        if not e or stamp is None or [e.get("size"), e.get("mtime")] != list(stamp):
            return None
        return e

    def put(self, path, code, conf=None, engine="", key_name=""):
        stamp = self._stamp(path)
        if stamp is None or not code:
            return
        with self.lock:
            self.data[self._id(path)] = {"size": stamp[0], "mtime": stamp[1], "camelot": code,
                                         "conf": None if conf is None else round(float(conf), 3),
                                         "engine": engine, "key": key_name, "at": time.strftime("%Y-%m-%d")}

    def restamp(self, path):
        """Ergebnis an den aktuellen Dateistand binden (die Datei wurde von aussen geändert, z. B. Auto-Tagging)."""
        e, stamp = self.data.get(self._id(path)), self._stamp(path)
        if e and stamp:
            with self.lock:
                e["size"], e["mtime"] = stamp

    def save(self):
        with self.lock:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False)
            os.replace(tmp, self.path)


# =========================================================================== Vergleich
def known_keys(f) -> list[tuple[str, str]]:
    """Schon vorhandene Tonarten einer Datei: [(Quelle, Camelot-Code)]."""
    t = f.text
    out = []
    for key, label in (("TKEY", "TKEY"), ("TXXX:INITIAL_KEY", "Beatport"), (FIELD, "OpenKeyScan bisher")):
        c = keys.parse_key(t(key)) if t(key) else None
        if c:
            out.append((label, c))
    for k in [k for k in f.items if k.startswith("COMM")]:
        m = _KEY_START.match(t(k) or "")
        c = keys.parse_key(m.group(1)) if m else None
        if c and ("Kommentar (MIK)", c) not in out:
            out.append(("Kommentar (MIK)", c))
            break
    return out


def relation(a: str, b: str) -> str:
    """same = gleich, related = harmonisch verwandt (±1 auf dem Rad, Paralleltonart), different = abweichend."""
    if a == b:
        return "same"
    return "related" if b in keys.compatible(a) else "different"


def propose(ctx, f, code: str, conf=None, key_name="", want_tkey=True, force_tkey=False) -> str:
    """Vorschläge für eine Datei. → Vergleich mit TKEY: "none" (leer), "same", "related" oder "different"."""
    nota = notation()
    known = known_keys(f)
    parts = [f"OpenKeyScan: {keys.format_key(code, 'camelot')} ({keys.format_key(code, 'musical')})"]
    if conf is not None:
        parts.append(f"Sicherheit {round(100 * float(conf))} %")
    for label, c in known:
        if label != "OpenKeyScan bisher":
            parts.append(f"{label}: {keys.format_key(c, nota)} – {REL_TEXT[relation(code, c)]}")
    note = " · ".join(parts)
    group = os.path.basename(f.path)
    ctx.propose(f, FIELD, keys.format_key(code, "camelot"), "Tonart (OpenKeyScan)", note=note, group=group)
    tk = next((c for label, c in known if label == "TKEY"), None)
    rel = "none" if tk is None else relation(code, tk)
    if want_tkey:
        hint = "" if tk is None else f"TKEY hat schon {keys.format_key(tk, nota)} ({REL_TEXT[rel]})"
        ctx.propose(f, "TKEY", keys.format_key(code, nota), "Tonart", note=note, group=group, hint=hint,
                    checked=tk is None or (force_tkey and rel != "same"))
    return rel


def summary(stats: dict) -> str:
    """Kurzfassung für die Meldung nach dem Lauf."""
    bits = []
    if stats.get("none"):
        bits.append(f"{stats['none']} ohne Tonart")
    for k in ("same", "related", "different"):
        if stats.get(k):
            bits.append(f"{stats[k]} {REL_TEXT[k]}")
    return ", ".join(bits)
