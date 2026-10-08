"""MarKusSXCH TagStudio – Audio-Merkmale (Energy, Danceability …) als TXXX-Felder mit Werten 0–100.

Gelesen wird ohne Rücksicht auf Gross-/Kleinschreibung der Beschreibung (TXXX:Energy = TXXX:ENERGY),
geschrieben immer in Grossbuchstaben; abweichend geschriebene Doppel werden dabei entfernt.
"""
import re

# (Name im Tag, Anzeige, Erklärung)
FEATURES = [
    ("ENERGY", "Energy", "Energie, Intensität"),
    ("DANCEABILITY", "Danceability", "Tanzbarkeit"),
    ("HAPPINESS", "Happiness", "Fröhlichkeit"),
    ("VALENCE", "Valence", "positive Stimmung"),
    ("ACOUSTICNESS", "Acousticness", "akustisch statt elektronisch"),
    ("INSTRUMENTALNESS", "Instrumentalness", "ohne Gesang"),
    ("LIVENESS", "Liveness", "Live-Charakter, Publikum"),
    ("SPEECHINESS", "Speechiness", "Sprachanteil"),
    ("BRIGHTNESS", "Brightness", "Klanghelligkeit"),
    ("AGGRESSIVENESS", "Aggressiveness", "Aggressivität"),
]
NAMES = [n for n, _l, _d in FEATURES]
KEYS = {n: f"TXXX:{n}" for n in NAMES}


def find_keys(f, name) -> list[str]:
    """Alle Schlüssel der Datei, die zu diesem Merkmal gehören (beliebige Schreibweise)."""
    want = f"TXXX:{name}".upper()
    return [k for k in f.items if k.upper() == want]


def get(f, name) -> str:
    """Wert als Text (bevorzugt die Grossbuchstaben-Variante)."""
    ks = find_keys(f, name)
    if not ks:
        return ""
    k = KEYS[name] if KEYS[name] in ks else ks[0]
    it = f.get(k)
    return it.text.strip() if it is not None and it.kind not in ("picture", "raw") else ""


def number(text):
    """Text → int 0–100 oder None. Versteht 78, 78.4, 0.78 (Anteil), „78 %“."""
    if text is None:
        return None
    s = str(text).strip().replace(",", ".").rstrip("%").strip()
    if not s:
        return None
    if not re.fullmatch(r"-?\d+(\.\d+)?", s):
        return None
    v = float(s)
    if "." in s and 0 <= v <= 1:      # 0.78 → 78
        v *= 100
    if v < 0 or v > 100:
        return None
    return int(round(v))


def normalize(text) -> str:
    """Eingabe → gespeicherter Text ('' = entfernen). ValueError bei ungültigen Werten."""
    if text is None or str(text).strip() == "":
        return ""
    n = number(text)
    if n is None:
        raise ValueError(f"„{text}“ ist kein Wert zwischen 0 und 100.")
    return str(n)


def set_value(f, name, value) -> bool:
    """Setzt ein Merkmal (leer = entfernen). Liefert True bei Änderung."""
    val = normalize(value)
    key = KEYS[name]
    changed = False
    for k in find_keys(f, name):          # andere Schreibweisen aufräumen
        if k != key:
            f.set(k, None)
            changed = True
    it = f.get(key)
    cur = it.text if it is not None else ""
    if val == "":
        if it is not None:
            f.set(key, None)
            changed = True
    elif cur != val:
        f.set_text(key, val)
        changed = True
    return changed


def common(files) -> dict:
    """Je Merkmal: {"value": "78" | "", "mixed": bool, "num": 78 | None}."""
    out = {}
    for name in NAMES:
        vals = {get(f, name) for f in files}
        v = vals.pop() if len(vals) == 1 else ""
        out[name] = {"value": v, "mixed": len(vals) > 0, "num": number(v)}
    return out


def values(f) -> dict:
    """Werte einer Datei als Zahlen (fehlend/ungültig = None)."""
    return {name: number(get(f, name)) for name in NAMES}
