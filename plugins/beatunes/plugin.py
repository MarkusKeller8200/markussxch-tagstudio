"""beaTunes übernehmen (#145): Stimmungs- und Klangwerte, die beaTunes in die Dateien schreibt, als Audio-Merkmale.

beaTunes schreibt (je nach Analyse-Einstellungen) u. a. TXXX:MOOD_DANCEABILITY, MOOD_ACOUSTIC, MOOD_ELECTRONIC,
MOOD_HAPPY, MOOD_SAD, MOOD_AGGRESSIVE, MOOD_RELAXED, MOOD_PARTY – Werte 0–100. Zugeordnet werden die, für die es ein
TagStudio-Merkmal gibt; die übrigen erscheinen als Hinweis. Abgleich über importsync: geänderte beaTunes-Werte
werden nur angehakt, wenn die Datei seit dem letzten Übernehmen unverändert ist – sonst fragt die Vorschau.
Nur Standardbibliothek.
"""
import features
import importsync

SOURCE, SOURCE_NAME = "beatunes", "beaTunes"
# beaTunes-Feld (ohne TXXX:) → (Merkmal, Option)
MAP = {
    "MOOD_DANCEABILITY": ("DANCEABILITY", "danceability"),
    "MOOD_ACOUSTIC": ("ACOUSTICNESS", "acoustic"),
    "MOOD_HAPPY": ("HAPPINESS", "happy"),
    "MOOD_AGGRESSIVE": ("AGGRESSIVENESS", "aggressive"),
    "MOOD_VALENCE": ("VALENCE", "valence"),
}

ACTIONS = [{
    "id": "import", "label": "beaTunes übernehmen …", "where": "tagger", "run_label": "Abgleichen",
    "description": "Liest die Werte, die beaTunes in die Dateien geschrieben hat (MOOD_DANCEABILITY, MOOD_ACOUSTIC …), "
                   "und schlägt sie als Audio-Merkmale vor. Wurde ein Wert in der Datei seit dem letzten Abgleich "
                   "geändert, ist er nicht angehakt – du entscheidest.",
    "options": [
        {"key": "danceability", "type": "check", "label": "MOOD_DANCEABILITY → DANCEABILITY", "default": True},
        {"key": "acoustic", "type": "check", "label": "MOOD_ACOUSTIC → ACOUSTICNESS", "default": True},
        {"key": "happy", "type": "check", "label": "MOOD_HAPPY → HAPPINESS", "default": True},
        {"key": "aggressive", "type": "check", "label": "MOOD_AGGRESSIVE → AGGRESSIVENESS", "default": True},
        {"key": "valence", "type": "check", "label": "MOOD_VALENCE → VALENCE", "default": True},
        {"type": "info", "label": "Werte ohne passendes Merkmal (z. B. MOOD_ELECTRONIC, MOOD_PARTY) werden als Hinweis "
                                  "gezeigt, aber nicht übernommen."},
    ],
}]


def read(f) -> dict:
    """beaTunes-Werte einer Datei: {FELD: 0–100} (alle TXXX:MOOD_*; Schreibweise egal)."""
    out = {}
    for k in f.items:
        if not k.upper().startswith("TXXX:MOOD_"):
            continue
        it = f.get(k)
        if it is None or it.kind in ("picture", "raw"):
            continue
        n = features.number(it.text, 100)
        if n is not None:
            out[k[5:].upper()] = n
    return out


def run(action, ctx, files, opts):
    if action != "import":
        raise ValueError(f"Unbekannte Aktion: {action}")
    found = changed = asks = 0
    for n, f in enumerate(files):
        group = f.path.replace("\\", "/").rsplit("/", 1)[-1]
        ctx.progress(n, len(files), group)
        vals = read(f)
        if not vals:
            continue
        found += 1
        rest = {k: v for k, v in vals.items() if k not in MAP}
        note = "beaTunes" + (" · ohne Merkmal: " + ", ".join(f"{k[5:].title()} {v}" for k, v in sorted(rest.items()))
                             if rest else "")
        any_ = False
        for field, (name, opt) in MAP.items():
            if field not in vals:
                continue
            st = importsync.propose(ctx, f, SOURCE, SOURCE_NAME, name, vals[field], enabled=bool(opts.get(opt)),
                                    group=group, note=note)
            any_ |= st != "same"
            asks += st == "conflict"
        changed += bool(any_)
    ctx.progress(len(files), len(files), "fertig")
    msg = f"{found} von {len(files)} Titel(n) mit beaTunes-Werten; {changed} mit Änderungen (Vorschau)"
    if asks:
        msg += f", {asks} Wert(e) zum Prüfen (nicht angehakt)"
    return {"message": msg + "."}
