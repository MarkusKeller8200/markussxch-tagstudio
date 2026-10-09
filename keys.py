"""MarKusSXCH TagStudio – Tonarten: erkennen, umschreiben (Camelot, musikalisch, Open Key), harmonisch passende
Tonarten fürs Mixen. Nur Standardbibliothek.

Camelot-Rad: Zahl 1–12, A = Moll (innen), B = Dur (aussen). 8B = C-Dur, 8A = a-Moll. Nachbarn (±1) und die
Paralleltonart (gleiche Zahl, anderer Buchstabe) passen harmonisch zusammen.
"""
import re

# Gängige Schreibweise (wie in DJ-Programmen) je Camelot-Code
MAJOR = {1: "B", 2: "F#", 3: "Db", 4: "Ab", 5: "Eb", 6: "Bb", 7: "F", 8: "C", 9: "G", 10: "D", 11: "A", 12: "E"}
MINOR = {1: "Abm", 2: "Ebm", 3: "Bbm", 4: "Fm", 5: "Cm", 6: "Gm", 7: "Dm", 8: "Am", 9: "Em", 10: "Bm",
         11: "F#m", 12: "Dbm"}
NOTATIONS = {"camelot": "Camelot (08A)", "musical": "Musikalisch (Am)", "openkey": "Open Key (1m)"}

_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
# Deutsche Namen (nur bei „Dur“/„Moll“): H = B, B = Bb, Endungen -is (♯) / -es, -s (♭)
_DE = {"c": 0, "cis": 1, "des": 1, "d": 2, "dis": 3, "es": 3, "e": 4, "eis": 5, "fes": 4, "f": 5, "fis": 6,
       "ges": 6, "g": 7, "gis": 8, "as": 8, "a": 9, "ais": 10, "b": 10, "hes": 10, "h": 11, "his": 0, "ces": 11}


def _code(num, minor):
    return f"{num}{'A' if minor else 'B'}"


def _from_pc(pc, minor):
    """Tonhöhenklasse (0 = C) → Camelot-Code."""
    major_pc = (pc + 3) % 12 if minor else pc     # Moll → Paralleltonart in Dur
    for n in range(1, 13):
        if (n - 8) * 7 % 12 == major_pc:
            return _code(n, minor)
    return None


def parse_key(text):
    """Erkennt eine Tonart in fast jeder Schreibweise. Liefert Camelot-Code ('8A') oder None.

    Camelot 8A/08a/8 A · Open Key 1m/1d · Am, A min, A minor, Amaj, C, C#, Db, D♭, F#m · a (klein = Moll)
    · deutsch: a-Moll, Fis-Dur, Es-Dur, H-Moll, B-Dur (= Bb)."""
    if not text:
        return None
    s = str(text).strip().replace("♯", "#").replace("♭", "b").replace("‐", "-")
    if not s:
        return None
    m = re.fullmatch(r"0?(1[0-2]|[1-9])\s*([ABab])", s)
    if m:
        return _code(int(m.group(1)), m.group(2).upper() == "A")
    m = re.fullmatch(r"0?(1[0-2]|[1-9])\s*([mdMD])", s)
    if m:  # Open Key: 1d = C-Dur = 8B
        n = (int(m.group(1)) + 6) % 12 + 1
        return _code(n, m.group(2).lower() == "m")
    m = re.fullmatch(r"([A-Ha-h](?:is|es|s)?)\s*-?\s*(dur|moll)", s, re.I)
    if m:
        pc = _DE.get(m.group(1).lower())
        return None if pc is None else _from_pc(pc, m.group(2).lower() == "moll")
    m = re.fullmatch(r"([A-Ga-g])\s*([#b]?)\s*(m|min|minor|moll|maj|major|dur)?", s, re.I)
    if not m:
        return None
    root, acc, mode = m.group(1), m.group(2), (m.group(3) or "")
    pc = (_PC[root.upper()] + (1 if acc == "#" else -1 if acc == "b" else 0)) % 12
    if mode:
        minor = mode.lower() in ("m", "min", "minor", "moll") and mode not in ("M",)  # „M“ = Major (selten)
    else:
        minor = root.islower()
    return _from_pc(pc, minor)


def split(code):
    """'8A' → (8, True)."""
    return int(code[:-1]), code[-1] == "A"


def format_key(code, notation="camelot"):
    if not code:
        return ""
    n, minor = split(code)
    if notation == "musical":
        return (MINOR if minor else MAJOR)[n]
    if notation == "openkey":
        return f"{(n + 4) % 12 + 1}{'m' if minor else 'd'}"
    return f"{n:02d}{'A' if minor else 'B'}"    # Camelot immer zweistellig: 01A … 12B (sortiert in jeder Liste richtig)


def compatible(code):
    """Harmonisch passende Codes: gleich, ±1 auf dem Rad, Paralleltonart."""
    if not code:
        return []
    n, minor = split(code)
    return [code, _code(n % 12 + 1, minor), _code((n - 2) % 12 + 1, minor), _code(n, not minor)]


def sort_value(code):
    """Sortierung: 1A, 1B, 2A … ; ohne Tonart ans Ende."""
    if not code:
        return 999
    n, minor = split(code)
    return n * 2 - (1 if minor else 0)


def wheel():
    """Alle 24 Tonarten für die Anzeige: [code, musikalisch, Open Key]."""
    return [[c, format_key(c, "musical"), format_key(c, "openkey")]
            for n in range(1, 13) for c in (_code(n, True), _code(n, False))]


def plan_notation(files, notation, text_of):
    """Vorschau zum Umschreiben von TKEY. Liefert (plan, unbekannt): plan = [(f, 'TKEY', alt, neu)],
    unbekannt = [(f, alt)] für Werte, die nicht erkannt wurden."""
    plan, unknown = [], []
    for f in files:
        old = text_of(f, "TKEY")
        if not old:
            continue
        code = parse_key(old)
        if not code:
            unknown.append((f, old))
            continue
        new = format_key(code, notation)
        if new != old:
            plan.append((f, "TKEY", old, new))
    return plan, unknown
