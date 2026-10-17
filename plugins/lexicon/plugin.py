"""Lexicon (#146, #237–#239): Werte aus Lexicon DJ übernehmen, Titel und Playlists aus Lexicon öffnen und – wenn
eingeschaltet – Änderungen nach Lexicon zurückschreiben. Über die Local API von Lexicon
(Lexicon › Settings › Integrations › Local API einschalten; Standard http://localhost:48624).

- Übernehmen: Tanzbarkeit, Energie, Fröhlichkeit, Popularität, Farbe, Custom Tags in eigene Felder TXXX:LEXICON_…
  (Herkunft „Lexicon“, Werte wie in Lexicon), Bewertung in POPM; Stimmung in TMOO (ID3v2.4) bzw. TXXX:LEXICON_MOOD.
  Zuordnung gezielt über den Dateipfad (/search/tracks), sonst über Künstler + Titel. Beatgrid und Cue-Punkte von
  Lexicon werden nur verglichen, nie in die Datei geschrieben.
- Öffnen: in Lexicon markierte Titel bzw. eine Playlist → Tagger oder DJ-Set.
- Zurückschreiben (Einstellungen, standardmässig aus): Pfade nachführen, neue Bibliothekstitel aufnehmen (Playlist,
  Analyse), geänderte Tags mit Vorschau senden, DJ-Set als Playlist; jede Änderung kommt ins Journal (Rückgängig).
  Geschrieben wird nur an Lexicon auf diesem Rechner (die API hat keine Anmeldung). Nie gelöscht wird etwas.
Nur Standardbibliothek.
"""
import importlib.util
import json
import os
import re
import time

import moods
from id3tags import MV

_spec = importlib.util.spec_from_file_location("tagstudio_lexapi", os.path.join(os.path.dirname(__file__), "lexapi.py"))
lexapi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lexapi)
LexiconError = lexapi.LexiconError

SOURCE, SOURCE_NAME = "lexicon", "Lexicon"
FIELDS = (("danceability", "DANCEABILITY"), ("energy", "ENERGY"), ("happiness", "HAPPINESS"))
TRACK_FIELDS = ["id", "location", "locationUnique", "artist", "title", "albumTitle", "genre", "bpm", "key", "rating",
                "color", "danceability", "energy", "happiness", "popularity", "tags", "archived", "incoming",
                "tempomarkers", "cuepoints", "duration"]
SEARCH_MAX = 150          # bis zu so vielen Dateien gezielt suchen, darüber die Bibliothek einmal ganz lesen
DEFAULT_URL = lexapi.DEFAULT
TARGETS = [["", "nicht übernehmen"], ["TIT1", "Grouping (TIT1)"], ["COMM", "Kommentar (COMM)"],
           ["TXXX:LEXICON_TAGS", "eigenes Feld TXXX:LEXICON_TAGS"]]

ACTIONS = [{
    "id": "import", "label": "Lexicon übernehmen …", "where": "tagger", "run_label": "Abgleichen",
    "description": "Liest Tanzbarkeit, Energie, Fröhlichkeit und auf Wunsch Bewertung, Popularität, Farbe und Custom Tags "
                   "aus Lexicon (Local API) und schlägt sie vor. Werte, die in der Datei seit dem letzten Abgleich geändert "
                   "wurden, sind nicht angehakt – du entscheidest.",
    "options": [
        {"key": "url", "type": "text", "label": "Adresse der Lexicon Local API", "default": DEFAULT_URL},
        {"key": "danceability", "type": "check", "label": "Tanzbarkeit → TXXX:LEXICON_DANCEABILITY", "default": True},
        {"key": "energy", "type": "check", "label": "Energie → TXXX:LEXICON_ENERGY", "default": True},
        {"key": "happiness", "type": "check", "label": "Fröhlichkeit → TXXX:LEXICON_HAPPINESS", "default": False},
        {"key": "rating", "type": "check", "label": "Bewertung (0–5 Sterne) → POPM", "default": False},
        {"key": "popularity", "type": "check", "label": "Popularität → TXXX:LEXICON_POPULARITY", "default": False},
        {"key": "color", "type": "check", "label": "Farbe → TXXX:LEXICON_COLOR", "default": False},
        {"key": "mood", "type": "check", "label": "Lexicon-Tags der Kategorie „Mood“ → TMOO (ID3v2.4) bzw. TXXX:LEXICON_MOOD",
         "default": False},
        {"key": "tags_to", "type": "select", "label": "Tags der übrigen Kategorien", "choices": TARGETS, "default": ""},
        {"key": "grid", "type": "check", "label": "Beatgrid und Cue-Punkte mit der Datei vergleichen (nur Hinweis)",
         "default": True},
        {"key": "by_name", "type": "check", "label": "Titel ohne Pfad-Treffer über Künstler + Titel zuordnen", "default": True},
        {"type": "info", "label": "Lexicon muss laufen und die Local API eingeschaltet sein (Settings › Integrations). "
                                  "Werte ohne offizielles MP3-Feld kommen in eigene Felder TXXX:LEXICON_… (Herkunft "
                                  "„Lexicon“) und bleiben so, wie Lexicon sie liefert (1–10); 0 heisst „nicht analysiert“ und "
                                  "wird übergangen. Die TagStudio-Felder (ENERGY usw.) bleiben unverändert."},
    ],
}, {
    "id": "open", "label": "Aus Lexicon öffnen …", "where": "tagger", "run_label": "Öffnen", "needs_selection": False,
    "description": "Öffnet die in Lexicon markierten Titel oder eine Lexicon-Playlist im Tagger oder im DJ-Set.",
    "options": [
        {"key": "source", "type": "select", "label": "Was", "default": "tracks",
         "choices": [["tracks", "In Lexicon markierte Titel"], ["playlist", "In Lexicon markierte Playlist"],
                     ["path", "Playlist über ihren Namen bzw. Pfad"]]},
        {"key": "path", "type": "text", "label": "Playlist (z. B. Sets/Freitag – nur bei „über ihren Namen“)", "default": "",
         "show_if": {"source": "path"}},
        {"key": "target", "type": "select", "label": "Wohin", "default": "tagger",
         "choices": [["tagger", "In den Tagger laden"], ["djset", "Als neues DJ-Set"], ["djadd", "Zum DJ-Set hinzufügen"]]},
        {"type": "info", "label": "Ordner und Smartlists gehen auch: Lexicon liefert die Titel aller enthaltenen Playlists."},
    ],
}, {
    "id": "send", "label": "Nach Lexicon übertragen …", "where": "tagger", "run_label": "Vergleichen",
    "description": "Vergleicht die markierten Dateien mit Lexicon und schlägt vor, abweichende Werte in Lexicon zu ändern "
                   "(Vorschau mit Häkchen, rückgängig machbar). Nur wenn das Zurückschreiben eingeschaltet ist.",
    "options": [
        {"key": "basic", "type": "check", "label": "Titel, Künstler, Album, Genre", "default": True},
        {"key": "bpm_key", "type": "check", "label": "BPM und Tonart", "default": True},
        {"key": "rating", "type": "check", "label": "Bewertung", "default": True},
        {"key": "features", "type": "check", "label": "Energie, Tanzbarkeit, Fröhlichkeit (10–100 → 1–10)", "default": True},
        {"key": "mood", "type": "check", "label": "Stimmung → Lexicon-Tags der Kategorie „Mood“ (fehlende Tags anlegen)",
         "default": False},
    ],
}, {
    "id": "djset", "label": "DJ-Set als Lexicon-Playlist …", "where": "page", "run_label": "Anlegen", "needs_selection": False,
    "description": "Legt das aktuelle DJ-Set als neue Playlist in Lexicon an (Reihenfolge wie im Set). "
                   "Nur wenn das Zurückschreiben eingeschaltet ist.",
    "options": [
        {"key": "name", "type": "text", "label": "Name der Playlist (leer: Name des DJ-Sets)", "default": ""},
    ],
}, {
    "id": "settings", "label": "Einstellungen …", "where": "page", "run_label": "Speichern", "needs_selection": False,
    "description": "Adresse und Zurückschreiben nach Lexicon (alles einzeln, standardmässig aus).",
    "options": [
        {"key": "url", "type": "text", "label": "Adresse der Lexicon Local API", "default": DEFAULT_URL},
        {"key": "write", "type": "check", "label": "Zurückschreiben nach Lexicon erlauben (Hauptschalter)", "default": False},
        {"key": "move", "type": "check", "label": "Pfade nachführen, wenn TagStudio Dateien umbenennt oder verschiebt",
         "default": True},
        {"key": "add", "type": "check", "label": "Neu in die Bibliothek übernommene Titel (Vorbereiten) in Lexicon aufnehmen",
         "default": False},
        {"key": "playlist", "type": "text", "label": "… und in diese Playlist legen (leer: keine)", "default": "TagStudio Neu"},
        {"key": "analyze", "type": "check", "label": "… und von Lexicon analysieren lassen (Tonart, Beatgrid, Energie …)",
         "default": False},
        {"type": "info", "title": "Sicherheit",
         "label": "Die Lexicon-API hat keine Anmeldung. TagStudio schreibt deshalb nur an Lexicon auf diesem Rechner "
                  "(localhost) und löscht nie etwas. Jede Änderung steht im Journal und lässt sich rückgängig machen "
                  "(„Letzte Änderung rückgängig …“). Die Local API in Lexicon nur in vertrauenswürdigen Netzen einschalten.",
         "links": [["Lexicon: Local API", "https://www.lexicondj.com/docs/developers/api"]]},
    ],
}, {
    "id": "undo", "label": "Letzte Änderung in Lexicon rückgängig …", "where": "page", "run_label": "Rückgängig",
    "needs_selection": False,
    "description": "Stellt die Werte bzw. Pfade vor der letzten Änderung durch TagStudio in Lexicon wieder her "
                   "(aufgenommene Titel und angelegte Playlists bleiben – TagStudio löscht nichts in Lexicon).",
    "options": [],
}, {
    "id": "test", "label": "Verbindung testen", "where": "page", "run_label": "Testen", "needs_selection": False,
    "description": "Prüft, ob die Lexicon Local API unter der eingestellten Adresse erreichbar ist (Standard "
                   "http://localhost:48624).",
    "options": [],
}]


# =========================================================================== Einstellungen und Verbindung
SETTINGS = {"url": "", "write": False, "move": True, "add": False, "playlist": "TagStudio Neu", "analyze": False}


def _settings_path(ctx) -> str:
    return os.path.join(ctx.data_dir, "settings.json")


def load_settings(ctx) -> dict:
    out = dict(SETTINGS)
    try:
        with open(_settings_path(ctx), encoding="utf-8") as fh:
            d = json.load(fh)
        out.update({k: d[k] for k in SETTINGS if k in d})
    except (OSError, ValueError, TypeError):
        pass
    return out


def save_settings(ctx, opts) -> dict:
    d = {k: (bool(opts.get(k)) if isinstance(v, bool) else str(opts.get(k) or "").strip()) for k, v in SETTINGS.items()}
    with open(_settings_path(ctx), "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
    return d


def _base(ctx, opts=None) -> str:
    """Adresse: Option der Aktion → Einstellungen → zuletzt bei „Lexicon übernehmen“ benutzt → Standard."""
    url = (opts or {}).get("url") or ""
    if not url:
        try:
            url = load_settings(ctx).get("url") or ""
        except (OSError, AttributeError, TypeError):
            url = ""
    if not url:
        try:
            url = ctx._session.cfg["plugin_options"]["lexicon"]["import"]["url"]
        except (AttributeError, KeyError, TypeError):
            url = ""
    return (url or DEFAULT_URL).strip().rstrip("/")


def client(ctx, opts=None, timeout=20):
    return lexapi.Client(_base(ctx, opts), timeout=timeout)


def writer(ctx, need=None):
    """Client zum Schreiben – nur mit Hauptschalter (und Unterschalter need) und nur auf diesem Rechner."""
    st = load_settings(ctx)
    if not st["write"] or (need and not st.get(need)):
        raise LexiconError("Zurückschreiben nach Lexicon ist ausgeschaltet (Plugins › Lexicon › Einstellungen …).")
    c = client(ctx)
    if not c.local:
        raise LexiconError(f"Geschrieben wird nur an Lexicon auf diesem Rechner (localhost) – nicht an {c.base}.")
    return c, st


# =========================================================================== Zuordnung Datei ↔ Lexicon
_norm_path = lexapi.norm_path


def _norm_name(artist, title) -> str:
    s = f"{artist or ''}\x00{title or ''}".lower()
    return re.sub(r"[^\w\x00]+", " ", s).strip()


def _same_path(t, path) -> bool:
    want = _norm_path(path)
    return any(_norm_path(t.get(k)) == want for k in ("location", "locationUnique") if t.get(k))


def load_tracks(base_or_client, ctx=None, fields=None) -> list:
    """Ganze Bibliothek (nicht archiviert) – nur für grosse Auswahlen und die Testabfrage."""
    c = base_or_client if isinstance(base_or_client, lexapi.Client) else lexapi.Client(base_or_client)

    def prog(n, total):
        if ctx:
            ctx.status(f"Lexicon: {n} von {total} Titeln gelesen")
            ctx.check_cancel()
    return c.tracks(fields=fields, progress=prog)


def index(tracks):
    by_path, by_name, dup = {}, {}, set()
    for t in tracks:
        if t.get("archived"):
            continue
        for k in (t.get("location"), t.get("locationUnique")):
            if k:
                by_path[_norm_path(k)] = t
        n = _norm_name(t.get("artist"), t.get("title"))
        if n.strip("\x00 "):
            if n in by_name:
                dup.add(n)
            by_name[n] = t
    for n in dup:
        by_name.pop(n, None)          # mehrdeutig → nicht über den Namen zuordnen
    return by_path, by_name


class Matcher:
    """Datei → Lexicon-Titel. Bis SEARCH_MAX Dateien gezielt über die Suche, sonst einmal die ganze Bibliothek."""

    def __init__(self, c, ctx, n_files, fields=None):
        self.c, self.ctx, self.fields = c, ctx, fields or TRACK_FIELDS
        self.full = n_files > SEARCH_MAX
        self.total = None
        if self.full:
            tracks = load_tracks(c, ctx, self.fields)
            self.total = len(tracks)
            self.by_path, self.by_name = index(tracks)

    def find(self, path, artist="", title="", by_name=True):
        if self.full:
            t = self.by_path.get(_norm_path(path))
            if t is None and by_name:
                return self.by_name.get(_norm_name(artist, title)), "Künstler + Titel"
            return t, "Pfad"
        hits = [t for t in self.c.search({"location": path}, self.fields, limit=20)
                if _same_path(t, path) and not t.get("archived")]
        if hits:
            return hits[0], "Pfad"
        if by_name and (artist or title):
            want = _norm_name(artist, title)
            filt = {k: v for k, v in (("artist", artist), ("title", title)) if v}
            hits = [t for t in self.c.search(filt, self.fields, limit=50)
                    if not t.get("archived") and _norm_name(t.get("artist"), t.get("title")) == want]
            if len(hits) == 1:                # mehrdeutig → nicht über den Namen zuordnen
                return hits[0], "Künstler + Titel"
        return None, ""


LABELS = {"danceability": "Tanzbarkeit", "energy": "Energie", "happiness": "Fröhlichkeit"}


def _native(v):
    """Lexicon-Wert 1–10 unverändert als Text („7“, „6.5“); 0 bzw. leer = nicht analysiert → None."""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return f"{n:g}" if 0 < n <= 10 else None


def _level(v):
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return int(round(n * 10)) if 0 < n <= 10 else None


def tag_names(c) -> tuple[dict, dict]:
    """→ ({Tag-ID: (Kategorie, Name)}, {Kategorie-Name (klein): Kategorie-ID})"""
    d = c.tags()
    cats = {x.get("id"): (x.get("label") or "") for x in d["categories"]}
    tags = {t["id"]: (cats.get(t.get("categoryId"), ""), t.get("label") or "") for t in d["tags"] if "id" in t}
    return tags, {v.strip().lower(): k for k, v in cats.items()}


def load_moods(base) -> dict:
    """Tag-ID → Name für die Kategorie „Mood“ (bleibt für ältere Aufrufer)."""
    tags, _cats = tag_names(lexapi.Client(base))
    return {i: n for i, (cat, n) in tags.items() if cat.strip().lower() in ("mood", "stimmung")}


def _is_mood(cat: str) -> bool:
    return cat.strip().lower() in ("mood", "stimmung")


# =========================================================================== Vergleich Beatgrid / Cue-Punkte (#237)
def lex_grid(t) -> dict | None:
    ms = sorted((m for m in t.get("tempomarkers") or [] if isinstance(m, dict) and m.get("bpm")),
                key=lambda m: float(m.get("startTime") or 0))
    if not ms:
        return None
    return {"bpm": float(ms[0]["bpm"]), "first": float(ms[0].get("startTime") or 0), "markers": ms}


def grid_note(f, t) -> str:
    """Kurzer Hinweis: Beatgrid und Cue-Punkte in Lexicon im Vergleich zur Datei (Serato bzw. eigene Analyse)."""
    import cues
    import gridstatus
    parts = []
    lg = lex_grid(t)
    if lg:
        other, name = gridstatus.serato_grid(f), "Serato"
        if other is None:
            other, name = gridstatus.own_beat(f), "Analyse"
        if other:
            _ok, txt = gridstatus.compare(lg, other, "Lexicon", name)
            parts.append("Beatgrid: " + txt)
        else:
            parts.append(f"Beatgrid in Lexicon: {lg['bpm']:.2f} BPM (Datei ohne Beatgrid)")
    lc = [c for c in t.get("cuepoints") or [] if isinstance(c, dict)]
    if lc:
        try:
            fc = cues.read(f)
        except Exception:  # noqa: BLE001
            fc = []
        lpos = [float(c.get("startTime") or 0) for c in lc]
        same = sum(1 for c in fc if any(abs(c["pos"] - p) < 0.05 for p in lpos))
        loops = sum(1 for c in lc if str(c.get("type")) == "5")
        parts.append(f"Cue-Punkte: Lexicon {len(lc)}" + (f" (davon {loops} Loop)" if loops else "")
                     + f", Datei {len(fc)}, gleiche Stelle {same}")
    return " · ".join(parts)


def status_note(t) -> str:
    bits = []
    if t.get("incoming"):
        bits.append("in Lexicon: Incoming")
    if not any((t.get(k) or 0) for k in ("energy", "danceability", "happiness")) and not t.get("tempomarkers"):
        bits.append("noch nicht analysiert")
    return " · ".join(bits)


# =========================================================================== Übernehmen (#146, #237)
def run_import(ctx, files, opts):
    c = client(ctx, opts)
    ctx.status("Verbinde mit Lexicon …")
    m = Matcher(c, ctx, len(files))
    tags, _cats = tag_names(c) if (opts.get("mood") or opts.get("tags_to")) else ({}, {})
    found = changed = 0
    missing = []
    for n, f in enumerate(files):
        group = f.path.replace("\\", "/").rsplit("/", 1)[-1]
        ctx.progress(n, len(files), group)
        t, how = m.find(f.path, f.text("TPE1"), f.text("TIT2"), bool(opts.get("by_name")))
        if t is None:
            missing.append(group)
            continue
        found += 1
        extra = [x for x in (status_note(t), grid_note(f, t) if opts.get("grid") else "") if x]
        note = f"Lexicon (zugeordnet über {how})" + ("" if not extra else " · " + " · ".join(extra))
        if extra:
            ctx.log(f"{group}: " + " · ".join(extra))
        any_ = False
        # #240 (Entscheid User 17.10.2026): Lexicon-Werte ohne offizielles MP3-Feld in eigene Felder TXXX:LEXICON_…,
        # unverändert wie in Lexicon (1–10) – die TagStudio-Felder (ENERGY usw.) fasst „Lexicon übernehmen“ nicht an
        for field, name in FIELDS:
            v = _native(t.get(field))
            if v is None or not opts.get(field):
                continue
            any_ |= ctx.propose(f, f"TXXX:LEXICON_{name}", v, f"Lexicon: {LABELS[field]} (LEXICON_{name})", note=note,
                                group=group, hint="Wert aus Lexicon (1–10)")
        r = t.get("rating")
        if opts.get("rating") and isinstance(r, (int, float)) and 0 < r <= 5:
            any_ |= ctx.propose(f, "POPM", str(int(r)), "Bewertung (Sterne)", kind="rating", note=note, group=group,
                                hint="aus Lexicon")
        pop = _native(t.get("popularity"))
        if opts.get("popularity") and pop is not None:
            any_ |= ctx.propose(f, "TXXX:LEXICON_POPULARITY", pop, "Lexicon: Popularität (LEXICON_POPULARITY)", note=note,
                                group=group, hint="Wert aus Lexicon (1–10)")
        if opts.get("color") and t.get("color"):
            any_ |= ctx.propose(f, "TXXX:LEXICON_COLOR", str(t["color"]), "Lexicon: Farbe (LEXICON_COLOR)", note=note, group=group)
        named = [tags[i] for i in t.get("tags") or [] if i in tags]
        if opts.get("mood"):
            names = [nm for cat, nm in named if _is_mood(cat)]
            # TMOO ist nur in ID3v2.4 ein offizielles Feld – sonst eigenes Lexicon-Feld (#240)
            key = "TMOO" if moods.key_for(f) == "TMOO" else "TXXX:LEXICON_MOOD"
            it = f.get(key)
            cur = [x for x in (it.text if it is not None else "").split(MV) if x]
            if names and [x.lower() for x in names] != [x.lower() for x in cur]:
                any_ |= ctx.propose(f, key, MV.join(names), f"Lexicon: Stimmung ({key.split(':')[-1]})", note=note,
                                    checked=not cur or key != "TMOO", group=group,
                                    hint="aus Lexicon-Tags" + (f" · Datei hat {', '.join(cur)}" if cur else ""))
        target = opts.get("tags_to") or ""
        if target:
            by_cat = {}
            for cat, nm in named:
                if not _is_mood(cat):
                    by_cat.setdefault(cat or "Tags", []).append(nm)
            if by_cat:
                text = "; ".join(f"{cat}: {', '.join(v)}" for cat, v in by_cat.items())
                key = "COMM:" if target == "COMM" else target
                cur = f.text(key) if f.get(key) is not None else ""
                any_ |= ctx.propose(f, key, text, f"Lexicon-Tags → {target}", note=note, group=group,
                                    checked=not cur, hint="schon gefüllt – bitte prüfen" if cur else "aus Lexicon-Tags")
        changed += bool(any_)
    ctx.progress(len(files), len(files), "fertig")
    msg = f"{found} von {len(files)} Titel(n) in Lexicon gefunden"
    msg += f" ({m.total} Titel in Lexicon)" if m.total is not None else ""
    msg += f"; {changed} mit Änderungen (Vorschau)"
    if missing:
        ctx.log("Nicht in Lexicon gefunden:\n" + "\n".join(missing))
    return {"message": msg + "."}


# =========================================================================== Öffnen (#238)
def find_playlist(c, text: str):
    """Playlist über Namen oder Pfad „Ordner/Name“ (ohne Gross-/Kleinschreibung); eindeutig, sonst Fehler."""
    want = [p.strip().lower() for p in re.split(r"[/\\›>]", text or "") if p.strip()]
    if not want:
        raise ValueError("Bitte den Namen der Playlist angeben (z. B. Sets/Freitag).")
    flat = lexapi.flatten(c.playlists())
    hits = [p for p in flat if [x.lower() for x in p["path"]][-len(want):] == want]
    if len(hits) > 1:                             # gleich benannt: Playlists/Smartlists vor Ordnern
        hits = [p for p in hits if p["type"] != "1"] or hits
    if not hits:
        raise ValueError(f"Keine Playlist „{text}“ in Lexicon gefunden.")
    if len(hits) > 1:
        raise ValueError(f"Mehrere Playlists heissen „{text}“ – bitte mit Ordner angeben, z. B. "
                         + " oder ".join("/".join(h["path"][-2:]) for h in hits[:3]) + ".")
    return hits[0]


def run_open(ctx, opts):
    c = client(ctx, opts)
    src = opts.get("source") or "tracks"
    ctx.status("Frage Lexicon …")
    if src == "tracks":
        ids, label = c.selected_ids(), "markierte Titel in Lexicon"
        if not ids:
            return {"message": "In Lexicon sind keine Titel markiert – bitte zuerst in Lexicon Titel auswählen."}
    else:
        if src == "playlist":
            sel = c.selected_playlists()
            if not sel:
                return {"message": "In Lexicon ist keine Playlist markiert – bitte zuerst in Lexicon eine Playlist auswählen."}
            pl = c.playlist(sel[0])
        else:
            pl = c.playlist(find_playlist(c, opts.get("path") or "")["id"])
        pl = pl or {}
        ids, label = pl.get("trackIds") or [], pl.get("name") or "Playlist"
    tracks = c.tracks_by_ids(ids, ["id", "location", "artist", "title"])
    paths = [t.get("location") for t in tracks if t.get("location")]
    here = [p for p in paths if os.path.isfile(p)]
    gone = [p for p in paths if p not in here]
    for p in gone[:50]:
        ctx.log(f"nicht auf diesem Rechner: {p}")
    if not here:
        return {"message": f"„{label}“: {len(ids)} Titel, aber keiner davon ist auf diesem Rechner vorhanden."}
    target = opts.get("target") or "tagger"
    msg = f"„{label}“: {len(here)} Titel" + (f" ({len(gone)} nicht auf diesem Rechner)" if gone else "")
    return {"message": msg + ".", "open": {"target": target, "files": here, "label": label}}


def detect_files(ctx, paths) -> list:
    """Vorbereiten (#238), Schritt „Lexicon“: Dateien, die in Lexicon vorhanden sind (nicht archiviert)."""
    c = client(ctx, timeout=5)
    out = []
    for p in paths[:500]:
        try:
            if any(_same_path(t, p) and not t.get("archived")
                   for t in c.search({"location": p}, ["id", "location", "locationUnique", "archived"], limit=20)):
                out.append(p)
        except LexiconError:
            break                                   # Lexicon läuft nicht → nichts erkannt, kein Fehler
    return out


# =========================================================================== Zurückschreiben (#239)
def _journal_path(ctx) -> str:
    return os.path.join(ctx.data_dir, "journal.json")


def journal_load(ctx) -> list:
    try:
        with open(_journal_path(ctx), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


def journal_add(ctx, what: str, items: list):
    """Änderung merken (neueste zuletzt, höchstens 100 Einträge)."""
    if not items:
        return
    j = journal_load(ctx)
    j.append({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "what": what, "items": items, "undone": False})
    tmp = _journal_path(ctx) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(j[-100:], fh, ensure_ascii=False, indent=1)
    os.replace(tmp, _journal_path(ctx))


def _journal_save(ctx, j):
    tmp = _journal_path(ctx) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(j[-100:], fh, ensure_ascii=False, indent=1)
    os.replace(tmp, _journal_path(ctx))


def on_moved(ctx, moves):
    """Pfade in Lexicon nachführen (alter Pfad → neuer Pfad)."""
    c, _st = writer(ctx, "move")
    done, items = 0, []
    for mv in moves:
        old, new = str(mv.get("old") or ""), str(mv.get("new") or "")
        if not old or not new or _norm_path(old) == _norm_path(new):
            continue
        hits = [t for t in c.search({"location": old}, ["id", "location", "locationUnique"], source="all", limit=20)
                if _same_path(t, old)]
        if not hits:
            ctx.log(f"nicht in Lexicon: {old}")
            continue
        t = hits[0]
        try:
            c.set_location(t["id"], new, check=True)
        except LexiconError as ex:
            ctx.log(f"Pfad nicht geändert ({os.path.basename(old)}): {ex}")
            continue
        items.append({"kind": "location", "id": t["id"], "old": t.get("location") or old, "new": new})
        ctx.log(f"Pfad nachgeführt: {old} → {new}")
        done += 1
    journal_add(ctx, f"{done} Pfad(e) nachgeführt", items)
    return done


def ensure_playlist(c, name: str) -> int:
    """Playlist (oberste Ebene) mit diesem Namen – vorhandene nutzen, sonst anlegen."""
    for p in lexapi.flatten(c.playlists()):
        if p["type"] == "2" and p["name"].strip().lower() == name.strip().lower():
            return int(p["id"])
    return c.playlist_create(name, "2")


def on_added(ctx, paths):
    """Neu in die Bibliothek übernommene Dateien in Lexicon aufnehmen (optional Playlist und Analyse)."""
    c, st = writer(ctx, "add")
    tracks = c.add_tracks([p for p in paths if isinstance(p, str)])
    ids = [t["id"] for t in tracks if isinstance(t, dict) and t.get("id") is not None]
    ctx.log(f"{len(ids)} Titel in Lexicon aufgenommen")
    items = [{"kind": "added", "id": i} for i in ids]
    if ids and (st.get("playlist") or "").strip():
        pid = ensure_playlist(c, st["playlist"].strip())
        c.playlist_add(pid, ids)
        items.append({"kind": "playlist_tracks", "id": pid, "tracks": ids})
        ctx.log(f"in Playlist „{st['playlist'].strip()}“ gelegt")
    if ids and st.get("analyze"):
        c.control("AudioAnalyzer_Analyze", {"trackIds": ids, "doNotOverwrite": True})
        ctx.log("Analyse in Lexicon gestartet")
    journal_add(ctx, f"{len(ids)} Titel in Lexicon aufgenommen", items)
    return len(ids)


def on_event(ctx, event, data):
    """Vom Plugin-Rahmen: Dateien verschoben/umbenannt bzw. neu in der Bibliothek (#239)."""
    st = load_settings(ctx)
    if not st["write"]:
        return
    try:
        if event == "files_moved" and st["move"]:
            on_moved(ctx, data)
        elif event == "files_added" and st["add"]:
            on_added(ctx, data)
    except LexiconError as ex:
        ctx.log(f"Lexicon: {ex}")


# ---- Tags nach Lexicon übertragen (Vorschau → apply_remote)
def _num(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _key_like(lex_value: str, code: str) -> str:
    """Tonart in der Schreibweise, die Lexicon für diesen Titel schon nutzt (sonst musikalisch, z. B. Am)."""
    import keys
    lv = str(lex_value or "").strip()
    if re.fullmatch(r"0?\d{1,2}[AB]", lv, re.I):
        return keys.format_key(code, "camelot").lstrip("0") if not lv.startswith("0") else keys.format_key(code, "camelot")
    if re.fullmatch(r"\d{1,2}[md]", lv, re.I):
        return keys.format_key(code, "openkey")
    return keys.format_key(code, "musical")


def run_send(ctx, files, opts):
    import features
    import keys
    import ratings
    c, _st = writer(ctx)
    m = Matcher(c, ctx, len(files))
    tags, cats = tag_names(c) if opts.get("mood") else ({}, {})
    mood_ids = {nm.lower(): i for i, (cat, nm) in tags.items() if _is_mood(cat)}
    mood_cat = next((cid for name, cid in cats.items() if _is_mood(name)), None)
    found = rows = 0
    missing = []
    for n, f in enumerate(files):
        group = os.path.basename(f.path)
        ctx.progress(n, len(files), group)
        t, how = m.find(f.path, f.text("TPE1"), f.text("TIT2"))
        if t is None:
            missing.append(group)
            continue
        found += 1
        note = f"Lexicon-Titel {t.get('id')} (zugeordnet über {how}) – geändert wird in Lexicon, nicht in der Datei"

        def prop(field, label, new_show, value, old_show):
            nonlocal rows
            if ctx.propose(f, field, new_show, f"Lexicon: {label}", kind="remote", old=old_show, group=group, note=note,
                           data={"id": t["id"], "field": field, "value": value}, hint="wird in Lexicon geändert"):
                rows += 1
        if opts.get("basic"):
            for field, key, label in (("title", "TIT2", "Titel"), ("artist", "TPE1", "Künstler"),
                                      ("albumTitle", "TALB", "Album"), ("genre", "TCON", "Genre")):
                v = f.text(key).replace(MV, ", ").strip()
                if v and v != (t.get(field) or ""):
                    prop(field, label, v, v, t.get(field) or "")
        if opts.get("bpm_key"):
            b = _num(f.text("TBPM"))
            lb = _num(t.get("bpm"))
            if b and (lb is None or abs(b - lb) > 0.01):
                prop("bpm", "BPM", f"{b:g}", round(b, 2), "" if lb is None else f"{lb:g}")
            code = keys.parse_key(f.text("TKEY"))
            if code and code != keys.parse_key(t.get("key") or ""):
                kv = _key_like(t.get("key") or "", code)
                prop("key", "Tonart", kv, kv, t.get("key") or "")
        if opts.get("rating"):
            r = ratings.get_rating(f)
            if r and r != int(t.get("rating") or 0):
                prop("rating", "Bewertung (Sterne)", str(r), r, str(t.get("rating") or ""))
        if opts.get("features"):
            for field, name in FIELDS:
                v = features.number(features.get(f, name))
                if v is None:
                    continue
                lv = max(1, min(10, int(round(v / 10))))
                if lv != int(t.get(field) or 0):
                    prop(field, name.title(), str(lv), lv, str(t.get(field) or ""))
        if opts.get("mood") and mood_cat is not None:
            want = moods.values(f)
            cur_ids = [i for i in t.get("tags") or []]
            cur_moods = [tags[i][1] for i in cur_ids if i in tags and _is_mood(tags[i][0])]
            if want and [x.lower() for x in want] != [x.lower() for x in cur_moods]:
                keep = [i for i in cur_ids if not (i in tags and _is_mood(tags[i][0]))]
                prop("tags", "Mood-Tags", ", ".join(want),
                     {"keep": keep, "moods": want, "category": mood_cat, "known": {k: mood_ids[k.lower()] for k in want
                                                                                 if k.lower() in mood_ids}},
                     ", ".join(cur_moods))
    ctx.progress(len(files), len(files), "fertig")
    if missing:
        ctx.log("Nicht in Lexicon gefunden:\n" + "\n".join(missing))
    return {"message": f"{found} von {len(files)} Titel(n) in Lexicon gefunden; {rows} Wert(e) weichen ab (Vorschau)."}


def apply_remote(ctx, items):
    """Gewählte Vorschläge aus „Nach Lexicon übertragen“ schreiben (je Titel ein PATCH), Journal für Rückgängig."""
    c, _st = writer(ctx)
    by_id = {}
    for it in items:
        d = it.get("data") or {}
        if "id" in d and d.get("field"):
            by_id.setdefault(int(d["id"]), {})[d["field"]] = d.get("value")
    done, errors, journal = 0, [], []
    for tid, edits in by_id.items():
        try:
            cur = c.track(tid) or {}
            if "tags" in edits:
                spec = edits["tags"]
                ids = list(spec.get("keep") or [])
                for name in spec.get("moods") or []:
                    tid_tag = (spec.get("known") or {}).get(name)
                    if tid_tag is None:
                        tid_tag = c.tag_create(spec["category"], name).get("id")
                        ctx.log(f"Tag „{name}“ in Lexicon angelegt")
                    if tid_tag is not None:
                        ids.append(int(tid_tag))
                edits["tags"] = ids
            old = {k: cur.get(k) for k in edits}
            c.patch_track(tid, edits)
            journal.append({"kind": "edits", "id": tid, "old": old, "new": edits})
            ctx.log(f"Lexicon-Titel {tid}: " + ", ".join(edits))
            done += 1
        except LexiconError as ex:
            errors.append(f"Titel {tid}: {ex}")
    journal_add(ctx, f"{done} Titel in Lexicon geändert", journal)
    msg = f"{done} Titel in Lexicon geändert." + (f" {len(errors)} Fehler." if errors else "")
    return {"count": done, "errors": errors, "message": msg}


def run_djset(ctx, opts):
    c, _st = writer(ctx)
    ds = ctx.djset()
    if not ds["paths"]:
        return {"message": "Das DJ-Set ist leer."}
    name = (opts.get("name") or ds["name"] or f"TagStudio DJ-Set {time.strftime('%Y-%m-%d')}").strip()
    m = Matcher(c, ctx, len(ds["paths"]), ["id", "location", "locationUnique", "archived"])
    ids, missing = [], []
    for n, p in enumerate(ds["paths"]):
        ctx.progress(n, len(ds["paths"]), os.path.basename(p))
        t, _how = m.find(p, by_name=False)
        if t is None:
            missing.append(os.path.basename(p))
        else:
            ids.append(t["id"])
    if not ids:
        return {"message": "Keiner der Titel des DJ-Sets ist in Lexicon."}
    pid = c.playlist_create(name, "2")
    c.playlist_add(pid, ids)
    journal_add(ctx, f"Playlist „{name}“ angelegt", [{"kind": "playlist", "id": pid, "name": name, "tracks": ids}])
    if missing:
        ctx.log("Nicht in Lexicon (nicht in der Playlist):\n" + "\n".join(missing))
    return {"message": f"Playlist „{name}“ in Lexicon angelegt: {len(ids)} Titel" +
                       (f", {len(missing)} nicht in Lexicon" if missing else "") + "."}


def run_undo(ctx):
    j = journal_load(ctx)
    k = next((i for i in range(len(j) - 1, -1, -1) if not j[i].get("undone")
              and any(x.get("kind") in ("edits", "location") for x in j[i].get("items") or [])), None)
    if k is None:
        return {"message": "Keine Änderung zum Rückgängigmachen."}
    c, _st = writer(ctx)
    e = j[k]
    done = 0
    for it in reversed(e.get("items") or []):
        try:
            if it.get("kind") == "edits":
                old = {f: v for f, v in (it.get("old") or {}).items() if v is not None}
                if old:
                    c.patch_track(it["id"], old)
                    done += 1
            elif it.get("kind") == "location":
                c.set_location(it["id"], it["old"], check=False)
                done += 1
        except LexiconError as ex:
            ctx.log(f"Titel {it.get('id')}: {ex}")
    e["undone"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _journal_save(ctx, j)
    keep = sum(1 for it in e.get("items") or [] if it.get("kind") in ("added", "playlist", "playlist_tracks"))
    return {"message": f"Rückgängig ({e['at']}, {e['what']}): {done} Titel zurückgesetzt."
                       + (" Aufgenommene Titel und Playlists bleiben (TagStudio löscht nichts in Lexicon)." if keep else "")}


# =========================================================================== #204: Integration
def api_request(ctx, ep, params):
    """API-Tester: GET an die Local API – ohne Proxy, Adresse aus den Plugin-Optionen."""
    import urllib.error
    import urllib.request
    import services
    svc = {"base": _base(ctx) + "/v1"}
    url = services.build_url(svc, ep, params)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=20) as r:
            return r.status, dict(r.headers), r.read(), url
    except urllib.error.HTTPError as ex:
        return ex.code, dict(ex.headers or {}), ex.read(), url
    except (urllib.error.URLError, OSError) as ex:
        raise LexiconError(f"Keine Verbindung zu Lexicon unter {_base(ctx)} – läuft Lexicon und ist die Local API "
                           f"eingeschaltet (Settings › Integrations)? ({getattr(ex, 'reason', ex)})") from ex


def test_query(ctx, info):
    """Testabfrage ohne Track: Titel in Lexicon über Künstler und Titel suchen."""
    c = client(ctx)
    filt = {k: v for k, v in (("artist", info.get("artist")), ("title", info.get("title"))) if v}
    tracks = c.search(filt, TRACK_FIELDS, limit=200) if filt else []
    ctx.log(f"Lexicon unter {c.base}: {len(tracks)} Treffer")
    out = []
    for t in tracks:
        if t.get("archived"):
            continue
        vals = [f"{lab} {_level(t.get(k)) or '–'}" for k, lab in (("energy", "Energie"), ("danceability", "Tanzbarkeit"),
                                                                    ("happiness", "Fröhlichkeit"))]
        out.append({"source_name": "Lexicon", "id": t.get("id"), "title": t.get("title") or "", "artists": [t.get("artist") or ""],
                    "album": t.get("albumTitle") or t.get("album") or "", "length": t.get("duration") or None,
                    "extra": " · ".join(vals) + (f" · {t.get('location')}" if t.get("location") else "")})
    ctx.log(f"{len(out)} passende Titel")
    return out


def test_connection(ctx) -> dict:
    """Verbindung testen: zeigt, ob Lexicon läuft und die Local API eingeschaltet ist."""
    c = client(ctx, timeout=5)
    ctx.status(f"Verbinde mit Lexicon unter {c.base} …")
    try:
        total = c.total()
    except LexiconError as ex:
        ctx.log(str(ex))
        return {"message": f"Lexicon nicht erreichbar: {ex}"}
    ctx.log(f"GET {c.base}/v1/tracks?limit=1 → OK, {total} Titel")
    msg = f"Lexicon ist erreichbar unter {c.base} – {total} Titel in der Bibliothek."
    if not c.local:
        msg += " Hinweis: Adresse nicht auf diesem Rechner – Zurückschreiben ist dort gesperrt."
    return {"message": msg}


def status(ctx) -> str:
    """Text auf der Plugin-Karte: was zurückgeschrieben wird."""
    st = load_settings(ctx)
    if not st["write"]:
        return "Liest nur aus Lexicon (Zurückschreiben aus)"
    on = [lab for k, lab in (("move", "Pfade"), ("add", "neue Titel")) if st.get(k)]
    return "Zurückschreiben nach Lexicon: " + (", ".join(on) if on else "nur von Hand")


def run(action, ctx, files, opts):
    if action == "test":
        return test_connection(ctx)
    if action == "settings":
        d = save_settings(ctx, opts)
        return {"message": "Gespeichert. " + status(ctx) + ("" if not d["write"] or lexapi.is_local(d["url"] or DEFAULT_URL)
                                                          else " – Achtung: Adresse nicht auf diesem Rechner, Schreiben gesperrt.")}
    if action == "import":
        return run_import(ctx, files, opts)
    if action == "open":
        return run_open(ctx, opts)
    if action == "send":
        return run_send(ctx, files, opts)
    if action == "djset":
        return run_djset(ctx, opts)
    if action == "undo":
        return run_undo(ctx)
    raise ValueError(f"Unbekannte Aktion: {action}")
