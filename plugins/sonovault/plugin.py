"""SonoVault (#253–#255, 4.11.0): Musik-Metadaten-API von Rekordcloud mit eigenem Schlüssel.

Entscheide des Users (docs/KONZEPT-SONOVAULT.md Abschnitt 6): Free-Tarif – TagStudio zählt die Anfragen je Monat,
zeigt den Rest und warnt vor dem Überschreiten (SV1); Plattform-IDs nur anzeigen (SV3); Vorrang in „Online-Metadaten“
nach MusicBrainz, vor Deezer und iTunes (SV4).

Nutzungsbedingungen (Abschnitt 3): In Dateien dürfen nur Titel, Künstler, Release-Titel, Label, Genre,
Erscheinungsdatum, Dauer und ISRC – BPM, Tonart, ISWC, Katalognummer und Plattform-IDs nur anzeigen bzw. vergleichen.
Zwischenspeicher höchstens 30 Tage, nichts exportieren, keine SonoVault-Werte ins Protokoll (Protokolle liegen als
Datei im Log-Ordner). Bei HTTP 429 wird nie wiederholt. Nur Standardbibliothek.

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
KEYS = ("sonovault",)
FREE_LIMIT = 1000                            # Anfragen je Monat im Free-Tarif
WARN_AT = 0.9                                # ab 90 % verbraucht warnen
CACHE_DAYS = 30                              # Nutzungsbedingungen §7: spätestens alle 30 Tage erneuern
# Felder, die laut Nutzungsbedingungen (§7) in die Datei dürfen
ALLOWED = ("TIT2", "TPE1", "TALB", "TPUB", "TCON", "TDRC", "TSRC", "TLEN")
PAID = {"tracks-browse", "releases-new", "tracks-identify", "streams"}
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
         {"key": "limit", "type": "text", "label": "Anfragen pro Monat (Free: 1000)", "default": ""},
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
        q = {"month": _month(), "used": 0, "hdr": {}}
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


# =========================================================================== Zwischenspeicher (≤ 30 Tage)
def _cache_dir(ctx) -> str:
    return os.path.join(ctx.data_dir, "cache")


def _cache_path(ctx, url: str) -> str:
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return os.path.join(_cache_dir(ctx), h[:2], h + ".json")


def _cache_get(ctx, url: str):
    p = _cache_path(ctx, url)
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        if time.time() - float(d["t"]) <= CACHE_DAYS * 86400:
            return base64.b64decode(d["body"])
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
def request(ctx, url: str, cache: bool = True):
    """GET mit Schlüssel, Drosselung und Zähler. 429 wird nie wiederholt. → (Status, Kopfzeilen, Inhalt)."""
    if cache:
        hit = _cache_get(ctx, url)
        if hit is not None:
            return 200, {}, hit
    key = token(ctx)
    if not key:
        raise HttpError(401, "SonoVault: kein Schlüssel gespeichert (Plugin SonoVault › „Schlüssel …“).")
    _reserve(ctx)
    for host, sec in INTERVALS.items():
        om.INTERVALS.setdefault(host, sec)
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


def get_json(ctx, path: str, params: dict | None = None, cache: bool = True):
    q = {k: v for k, v in (params or {}).items() if v not in (None, "")}
    url = API + path + (("?" + urllib.parse.urlencode(q)) if q else "")
    st, _hd, body = request(ctx, url, cache)
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
    return {"source": "sonovault", "source_name": "SonoVault", "id": str(t.get("id", "")), "title": title, "mix": mix,
            "artists": _names(t), "length": _length(t.get("duration")), "isrc": _isrc(t),
            "album": _text(rel.get("title") or rel.get("album") or rel.get("name")),
            "label": _text(rel.get("label") or rel.get("labels")),
            "date": str(rel.get("release_date") or rel.get("date") or "")[:10], "genre": _genre(t),
            "ids": {}, "url": "", "allowed_fields": list(ALLOWED),
            "compare": {"source": "SonoVault", "bpm": t.get("bpm"), "key": t.get("key_alphanumeric") or "",
                        "sources": len(keys_) if isinstance(keys_, list) else 0}}


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
    if ep.get("id") in PAID or ep.get("method", "GET") != "GET":
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
    for host, sec in INTERVALS.items():
        om.INTERVALS.setdefault(host, sec)
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
              "default": False}]}]


def status(ctx):
    return ("Schlüssel gespeichert" if token(ctx) else "kein Schlüssel – unter „Schlüssel …“ eintragen") + \
        f" · {quota_text(ctx)}"


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
