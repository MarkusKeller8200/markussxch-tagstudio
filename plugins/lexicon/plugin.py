"""Lexicon übernehmen (#146): Tanzbarkeit, Energie und Fröhlichkeit aus Lexicon DJ als Audio-Merkmale.

Gelesen wird über die Local API von Lexicon (Lexicon › Settings › Integrations › Local API einschalten; Standard
http://localhost:48624). Endpunkte: /v1/tracks (Seiten zu höchstens 1000 Titeln) und /v1/tags.
Felder pro Titel u. a.: location (Pfad), artist, title, danceability, energy, happiness (je 1–10, 0 = nicht
analysiert), tags (IDs, Kategorien Genre/Mood/…). Zuordnung über den Dateipfad, sonst über Künstler + Titel.
Abgleich wie bei beaTunes (importsync): geänderte Werte werden nur angehakt, wenn die Datei seit dem letzten
Übernehmen unverändert ist – sonst fragt die Vorschau. Nur Standardbibliothek; nur lesender Zugriff auf Lexicon.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

import importsync

SOURCE, SOURCE_NAME = "lexicon", "Lexicon"
FIELDS = (("danceability", "DANCEABILITY"), ("energy", "ENERGY"), ("happiness", "HAPPINESS"))
PAGE = 1000

ACTIONS = [{
    "id": "import", "label": "Lexicon übernehmen …", "where": "tagger", "run_label": "Abgleichen",
    "description": "Liest Tanzbarkeit, Energie und Fröhlichkeit aus Lexicon (Local API) und schlägt sie als "
                   "Audio-Merkmale vor. Werte, die in der Datei seit dem letzten Abgleich geändert wurden, sind nicht "
                   "angehakt – du entscheidest.",
    "options": [
        {"key": "url", "type": "text", "label": "Adresse der Lexicon Local API", "default": "http://localhost:48624"},
        {"key": "danceability", "type": "check", "label": "Tanzbarkeit → DANCEABILITY", "default": True},
        {"key": "energy", "type": "check", "label": "Energie → ENERGY", "default": True},
        {"key": "happiness", "type": "check", "label": "Fröhlichkeit → HAPPINESS", "default": False},
        {"key": "mood", "type": "check", "label": "Lexicon-Tags der Kategorie „Mood“ → Stimmung (TMOO)", "default": False},
        {"key": "by_name", "type": "check", "label": "Titel ohne Pfad-Treffer über Künstler + Titel zuordnen", "default": True},
        {"type": "info", "label": "Lexicon muss laufen und die Local API eingeschaltet sein (Settings › Integrations). "
                                  "Lexicon-Werte 1–10 werden zu 10–100; 0 heisst „nicht analysiert“ und wird übergangen."},
    ],
}]


def _norm_path(p: str) -> str:
    return (p or "").replace("\\", "/").strip().lower()


def _norm_name(artist, title) -> str:
    s = f"{artist or ''}\x00{title or ''}".lower()
    return re.sub(r"[^\w\x00]+", " ", s).strip()


class LexiconError(RuntimeError):
    pass


def _get(base: str, path: str, timeout=20):
    url = base.rstrip("/") + path
    if not re.match(r"^https?://", url):
        raise LexiconError(f"Ungültige Adresse: {base}")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # nie über einen Proxy
    try:
        with opener.open(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        try:
            msg = json.loads(ex.read().decode("utf-8")).get("message", "")
        except Exception:  # noqa: BLE001
            msg = ""
        raise LexiconError(f"Lexicon meldet Fehler {ex.code}{': ' + msg if msg else ''} ({path})") from ex
    except (urllib.error.URLError, OSError, ValueError) as ex:
        raise LexiconError(f"Keine Verbindung zu Lexicon unter {base} – läuft Lexicon und ist die Local API "
                           f"eingeschaltet (Settings › Integrations)? ({getattr(ex, 'reason', ex)})") from ex
    if not isinstance(data, dict) or not isinstance(data.get("data"), dict):
        raise LexiconError(f"Unerwartete Antwort von Lexicon ({path}).")
    return data["data"]


def load_tracks(base, ctx=None) -> list:
    out, offset, total = [], 0, None
    while total is None or offset < total:
        d = _get(base, f"/v1/tracks?limit={PAGE}&offset={offset}")
        tracks = d.get("tracks") or []
        total = int(d.get("total") or 0)
        out += tracks
        offset += len(tracks)
        if ctx:
            ctx.status(f"Lexicon: {len(out)} von {total} Titeln gelesen")
            ctx.check_cancel()
        if not tracks:
            break
    return out


def load_moods(base) -> dict:
    """Tag-ID → Name für die Kategorie „Mood“."""
    d = _get(base, "/v1/tags")
    cats = {c.get("id"): (c.get("label") or "") for c in d.get("categories") or []}
    return {t["id"]: t.get("label") or "" for t in d.get("tags") or []
            if cats.get(t.get("categoryId"), "").strip().lower() in ("mood", "stimmung")}


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


def _level(v):
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return int(round(n * 10)) if 0 < n <= 10 else None


def run(action, ctx, files, opts):
    if action != "import":
        raise ValueError(f"Unbekannte Aktion: {action}")
    base = (opts.get("url") or "http://localhost:48624").strip()
    ctx.status("Verbinde mit Lexicon …")
    tracks = load_tracks(base, ctx)
    moods = load_moods(base) if opts.get("mood") else {}
    by_path, by_name = index(tracks)
    found = changed = asks = 0
    missing = []
    for n, f in enumerate(files):
        ctx.progress(n, len(files), f.path.replace("\\", "/").rsplit("/", 1)[-1])
        group = f.path.replace("\\", "/").rsplit("/", 1)[-1]
        t = by_path.get(_norm_path(f.path))
        how = "Pfad"
        if t is None and opts.get("by_name"):
            t = by_name.get(_norm_name(f.text("TPE1"), f.text("TIT2")))
            how = "Künstler + Titel"
        if t is None:
            missing.append(group)
            continue
        found += 1
        note = f"Lexicon (zugeordnet über {how})"
        any_ = False
        for field, name in FIELDS:
            v = _level(t.get(field))
            if v is None:
                continue
            st = importsync.propose(ctx, f, SOURCE, SOURCE_NAME, name, v, enabled=bool(opts.get(field)),
                                    group=group, note=note)
            any_ |= st != "same"
            asks += st == "conflict"
        if moods:
            names = [moods[i] for i in t.get("tags") or [] if i in moods]
            if names:
                val = ", ".join(names)
                any_ |= ctx.propose(f, "TMOO", val, "Stimmung (TMOO)", note=note, checked=not f.text("TMOO"), group=group,
                                    hint="aus Lexicon-Tags" + (" · Feld schon gefüllt" if f.text("TMOO") else ""))
        changed += bool(any_)
    ctx.progress(len(files), len(files), "fertig")
    msg = (f"{found} von {len(files)} Titel(n) in Lexicon gefunden ({len(tracks)} Titel in Lexicon); "
           f"{changed} mit Änderungen (Vorschau)")
    if asks:
        msg += f", {asks} Wert(e) zum Prüfen (nicht angehakt)"
    if missing:
        ctx.log("Nicht in Lexicon gefunden:\n" + "\n".join(missing))
    return {"message": msg + "."}
