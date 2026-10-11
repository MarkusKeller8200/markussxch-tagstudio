"""Mixed In Key übernehmen (#147): Tonart, BPM und Energie aus den Tags, die Mixed In Key geschrieben hat.

Mixed In Key schreibt je nach Einstellung (Settings › Tag Options):
  Tonart   ins Feld Initial Key (TKEY), vor den Kommentar bzw. als Kommentar („10A - Energy 7“), vor den Titel oder
           Künstler („10A - Titel“) oder ans Ende des Titels („Titel - 10A“)
  BPM      ins Feld TBPM (teils mit Nachkommastellen)
  Energie  vor die Gruppierung („Energy 7“), anstelle des Labels oder als TXXX:EnergyLevel
Dieses Plugin sucht die Werte dort, schlägt TKEY (in deiner Schreibweise), TBPM (gerundet) und das Merkmal ENERGY
(1–10 → 10–100) vor und entfernt auf Wunsch die Präfixe wieder aus Titel, Künstler und Kommentar.
Nur Standardbibliothek. Alle Änderungen als Vorschau mit Häkchen.
"""
import re

import features
import keys

ACTIONS = [{
    "id": "import", "label": "Mixed In Key übernehmen …", "where": "tagger", "run_label": "Suchen",
    "description": "Sucht Tonart, BPM und Energie, die Mixed In Key in Felder wie Kommentar, Titel oder Gruppierung "
                   "geschrieben hat, und schlägt sie für die richtigen Felder vor.",
    "options": [
        {"key": "key", "type": "check", "label": "Tonart → TKEY (in deiner Schreibweise)", "default": True},
        {"key": "energy", "type": "check", "label": "Energie → Merkmal ENERGY (1–10 wird 10–100)", "default": True},
        {"key": "bpm", "type": "check", "label": "BPM runden (124.00 → 124)", "default": True},
        {"key": "clean_title", "type": "check", "label": "Präfix aus Titel und Künstler entfernen („10A - …“)", "default": False},
        {"key": "clean_comment", "type": "check", "label": "Mixed-In-Key-Text aus dem Kommentar entfernen", "default": False},
        {"key": "clean_group", "type": "check", "label": "„Energy N“ aus Gruppierung bzw. Label entfernen", "default": False},
        {"type": "info", "label": "Vorhandene, passende Werte werden nicht geändert. Steht die Tonart schon in TKEY, "
                                  "gilt dieser Wert; sonst Kommentar, Titel, Künstler (in dieser Reihenfolge)."},
    ],
}]

KEY_RE = r"(?:0?(?:1[0-2]|[1-9])\s?[ABab]|[A-G][#b♯♭]?\s?(?:m|min|maj)?)"
PREFIX_RE = re.compile(r"^\s*(" + KEY_RE + r")(?:\s*[-–/|]\s*(?:Energy\s*)?(\d{1,2}))?\s*[-–/|]\s+(.+)$")
SUFFIX_RE = re.compile(r"^(.+?)\s+[-–/|]\s*(" + KEY_RE + r")(?:\s*[-–/|]\s*(?:Energy\s*)?(\d{1,2}))?\s*$")
ENERGY_RE = re.compile(r"\bEnergy\s*[:=]?\s*(\d{1,2})\b", re.I)
COMMENT_KEY_RE = re.compile(r"^\s*(" + KEY_RE + r")\b")
ONLY_ENERGY_RE = re.compile(r"^\s*(?:Energy\s*)?(\d{1,2})\s*$", re.I)


def _key(text):
    return keys.parse_key((text or "").replace("♯", "#").replace("♭", "b").strip())


def _energy(v):
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= 10 else None


def _notation():
    try:
        import core
        return core.load_config().get("key_notation", "camelot")
    except Exception:  # noqa: BLE001
        return "camelot"


def _comment_keys(f):
    return [k for k in f.items if k.startswith("COMM")]


def analyse(f) -> dict:
    """Werte und Fundstellen einer Datei → {"key": (Code, Quelle), "energy": (1–10, Quelle), "clean": {Feld: neu}}"""
    out = {"key": None, "energy": None, "clean_title": {}, "clean_comment": {}, "clean_group": {}}
    t = f.text
    code = _key(t("TKEY"))
    if code:
        out["key"] = (code, "TKEY")
    lvl = _energy(t("TXXX:EnergyLevel").strip()) if t("TXXX:EnergyLevel") else None
    if lvl:
        out["energy"] = (lvl, "TXXX:EnergyLevel")
    # Kommentar: „10A - Energy 7“, „10A“, „Energy 7 - …“
    for ck in _comment_keys(f):
        c = t(ck)
        m = COMMENT_KEY_RE.match(c)
        if m and _key(m.group(1)) and not out["key"]:
            out["key"] = (_key(m.group(1)), "Kommentar")
        e = ENERGY_RE.search(c)
        if e and _energy(e.group(1)) and not out["energy"]:
            out["energy"] = (_energy(e.group(1)), "Kommentar")
        rest = c
        if m and _key(m.group(1)):
            rest = rest[m.end():]
        rest = ENERGY_RE.sub("", rest)
        rest = re.sub(r"^[\s\-–/|,]+|[\s\-–/|,]+$", "", rest)
        if rest != c.strip():
            out["clean_comment"][ck] = rest
    # Titel/Künstler: Präfix „10A - …“ bzw. „10A - 7 - …“, Titel auch mit Endung „… - 10A“
    for fk in ("TIT2", "TPE1"):
        v = t(fk)
        m = PREFIX_RE.match(v)
        if m and re.fullmatch(r"[A-G]", m.group(1).strip()):     # „A - Titel“ ist eher ein Name als eine Tonart
            m = None
        if m and _key(m.group(1)):
            if not out["key"]:
                out["key"] = (_key(m.group(1)), "Titel" if fk == "TIT2" else "Künstler")
            if m.group(2) and _energy(m.group(2)) and not out["energy"]:
                out["energy"] = (_energy(m.group(2)), "Titel" if fk == "TIT2" else "Künstler")
            out["clean_title"][fk] = m.group(3).strip()
            continue
        m = SUFFIX_RE.match(v) if fk == "TIT2" else None
        if m and re.fullmatch(r"[A-G]", m.group(2).strip()):
            m = None
        if m and _key(m.group(2)) and not re.search(r"\b(mix|edit|remix|version|dub)\b", m.group(2), re.I):
            if not out["key"]:
                out["key"] = (_key(m.group(2)), "Titel")
            if m.group(3) and _energy(m.group(3)) and not out["energy"]:
                out["energy"] = (_energy(m.group(3)), "Titel")
            out["clean_title"][fk] = m.group(1).strip()
    # Gruppierung (TIT1, GRP1) und Label (TPUB): „Energy 7 …“ bzw. nur „7“
    for gk in ("TIT1", "GRP1", "TPUB"):
        v = t(gk)
        if not v:
            continue
        e = ENERGY_RE.search(v)
        only = ONLY_ENERGY_RE.match(v) if gk == "TPUB" else None
        lvl = _energy(e.group(1)) if e else _energy(only.group(1)) if only and "energy" in v.lower() else None
        if lvl:
            if not out["energy"]:
                out["energy"] = (lvl, {"TPUB": "Label", "TIT1": "Gruppierung", "GRP1": "Gruppierung"}[gk])
            out["clean_group"][gk] = re.sub(r"^[\s\-–/|,]+|[\s\-–/|,]+$", "", ENERGY_RE.sub("", v))
    return out


def run(action, ctx, files, opts):
    if action != "import":
        raise ValueError(f"Unbekannte Aktion: {action}")
    notation = _notation()
    found = changed = 0
    for n, f in enumerate(files):
        ctx.progress(n, len(files), f.path.rsplit("/", 1)[-1])
        a = analyse(f)
        group = f.path.replace("\\", "/").rsplit("/", 1)[-1]
        src = []
        if a["key"]:
            src.append(f"Tonart aus {a['key'][1]}")
        if a["energy"]:
            src.append(f"Energie aus {a['energy'][1]}")
        note = "Mixed In Key: " + (", ".join(src) if src else "keine Werte gefunden")
        any_ = False
        if a["key"]:
            val = keys.format_key(a["key"][0], notation)
            any_ |= ctx.propose(f, "TKEY", val, "Tonart", note=note, checked=bool(opts.get("key")), group=group,
                                hint="" if opts.get("key") else "in den Optionen abgewählt")
        if a["energy"]:
            val = features.stored(a["energy"][0] * 10)
            cur = features.number(f.text(features.KEYS["ENERGY"]))
            if cur != a["energy"][0] * 10:
                any_ |= ctx.propose(f, features.KEYS["ENERGY"], val, "Energie (ENERGY)", note=note,
                                    checked=bool(opts.get("energy")), group=group,
                                    hint=f"Mixed In Key {a['energy'][0]}/10" + ("" if opts.get("energy") else " · abgewählt"))
        bpm = f.text("TBPM").strip().replace(",", ".")
        if re.fullmatch(r"\d{2,3}\.\d+", bpm):
            any_ |= ctx.propose(f, "TBPM", str(int(round(float(bpm)))), "BPM", note=note,
                                checked=bool(opts.get("bpm")), group=group, hint="gerundet")
        for opt, label in (("clean_title", None), ("clean_comment", "Kommentar"), ("clean_group", None)):
            for k, new in a[opt].items():
                lab = label or {"TIT2": "Titel", "TPE1": "Künstler", "TIT1": "Gruppierung", "GRP1": "Gruppierung",
                                "TPUB": "Label"}.get(k, k)
                any_ |= ctx.propose(f, k, new, f"{lab} bereinigen", note=note, checked=bool(opts.get(opt)), group=group,
                                    hint=("leer → Feld wird entfernt" if not new else "") +
                                    ("" if opts.get(opt) else (" · " if not new else "") + "in den Optionen abgewählt"))
        found += bool(a["key"] or a["energy"])
        changed += bool(any_)
    ctx.progress(len(files), len(files), "fertig")
    return {"message": f"{found} von {len(files)} Titel(n) mit Werten von Mixed In Key; "
                       f"{changed} mit möglichen Änderungen (Vorschau)."}
