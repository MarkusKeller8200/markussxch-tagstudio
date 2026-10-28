"""SonoVault (#253–#255, 4.11.0): Musik-Metadaten-API von Rekordcloud mit eigenem Schlüssel.

Entscheide des Users (docs/KONZEPT-SONOVAULT.md Abschnitt 6): Free-Tarif – TagStudio zählt die Anfragen je Monat,
zeigt den Rest und warnt vor dem Überschreiten (SV1); Plattform-IDs nur anzeigen (SV3); Vorrang in „Online-Metadaten“
nach MusicBrainz, vor Deezer und iTunes (SV4).

Nutzungsbedingungen (Abschnitt 3): In Dateien dürfen nur Titel, Künstler, Release-Titel, Label, Genre,
Erscheinungsdatum, Dauer und ISRC – BPM, Tonart, ISWC, Katalognummer und Plattform-IDs nur anzeigen bzw. vergleichen.
Zwischenspeicher höchstens 30 Tage, nichts exportieren, keine SonoVault-Werte ins Protokoll (Protokolle liegen als
Datei im Log-Ordner). Bei HTTP 429 wird nie wiederholt. Nur Standardbibliothek.

Seit 1.2 (#380, #381, #383, #259): eigene Felder ``TXXX:SONOVAULT_*`` mit Herkunft „SonoVault“ (nur die erlaubten
Felder + Abrufdatum), „Release nachschlagen“ (ganzes Album/EP mit zwei Anfragen), Tarif-Einstellung – mit bezahltem Tarif
zusätzlich Entdecken über Browse (Label/Genre, neueste zuerst) und „Genre-Korrektur melden“ (``genreId`` + ``note``).

Antwortfelder (snake_case) laut den offiziellen SDKs von Rekordcloud: Titel mit ``id``, ``title``, ``artists``
(``name``), ``isrc``, ``duration``, ``bpm``, ``key_alphanumeric``, ``keys`` (je Quelle), ``genre``/``subgenre`` (Listen)
und ``releases`` (Album, Label, ``release_date``). Release-Felder werden tolerant gelesen.
"""
import base64
import datetime
import hashlib
import json
import os
import time
import urllib.parse

import onlinematch as om
import servicekit as sk
from onlinematch import HttpError

SOURCE = {"id": "sonovault", "name": "SonoVault", "order": 22, "role": "metadata"}
API = "https://api.sonovault.now"
HOST = "api.sonovault.now"
INTERVALS = {HOST: 3.05}                     # Free: 20 Anfragen pro Minute
PAID_INTERVAL = 1.05                         # Starter: 60 pro Minute (#381)
KEYS = ("sonovault",)
FREE_LIMIT = 1000                            # Anfragen je Monat im Free-Tarif
WARN_AT = 0.9                                # ab 90 % verbraucht warnen
CACHE_DAYS = 30                              # Nutzungsbedingungen §7: spätestens alle 30 Tage erneuern
# Felder, die laut Nutzungsbedingungen (§7) in die Datei dürfen
ALLOWED = ("TIT2", "TPE1", "TALB", "TPUB", "TCON", "TDRC", "TSRC", "TLEN")
PAID = {"tracks-browse", "releases-new", "tracks-identify", "streams", "suggestions", "suggestions-list"}
STARTER_LIMIT = 50_000                       # Anfragen je Monat im kleinsten bezahlten Tarif
# #383: eigene Felder mit Herkunft „SonoVault“ – nur die laut §7 erlaubten Werte plus das Abrufdatum (Entscheid User 27.10.)
OWN = (("TITLE", "Titel"), ("ARTIST", "Künstler"), ("RELEASE", "Release"), ("LABEL", "Label"), ("GENRE", "Genre"),
       ("RELEASE_DATE", "Veröffentlichung"), ("DURATION", "Dauer"), ("ISRC", "ISRC"), ("DATE", "Abgerufen"))
PAID_PREFIX = ("stream", "webhook")      # #379: Radio-Überwachung und Webhooks – kostenpflichtig, nie im API-Tester


def paid(eid) -> bool:
    return eid in PAID or str(eid or "").startswith(PAID_PREFIX)
PLATFORMS = {"spotify": "Spotify", "applemusic": "Apple Music", "apple_music": "Apple Music", "tidal": "Tidal",
             "beatport": "Beatport", "discogs": "Discogs", "musicbrainz": "MusicBrainz", "youtube": "YouTube"}
PRIVACY = ("Datenschutz: SonoVault sieht, welche Titel du abfragst (Künstler, Titel, ISRC), und speichert die Anfragen "
           "ohne festes Ablaufdatum (Rekordcloud B.V., Server in der EU).")

ACTIONS = [
    {"id": "keys", "label": "Schlüssel …", "where": "page", "run_label": "Speichern", "needs_selection": False,
     "description": "Eigener SonoVault-Schlüssel. Leer lassen = unverändert. Wird verschlüsselt gespeichert und nie angezeigt.",
     "options": [
         {"type": "info", "title": "SonoVault",
          "label": "Free-Tarif: 1000 Anfragen im Monat, ohne Kreditkarte. 1. Auf sonovault.now ein Konto anlegen und die "
                   "E-Mail-Adresse bestätigen. 2. Im Konto einen Schlüssel erstellen (beginnt mit „svk_live_“; "
                   "„svk_test_“ liefert nur Musterdaten). 3. Den Schlüssel unten einfügen.",
          "links": [["SonoVault", "https://sonovault.now"], ["Tarife", "https://sonovault.now/pricing"],
                    ["Nutzungsbedingungen", "https://sonovault.now/terms"], ["Datenschutz", "https://sonovault.now/privacy"]]},
         {"type": "info", "label": PRIVACY},
         {"key": "sonovault", "type": "password", "label": "SonoVault: Schlüssel"},
         {"key": "tier", "type": "select", "label": "Tarif",
          "choices": [["free", "Free (1000 Anfragen im Monat)"], ["paid", "Bezahlt (Starter oder höher)"]], "default": "free"},
         {"key": "limit", "type": "text", "label": "Anfragen pro Monat (Free: 1000, Starter: 50000)", "default": ""},
         {"key": "clear", "type": "check", "label": "Gespeicherten Schlüssel löschen", "default": False}]},
    {"id": "test", "label": "Verbindung testen", "where": "page", "run_label": "Testen", "needs_selection": False,
     "description": "Prüft Schlüssel und Erreichbarkeit (1 Anfrage).", "options": []},
    {"id": "links", "label": "Plattform-IDs anzeigen (SonoVault) …", "where": "tagger", "run_label": "Anzeigen",
     "description": "Zeigt die IDs der markierten Titel bei Spotify, Beatport, Apple Music, Tidal, Discogs, MusicBrainz und "
                    "YouTube. Nur Anzeige – die Nutzungsbedingungen erlauben nicht, sie in die Dateien zu schreiben. "
                    "Je Titel eine Anfrage (Titel ohne ISRC: zwei).",
     "options": []},
    {"id": "cache", "label": "Zwischenspeicher leeren", "where": "page", "run_label": "Leeren", "needs_selection": False,
     "description": "Löscht die gespeicherten SonoVault-Antworten (laufen sonst nach 30 Tagen von selbst ab).",
     "options": [{"key": "confirm", "type": "check", "label": "Ja, Zwischenspeicher leeren", "default": False}]},
]


# =========================================================================== Schlüssel
def token(ctx) -> str:
    return sk.load_keys(ctx, KEYS).get("sonovault", "")


def ready(ctx):
    return (True, "") if token(ctx) else (False, "kein Schlüssel gespeichert (Plugin SonoVault › „Schlüssel …“)")


def auth(ctx):
    t = token(ctx)
    return {"headers": {"x-api-key": t}} if t else {}


# =========================================================================== Anfragen zählen (SV1)
def _month() -> str:
    return datetime.date.today().strftime("%Y-%m")


def _quota_file(ctx) -> str:
    return os.path.join(ctx.data_dir, "quota.json")


def quota(ctx) -> dict:
    """{"month", "used", "limit", "hdr"} des laufenden Monats (neuer Monat → Zähler 0)."""
    try:
        with open(_quota_file(ctx), encoding="utf-8") as fh:
            q = json.load(fh)
    except (OSError, ValueError):
        q = {}
    lim = q.get("limit") if isinstance(q.get("limit"), int) and q.get("limit") > 0 else FREE_LIMIT
    if q.get("month") != _month():
        q = {"month": _month(), "used": 0, "hdr": {}, "tier": q.get("tier", "free")}
    q["limit"] = lim
    q["used"] = int(q.get("used") or 0)
    return q


def _quota_save(ctx, q: dict):
    tmp = _quota_file(ctx) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(q, fh)
    os.replace(tmp, _quota_file(ctx))


def set_limit(ctx, value) -> int:
    s = str(value or "").strip().replace("'", "").replace("’", "")
    if not s:
        return quota(ctx)["limit"]
    if not s.isdigit() or not 1 <= int(s) <= 100_000_000:
        raise ValueError("Anfragen pro Monat: ganze Zahl erwartet (Free: 1000).")
    q = quota(ctx)
    q["limit"] = int(s)
    _quota_save(ctx, q)
    return q["limit"]


def _reserve(ctx, n: int = 1):
    q = quota(ctx)
    if q["used"] + n > q["limit"]:
        raise HttpError(429, f"SonoVault: Monatskontingent aufgebraucht ({q['used']} von {q['limit']} Anfragen) – "
                             "ab dem 1. des nächsten Monats wieder möglich.")
    if q["used"] + n >= WARN_AT * q["limit"] and not getattr(ctx, "_sv_warned", False):
        ctx.log(f"SonoVault: Achtung – diesen Monat schon {q['used'] + n} von {q['limit']} Anfragen verbraucht.")
        ctx._sv_warned = True


def _count(ctx, headers: dict, n: int = 1):
    q = quota(ctx)
    q["used"] += n
    low = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    hdr = {k: low[k] for k in low if "ratelimit" in k or "credit" in k}
    if hdr:
        q["hdr"] = hdr
    _quota_save(ctx, q)


def quota_text(ctx) -> str:
    q = quota(ctx)
    rest = max(0, q["limit"] - q["used"])
    s = f"diesen Monat {q['used']} von {q['limit']} Anfragen (Rest {rest})"
    if q["used"] >= q["limit"]:
        s += " – aufgebraucht"
    elif q["used"] >= WARN_AT * q["limit"]:
        s += " – fast aufgebraucht"
    return s


def is_paid(ctx) -> bool:
    """#381/#259: bezahlter Tarif eingetragen (Plugin SonoVault › „Schlüssel …“ › Tarif)?"""
    try:
        with open(_quota_file(ctx), encoding="utf-8") as fh:
            return json.load(fh).get("tier") == "paid"
    except (OSError, ValueError, AttributeError):
        return False


def set_tier(ctx, tier: str):
    q = quota(ctx)
    q["tier"] = "paid" if tier == "paid" else "free"
    if q["tier"] == "paid" and q["limit"] == FREE_LIMIT:
        q["limit"] = STARTER_LIMIT                       # Starter; unter „Anfragen pro Monat“ anpassbar
    elif q["tier"] == "free" and q["limit"] == STARTER_LIMIT:
        q["limit"] = FREE_LIMIT
    _quota_save(ctx, q)


def _need_paid(ctx, what: str):
    if not is_paid(ctx):
        raise ValueError(f"SonoVault: {what} gibt es nur mit einem bezahlten Tarif – unter Plugins › SonoVault › "
                         "„Schlüssel …“ den Tarif „Bezahlt“ wählen.")


# =========================================================================== Zwischenspeicher (≤ 30 Tage)
def _cache_dir(ctx) -> str:
    return os.path.join(ctx.data_dir, "cache")


def _cache_path(ctx, url: str) -> str:
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return os.path.join(_cache_dir(ctx), h[:2], h + ".json")


def _cache_get(ctx, url: str, max_age: float | None = None):
    """Gespeicherte Antwort oder None. max_age (Sekunden) kürzer als 30 Tage: z. B. Neuerscheinungen nur 20 Stunden."""
    p = _cache_path(ctx, url)
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        age = time.time() - float(d["t"])
        if age <= CACHE_DAYS * 86400:
            return base64.b64decode(d["body"]) if max_age is None or age <= max_age else None
    except (OSError, ValueError, KeyError, TypeError):
        return None
    try:
        os.remove(p)                                     # abgelaufen
    except OSError:
        pass
    return None


def _cache_put(ctx, url: str, body: bytes):
    p = _cache_path(ctx, url)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w", encoding="utf-8") as fh:
        json.dump({"t": time.time(), "body": base64.b64encode(body).decode("ascii")}, fh)
    os.replace(p + ".tmp", p)


def cache_prune(ctx, everything: bool = False) -> int:
    """Abgelaufene (bzw. alle) Antworten entfernen. → Anzahl."""
    n, limit = 0, time.time() - CACHE_DAYS * 86400
    for root, _dirs, names in os.walk(_cache_dir(ctx)):
        for name in names:
            p = os.path.join(root, name)
            try:
                if everything or os.path.getmtime(p) < limit:
                    os.remove(p)
                    n += 1
            except OSError:
                pass
    return n


# =========================================================================== HTTP
def _throttle(ctx):
    """Abstand zwischen Anfragen nach Tarif (Free 20/min, bezahlt 60/min); Tests setzen 0."""
    if om.INTERVALS.get(HOST) != 0:
        om.INTERVALS[HOST] = PAID_INTERVAL if is_paid(ctx) else INTERVALS[HOST]


def request(ctx, url: str, cache: bool = True, max_age: float | None = None):
    """GET mit Schlüssel, Drosselung und Zähler. 429 wird nie wiederholt. → (Status, Kopfzeilen, Inhalt)."""
    if cache:
        hit = _cache_get(ctx, url, max_age)
        if hit is not None:
            return 200, {}, hit
    key = token(ctx)
    if not key:
        raise HttpError(401, "SonoVault: kein Schlüssel gespeichert (Plugin SonoVault › „Schlüssel …“).")
    _reserve(ctx)
    _throttle(ctx)
    cancel = getattr(ctx, "check_cancel", None)
    if callable(cancel):
        cancel()
    om.SHARED.wait(HOST)
    st, hd, body = om.http_get(url, {"User-Agent": sk.USER_AGENT, "Accept": "application/json", "x-api-key": key})
    _count(ctx, hd)
    if st == 200 and cache and body:
        _cache_put(ctx, url, body)
    return st, hd, body


def _error(st: int, body: bytes) -> str:
    try:
        d = json.loads(body.decode("utf-8"))
        msg = str(d.get("error") or d.get("message") or "") if isinstance(d, dict) else ""
    except (UnicodeDecodeError, ValueError):
        msg = ""
    base = {401: "Schlüssel ungültig oder fehlt", 403: "nicht erlaubt (Funktion nur in bezahlten Tarifen?)",
            429: "zu viele Anfragen bzw. Kontingent aufgebraucht – nicht wiederholt"}.get(st, f"HTTP {st}")
    return f"SonoVault: {base}" + (f" ({msg[:120]})" if msg and st != 401 else "")


def get_json(ctx, path: str, params: dict | None = None, cache: bool = True, max_age: float | None = None):
    q = {k: v for k, v in (params or {}).items() if v not in (None, "")}
    url = API + path + (("?" + urllib.parse.urlencode(q)) if q else "")
    st, _hd, body = request(ctx, url, cache, max_age)
    if st == 404:
        return None
    if st >= 400 or st == 0:
        raise HttpError(st, _error(st, body))
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as ex:
        raise HttpError(-1, "SonoVault: unerwartete Antwort") from ex


# =========================================================================== Treffer
def _names(t) -> list:
    out = []
    for a in t.get("artists") or []:
        if isinstance(a, dict):
            if a.get("remixer") and not a.get("primary"):
                continue
            n = a.get("name") or ""
        else:
            n = str(a)
        if n and n not in out:
            out.append(n)
    return out


def _text(v) -> str:
    if isinstance(v, dict):
        return str(v.get("name") or v.get("title") or "")
    if isinstance(v, list):
        return _text(v[0]) if v else ""
    return str(v or "")


def _isrc(t) -> str:
    v = t.get("isrc") or t.get("isrcs") or ""
    return (_text(v) if isinstance(v, list) else str(v)).strip().upper()


def _genre(t) -> str:
    vals = []
    for k in ("genre", "subgenre"):
        v = t.get(k)
        for x in (v if isinstance(v, list) else [v] if v else []):
            x = _text(x).strip()
            if x and x not in vals:
                vals.append(x)
    return ", ".join(vals[:2])


def _length(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v / 1000 if v > 20000 else v                     # Millisekunden → Sekunden


def candidate(t: dict) -> dict:
    """Ein SonoVault-Titel → Kandidat für „Online-Metadaten“ – nur mit den Feldern, die in die Datei dürfen;
    BPM und Tonart nur zum Vergleich (``compare``)."""
    title, mix = om.split_title(t.get("title", ""))
    rel = (t.get("releases") or [{}])[0] or {}
    if not isinstance(rel, dict):
        rel = {}
    keys_ = t.get("keys") or []
    c = {"source": "sonovault", "source_name": "SonoVault", "id": str(t.get("id", "")), "title": title, "mix": mix,
            "artists": _names(t), "length": _length(t.get("duration")), "isrc": _isrc(t),
            "album": _text(rel.get("title") or rel.get("album") or rel.get("name")),
            "label": _text(rel.get("label") or rel.get("labels")),
            "date": str(rel.get("release_date") or rel.get("date") or "")[:10], "genre": _genre(t),
            "ids": {}, "url": "", "allowed_fields": list(ALLOWED),
            "compare": {"source": "SonoVault", "bpm": t.get("bpm"), "key": t.get("key_alphanumeric") or "",
                        "sources": len(keys_) if isinstance(keys_, list) else 0}}
    c["own_fields"] = own_fields(c)                     # #383: TXXX:SONOVAULT_* (nur auf Wunsch, Option in Online-Metadaten)
    return c


def fmt_duration(sec) -> str:
    try:
        sec = int(round(float(sec)))
    except (TypeError, ValueError):
        return ""
    return f"{sec // 3600}:{sec // 60 % 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


def own_fields(c: dict) -> list:
    """#383: Kopie der erlaubten Werte als TXXX:SONOVAULT_<FELD> – [(Schlüssel, Wert, Beschriftung, Stempel)]. Nie IDs, BPM,
    Tonart, ISWC oder Katalognummer (Terms §7; Erweiterung erst nach Zusage von Rekordcloud, #382)."""
    title = (c.get("title") or "") + (f" ({c['mix']})" if c.get("mix") else "")
    vals = {"TITLE": title, "ARTIST": ", ".join(a for a in c.get("artists") or [] if a), "RELEASE": c.get("album") or "",
            "LABEL": c.get("label") or "", "GENRE": c.get("genre") or "", "RELEASE_DATE": (c.get("date") or "")[:10],
            "DURATION": fmt_duration(c.get("length")) if c.get("length") else "", "ISRC": c.get("isrc") or ""}
    out = [(f"TXXX:SONOVAULT_{k}", str(vals[k]).strip(), f"SONOVAULT_{k}", False)
           for k, _l in OWN if k in vals and str(vals[k]).strip()]
    if out:                                              # Abrufdatum (4. Wert True = nur Stempel, kein SonoVault-Wert)
        out.append(("TXXX:SONOVAULT_DATE", datetime.date.today().isoformat(), "SONOVAULT_DATE", True))
    return out


def propose_own(ctx, f, c: dict, note: str, group: str, checked: bool):
    """Eigene Felder als Vorschläge; gleiche Werte werden übersprungen."""
    fields = own_fields(c)
    for key, val, label, stamp in fields:
        if stamp:
            if all(f.text(k).strip() == v for k, v, _l, st in fields if not st):
                continue                                 # nichts Neues → Abrufdatum nicht ändern
        elif f.text(key).strip() == val:
            continue
        ctx.propose(f, key, val, f"{label} (SonoVault)", note=note, group=group, checked=checked,
                    hint="eigenes Feld mit Herkunft „SonoVault“")


def _tracks(d) -> list:
    if not d:
        return []
    if isinstance(d, dict) and d.get("id") is not None and d.get("title") is not None:
        return [d]
    if isinstance(d, dict):
        for k in ("track", "result"):
            if isinstance(d.get(k), dict):
                return [d[k]]
        for k in ("results", "tracks", "data"):
            if isinstance(d.get(k), list):
                return [x for x in d[k] if isinstance(x, dict)]
    return []


def candidates(ctx, cl=None, info=None, opts=None) -> list:
    """Zuerst über die ISRC, sonst Künstler + Titel (beides nötig)."""
    info = info or {}
    found = []
    if info.get("isrc"):
        found = _tracks(get_json(ctx, f"/v1/tracks/isrc/{urllib.parse.quote(info['isrc'], safe='')}"))
    if not found and info.get("title") and info.get("artist"):
        title = info["title"] + (f" ({info['mix']})" if info.get("mix") else "")
        found = _tracks(get_json(ctx, "/v1/tracks/search", {"artist": info["artist"], "title": title, "limit": 5}))
    return [candidate(t) for t in found[:5]]


def details(ctx, cl, c) -> dict:
    return c                       # Suche liefert schon alle Felder


def check(ctx, cl=None):
    if not token(ctx):
        return False, "kein Schlüssel"
    d = get_json(ctx, "/v1/genres", cache=False)
    ok = d is not None
    return ok, ("in Ordnung" if ok else "keine Antwort") + f" · {quota_text(ctx)}"


def test_query(ctx, info):
    ok, why = ready(ctx)
    if not ok:
        raise ValueError(f"SonoVault: {why}.")
    cands = candidates(ctx, None, info)
    ctx.log(f"Suche: {len(cands)} Treffer · {quota_text(ctx)}")      # keine SonoVault-Werte ins Protokoll
    return cands


def api_request(ctx, ep, params):
    """API-Tester und „Zugriff prüfen“: über den Zähler; kostenpflichtige Endpunkte werden nicht aufgerufen."""
    import services
    url = services.build_url(ctx.plugin.service, ep, params or {})
    if paid(ep.get("id")) or ep.get("method", "GET") != "GET":
        return 403, {}, json.dumps({"error": "nicht abgefragt – kostenpflichtig bzw. nur in bezahlten Tarifen"}).encode(), url
    if not token(ctx):
        return 401, {}, json.dumps({"error": "kein Schlüssel gespeichert"}).encode(), url
    try:
        st, hd, body = request(ctx, url, cache=False)
    except HttpError as ex:
        return ex.status or 429, {}, json.dumps({"error": str(ex)}, ensure_ascii=False).encode(), url
    return st, hd, body, url


# =========================================================================== Bibliothek abgleichen (#256, nur Anzeige)
BATCH = 100
COMPARE = (("TSRC", "ISRC", "isrc"), ("TPUB", "Label", "label"), ("TCON", "Genre", "genre"), ("TALB", "Album", "album"),
           ("TDRC", "Jahr", "date"))


def _post(ctx, path: str, body: dict, lines: int):
    """POST mit Zähler (1 Kredit je Zeile, laut Nutzungsbedingungen bzw. Preisliste). 429 nie wiederholen."""
    key = token(ctx)
    if not key:
        raise HttpError(401, "SonoVault: kein Schlüssel gespeichert (Plugin SonoVault › „Schlüssel …“).")
    _reserve(ctx, lines)
    _throttle(ctx)
    cancel = getattr(ctx, "check_cancel", None)
    if callable(cancel):
        cancel()
    om.SHARED.wait(HOST)
    st, hd, data = om.http_post(API + path, {"User-Agent": sk.USER_AGENT, "Accept": "application/json",
                                             "Content-Type": "application/json", "x-api-key": key},
                                json.dumps(body).encode("utf-8"))
    if st >= 400 or st == 0:
        _count(ctx, hd, 1 if st != 429 else 0)
        raise HttpError(st, _error(st, data))
    try:
        d = json.loads(data.decode("utf-8")) if data else {}
    except (UnicodeDecodeError, ValueError) as ex:
        _count(ctx, hd, lines)
        raise HttpError(-1, "SonoVault: unerwartete Antwort") from ex
    rows = d.get("results") if isinstance(d, dict) else d
    rows = rows if isinstance(rows, list) else []
    used = sum(1 for r in rows if isinstance(r, dict) and r.get("status") != "skipped_no_credits") if rows else lines
    _count(ctx, hd, used)
    return rows


def _item_key(f) -> tuple[str, object, str]:
    """(input_type, Eintrag, Zwischenspeicher-Schlüssel) einer Datei."""
    info = om.file_info(f)
    if info["isrc"]:
        return "isrc", info["isrc"], "resolve:isrc:" + info["isrc"]
    title = info["title"] + (f" ({info['mix']})" if info.get("mix") else "")
    return "track_name", {"artist": info["artist"], "title": title}, "resolve:name:" + om.norm(info["artist"]) + "|" + om.norm(title)


def resolve_plan(ctx, files) -> dict:
    """Wie viele Titel brauchen eine Anfrage (nicht im Zwischenspeicher, mit Künstler+Titel oder ISRC)?"""
    need, cached, skip = [], [], []
    for f in files:
        kind, item, ck = _item_key(f)
        if kind == "track_name" and not (item["artist"] and item["title"]):
            skip.append(f)
        elif _cache_get(ctx, ck) is not None:
            cached.append(f)
        else:
            need.append(f)
    q = quota(ctx)
    return {"need": need, "cached": cached, "skip": skip, "rest": max(0, q["limit"] - q["used"]), "limit": q["limit"]}


def _diff_rows(f, c) -> list:
    rows = []
    for key, label, field in COMPARE:
        new = (c.get(field) or "").strip()
        if not new:
            continue
        cur = f.text(key).strip()
        if key == "TDRC":
            new, cur = new[:4], cur[:4]
        if om.norm(cur) != om.norm(new):
            rows.append([os.path.basename(f.path), label, cur or "–", new])
    cmp = c.get("compare") or {}
    if cmp.get("key"):
        import keys as keys_mod
        code, tk = keys_mod.parse_key(str(cmp["key"])), keys_mod.parse_key(f.text("TKEY")) if f.text("TKEY") else None
        if code and tk and code != tk:
            rows.append([os.path.basename(f.path), "Tonart (Vergleich)", keys_mod.format_key(tk, "camelot"),
                         keys_mod.format_key(code, "camelot")])
    return rows


def resolve_run(ctx, files, limit: int) -> dict:
    """Abgleich: Titel aus dem Zwischenspeicher kosten nichts, die übrigen in Blöcken zu 100 – höchstens limit Kredite."""
    plan = resolve_plan(ctx, files)
    todo = plan["need"][:max(0, min(limit, plan["rest"]))]
    later = len(plan["need"]) - len(todo)
    groups = {"isrc": [], "track_name": []}
    for f in todo:
        kind, item, ck = _item_key(f)
        groups[kind].append((f, item, ck))
    done = 0
    for kind, lst in groups.items():
        for i in range(0, len(lst), BATCH):
            part = lst[i:i + BATCH]
            ctx.progress(done, len(todo), f"Abgleich {done + 1}–{done + len(part)} von {len(todo)}")
            res = _post(ctx, "/v1/tracks/resolve", {"input_type": kind, "items": [it for _f, it, _k in part]}, len(part))
            for (f, _it, ck), r in zip(part, res):
                if not isinstance(r, dict):
                    continue
                if r.get("status") == "matched" and isinstance(r.get("track"), dict):
                    _cache_put(ctx, ck, json.dumps(r["track"]).encode("utf-8"))
                elif r.get("status") == "not_found":
                    _cache_put(ctx, ck, b"{}")
                else:                                                   # skipped_no_credits
                    later += 1
            done += len(part)
    rows, same, missing = [], 0, 0
    for f in plan["need"] + plan["cached"]:
        _kind, _it, ck = _item_key(f)
        raw = _cache_get(ctx, ck)
        if raw is None:
            continue
        t = json.loads(raw.decode("utf-8") or "{}")
        if not t:
            missing += 1
            rows.append([os.path.basename(f.path), "–", "–", "nicht gefunden"])
            continue
        d = _diff_rows(f, candidate(t))
        same += not d
        rows += d
    return {"rows": rows, "sent": len(todo), "cached": len(plan["cached"]), "later": later, "same": same,
            "missing": missing, "skip": len(plan["skip"])}


# =========================================================================== Entdecken (#258)
def _list(d, *keys) -> list:
    if isinstance(d, list):
        return [x for x in d if isinstance(x, dict)]
    if isinstance(d, dict):
        for k in keys + ("results", "data"):
            if isinstance(d.get(k), list):
                return [x for x in d[k] if isinstance(x, dict)]
    return []


def _find(ctx, kind: str, name: str):
    """Künstler bzw. Label mit genau diesem Namen (Suche 30 Tage zwischengespeichert)."""
    d = get_json(ctx, f"/v1/{kind}s/search", {"name": name, "limit": 5})
    return next((x for x in _list(d, kind + "s") if om.norm(x.get("name")) == om.norm(name) and x.get("id") is not None), None)


def _release_entry(r: dict, seed: str, fallback_artist: str = "") -> dict | None:
    rid = r.get("id")
    title = _text(r.get("title") or r.get("name"))
    if rid is None or not title:
        return None
    arts = r.get("artists") or r.get("artist") or fallback_artist
    artist = ", ".join(_text(a) for a in arts if _text(a)) if isinstance(arts, list) else _text(arts)
    return {"key": f"sonovault:rel:{rid}", "src": "sonovault", "id": str(rid), "artist": artist, "title": title, "mix": "",
            "label": _text(r.get("label") or r.get("labels")), "release": title,
            "date": str(r.get("release_date") or r.get("date") or "")[:10], "preview": "", "url": "", "cover": "", "seed": seed}


def discover_releases(ctx, kind: str, name: str, days: int) -> list:
    """Neue Veröffentlichungen eines gefolgten Künstlers bzw. Labels (neueste zuerst, ab „days“ Tagen zurück).
    Kosten: 1 Anfrage für die Suche (30 Tage zwischengespeichert) + 1 für die Liste (20 Stunden zwischengespeichert)."""
    if kind not in ("artist", "label"):
        raise ValueError("artist oder label erwartet")
    x = _find(ctx, kind, name)
    if not x:
        ctx.log(f"SonoVault: {'Künstler' if kind == 'artist' else 'Label'} „{name}“ nicht gefunden")
        return []
    since = (datetime.date.today() - datetime.timedelta(days=max(1, int(days or 60)))).isoformat()
    d = get_json(ctx, f"/v1/{kind}s/{x['id']}/releases", {"from": since, "limit": 50}, max_age=20 * 3600)
    seed = f"{'Künstler' if kind == 'artist' else 'Label'} {name}"
    out = [_release_entry(r, seed, name if kind == "artist" else "") for r in _list(d, "releases")]
    return [e for e in out if e]


def _track_entry(t: dict, seed: str) -> dict | None:
    """#381: Titel aus Browse → Eintrag für Entdecken (ohne Link, nach 30 Tagen entfernt – wie #258)."""
    c = candidate(t)
    if not t.get("id") or not c["title"]:
        return None
    return {"key": f"sonovault:trk:{t['id']}", "src": "sonovault", "id": str(t["id"]), "artist": ", ".join(c["artists"]),
            "title": c["title"], "mix": c["mix"], "label": c["label"], "release": c["album"], "date": c["date"],
            "genre": c["genre"], "preview": "", "url": "", "cover": "", "seed": seed}


def browse(ctx, params: dict, seed: str, days: int) -> list:
    """#381 (bezahlt): GET /v1/tracks/browse – höchstens 20 Titel, neueste zuerst; nur die der letzten „days“ Tage."""
    _need_paid(ctx, "Browse")
    d = get_json(ctx, "/v1/tracks/browse", params, max_age=20 * 3600)
    since = (datetime.date.today() - datetime.timedelta(days=max(1, int(days or 60)))).isoformat()
    out = [_track_entry(t, seed) for t in _list(d, "tracks")]
    return [e for e in out if e and (not e["date"] or e["date"] >= since)]


def discover(ctx, kind: str, name: str, days: int) -> list:
    """Entdecken: „artist“/„label“ = Veröffentlichungen (Free, #258); „browse_label“/„browse_genre“ = neueste Titel eines
    Labels bzw. Genres (bezahlt, #381; Genre = genauer Name, z. B. ein gefolgtes Beatport-Genre)."""
    if kind in ("artist", "label"):
        return discover_releases(ctx, kind, name, days)
    if kind == "browse_label":
        x = _find(ctx, "label", name)
        if not x:
            ctx.log(f"SonoVault: Label „{name}“ nicht gefunden")
            return []
        return browse(ctx, {"labelId": x["id"]}, f"Label {name} (neueste Titel)", days)
    if kind == "browse_genre":
        return browse(ctx, {"genre": name}, f"Genre {name} (neueste Titel)", days)
    raise ValueError(f"Unbekannte Art: {kind}")


# =========================================================================== Release nachschlagen (#380, Free)
def _release_score(r: dict, title: str, artist: str) -> float:
    rt, ra = om.norm(_text(r.get("title"))), om.norm(_text(r.get("artist")))
    s = 1.0 if rt == om.norm(title) else 0.6 if om.norm(title) in rt or rt in om.norm(title) else 0.0
    if artist and ra:
        s += 0.5 if ra == om.norm(artist) or om.norm(artist) in ra or ra in om.norm(artist) else -0.3
    return s


def find_release(ctx, title: str, artist: str = ""):
    """Release über Titel (+ Künstler) suchen und mit Trackliste holen – 2 Anfragen (30 Tage zwischengespeichert)."""
    d = get_json(ctx, "/v1/releases/search", {"title": title, "artist": artist, "limit": 10})
    rs = sorted(_list(d, "releases"), key=lambda r: -_release_score(r, title, artist))
    if not rs or _release_score(rs[0], title, artist) < 0.6 or rs[0].get("id") is None:
        return None
    return get_json(ctx, f"/v1/releases/{rs[0]['id']}")


def _release_track_cand(rel: dict, t: dict) -> dict:
    """Titel einer Release-Trackliste → Kandidat mit Album, Label und Datum des Release."""
    t = dict(t)
    t["releases"] = [{"title": rel.get("title"), "label": rel.get("label"), "release_date": rel.get("release_date")}]
    return candidate(t)


def match_release(rel: dict, files) -> list:
    """[(Datei, Release-Titel)] – über die ISRC, sonst über Titel (+ Mix)."""
    tracks = _list(rel, "tracks")
    by_isrc = {_isrc(t): t for t in tracks if _isrc(t)}
    out, used = [], set()
    for f in files:
        info = om.file_info(f)
        t = by_isrc.get(info["isrc"]) if info["isrc"] else None
        if t is None:
            want = om.norm(info["title"] + (f" ({info['mix']})" if info.get("mix") else ""))
            plain = om.norm(info["title"])
            t = next((x for x in tracks if id(x) not in used and om.norm(_text(x.get("title"))) == want), None) or \
                next((x for x in tracks if id(x) not in used and om.norm(om.split_title(_text(x.get("title")))[0]) == plain), None)
        if t is not None:
            used.add(id(t))
        out.append((f, t))
    return out


def propose_release(ctx, f, rel: dict, t: dict, opts: dict):
    """Vorschläge nur für erlaubte Felder (§7); Katalognummer, Titel- und CD-Nummer nur in der Notiz."""
    c = _release_track_cand(rel, t)
    name = os.path.basename(f.path)
    bits = [f"Release: {c['album']}"]
    if rel.get("catalog_no"):
        bits.append(f"Katalognummer {rel['catalog_no']} (nur Anzeige)")
    if t.get("track_number"):
        bits.append(f"Titel {t['track_number']}" + (f" / CD {t['disc_number']}" if t.get("disc_number") else "") + " (nur Anzeige)")
    note = "SonoVault · " + " · ".join(bits)
    overwrite = opts.get("mode") == "overwrite"
    full = opts.get("date") == "full"
    vals = [("TALB", c["album"], "Album", True), ("TPUB", c["label"], "Label", True),
            ("TDRC", c["date"][:10] if full else c["date"][:4], "Datum" if full else "Jahr", True),
            ("TSRC", c["isrc"], "ISRC", True), ("TCON", c["genre"], "Genre", True),
            ("TIT2", c["title"] + (f" ({c['mix']})" if c["mix"] else ""), "Titel", bool(opts.get("names"))),
            ("TPE1", ", ".join(c["artists"]), "Künstler", bool(opts.get("names")))]
    for key, val, label, wanted in vals:
        val = (val or "").strip()
        if not val or key not in ALLOWED:
            continue
        cur = f.text(key).strip()
        if cur == val:
            continue
        ctx.propose(f, key, val, f"{label} (SonoVault)", note=note, group=name,
                    checked=wanted and (overwrite or not cur),
                    hint="" if wanted and (overwrite or not cur) else "schon gefüllt" if cur else "in den Optionen abgewählt")
    if opts.get("own"):
        propose_own(ctx, f, c, note, name, True)


def run_release(ctx, files, opts) -> dict:
    groups = {}
    for f in files:
        title = str(opts.get("title") or "").strip() or f.text("TALB").strip()
        artist = str(opts.get("artist") or "").strip() or f.text("TPE2").strip() or f.text("TPE1").replace("\x00", ", ").strip()
        groups.setdefault((title, artist), []).append(f)
    found = matched = 0
    rows = []
    for i, ((title, artist), fs) in enumerate(groups.items()):
        ctx.progress(i, len(groups), title or "?")
        if not title:
            rows += [[os.path.basename(f.path), "–", "kein Album (TALB) – Release-Titel in den Optionen angeben"] for f in fs]
            continue
        try:
            rel = find_release(ctx, title, artist)
        except HttpError as ex:
            if ex.status in (0, 401, 429):
                raise RuntimeError(f"{ex} · {quota_text(ctx)}") from ex
            ctx.log(f"{title}: {ex}")
            rel = None
        if not rel:
            rows += [[os.path.basename(f.path), "–", "Release nicht gefunden"] for f in fs]
            continue
        found += 1
        ctx.log("Release-Felder: " + ", ".join(sorted(rel)) + " · Trackliste: " + str(len(_list(rel, "tracks"))) + " Titel")
        for f, t in match_release(rel, fs):
            if t is None:
                rows.append([os.path.basename(f.path), _text(rel.get("title")), "nicht in der Trackliste"])
                continue
            matched += 1
            pos = f"{t.get('track_number') or '?'}/{len(_list(rel, 'tracks'))}"
            rows.append([os.path.basename(f.path), _text(rel.get("title")), f"Titel {pos}"])
            propose_release(ctx, f, rel, t, opts)
    ctx.progress(len(groups), len(groups), "fertig")
    return {"message": f"{found} von {len(groups)} Release(s) gefunden, {matched} von {len(files)} Titel(n) zugeordnet "
                       f"(Quelle: SonoVault). {quota_text(ctx)}.",
            "table": {"cols": ["Datei", "Release", "Ergebnis"], "rows": rows[:2000]}}


# =========================================================================== Genre-Korrektur melden (#259, bezahlt)
def genres(ctx) -> list:
    """Kanonische Genres und Subgenres [{id, name, type, parent}] (30 Tage zwischengespeichert)."""
    d = get_json(ctx, "/v1/genres")
    return _list(d, "genres")


def _post_json(ctx, path: str, body: dict) -> dict:
    """POST mit Zähler (1 Anfrage) – für Genre-Vorschläge. 429 nie wiederholen."""
    key = token(ctx)
    if not key:
        raise HttpError(401, "SonoVault: kein Schlüssel gespeichert (Plugin SonoVault › „Schlüssel …“).")
    _reserve(ctx)
    _throttle(ctx)
    om.SHARED.wait(HOST)
    st, hd, data = om.http_post(API + path, {"User-Agent": sk.USER_AGENT, "Accept": "application/json",
                                             "Content-Type": "application/json", "x-api-key": key},
                                json.dumps(body).encode("utf-8"))
    _count(ctx, hd, 1 if st != 429 else 0)
    if st >= 400 or st == 0:
        raise HttpError(st, _error(st, data))
    try:
        return json.loads(data.decode("utf-8")) if data else {}
    except (UnicodeDecodeError, ValueError) as ex:
        raise HttpError(-1, "SonoVault: unerwartete Antwort") from ex


def suggest_plan(ctx, files) -> list:
    """Je Titel: SonoVault-Titel finden und das Genre der Datei (erster Wert von TCON) mit der Genre-Liste abgleichen.
    → [{file, id, sv, mine, genre_id, why}] – genre_id nur, wenn eine Meldung sinnvoll ist."""
    by_name = {}
    for g in genres(ctx):
        if g.get("id") is not None and g.get("name"):
            by_name.setdefault(om.norm(g["name"]), g)
    out = []
    for i, f in enumerate(files):
        ctx.progress(i, len(files), os.path.basename(f.path))
        info = om.file_info(f)
        mine = f.text("TCON").replace("\x00", ";").split(";")[0].split(",")[0].strip()
        row = {"file": f, "id": None, "sv": "", "mine": mine, "genre_id": None, "why": ""}
        out.append(row)
        if not mine:
            row["why"] = "Datei ohne Genre"
            continue
        c, sc = om.best(info, candidates(ctx, None, info))
        if not c or sc < om.SURE or not c.get("id"):
            row["why"] = "bei SonoVault nicht sicher gefunden"
            continue
        row["id"], row["sv"] = c["id"], c.get("genre") or ""
        if om.norm(mine) in {om.norm(x) for x in row["sv"].split(",")}:
            row["why"] = "gleich"
            continue
        g = by_name.get(om.norm(mine))
        if not g:
            row["why"] = "Genre nicht in der SonoVault-Liste"
            continue
        row["genre_id"], row["genre_name"] = g["id"], g["name"]
    return out


def suggest_run(ctx, plan: list, note: str) -> list:
    rows = []
    for i, r in enumerate([x for x in plan if x["genre_id"]]):
        ctx.progress(i, len(plan), os.path.basename(r["file"].path))
        body = {"genreId": int(r["genre_id"])}
        if note:
            body["note"] = note[:100]
        d = _post_json(ctx, f"/v1/tracks/{urllib.parse.quote(str(r['id']), safe='')}/suggestions", body)
        rows.append([os.path.basename(r["file"].path), r["sv"] or "–", r["genre_name"], str(d.get("status") or "gesendet")])
    return rows


def suggestions_list(ctx) -> list:
    """Eigene Vorschläge mit Status (neueste zuerst, höchstens 100)."""
    d = get_json(ctx, "/v1/suggestions", {"limit": 100}, cache=False)
    rows = []
    for x in _list(d, "suggestions"):
        pv, cv = x.get("proposed_value") or {}, x.get("current_value") or {}
        rows.append([str(x.get("created_at") or "")[:10], str(x.get("track_id") or ""),
                     ", ".join((cv.get("genre") or []) + (cv.get("subgenre") or [])) or "–",
                     str(pv.get("genre_name") or pv.get("genre_id") or ""), str(x.get("status") or ""),
                     str(x.get("review_note") or "")])
    return rows


# =========================================================================== Audio-Erkennung (#257, SV2 – optional, kostenpflichtig)
ID_BASE, ID_PER_MB = 10, 1                    # Kosten laut Preisliste: 10 Kredite + 1 je angefangenes MB
ID_SECONDS = ("30", "45", "60")


def find_ffmpeg() -> str:
    import shutil
    cands = []
    try:
        import plugins
        cands.append(os.path.join(plugins.shared_root(), "stems", "ffmpeg", "ffmpeg.exe" if os.name == "nt" else "ffmpeg"))
    except Exception:  # noqa: BLE001
        pass
    for c in cands:
        if os.path.isfile(c):
            return c
    p = shutil.which("ffmpeg")
    if p:
        return p
    raise RuntimeError("FFmpeg nicht gefunden – das Stems-Plugin installieren (bringt FFmpeg mit) oder FFmpeg in den "
                       "Suchpfad legen.")


def excerpt(ctx, path: str, seconds: int, duration: float = 0.0) -> bytes:
    """Kurzer Ausschnitt aus der Mitte des Titels: mono, 16 kHz, MP3 48 kbit/s – so wenig Audio wie möglich."""
    import subprocess
    start = max(0.0, (float(duration or 0) - seconds) / 2)
    cmd = [find_ffmpeg(), "-v", "error", "-ss", f"{start:.1f}", "-t", str(int(seconds)), "-i", path, "-vn", "-ac", "1",
           "-ar", "16000", "-b:a", "48k", "-map_metadata", "-1", "-id3v2_version", "0", "-f", "mp3", "pipe:1"]
    flags = 0x08000000 if os.name == "nt" else 0          # CREATE_NO_WINDOW
    r = subprocess.run(cmd, capture_output=True, timeout=120, creationflags=flags)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError(f"Ausschnitt nicht möglich: {r.stderr.decode('utf-8', 'replace')[-200:].strip()}")
    return r.stdout


def identify_cost(nbytes: int) -> int:
    return ID_BASE + max(1, -(-int(nbytes) // 1_000_000)) * ID_PER_MB


def estimate_cost(seconds: int) -> int:
    """Kosten je Titel vor dem Ausschnitt (48 kbit/s ≈ 6 KB/s → bis 60 s unter 1 MB)."""
    return identify_cost(int(seconds) * 6000)


def _usable(f) -> bool:
    """Hat der Titel brauchbare Tags (Titel und Künstler, nicht „Track 01“)?"""
    import re
    t, a = f.text("TIT2").strip(), f.text("TPE1").strip()
    return bool(t and a and not re.match(r"^(track|titel|audio|unknown|unbekannt)\s*\d*$", t, re.I))


def identify(ctx, data: bytes, cost: int) -> list:
    """POST /v1/tracks/identify mit dem Ausschnitt → [(Kandidat, Sicherheit)]. 429 nie wiederholen."""
    key = token(ctx)
    if not key:
        raise HttpError(401, "SonoVault: kein Schlüssel gespeichert (Plugin SonoVault › „Schlüssel …“).")
    _reserve(ctx, cost)
    _throttle(ctx)
    om.SHARED.wait(HOST)
    st, hd, body = om.http_post(API + "/v1/tracks/identify?top_n=3",
                                {"User-Agent": sk.USER_AGENT, "Accept": "application/json",
                                 "Content-Type": "application/octet-stream", "x-api-key": key}, data)
    if st >= 400 or st == 0:
        _count(ctx, hd, 0)                       # abgelehnt: nichts verrechnet
        raise HttpError(st, _error(st, body) + (" – Audio-Erkennung braucht gekaufte Kredite bzw. einen bezahlten Tarif"
                                                 if st in (402, 403) else ""))
    _count(ctx, hd, cost)
    try:
        d = json.loads(body.decode("utf-8")) if body else {}
    except (UnicodeDecodeError, ValueError) as ex:
        raise HttpError(-1, "SonoVault: unerwartete Antwort") from ex
    out = []
    for m in _list(d, "matches", "candidates", "tracks"):
        t = m.get("track") if isinstance(m.get("track"), dict) else m
        try:
            conf = float(m.get("confidence", m.get("score", 0)) or 0)
        except (TypeError, ValueError):
            conf = 0.0
        conf = conf / 100 if conf > 1 else conf
        if t.get("title") and not t.get("isrc") and t.get("id") is not None:
            try:                                         # Antwort ist schlank (id, title, artists) – Rest über die ID
                full = get_json(ctx, f"/v1/tracks/{urllib.parse.quote(str(t['id']), safe='')}")
                t = full if isinstance(full, dict) and full.get("title") else t
            except HttpError as ex:
                ctx.log(f"SonoVault: Titel {t.get('id')} nicht nachgeladen ({ex})")
        if t.get("title"):
            out.append((candidate(t), conf))
    return out


# =========================================================================== #393 „MixID light“: Lücken eines Mixes
def excerpt_at(ctx, path: str, start: float, seconds: int) -> bytes:
    """Ausschnitt ab Sekunde start (für Mixe) – mono, 16 kHz, MP3 48 kbit/s, ohne Tags."""
    import subprocess
    cmd = [find_ffmpeg(), "-v", "error", "-ss", f"{max(0.0, float(start)):.1f}", "-t", str(int(seconds)), "-i", path, "-vn",
           "-ac", "1", "-ar", "16000", "-b:a", "48k", "-map_metadata", "-1", "-id3v2_version", "0", "-f", "mp3", "pipe:1"]
    flags = 0x08000000 if os.name == "nt" else 0          # CREATE_NO_WINDOW
    r = subprocess.run(cmd, capture_output=True, timeout=120, creationflags=flags)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError(f"Ausschnitt nicht möglich: {r.stderr.decode('utf-8', 'replace')[-200:].strip()}")
    return r.stdout


def identify_clip_info(ctx) -> dict:
    """Rahmen „Erkennungsdienst“ (#393): bereit?, Kosten je Ausschnitt, Längen, Kontingent, Aufbewahrung.
    retain_days: None = Treffer dürfen im Mix-Ergebnis bleiben (bezahlter Tarif, Terms §7 „Retained Data“);
    sonst höchstens so viele Tage (Free: nur Zwischenspeicher ≤ 30 Tage)."""
    ok, why = ready(ctx)
    q = quota(ctx)
    return {"ready": bool(ok), "why": why or "", "name": "SonoVault", "seconds": [int(x) for x in ID_SECONDS], "default": 30,
            "cost": {str(x): estimate_cost(int(x)) for x in ID_SECONDS}, "unit": "Kredite",
            "rest": max(0, q["limit"] - q["used"]), "quota": quota_text(ctx), "paid": is_paid(ctx),
            "retain_days": None if is_paid(ctx) else 30}


def identify_clip(ctx, path: str, start: float, seconds: int) -> list:
    """Ausschnitt [start, start+seconds] aus path erkennen → [{"artist", "title", "conf", "id", "source"}] (beste zuerst).
    Nur Anzeige-Daten (Titel/Künstler); 429/401/402/403 → HttpError an den Aufrufer (Lauf abbrechen)."""
    secs = int(seconds) if str(int(seconds)) in ID_SECONDS else 30
    data = excerpt_at(ctx, path, start, secs)
    out = []
    for c, conf in identify(ctx, data, identify_cost(len(data))):
        title = c.get("title", "") + (f" ({c['mix']})" if c.get("mix") else "")
        out.append({"artist": ", ".join(c.get("artists") or []), "title": title, "conf": round(float(conf or 0), 3),
                    "id": c.get("id", ""), "source": "sonovault", "source_name": "SonoVault"})
    out.sort(key=lambda x: -x["conf"])
    return out


FIELDS = (("TIT2", "Titel", "title"), ("TPE1", "Künstler", "artists"), ("TALB", "Album", "album"), ("TPUB", "Label", "label"),
          ("TCON", "Genre", "genre"), ("TDRC", "Jahr", "date"), ("TSRC", "ISRC", "isrc"))


def propose_identified(ctx, f, c: dict, conf: float):
    """Treffer der Erkennung als Vorschläge – nur erlaubte Felder, nur leere vorausgewählt (ab 80 % Sicherheit)."""
    name = os.path.basename(f.path)
    note = f"SonoVault-Erkennung: {round(conf * 100)} %"
    for key, label, field in FIELDS:
        v = c.get(field)
        if field == "title" and c.get("mix"):
            v = f"{v} ({c['mix']})"
        v = ", ".join(v) if isinstance(v, list) else str(v or "")
        if field == "date":
            v = v[:4]
        v = v.strip()
        if not v:
            continue
        cur = f.text(key).strip()
        ctx.propose(f, key, v, f"{label} (SonoVault)", note=note, group=name, checked=conf >= 0.8 and not cur,
                    hint="" if not cur else "schon gefüllt – nur bei Bedarf anhaken")
    if getattr(ctx, "_sv_own", False):
        propose_own(ctx, f, c, note, name, conf >= 0.8)


def actions(ctx):
    q = quota(ctx)
    rest = max(0, q["limit"] - q["used"])
    return ACTIONS + [
        {"id": "resolve", "label": "Mit SonoVault abgleichen (Bibliothek) …", "where": "tagger", "run_label": "Abgleichen",
         "description": "Vergleicht die markierten Titel in Blöcken zu 100 mit SonoVault und zeigt, wo ISRC, Label, Genre, "
                        "Album, Jahr oder Tonart abweichen. Nur Anzeige – übernehmen pro Titel über „Online-Metadaten“ "
                        "(Massen-Schreiben erlauben die Nutzungsbedingungen nicht). 1 Kredit je Titel; Titel im "
                        "Zwischenspeicher (30 Tage) kosten nichts.",
         "options": [
             {"type": "info", "label": f"Kontingent: {quota_text(ctx)}. Reicht es nicht, gleicht TagStudio nur so viele "
                                      "Titel ab, wie übrig sind – den Rest im nächsten Monat erneut starten (bereits "
                                      "abgeglichene kosten dann nichts)."},
             {"key": "max", "type": "text", "label": "Höchstens so viele Kredite verwenden", "default": str(min(rest, 500))},
             {"key": "confirm", "type": "check", "label": "Kredite verwenden (ohne Häkchen: nur Kosten anzeigen)",
              "default": False}]},
        {"id": "identify", "label": "Audio erkennen (SonoVault, kostenpflichtig) …", "where": "tagger", "run_label": "Erkennen",
         "description": "Erkennt Titel ohne brauchbare Tags aus einem kurzen Ausschnitt (Mitte des Titels, mono, 16 kHz). "
                        "Kostet je Titel 10 Kredite + 1 je angefangenes MB – dafür müssen bei SonoVault Kredite gekauft "
                        "werden (im Free-Tarif lehnt SonoVault ab). Tipp: zuerst AcoustID in „Online-Metadaten“ – gratis, "
                        "ohne Audio hochzuladen.",
         "options": [
             {"type": "info", "label": "Datenschutz: Der Ausschnitt wird zu SonoVault hochgeladen und dort mit den "
                                      "Ergebnissen ohne feste Frist aufbewahrt. Nur eigene Aufnahmen bzw. solche, für die du "
                                      f"die Rechte hast. Kontingent: {quota_text(ctx)}."},
             {"key": "seconds", "type": "select", "label": "Länge des Ausschnitts",
              "choices": [[s, f"{s} Sekunden (~{estimate_cost(int(s))} Kredite je Titel)"] for s in ID_SECONDS], "default": "30"},
             {"key": "only_untagged", "type": "check", "label": "Nur Titel ohne brauchbare Tags (ohne Titel/Künstler)",
              "default": True},
             {"key": "own", "type": "check", "label": "Zusätzlich eigene Felder TXXX:SONOVAULT_* (Herkunft „SonoVault“)",
              "default": False},
             {"key": "confirm", "type": "check", "label": "Kosten und Hochladen bestätigen (ohne Häkchen: nur Kosten anzeigen)",
              "default": False}]},
        {"id": "release", "label": "Release nachschlagen (SonoVault) …", "where": "tagger", "run_label": "Nachschlagen",
         "description": "Sucht das ganze Release (Album, EP) der markierten Titel und schlägt Album, Label, Datum, ISRC und "
                        "Genre je Titel vor – 2 Anfragen je Release statt je Titel. Katalog-, Titel- und CD-Nummer nur "
                        "zur Anzeige (Nutzungsbedingungen).",
         "options": [
             {"key": "title", "type": "text", "label": "Release-Titel (leer = Album der markierten Titel)"},
             {"key": "artist", "type": "text", "label": "Künstler (leer = Albumkünstler bzw. Künstler)"},
             {"key": "mode", "type": "select", "label": "Vorhandene Werte",
              "choices": [["empty", "Nur leere Felder füllen"], ["overwrite", "Überschreiben (Vorschau zeigt alt → neu)"]],
              "default": "empty"},
             {"key": "date", "type": "select", "label": "Erscheinungsdatum",
              "choices": [["year", "Nur Jahr"], ["full", "Volles Datum (JJJJ-MM-TT)"]], "default": "year"},
             {"key": "names", "type": "check", "label": "Titel und Künstler übernehmen", "default": False},
             {"key": "own", "type": "check", "label": "Zusätzlich eigene Felder TXXX:SONOVAULT_* (Herkunft „SonoVault“)",
              "default": False},
             {"type": "info", "label": f"Kontingent: {quota_text(ctx)}."}]},
        {"id": "suggest", "label": "Genre-Korrektur an SonoVault melden …", "where": "tagger", "run_label": "Prüfen",
         "description": "Vergleicht das Genre deiner Titel (erster Wert in TCON) mit SonoVault und meldet auf Wunsch eine "
                        "Korrektur – das SonoVault-Team prüft sie. Nur mit bezahltem Tarif, höchstens 100 je Tag. Ohne "
                        "Häkchen unten wird nichts gesendet (nur Vorschau).",
         "options": [
             {"type": "info", "label": "Gemeldet wird nur, wenn das Genre der Datei genau einem SonoVault-Genre entspricht "
                                      "und sich von SonoVault unterscheidet. Je Titel 1 Anfrage zum Finden, 1 zum Melden. "
                                      + ("" if is_paid(ctx) else "Hinweis: Tarif ist auf „Free“ gestellt – erst unter "
                                         "„Schlüssel …“ den bezahlten Tarif wählen.")},
             {"key": "note", "type": "text", "label": "Notiz für das SonoVault-Team (optional, höchstens 100 Zeichen)"},
             {"key": "confirm", "type": "check", "label": "Korrekturen wirklich melden (ohne Häkchen: nur Vorschau)",
              "default": False}]},
        {"id": "suggestions", "label": "Meine Genre-Vorschläge …", "where": "page", "run_label": "Anzeigen",
         "needs_selection": False, "direct": True,
         "description": "Zeigt deine gemeldeten Genre-Korrekturen mit Status (offen, angenommen, abgelehnt) – 1 Anfrage.",
         "options": []}]


def status(ctx):
    return ("Schlüssel gespeichert" if token(ctx) else "kein Schlüssel – unter „Schlüssel …“ eintragen") + \
        (" · Tarif bezahlt" if is_paid(ctx) else " · Tarif Free") + f" · {quota_text(ctx)}"


# =========================================================================== Plattform-IDs (#255, nur anzeigen)
def platform_links(ctx, f) -> list:
    """[(Plattform, ID)] eines Titels – über die ISRC, sonst den besten Suchtreffer."""
    info = om.file_info(f)
    params = None
    if info["isrc"]:
        params = {"isrc": info["isrc"]}
    else:
        c, s = om.best(info, candidates(ctx, None, info))
        if c and s >= om.MAYBE and c.get("id"):
            params = {"id": c["id"]}
    if not params:
        return []
    d = get_json(ctx, "/v1/tracks/links", params) or {}
    rows = []
    for lk in (d.get("links") if isinstance(d, dict) else d) or []:
        if not isinstance(lk, dict):
            continue
        src = str(lk.get("source") or lk.get("platform") or "").lower()
        eid = str(lk.get("external_id") or lk.get("id") or "")
        if src and eid:
            rows.append((PLATFORMS.get(src, src.title()), eid))
    return rows


def run(action, ctx, files, opts):
    if action == "keys":
        if opts.get("tier") in ("free", "paid"):
            set_tier(ctx, opts["tier"])
        if (opts.get("limit") or "").strip():
            set_limit(ctx, opts["limit"])
        sk.keys_action(ctx, opts, KEYS)
        return {"message": status(ctx)}
    if action == "test":
        try:
            ok, why = check(ctx)
            return {"message": f"SonoVault: {why}"}
        except HttpError as ex:
            return {"message": f"{ex} · {quota_text(ctx)}"}
    if action == "cache":
        if not opts.get("confirm"):
            return {"message": "Nichts gelöscht – zum Leeren das Häkchen setzen."}
        return {"message": f"{cache_prune(ctx, everything=True)} gespeicherte Antwort(en) gelöscht."}
    if action == "resolve":
        ok, why = ready(ctx)
        if not ok:
            raise ValueError(f"SonoVault: {why}.")
        cache_prune(ctx)
        s = str(opts.get("max") or "").strip()
        if not s.isdigit():
            raise ValueError("Höchstens so viele Kredite: ganze Zahl erwartet.")
        plan = resolve_plan(ctx, files)
        cost = min(len(plan["need"]), int(s), plan["rest"])
        head = (f"{len(files)} Titel: {len(plan['need'])} brauchen eine Anfrage, {len(plan['cached'])} aus dem "
                f"Zwischenspeicher" + (f", {len(plan['skip'])} ohne Künstler/Titel übersprungen" if plan["skip"] else "")
                + f". Kosten jetzt: {cost} Kredite · {quota_text(ctx)}")
        if not opts.get("confirm"):
            return {"message": head + ". Nichts abgefragt – zum Starten „Kredite verwenden“ anhaken."}
        try:
            r = resolve_run(ctx, files, int(s))
        except HttpError as ex:
            raise RuntimeError(f"{ex} · {quota_text(ctx)}") from ex
        msg = (f"Abgeglichen: {r['sent']} neu, {r['cached']} aus dem Zwischenspeicher – {r['same']} stimmen überein, "
               f"{r['missing']} nicht gefunden" + (f", {r['later']} noch offen (Kontingent) – später erneut starten"
                                                    if r["later"] else "") + f". Quelle: SonoVault, nur Anzeige. {quota_text(ctx)}.")
        return {"message": msg, "table": {"cols": ["Datei", "Feld", "In der Datei", "SonoVault"], "rows": r["rows"][:2000]}}
    if action == "identify":
        ok, why = ready(ctx)
        if not ok:
            raise ValueError(f"SonoVault: {why}.")
        secs = int(opts.get("seconds") or 30) if str(opts.get("seconds") or "30") in ID_SECONDS else 30
        todo = [f for f in files if not (opts.get("only_untagged", True) and _usable(f))]
        each = estimate_cost(secs)
        head = (f"{len(todo)} von {len(files)} Titel(n) zum Erkennen – geschätzt {len(todo) * each} Kredite "
                f"({each} je Titel) · {quota_text(ctx)}")
        if not todo:
            return {"message": f"{head}. Alle markierten Titel haben schon Titel und Künstler."}
        if not opts.get("confirm"):
            return {"message": head + ". Nichts hochgeladen – zum Starten „Kosten und Hochladen bestätigen“ anhaken."}
        found = 0
        ctx._sv_own = bool(opts.get("own"))
        for i, f in enumerate(todo):
            name = os.path.basename(f.path)
            ctx.progress(i, len(todo), name)
            data = excerpt(ctx, f.path, secs, getattr(f, "duration", 0))
            try:
                hits = identify(ctx, data, identify_cost(len(data)))
            except HttpError as ex:
                if ex.status in (0, 401, 402, 403, 429):
                    raise RuntimeError(f"{ex} · {quota_text(ctx)}") from ex
                ctx.log(f"{name}: {ex}")
                continue
            if hits:
                c, conf = max(hits, key=lambda x: x[1])
                propose_identified(ctx, f, c, conf)
                found += 1
            ctx.log(f"{name}: {'erkannt' if hits else 'nicht erkannt'}")
        ctx.progress(len(todo), len(todo), "fertig")
        return {"message": f"{found} von {len(todo)} Titel(n) erkannt (Quelle: SonoVault). {quota_text(ctx)}."}
    if action == "release":
        ok, why = ready(ctx)
        if not ok:
            raise ValueError(f"SonoVault: {why}.")
        cache_prune(ctx)
        return run_release(ctx, files, opts)
    if action == "suggest":
        ok, why = ready(ctx)
        if not ok:
            raise ValueError(f"SonoVault: {why}.")
        _need_paid(ctx, "Genre-Korrekturen")
        try:
            plan = suggest_plan(ctx, files)
            todo = [r for r in plan if r["genre_id"]]
            if not opts.get("confirm"):
                rows = [[os.path.basename(r["file"].path), r["sv"] or "–", r["mine"] or "–",
                         r.get("genre_name", "") if r["genre_id"] else r["why"]] for r in plan]
                return {"message": f"{len(todo)} von {len(files)} Titel(n) könnten gemeldet werden – nichts gesendet. Zum "
                                   f"Melden „Korrekturen wirklich melden“ anhaken. {quota_text(ctx)}.",
                        "table": {"cols": ["Datei", "SonoVault", "Datei", "Vorschlag"], "rows": rows[:2000]}}
            rows = suggest_run(ctx, plan, str(opts.get("note") or "").strip())
        except HttpError as ex:
            raise RuntimeError(f"{ex} · {quota_text(ctx)}") from ex
        for r in rows:
            ctx.log(f"{r[0]}: Genre-Korrektur gemeldet ({r[3]})")
        return {"message": f"{len(rows)} Genre-Korrektur(en) gemeldet – das SonoVault-Team prüft sie (Status: „Meine "
                           f"Genre-Vorschläge …“). {quota_text(ctx)}.",
                "table": {"cols": ["Datei", "SonoVault", "Vorschlag", "Status"], "rows": rows}}
    if action == "suggestions":
        ok, why = ready(ctx)
        if not ok:
            raise ValueError(f"SonoVault: {why}.")
        try:
            rows = suggestions_list(ctx)
        except HttpError as ex:
            raise RuntimeError(f"{ex} · {quota_text(ctx)}") from ex
        return {"message": f"{len(rows)} Genre-Vorschläge. {quota_text(ctx)}." if rows else "Noch keine Genre-Vorschläge gemeldet.",
                "table": {"cols": ["Datum", "SonoVault-Titel", "Bisher", "Vorschlag", "Status", "Antwort"], "rows": rows}}
    if action == "links":
        ok, why = ready(ctx)
        if not ok:
            raise ValueError(f"SonoVault: {why}.")
        cache_prune(ctx)
        rows, none = [], 0
        for i, f in enumerate(files):
            name = os.path.basename(f.path)
            ctx.progress(i, len(files), name)
            try:
                found = platform_links(ctx, f)
            except HttpError as ex:
                if ex.status in (0, 401, 429):
                    raise RuntimeError(str(ex)) from ex
                found = []
            none += not found
            rows += [[name, p, eid] for p, eid in found] or [[name, "–", "nicht gefunden"]]
        ctx.progress(len(files), len(files), "fertig")
        return {"message": f"Plattform-IDs für {len(files) - none} von {len(files)} Titel(n) – Quelle: SonoVault, "
                           f"nur Anzeige (nicht in die Dateien). {quota_text(ctx)}.",
                "table": {"cols": ["Datei", "Plattform", "ID"], "rows": rows[:2000]}}
    raise ValueError(f"Unbekannte Aktion: {action}")
