"""MarKusSXCH TagStudio – Stimmung (Mood) als Feld mit Mehrfachwerten (#12).

Gespeichert wie in Mp3tag (Feldname MOOD): ID3v2.4 → TMOO, ID3v2.3 → TXXX:MOOD (TMOO gibt es in v2.3 nicht).
Gelesen werden beide (TXXX-Beschreibung ohne Rücksicht auf Gross-/Kleinschreibung). Mehrere Stimmungen als
Mehrfachwert (v2.4 null-getrennt, v2.3 mit „ / “); beim Lesen werden auch „;“ und „,“ als Trenner verstanden.
Nur Standardbibliothek.
"""
from __future__ import annotations

import re

from id3tags import MV

# Vorschläge ohne eigene Werte – angelehnt an die Mood-Tags von Lexicon und Mixed In Key
DEFAULTS = ["Aggressive", "Chill", "Dark", "Deep", "Dreamy", "Driving", "Emotional", "Energetic", "Euphoric",
            "Funky", "Groovy", "Happy", "Hypnotic", "Melancholic", "Mysterious", "Peaktime", "Romantic", "Sad",
            "Sexy", "Uplifting", "Warm-up"]
_SPLIT = re.compile(r"\s*(?:\x00|;|,|\s/\s|¦)\s*")


def keys(f) -> list[str]:
    """Vorhandene Mood-Felder der Datei (TMOO, TXXX:MOOD in beliebiger Schreibweise)."""
    return [k for k in f.items if k == "TMOO" or k.upper() == "TXXX:MOOD"]


def key_for(f) -> str:
    return "TMOO" if getattr(f, "version", 3) == 4 else "TXXX:MOOD"


def split(text) -> list[str]:
    out, seen = [], set()
    for v in _SPLIT.split(text or ""):
        v = v.strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out


def values(f) -> list[str]:
    out, seen = [], set()
    for k in sorted(keys(f), key=lambda k: k != key_for(f)):      # bevorzugtes Feld zuerst
        it = f.get(k)
        if it is None or it.kind in ("picture", "raw"):
            continue
        for v in split(it.text):
            if v.lower() not in seen:
                seen.add(v.lower())
                out.append(v)
    return out


def text(f) -> str:
    return " ¦ ".join(values(f))


def set_values(f, vals) -> bool:
    """Stimmungen setzen (leer = entfernen); räumt das jeweils andere Feld auf. → True bei Änderung."""
    vals = split(MV.join(vals))
    key, changed = key_for(f), False
    for k in keys(f):
        if k != key:
            f.set(k, None)
            changed = True
    it = f.get(key)
    new = MV.join(vals)
    if not vals:
        if it is not None:
            f.set(key, None)
            changed = True
    elif it is None or it.text != new:
        f.set_text(key, new)
        changed = True
    return changed


def common(files) -> dict:
    """{"all": in allen Dateien, "some": [[Wert, Anzahl], …] nur in einem Teil}"""
    counts, names = {}, {}
    for f in files:
        for v in values(f):
            counts[v.lower()] = counts.get(v.lower(), 0) + 1
            names.setdefault(v.lower(), v)
    n = len(files)
    return {"all": [names[k] for k in counts if counts[k] == n],
            "some": [[names[k], counts[k]] for k in counts if counts[k] < n]}


def edit(files, add=(), remove=()) -> int:
    """Stimmungen hinzufügen bzw. entfernen (je Datei). → Anzahl geänderter Dateien."""
    add = split(MV.join(add or []))
    rem = {v.lower() for v in split(MV.join(remove or []))}
    n = 0
    for f in files:
        cur = [v for v in values(f) if v.lower() not in rem]
        have = {v.lower() for v in cur}
        cur += [v for v in add if v.lower() not in have]
        if set_values(f, cur):
            n += 1
    return n


def suggestions(files, extra=()) -> list[dict]:
    """Vorschlagsliste: Werte der geladenen Dateien (mit Anzahl, häufigste zuerst), eigene Liste, Vorgaben."""
    counts, names = {}, {}
    for f in files:
        for v in values(f):
            counts[v.lower()] = counts.get(v.lower(), 0) + 1
            names.setdefault(v.lower(), v)
    out = [{"value": names[k], "count": c} for k, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    seen = set(counts)
    for v in list(extra or []) + DEFAULTS:
        if isinstance(v, str) and v.strip() and v.strip().lower() not in seen:
            seen.add(v.strip().lower())
            out.append({"value": v.strip(), "count": 0})
    return out
