"""MarKusSXCH TagStudio – Hilfe: Übersicht aller Tags mit Bedeutung und Herkunft, Bibliotheks-Scan (#158).

`overview()` baut Kapitel (aufklappbar in der Oberfläche) aus den bekannten Feldern; `scan()` zählt, in wie vielen
Titeln eines Ordners welches Feld vorkommt, und merkt das Ergebnis im Cache (~/TagStudio/cache/tagscan/…json).
Damit zeigt die Hilfe hinter jedem Tag einen Zähler, und der Abschnitt „Eigene Tags“ listet alle benutzerdefinierten
Felder der Bibliothek. Nur Standardbibliothek.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import paths
import time

import id3frames
from id3tags import field_help, field_name, key_label

# Kapitel nach der Übersicht des Users („DJ Software vergleichen“, offizielle ID3v2.4-Frames nach Funktion)
# (Kapitel-ID, Titel, Beschreibung, Schlüssel)
CHAPTERS = [
    ("ident", "1. Titel, Album und Musikidentifikation", "",
     ["TIT1", "TIT2", "TIT3", "TALB", "TOAL", "TRCK", "TPOS", "TSST", "TSRC", "UFID"]),
    ("people", "2. Künstler, Komponisten und Mitwirkende",
     "ID3v2.4 erlaubt in Textfeldern mehrere Werte (null-getrennt, in TagStudio „¦“) – auch in TPE1. Wie gut DJ-Programme "
     "das lesen, ist verschieden.",
     ["TPE1", "TPE2", "TPE3", "TPE4", "TOPE", "TEXT", "TOLY", "TCOM", "TMCL", "TIPL", "TENC"]),
    ("music", "3. Musikalische und technische Eigenschaften",
     "TBPM ist laut Spezifikation eine ganze Zahl; genaue BPM in einem eigenen Feld. TKEY erwartet eine Tonart wie „Am“ "
     "oder „F#m“ – Camelot („8A“) ist verbreitet, aber nicht vorgesehen (Schreibweise unter Einstellungen › Tonart).",
     ["TBPM", "TKEY", "TCON", "TMOO", "TLEN", "TLAN", "TFLT", "TMED", "TSSE"]),
    ("dates", "4. Datum, Veröffentlichung und Sortierung",
     "ID3v2.4 hat modernere Datumsfelder als ID3v2.3 (dort z. B. TYER für das Jahr).",
     ["TDEN", "TDOR", "TDRC", "TDRL", "TDTG", "TSOA", "TSOP", "TSOT", "TOFN", "TDLY"]),
    ("rights", "5. Rechte, Label und Veröffentlichung", "",
     ["TCOP", "TPRO", "TPUB", "TOWN", "TRSN", "TRSO"]),
    ("texts", "6. Texte, Kommentare und frei definierte Felder",
     "TXXX ist offiziell, die Namen darin (z. B. ENERGY) sind es nicht – sie müssen einheitlich verwendet werden. "
     "Die Namen in deiner Bibliothek stehen unter „Eigene Tags (CUSTOM)“.",
     ["COMM", "USLT", "SYLT", "USER", "TXXX", "WXXX"]),
    ("urls", "7. Offizielle URL-Felder", "",
     ["WCOM", "WCOP", "WOAF", "WOAR", "WOAS", "WORS", "WPAY", "WPUB", "WXXX"]),
    ("media", "8. Bilder, Bewertungen und Wiedergabeinformationen",
     "SYTC beschreibt Tempoänderungen, ist aber kein DJ-Beatgrid; ETCO und ASPI sind keine Hot-Cue-Formate.",
     ["APIC", "POPM", "PCNT", "MCDI", "GEOB", "ETCO", "SYTC", "MLLT", "ASPI", "POSS", "SEEK"]),
    ("audio", "9. Lautstärke, Audioverarbeitung und Puffer",
     "RVA2 ist eine relative Lautstärkeanpassung, kein Feld für LUFS-Messwerte.",
     ["RVA2", "EQU2", "RVRB", "RBUF"]),
    ("security", "10. Sicherheit, Verschlüsselung und interne Verwaltung",
     "PRIV und GEOB nutzen DJ-Programme für eigene Binärdaten – lesbar nur für Programme, die das Format kennen.",
     ["AENC", "ENCR", "GRID", "PRIV", "LINK", "OWNE", "COMR", "SIGN"]),
]
# (Parameter, eigener Frame?, empfohlene Ablage, Unterstützung in TagStudio)
ANALYSIS = [
    ("BPM", "Ja", "TBPM", "Feld BPM, Spalte, DJ-Set"), ("Musikalische Tonart", "Ja", "TKEY", "Camelot-Rad, Schreibweisen"),
    ("Mood / Stimmung", "Ja", "TMOO (v2.3: TXXX:MOOD)", "Feld Stimmung"), ("Genre", "Ja", "TCON", "Feld Genre"),
    ("Bewertung", "Ja", "POPM", "Sterne und Like"), ("Energie", "Nein", "TXXX:ENERGY", "Merkmal (0–100)"),
    ("Tanzbarkeit", "Nein", "TXXX:DANCEABILITY", "Merkmal"), ("Happiness", "Nein", "TXXX:HAPPINESS", "Merkmal"),
    ("Valence", "Nein", "TXXX:VALENCE", "Merkmal"), ("Camelot-Key", "Nein", "TXXX:CAMELOT", "TagStudio schreibt Camelot in TKEY (wählbar)"),
    ("LUFS", "Nein", "TXXX:LUFS_I", "–"), ("True Peak", "Nein", "TXXX:TRUE_PEAK", "–"),
    ("Dynamic Range", "Nein", "TXXX:DYNAMIC_RANGE", "–"), ("Acousticness", "Nein", "TXXX:ACOUSTICNESS", "Merkmal"),
    ("Instrumentalness", "Nein", "TXXX:INSTRUMENTALNESS", "Merkmal"), ("Speechiness", "Nein", "TXXX:SPEECHINESS", "Merkmal"),
    ("Dance Intro / Outro", "Nein", "benutzerdefinierte Daten", "–"),
    ("Hot Cues", "Nein", "proprietäre DJ-Daten (z. B. GEOB:Serato Markers2)", "Anzeige im Player"),
    ("Beatgrid", "Nein", "proprietäre DJ-Daten (z. B. GEOB:Serato BeatGrid)", "Anzeige, Überblenden im Takt"),
    ("Saved Loops", "Nein", "proprietäre DJ-Daten", "Anzeige im Player"),
]
# Vergleich der DJ-Software (aus der Übersicht des Users, Stand 2026-10)
SOFTWARE = [
    ("Serato DJ Pro", "Ja", "Ja", "Ja"), ("VirtualDJ", "Ja", "Nein, primär Datenbank", "Ja"),
    ("Traktor Pro", "Teilweise", "versions-/formatabhängig", "Ja"), ("rekordbox", "Teilweise", "Nein, primär Datenbank", "Ja"),
    ("Engine DJ", "Teilweise", "Nein, primär Datenbank", "Ja"), ("djay Pro", "Metadaten bearbeitbar", "Nein, primär Datenbank", "Ja"),
    ("Lexicon DJ", "Ja, konfigurierbar", "nicht als universelle ID3-Cues", "Ja"),
]
# vom User als DJ-relevant markiert
DJ_RELEVANT = set("TIT2 TIT3 TALB TRCK TSRC UFID TPE1 TPE2 TPE4 TOPE TCOM TIPL TBPM TKEY TCON TMOO TLEN TLAN TDOR TDRC "
                  "TDRL TSOA TSOP TSOT TPUB COMM USLT TXXX WXXX APIC POPM PCNT SYTC RVA2".split())
# Bedeutung laut Spezifikation (kurz)
MEANING = {
    "TIT1": "Übergeordnete Werkgruppe", "TIT2": "Titel des Tracks", "TIT3": "Untertitel / Titelzusatz", "TALB": "Albumname",
    "TOAL": "Ursprünglicher Albumname", "TRCK": "Tracknummer / Gesamtanzahl", "TPOS": "Disc-Nummer / Gesamtanzahl",
    "TSST": "Untertitel eines Sets bzw. Datenträgers", "TSRC": "International Standard Recording Code (ISRC)",
    "UFID": "Eindeutige Dateiidentifikation", "TPE1": "Hauptkünstler / Interpreten", "TPE2": "Band / Orchester / Begleitung",
    "TPE3": "Dirigent / nähere Interpretenangabe", "TPE4": "Remixer / Bearbeiter", "TOPE": "Ursprünglicher Interpret",
    "TEXT": "Texter / Songwriter der Lyrics", "TOLY": "Ursprünglicher Texter", "TCOM": "Komponist",
    "TMCL": "Musiker und ihre Instrumente", "TIPL": "Weitere Mitwirkende und Rollen",
    "TENC": "Person oder Organisation, die die Datei codiert hat", "TBPM": "Beats per Minute", "TKEY": "Musikalische Tonart",
    "TCON": "Genre / Inhaltstyp", "TMOO": "Stimmung / Mood", "TLEN": "Länge in Millisekunden", "TLAN": "Sprache(n)",
    "TFLT": "Typ der Audiodatei", "TSSE": "Software/Hardware und Einstellungen der Kodierung", "TMED": "Ursprünglicher Medientyp", "TDEN": "Zeitpunkt der Audio-Codierung",
    "TDOR": "Ursprüngliches Veröffentlichungsdatum", "TDRC": "Zeitpunkt der Aufnahme", "TDRL": "Veröffentlichungsdatum",
    "TDTG": "Zeitpunkt der Tag-Bearbeitung", "TSOA": "Album-Sortiername", "TSOP": "Künstler-Sortiername",
    "TSOT": "Titel-Sortiername", "TOFN": "Ursprünglicher Dateiname", "TDLY": "Playlist-Verzögerung in Millisekunden",
    "TCOP": "Copyright-Hinweis", "TPRO": "Produktionsrecht / Produced Notice", "TPUB": "Publisher / Label",
    "TOWN": "Eigentümer / Lizenznehmer", "TRSN": "Name eines Internetradios", "TRSO": "Betreiber eines Internetradios",
    "COMM": "Kommentare", "USLT": "Unsynchronisierte Songtexte", "SYLT": "Zeitlich synchronisierte Songtexte",
    "USER": "Nutzungsbedingungen", "TXXX": "Benutzerdefiniertes Textfeld", "WXXX": "Benutzerdefinierte URL",
    "WCOM": "Kommerzielle Informationen", "WCOP": "Copyright- und rechtliche Informationen",
    "WOAF": "Offizielle Webseite der Audiodatei", "WOAR": "Offizielle Webseite des Künstlers",
    "WOAS": "Offizielle Webseite der Audioquelle", "WORS": "Webseite eines Internetradios", "WPAY": "Zahlungsinformationen",
    "WPUB": "Webseite des Publishers", "APIC": "Eingebettetes Coverbild", "POPM": "Bewertung und optionaler Wiedergabezähler",
    "PCNT": "Wiedergabezähler", "MCDI": "Musik-CD-Identifikation", "GEOB": "Eingebettetes beliebiges Datenobjekt",
    "ETCO": "Zeitlich markierte Ereignisse", "SYTC": "Zeitlich veränderliches Tempo",
    "MLLT": "MPEG-Positions-Nachschlagetabelle", "ASPI": "Audio-Suchpunktindex", "POSS": "Positionssynchronisierung",
    "SEEK": "Verweis auf einen weiteren Tag-Bereich", "RVA2": "Relative Lautstärkeanpassung", "EQU2": "Equalizer-Einstellungen",
    "RVRB": "Hall-Informationen", "RBUF": "Empfohlene Puffergrösse", "AENC": "Audioverschlüsselung",
    "ENCR": "Registrierung einer Verschlüsselungsmethode", "GRID": "Registrierung einer Frame-Gruppierung",
    "PRIV": "Private, anwendungsspezifische Daten", "LINK": "Verknüpfte Informationen", "OWNE": "Eigentumsinformationen",
    "COMR": "Kommerzielle Informationen zu Angeboten", "SIGN": "Digitale Signatur",
}
PROGRAMS = "programs"     # Kapitel mit den Feldern der Programme (aus der Herkunfts-Liste)
CUSTOM = "custom"         # Kapitel mit den eigenen Tags der Bibliothek (aus dem Scan)


def _base(key: str) -> str:
    return key.split("#")[0]


def _family(key: str) -> str:
    """Schlüssel, unter dem ein Feld in der Übersicht steht: COMM:xyz → COMM, APIC:3 → APIC, TXXX:X bleibt."""
    k = _base(key)
    fid = k.split(":")[0]
    return fid if fid in ("COMM", "USLT", "APIC", "POPM", "UFID", "SYLT", "WXXX", "PCNT", "CHAP", "CTOC", "LINK",
                          "OWNE", "USER", "RVA2", "EQU2", "ENCR", "GRID", "SIGN", "AENC") else k


def is_custom(key: str) -> bool:
    """Benutzerdefiniertes Feld (eigener Name): TXXX/WXXX/GEOB/PRIV mit Beschreibung, COMM mit Beschreibung."""
    fid, _sep, desc = _base(key).partition(":")
    return bool(desc) and fid in ("TXXX", "WXXX", "GEOB", "PRIV", "COMM", "USLT")


def _row(key: str, origin_of, counts: dict | None) -> dict:
    fid = key.split(":")[0]
    spec = id3frames.SPEC.get(fid)
    ver = {"34": "2.3 + 2.4", "3": "nur 2.3", "4": "nur 2.4", "x": "inoffiziell"}.get(spec[1], "") if spec else ""
    help_ = field_help(key) or (id3frames.label(fid) if ":" not in key else "")
    return {"key": key, "name": field_name(key), "label": key_label(key) if ":" in key else
            (key_label(key) if key_label(key) != key else id3frames.label(fid) or key),
            "meaning": MEANING.get(key, ""), "help": help_, "frame": fid, "ver": ver, "src": origin_of(key),
            "dj": key in DJ_RELEVANT, "count": None if counts is None else _count(key, counts)}


def _count(key: str, counts: dict) -> int:
    """Titel mit diesem Feld; bei TXXX/WXXX/GEOB/PRIV (ohne Namen) zählt jede Variante."""
    if key in ("TXXX", "WXXX", "GEOB", "PRIV"):
        return counts.get("__frame__" + key, 0)
    return counts.get(key, 0)


def overview(origin_of, catalog: dict, builtin_patterns: list, scan_result: dict | None = None,
             custom_rules: list | None = None) -> dict:
    """Kapitel für die Hilfe. origin_of(key) → Quellen-ID; catalog: Quellen (Name, Erklärung);
    builtin_patterns: [(Muster, Quelle)]; scan_result: Ergebnis von scan() (Zähler) oder None."""
    counts = None
    if scan_result:
        counts = dict(scan_result["families"])
        counts.update({"__frame__" + k: v for k, v in scan_result["frames"].items()})
    chapters, seen = [], set()
    for cid, title, desc, keys in CHAPTERS:
        rows = [_row(k, origin_of, counts) for k in keys]
        seen.update(keys)
        chapters.append({"id": cid, "title": title, "desc": desc, "rows": rows})
    # Programme: Muster aus der Herkunfts-Liste (eigene Zuordnungen zuerst), je Programm gruppiert
    by_src: dict[str, list] = {}
    for pat, sid in list((custom_rules or [])) + list(builtin_patterns):
        by_src.setdefault(sid, [])
        if pat not in by_src[sid]:
            by_src[sid].append(pat)
    prog_rows = []
    for sid, pats in by_src.items():
        info = catalog.get(sid) or {}
        for pat in pats:
            n = _pattern_count(pat, scan_result) if scan_result else None
            fid = pat.split(":")[0]
            prog_rows.append({"key": pat, "name": field_name(pat.replace("*", "…")), "label": info.get("name", sid),
                              "help": info.get("desc", ""), "frame": fid, "ver": "", "src": sid, "count": n,
                              "pattern": "*" in pat or "?" in pat})
    chapters.append({"id": PROGRAMS, "title": "Programm-Daten (Herkunft)",
                     "desc": "Felder, die DJ- und Musikprogramme selbst schreiben – zugeordnet nach den Herkunfts-"
                             "Regeln (Einstellungen › Herkunft der Tags). „*“ steht für beliebige Zeichen.",
                     "rows": prog_rows})
    # Eigene Tags aus dem Scan
    custom_rows = []
    if scan_result:
        for k, n in sorted(scan_result["families"].items(), key=lambda kv: (-kv[1], kv[0].lower())):
            if is_custom(k) and k not in seen:
                custom_rows.append(_row(k, origin_of, counts))
    chapters.append({"id": CUSTOM, "title": "Eigene Tags (CUSTOM) in der Bibliothek",
                     "desc": "Alle benutzerdefinierten Felder (TXXX, WXXX, GEOB, PRIV, COMM mit eigenem Namen), die in "
                             "der gescannten Bibliothek vorkommen – mit Anzahl der Titel." if scan_result else
                             "Noch nicht gescannt: oben einen Ordner wählen und „Bibliothek scannen“.",
                     "rows": custom_rows})
    # 11. DJ-Analysewerte ohne eigenen Frame (Tabelle), dann übrige Frames (v2.3, inoffiziell)
    ana = []
    for par, own, where, ts in ANALYSIS:
        k = where.split(" ")[0]
        ana.append({"param": par, "own": own, "where": where, "tagstudio": ts, "key": k if k.isupper() and len(k) >= 4 else "",
                    "src": origin_of(k) if k.isupper() else None,
                    "count": None if counts is None or not k.isupper() else _count(k, counts)})
    chapters.insert(len(CHAPTERS), {"id": "analysis", "title": "11. DJ-Analysewerte ohne eigenen offiziellen Frame",
                                    "desc": "Empfohlene Ablage – wie TagStudio sie unterstützt.", "kind": "analysis",
                                    "rows": ana})
    rest = [f for f in sorted(id3frames.SPEC) if f not in seen]
    chapters.append({"id": "other", "title": "Weitere Frames (nur ID3v2.3, inoffiziell, Kapitel)",
                     "desc": "Frames ausserhalb von ID3v2.4 – TagStudio liest und schreibt sie ebenfalls (siehe ID3-Felder).",
                     "rows": [_row(k, origin_of, counts) for k in rest]})
    return {"chapters": chapters, "scan": _scan_meta(scan_result),
            "software": [{"name": a, "id3": b, "cues": c, "db": d} for a, b, c, d in SOFTWARE]}


def _pattern_count(pat: str, r: dict) -> int:
    """Titel, die mindestens ein Feld haben, das zum Muster passt."""
    p = pat.lower()
    keys = [k for k in r["families"] if fnmatch.fnmatchcase(k.lower(), p)]
    if not keys:
        return 0
    if len(keys) == 1:
        return r["families"][keys[0]]
    want = set(keys)
    return sum(1 for ks in r["file_keys"] if want.intersection(ks))


# =========================================================================== Scan
def cache_dir() -> str:
    return paths.sub("cache", "tagscan")


def _cache_path(root: str) -> str:
    h = hashlib.sha1(os.path.normcase(os.path.abspath(root)).encode("utf-8")).hexdigest()[:16]
    return os.path.join(cache_dir(), f"{h}.json")


def _scan_meta(r):
    if not r:
        return None
    return {"root": r["root"], "files": r["count"], "scanned": r["scanned"], "seconds": r.get("seconds"),
            "keys": len(r["families"])}


def scan(files, root: str) -> dict:
    """Zähler aus geladenen Dateien (MP3File) bilden und im Cache speichern."""
    t0 = time.time()
    families: dict[str, int] = {}
    frames: dict[str, int] = {}
    file_keys = []
    rels = []
    for f in files:
        ks = sorted({_family(k) for k in f.items})
        file_keys.append(ks)
        rels.append(os.path.relpath(f.path, root) if os.path.isdir(root) else os.path.basename(f.path))
        for k in ks:
            families[k] = families.get(k, 0) + 1
        for fid in {k.split(":")[0].split("#")[0] for k in f.items}:
            frames[fid] = frames.get(fid, 0) + 1
    out = {"format": 1, "root": os.path.abspath(root), "scanned": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "count": len(files), "families": families, "frames": frames, "file_keys": file_keys, "files": rels,
           "seconds": round(time.time() - t0, 2)}
    try:
        os.makedirs(cache_dir(), exist_ok=True)
        tmp = _cache_path(root) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, _cache_path(root))
    except OSError:
        pass                      # Cache ist Komfort – ohne geht es auch
    return out


def cached(root: str) -> dict | None:
    if not root:
        return None
    try:
        with open(_cache_path(root), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if d.get("format") == 1 else None
    except (OSError, ValueError):
        return None


def matches(file_keys: list, key: str) -> bool:
    """Hat ein Titel (Liste seiner Feld-Familien) das Feld? key darf ein Muster mit * sein."""
    k = key.lower()
    if "*" in k or "?" in k:
        return any(fnmatch.fnmatchcase(x.lower(), k) for x in file_keys)
    return any(x.lower() == k or x.split(":")[0].lower() == k for x in file_keys)
