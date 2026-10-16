"""TagStudio-Zeitstempel in den Tags (#184, #185).

- ``TXXX:TAGSTUDIO_EDITED`` – „Letzte Bearbeitung“: Zeitpunkt des letzten erfolgreichen Speicherns GEÄNDERTER Tags durch
  TagStudio (je Datei). Nicht bei Anzeigen, Einlesen, Vorhören oder Speichern ohne Änderung. Rückgängig/Wiederherstellen
  ist ebenfalls ein Speichern → neue Zeit (Entscheid 16.10.2026).
- ``TXXX:TAGSTUDIO_ADDED`` – „In Bibliothek aufgenommen“: Zeitpunkt der ersten Übernahme in die Bibliothek. Einmal
  gesetzt, wird er nie automatisch geändert (nur ausdrücklich durch den Nutzer).

Werte: ISO 8601 mit Zeitzone, sekundengenau, z. B. ``2026-10-16T01:55:00+02:00`` – lesbar und sortierbar auch in
Mp3tag, Lexicon & Co. Eigene TXXX-Felder statt TXXX:TAGSTUDIO-JSON, damit Drittprogramme sie zeigen und filtern können.
"""
from __future__ import annotations

import datetime

EDITED = "TXXX:TAGSTUDIO_EDITED"
ADDED = "TXXX:TAGSTUDIO_ADDED"
KEYS = (EDITED, ADDED)


def now_iso(when: datetime.datetime | None = None) -> str:
    """Zeitpunkt als ISO 8601 mit lokaler Zeitzone (sekundengenau)."""
    t = when or datetime.datetime.now()
    if t.tzinfo is None:
        t = t.astimezone()
    return t.replace(microsecond=0).isoformat()


def parse(text: str) -> datetime.datetime | None:
    """ISO-Text → datetime (mit Zeitzone, falls angegeben); ungültig → None. Nur Datum erlaubt (00:00 Uhr)."""
    s = str(text or "").strip()
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.datetime.fromisoformat(s[:10])
        except ValueError:
            return None


def normalize(text: str) -> str:
    """Eingabe (z. B. „2026-10-16“ oder ISO mit Zeit) einheitlich als ISO mit Zeitzone; ungültig → ValueError."""
    t = parse(text)
    if t is None:
        raise ValueError(f"Ungültiges Datum: {text!r} – erwartet z. B. 2026-10-16 oder 2026-10-16T14:30")
    return now_iso(t)


def stamp_edited(f, when: datetime.datetime | None = None) -> bool:
    """Vor dem Speichern: „Letzte Bearbeitung“ setzen – nur wenn die Datei tatsächlich geänderte Tags hat."""
    if not f.is_modified():
        return False
    f.set_text(EDITED, now_iso(when))
    return True


def set_added(f, when: datetime.datetime | str | None = None, overwrite: bool = False) -> bool:
    """„In Bibliothek aufgenommen“ setzen. Vorhandener Wert bleibt, ausser overwrite=True. True = geändert."""
    if f.text(ADDED) and not overwrite:
        return False
    value = normalize(when) if isinstance(when, str) else now_iso(when)
    if f.text(ADDED) == value:
        return False
    f.set_text(ADDED, value)
    return True
