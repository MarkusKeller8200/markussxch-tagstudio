"""Spotify (#280, #384) – eigene Playlists und Lieblingssongs als Playlists, Titel-Daten mit ISRC und Link für
„Online-Metadaten“, gefolgte Künstler für „Entdecken“. Seit 1.3 (#384): „Läuft gerade“/„Zuletzt gehört“ → Ideen (SP2),
neue Veröffentlichungen gefolgter Künstler in Entdecken (SP1), Wunschliste als Spotify-Playlist (SP5, nur auf Klick),
gespeicherte Alben (SP3), ganzes Album nachschlagen (SP4), „In deiner Spotify-Bibliothek“ (SP6, speichern nur auf Klick).
Schreibende Aufrufe (SP5, SP6) laufen nie automatisch.

Zugang über eine **eigene Spotify-App** (developer.spotify.com, Entwicklungsmodus; der Besitzer braucht Spotify
Premium) und OAuth mit PKCE – kein Client-Secret nötig. Client-ID und Token liegen verschlüsselt im Datenordner
des Plugins. Stand der Web-API: Februar 2026 (Inhalte nur eigener bzw. gemeinsamer Playlists, Suche höchstens 10
Treffer pro Abfrage, keine Sammelabfragen, Album ohne Label).
Nur Standardbibliothek.
"""
import urllib.parse

import oauthkit
import onlinematch as om
import servicekit as sk
from onlinematch import HttpError
from oauthkit import OAuthError

SOURCE = {"id": "spotify", "name": "Spotify", "order": 35, "role": "metadata"}
API = "https://api.spotify.com/v1"
INTERVALS = {"api.spotify.com": 0.2}
LIKED = "liked"
ALBUM = "album:"                                        # #384 SP3: gespeicherte Alben als Playlist-Quelle
MAX_ALBUMS = 300
SCOPES = ["playlist-read-private", "playlist-read-collaborative", "user-library-read", "user-follow-read",
          "user-top-read", "user-read-recently-played",
          # #384 (Entscheid User: alle auf einmal – eine neue Anmeldung): Läuft gerade, Playlist anlegen, Bibliothek
          "user-read-currently-playing", "playlist-modify-private", "user-library-modify"]
NEW_SCOPES = ("user-read-currently-playing", "playlist-modify-private", "user-library-modify")
CFG = {"name": "Spotify", "authorize": "https://accounts.spotify.com/authorize",
       "token": "https://accounts.spotify.com/api/token", "scopes": SCOPES, "header": "Bearer", "secret": False,
       "redirect": "http://127.0.0.1:8765/callback"}
MAX_ITEMS = 5000

ACTIONS = [
    {"id": "login", "label": "Anmelden …", "where": "page", "run_label": "Anmelden", "needs_selection": False,
     "description": "Zugangsdaten deiner eigenen Spotify-App eintragen (leer = unverändert, verschlüsselt gespeichert) und die Anmeldeseite im Browser öffnen. TagStudio liest – geändert wird dein Konto nur auf deinen Klick (Wunschliste als Playlist, in deiner Bibliothek speichern).",
     "options": [{"type": "info", "title": "Spotify-App anlegen",
          "label": "1. Auf developer.spotify.com mit deinem Spotify-Konto anmelden (Premium nötig). 2. Dashboard › "
                   "„Create app“, bei „Redirect URIs“ genau die Adresse unten eintragen (Standard "
                   "http://127.0.0.1:8765/callback), „Web API“ wählen und speichern. 3. Die Client-ID aus den "
                   "Einstellungen der App kopieren und hier einfügen. Ein Client-Secret ist nicht nötig.",
          "links": [["Spotify: Developer Dashboard", "https://developer.spotify.com/dashboard"],
                    ["Spotify: Redirect URIs", "https://developer.spotify.com/documentation/web-api/concepts/redirect_uri"]]},
         {"key": "client_id", "type": "password", "label": "Client-ID"},
         {"key": "redirect", "type": "text", "label": "Redirect URI (wie in der Spotify-App)",
          "default": CFG["redirect"]},
         {"key": "method", "type": "select", "label": "Methode",
          "choices": [["browser", "Im Browser anmelden (automatisch)"], ["paste", "Adresse einfügen (wenn automatisch nicht geht)"]],
          "default": "browser"},
         {"key": "url", "type": "text", "label": "Adresse aus der Adresszeile nach der Anmeldung",
          "show_if": {"method": "paste"}},
         {"type": "info", "show_if": {"method": "paste"},
          "label": "Zuerst ohne Adresse „Anmelden“ – der Browser öffnet Spotify. Nach der Zustimmung zeigt der Browser "
                   "eine Fehlerseite mit http://127.0.0.1:… in der Adresszeile: diese Adresse kopieren, hier einfügen "
                   "und nochmals „Anmelden“."}]},
    {"id": "logout", "label": "Abmelden …", "where": "page", "run_label": "Abmelden", "needs_selection": False,
     "description": "Gespeicherte Anmeldung löschen.", "options": [{"key": "clear", "type": "check", "label": "Auch die Zugangsdaten der App löschen", "default": False}]},
    {"id": "test", "label": "Verbindung testen", "where": "page", "run_label": "Testen", "needs_selection": False,
     "description": "Prüft Zugang und Anmeldung bei Spotify.", "options": []},
    {"id": "album", "label": "Album nachschlagen (Spotify) …", "where": "tagger", "run_label": "Nachschlagen",
     "short": "Album nachschlagen",
     "description": "Sucht das ganze Album bzw. die EP der markierten Titel bei Spotify (wenige Anfragen statt je Titel) "
                    "und schlägt Album, Albumkünstler, Datum, Titel-/CD-Nummer, Genre und Cover vor. Spotify liefert kein "
                    "Label mehr. Nichts wird ohne Bestätigung geändert.",
     "options": [
         {"key": "title", "type": "text", "label": "Album-Titel (leer = Album der markierten Titel)"},
         {"key": "artist", "type": "text", "label": "Künstler (leer = Albumkünstler bzw. Künstler)"},
         {"key": "mode", "type": "select", "label": "Vorhandene Werte",
          "choices": [["empty", "Nur leere Felder füllen"], ["overwrite", "Überschreiben (Vorschau zeigt alt → neu)"]],
          "default": "empty"},
         {"key": "date", "type": "select", "label": "Erscheinungsdatum",
          "choices": [["year", "Nur Jahr"], ["full", "Volles Datum (JJJJ-MM-TT)"]], "default": "year"},
         {"key": "cover", "type": "select", "label": "Cover",
          "choices": [["missing", "Nur wenn keins vorhanden"], ["replace", "Ersetzen"], ["no", "Nicht übernehmen"]],
          "default": "missing"},
         {"key": "names", "type": "check", "label": "Titel und Künstler übernehmen", "default": False},
         {"key": "ids", "type": "check", "label": "Spotify-ID und -Link speichern (TXXX:SPOTIFY_TRACK_ID, _URL)", "default": True},
         {"key": "own", "type": "check", "default": False,
          "label": "Zusätzlich eigene Felder TXXX:SPOTIFY_* (Herkunft „Spotify“, auf eigene Verantwortung)"}]},
    {"id": "follow", "label": "Gefolgte Künstler in „Entdecken“ übernehmen …", "where": "page", "run_label": "Übernehmen",
     "needs_selection": False,
     "description": "Liest die Künstler, denen du auf Spotify folgst, und ergänzt sie in „Entdecken“ › Gefolgte Künstler.",
     "options": [{"key": "top", "type": "check", "label": "Auch deine meistgehörten Künstler (Top 20)", "default": False}]},
]


def app(ctx) -> oauthkit.App:
    return oauthkit.App(ctx, CFG)


def client(ctx):
    return sk.client(ctx, INTERVALS)


def ready(ctx):
    a = app(ctx)
    if not a.configured():
        return False, "keine Client-ID (Plugin Spotify › „Anmelden …“)"
    if not a.logged_in():
        return False, "nicht angemeldet (Plugin Spotify › „Anmelden …“)"
    return True, ""


def missing_scopes(ctx, need=SCOPES) -> list:
    """Berechtigungen, die der gespeicherten Anmeldung fehlen (ältere Anmeldung vor 1.3) – dann neu anmelden."""
    have = set(str(app(ctx).token.get("scope") or "").split())
    return [x for x in need if x not in have] if have else []


def need_scopes(ctx, *need):
    miss = missing_scopes(ctx, need)
    if miss:
        raise OAuthError("Für diese Funktion fehlt eine Berechtigung (" + ", ".join(miss) + ") – bitte unter Plugins › "
                         "Spotify einmal „Anmelden …“ (neue Anmeldung mit den zusätzlichen Berechtigungen).")


def auth(ctx):
    try:
        return {"headers": app(ctx).headers()}
    except OAuthError:
        return {}


def get(ctx, path, cl=None, **params):
    if path.startswith("https://") and urllib.parse.urlparse(path).hostname != urllib.parse.urlparse(API).hostname:
        raise RuntimeError(f"Unerwartete Adresse ({urllib.parse.urlparse(path).hostname}) – Anmeldung wird nicht mitgeschickt.")
    url = path if path.startswith("https://") else API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    return app(ctx).get(url, cl or client(ctx)) or {}


MAX_PAGES = 500


def pages(ctx, path, cl=None, limit=50, key="items", max_items=MAX_ITEMS, **params):
    """Alle Seiten einer Liste (next-Links bzw. Cursor) → Einträge."""
    cl = cl or client(ctx)
    d = get(ctx, path, cl, limit=limit, **params)
    out, seen, before = [], set(), -1
    while d:
        box = d.get(key) if isinstance(d.get(key), dict) else d          # /me/following: {"artists": {...}}
        out += box.get("items") or []
        nxt = box.get("next")
        if not nxt or len(out) >= max_items or nxt in seen or len(out) == before or len(seen) >= MAX_PAGES:
            break                                       # Ende, gleiche Seite nochmals oder leere Seite: nicht endlos laden
        seen.add(nxt)
        before = len(out)
        ctx.check_cancel()
        d = get(ctx, nxt, cl)
    return out[:max_items]


# =========================================================================== Titel → Eintrag / Kandidat
def _artists(t) -> list:
    return [a.get("name", "") for a in t.get("artists") or [] if a.get("name")]


def ref_of(t) -> dict:
    """Spotify-Titel → Eintrag ohne Datei (Playlists)."""
    title, mix = om.split_title(t.get("name", ""))
    return {"artist": ", ".join(_artists(t)), "title": title, "mix": mix,
            "isrc": ((t.get("external_ids") or {}).get("isrc") or "").upper(), "dur": int((t.get("duration_ms") or 0) / 1000),
            "source": "spotify", "url": (t.get("external_urls") or {}).get("spotify", "")}


def _cand(t) -> dict:
    title, mix = om.split_title(t.get("name", ""))
    alb = t.get("album") or {}
    imgs = alb.get("images") or []
    url = (t.get("external_urls") or {}).get("spotify", "")
    return {"source": "spotify", "source_name": "Spotify", "id": t.get("id", ""), "title": title, "mix": mix,
            "artists": _artists(t), "length": (t.get("duration_ms") or 0) / 1000 or None,
            "isrc": ((t.get("external_ids") or {}).get("isrc") or "").upper(), "album": alb.get("name", ""),
            "album_id": alb.get("id", ""), "album_artist": ", ".join(_artists(alb)), "date": alb.get("release_date", ""),
            "cover": imgs[0].get("url", "") if imgs else "", "track": str(t.get("track_number") or ""),
            "disc": str(t.get("disc_number") or ""), "url": url, "total_tracks": alb.get("total_tracks") or 0,
            "explicit": t.get("explicit"), "artist_id": ((t.get("artists") or [{}])[0] or {}).get("id", ""),
            "ids": {k: v for k, v in (("TXXX:SPOTIFY_TRACK_ID", t.get("id", "")), ("TXXX:SPOTIFY_URL", url)) if v}}


# =========================================================================== #385: eigene Felder TXXX:SPOTIFY_*
# Entscheid User 27.10.2026: Variante B (volle Liste) auf eigene Verantwortung – die Spotify Developer Terms zählen
# Metadaten zu den Spotify-Inhalten (nicht dauerhaft speichern). Hinweis in der Vorschau und in PLUGINS.md.
OWN = ("ALBUM_ID", "ARTIST_ID", "TITLE", "ARTIST", "ALBUM", "RELEASE_DATE", "ISRC", "GENRE", "TRACK", "DURATION",
       "EXPLICIT")
OWN_HINT = ("eigenes Feld mit Herkunft „Spotify“ – auf eigene Verantwortung: die Spotify Developer Terms erlauben "
            "kein dauerhaftes Speichern von Spotify-Metadaten")


def fmt_duration(sec) -> str:
    try:
        sec = int(round(float(sec)))
    except (TypeError, ValueError):
        return ""
    return f"{sec // 3600}:{sec // 60 % 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


def own_fields(c: dict) -> list:
    """Kopie der Spotify-Werte als TXXX:SPOTIFY_<FELD> – [(Schlüssel, Wert, Beschriftung, Stempel)]. TRACK_ID und URL
    kommen wie bisher über „IDs speichern“. Popularität, Label und Audio-Merkmale liefert Spotify eigenen Apps nicht."""
    title = (c.get("title") or "") + (f" ({c['mix']})" if c.get("mix") else "")
    track = str(c.get("track") or "")
    if track and c.get("total_tracks"):
        track = f"{track}/{c['total_tracks']}"
    ex = c.get("explicit")
    vals = {"ALBUM_ID": c.get("album_id") or "", "ARTIST_ID": c.get("artist_id") or "", "TITLE": title,
            "ARTIST": ", ".join(a for a in c.get("artists") or [] if a), "ALBUM": c.get("album") or "",
            "RELEASE_DATE": c.get("date") or "", "ISRC": c.get("isrc") or "", "GENRE": c.get("genre") or "",
            "TRACK": track, "DURATION": fmt_duration(c.get("length")) if c.get("length") else "",
            "EXPLICIT": "" if ex is None else ("1" if ex else "0")}
    out = [(f"TXXX:SPOTIFY_{k}", str(vals[k]).strip(), f"SPOTIFY_{k}", False) for k in OWN if str(vals[k]).strip()]
    if out:                                              # Abrufdatum (Stempel – kein Spotify-Wert)
        import datetime
        out.append(("TXXX:SPOTIFY_DATE", datetime.date.today().isoformat(), "SPOTIFY_DATE", True))
    return out


def candidates(ctx, cl, info, opts=None) -> list:
    if not ready(ctx)[0]:
        return []
    if info.get("isrc"):
        d = get(ctx, "/search", cl, q=f"isrc:{info['isrc']}", type="track", limit=10)
        hits = (d.get("tracks") or {}).get("items") or []
        if hits:
            return [_cand(t) for t in hits]
    if not info.get("title"):
        return []
    q = f'track:"{info["title"]}"' + (f' artist:"{om.first_artist(info)}"' if info.get("artist") else "")
    d = get(ctx, "/search", cl, q=q, type="track", limit=10)
    out = [_cand(t) for t in (d.get("tracks") or {}).get("items") or []]
    if not out:
        q = " ".join(x for x in (om.first_artist(info) if info.get("artist") else "", info["title"], info.get("mix", "")) if x)
        d = get(ctx, "/search", cl, q=q, type="track", limit=10)
        out = [_cand(t) for t in (d.get("tracks") or {}).get("items") or []]
    return out


def details(ctx, cl, c) -> dict:
    """Genre über den Künstler (Album liefert seit 2026 kein Label mehr)."""
    t = get(ctx, f"/tracks/{c['id']}", cl) if c.get("id") else {}
    if t.get("id"):
        c.update({k: v for k, v in _cand(t).items() if v})
        art = (t.get("artists") or [{}])[0].get("id")
        if art:
            a = get(ctx, f"/artists/{art}", cl)
            g = a.get("genres") or []
            if g:
                c["genre"] = g[0].title()
    c["own_fields"] = own_fields(c)                     # #385: nur auf Wunsch (Option „eigene Felder“ in Online-Metadaten)
    c["own_hint"] = OWN_HINT
    return c


def test_query(ctx, info):
    ok, why = ready(ctx)
    if not ok:
        raise ValueError(f"Spotify: {why}.")
    cands = candidates(ctx, client(ctx), info)
    ctx.log(("ISRC " + info["isrc"] + ", sonst " if info.get("isrc") else "") + f"Suche: {len(cands)} Titel")
    return cands


def api_request(ctx, ep, params):
    """API-Tester: GET mit dem eigenen Token (bei Bedarf erneuert); der Token wird geschwärzt."""
    import services
    a = app(ctx)
    url = services.build_url({"base": API}, ep, params)
    st, h, body, _n = om.get_retry(url, {"User-Agent": sk.USER_AGENT, "Accept": "application/json", **a.headers()})
    if st == 401 and a.refresh():
        st, h, body, _n = om.get_retry(url, {"User-Agent": sk.USER_AGENT, "Accept": "application/json", **a.headers()})
    ctx.secrets = a.secrets()
    return st, h, body, url


# =========================================================================== Playlists (Playlists › Importieren)
def _me(ctx, cl):
    return get(ctx, "/me", cl)


def playlists(ctx) -> list:
    """Lieblingssongs und eigene bzw. gemeinsame Playlists. Fremde Playlists liefert Spotify seit 2026 ohne Titel."""
    ok, why = ready(ctx)
    if not ok:
        raise ValueError(f"Spotify: {why}.")
    cl = client(ctx)
    me = (_me(ctx, cl).get("id") or "")
    out = [{"id": LIKED, "name": "Lieblingssongs", "path": [], "depth": 0, "type": "liked"}]
    for p in pages(ctx, "/me/playlists", cl):
        own = (p.get("owner") or {}).get("id") == me or p.get("collaborative")
        if own:
            out.append({"id": p["id"], "name": p.get("name") or p["id"], "path": [], "depth": 0, "type": "playlist"})
    # #384 SP3: gespeicherte Alben (je Album eine Playlist mit allen Titeln)
    for r in pages(ctx, "/me/albums", cl, max_items=MAX_ALBUMS):
        a = r.get("album") or {}
        if a.get("id"):
            out.append({"id": f"{ALBUM}{a['id']}", "name": f"Album: {a.get('name') or a['id']} – {', '.join(_artists(a))}",
                        "path": [], "depth": 0, "type": "album"})
    return out


def album_tracks(ctx, aid: str, cl=None) -> tuple[dict, list]:
    """Album und alle Titel (eingebettete erste Seite, weitere Seiten über /albums/{id}/tracks) → (Album, [Titel])."""
    cl = cl or client(ctx)
    alb = get(ctx, f"/albums/{aid}", cl) or {}
    box = alb.get("tracks") or {}
    rows = list(box.get("items") or [])
    if box.get("next"):
        rows += pages(ctx, box["next"], cl)
    elif not rows:
        rows = pages(ctx, f"/albums/{aid}/tracks", cl)
    for t in rows:                                       # Titel aus dem Album kennen ihr Album nicht – ergänzen
        t.setdefault("album", {k: alb.get(k) for k in ("id", "name", "release_date", "images", "artists", "total_tracks")})
    return alb, rows


def playlist_files(ctx, pid) -> dict:
    """Titel einer Playlist als Einträge ohne Datei → {name, files: [], items, missing: 0}"""
    cl = client(ctx)
    if pid == LIKED:
        name, rows = "Lieblingssongs", pages(ctx, "/me/tracks", cl)
    elif str(pid).startswith(ALBUM):                     # #384 SP3
        alb, rows = album_tracks(ctx, str(pid)[len(ALBUM):], cl)
        name = f"{alb.get('name') or pid} – {', '.join(_artists(alb))}"
        rows = [{"item": t} for t in rows]
    else:
        meta = get(ctx, f"/playlists/{pid}", cl, fields="name")
        name = meta.get("name") or f"Playlist {pid}"
        rows = pages(ctx, f"/playlists/{pid}/items", cl)
    items = []
    for r in rows:
        t = r.get("item") or r.get("track") or {}
        if t and t.get("type", "track") == "track" and t.get("name"):
            items.append({"ref": ref_of(t)})
    return {"name": name, "files": [], "items": items, "missing": 0}


# =========================================================================== #384 SP2: Läuft gerade / Zuletzt gehört → Ideen
def idea_of(t, played_at: str = "") -> dict:
    """Spotify-Titel → Eintrag für eine Wunschliste (Künstler, Titel, Mix, ISRC, Link, Cover, Album, Datum)."""
    r = ref_of(t)
    alb = t.get("album") or {}
    imgs = alb.get("images") or []
    r.update({"id": t.get("id", ""), "uri": t.get("uri") or (f"spotify:track:{t['id']}" if t.get("id") else ""),
              "cover": imgs[-1].get("url", "") if imgs else "", "release": alb.get("name", ""),
              "date": str(alb.get("release_date") or "")[:10], "played_at": played_at})
    return r


def now_playing(ctx) -> dict:
    """Was gerade in Spotify läuft → {"track": Eintrag | None, "playing": bool}. Podcasts/Werbung → kein Titel."""
    ok, why = ready(ctx)
    if not ok:
        raise ValueError(f"Spotify: {why}.")
    need_scopes(ctx, "user-read-currently-playing")
    d = get(ctx, "/me/player/currently-playing", client(ctx)) or {}
    t = d.get("item") or {}
    if not t or t.get("type", "track") != "track" or not t.get("name"):
        return {"track": None, "playing": bool(d.get("is_playing"))}
    return {"track": idea_of(t), "playing": bool(d.get("is_playing"))}


def recently_played(ctx, n=50) -> list:
    """Zuletzt gehörte Titel (neueste zuerst, höchstens 50 – mehr liefert Spotify nicht), ohne Doppel."""
    ok, why = ready(ctx)
    if not ok:
        raise ValueError(f"Spotify: {why}.")
    d = get(ctx, "/me/player/recently-played", client(ctx), limit=max(1, min(50, int(n or 50)))) or {}
    out, seen = [], set()
    for it in d.get("items") or []:
        t = it.get("track") or {}
        if t.get("name") and t.get("id") not in seen:
            seen.add(t.get("id"))
            out.append(idea_of(t, str(it.get("played_at") or "")))
    return out


# =========================================================================== Schreiben (nur auf Klick: SP5, SP6)
WRITE_403 = ("Spotify hat das Schreiben abgelehnt (HTTP 403). Im Entwicklungsmodus sperrt Spotify Schreibzugriffe für "
             "manche Apps; prüfe im Developer Dashboard, ob dein Konto unter „Users Management“ eingetragen ist, und melde "
             "dich mit den neuen Berechtigungen neu an.")


def send(ctx, method: str, path: str, body=None, **params):
    """Schreibender Aufruf (POST/PUT/DELETE) mit Token, einmal erneuern bei 401 → JSON (oder {})."""
    import json as _json
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    a = app(ctx)
    data = _json.dumps(body).encode("utf-8") if body is not None else None
    for attempt in (0, 1):
        h = {"User-Agent": sk.USER_AGENT, "Accept": "application/json", **a.headers()}
        if data is not None:
            h["Content-Type"] = "application/json"
        om.SHARED.wait("api.spotify.com")
        st, _hd, raw = om.http_request(method, url, h, data)
        if st == 401 and attempt == 0 and a.refresh():
            continue
        break
    if st == 403:
        raise HttpError(403, WRITE_403)
    if st == 0 or st >= 400:
        raise HttpError(st, f"Spotify: HTTP {st} bei {method} {path}")
    try:
        return _json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, ValueError):
        return {}


def _uri_ok(u) -> bool:
    import re
    return bool(re.fullmatch(r"spotify:(track|album):[A-Za-z0-9]{22}", str(u or "")))


def wish_push(ctx, name: str, uris: list, existing_id: str = "") -> dict:
    """SP5: Wunschliste als **private** Spotify-Playlist anlegen bzw. fehlende Titel ergänzen (nur auf Klick).
    Nie werden Titel entfernt oder fremde Playlists verändert. → {"id", "url", "created", "added", "existing"}"""
    ok, why = ready(ctx)
    if not ok:
        raise ValueError(f"Spotify: {why}.")
    need_scopes(ctx, "playlist-modify-private")
    uris = [u for u in dict.fromkeys(uris or []) if _uri_ok(u)]
    cl = client(ctx)
    me = _me(ctx, cl).get("id") or ""
    pl = {}
    if existing_id:
        pl = get(ctx, f"/playlists/{existing_id}", cl, fields="id,name,owner(id),external_urls") or {}
        if (pl.get("owner") or {}).get("id") != me:
            pl = {}
    if not pl:                                           # gleichnamige eigene Playlist wiederverwenden (kein Doppel)
        for p in pages(ctx, "/me/playlists", cl):
            if p.get("name") == name and (p.get("owner") or {}).get("id") == me:
                pl = p
                break
    created = False
    if not pl:
        pl = send(ctx, "POST", "/me/playlists", {"name": name, "public": False,
                                                 "description": "Wunschliste aus MarKusSXCH TagStudio"})
        created = True
        ctx.log(f"Playlist angelegt: {name} ({pl.get('id')})")
    pid = pl.get("id") or ""
    if not pid:
        raise HttpError(-1, "Spotify: Playlist wurde nicht angelegt (keine ID).")
    have = set()
    if not created:
        for r in pages(ctx, f"/playlists/{pid}/items", cl, fields="items(item(uri),track(uri)),next"):
            u = (r.get("item") or r.get("track") or {}).get("uri")
            if u:
                have.add(u)
    todo = [u for u in uris if u not in have]
    for i in range(0, len(todo), 100):
        ctx.check_cancel()
        send(ctx, "POST", f"/playlists/{pid}/items", {"uris": todo[i:i + 100]})
    url = (pl.get("external_urls") or {}).get("spotify") or f"https://open.spotify.com/playlist/{pid}"
    ctx.log(f"{len(todo)} Titel ergänzt, {len(uris) - len(todo)} waren schon drin.")
    return {"id": pid, "url": url, "created": created, "added": len(todo), "existing": len(uris) - len(todo),
            "message": (f"Spotify-Playlist „{name}“ {'angelegt' if created else 'ergänzt'}: {len(todo)} Titel hinzugefügt"
                        + (f", {len(uris) - len(todo)} waren schon drin" if len(uris) > len(todo) else "") + ".")}


# =========================================================================== #384 SP4: ganzes Album nachschlagen
def _album_score(a: dict, title: str, artist: str) -> float:
    at, aa = om.norm(a.get("name", "")), om.norm(", ".join(_artists(a)))
    t = om.norm(title)
    sc = 1.0 if at == t else 0.6 if t and (t in at or at in t) else 0.0
    if artist and aa:
        ar = om.norm(artist)
        sc += 0.5 if ar == aa or ar in aa or aa in ar else -0.3
    return sc


def find_album(ctx, title: str, artist: str = "", cl=None):
    """Album über Titel (+ Künstler) suchen (Suche höchstens 10 Treffer) und mit allen Titeln holen."""
    cl = cl or client(ctx)
    q = f'album:"{title}"' + (f' artist:"{artist}"' if artist else "")
    d = get(ctx, "/search", cl, q=q, type="album", limit=10) or {}
    items = (d.get("albums") or {}).get("items") or []
    if not items and artist:
        d = get(ctx, "/search", cl, q=f"{artist} {title}", type="album", limit=10) or {}
        items = (d.get("albums") or {}).get("items") or []
    items = sorted(items, key=lambda a: -_album_score(a, title, artist))
    if not items or _album_score(items[0], title, artist) < 0.6:
        return None, []
    return album_tracks(ctx, items[0]["id"], cl)


def match_album(rows: list, files) -> list:
    """[(Datei, Album-Titel | None)] – über Titel mit Mix, sonst Titel ohne Mix; jeder Album-Titel nur einmal."""
    out, used = [], set()
    for f in files:
        info = om.file_info(f)
        want = om.norm(info["title"] + (f" ({info['mix']})" if info.get("mix") else ""))
        plain = om.norm(info["title"])

        def full(t):
            ti, mx = om.split_title(t.get("name", ""))
            return om.norm(ti + (f" ({mx})" if mx else ""))
        t = next((x for x in rows if id(x) not in used and full(x) == want), None) or \
            next((x for x in rows if id(x) not in used and om.norm(om.split_title(x.get("name", ""))[0]) == plain), None)
        if t is not None:
            used.add(id(t))
        out.append((f, t))
    return out


def run_album(ctx, files, opts) -> dict:
    import os
    ok, why = ready(ctx)
    if not ok:
        raise ValueError(f"Spotify: {why}.")
    cl = client(ctx)
    groups = {}
    for f in files:
        title = str(opts.get("title") or "").strip() or f.text("TALB").strip()
        artist = str(opts.get("artist") or "").strip() or f.text("TPE2").strip() or f.text("TPE1").replace(om.MV, ", ").strip()
        groups.setdefault((title, artist), []).append(f)
    found = matched = 0
    rows_out = []
    overwrite, full = opts.get("mode") == "overwrite", opts.get("date") == "full"
    for i, ((title, artist), fs) in enumerate(groups.items()):
        ctx.progress(i, len(groups), title or "?")
        if not title:
            rows_out += [[os.path.basename(f.path), "–", "kein Album (TALB) – Album-Titel in den Optionen angeben"] for f in fs]
            continue
        alb, tracks = find_album(ctx, title, artist, cl)
        if not alb:
            rows_out += [[os.path.basename(f.path), "–", "Album nicht gefunden"] for f in fs]
            continue
        found += 1
        genre = ""
        art = ((alb.get("artists") or [{}])[0] or {}).get("id")
        if art:
            g = (get(ctx, f"/artists/{art}", cl) or {}).get("genres") or []
            genre = g[0].title() if g else ""
        cover = b""
        imgs = alb.get("images") or []
        total = alb.get("total_tracks") or len(tracks)
        for f, t in match_album(tracks, fs):
            name = os.path.basename(f.path)
            if t is None:
                rows_out.append([name, alb.get("name", ""), "nicht in der Titelliste"])
                continue
            matched += 1
            rows_out.append([name, alb.get("name", ""), f"Titel {t.get('track_number') or '?'}/{total}"])
            t = dict(t, album=alb)
            c = _cand(t)
            c["genre"] = genre
            note = f"Spotify · Album: {alb.get('name', '')}"
            date = str(alb.get("release_date") or "")
            vals = [("TALB", alb.get("name", ""), "Album", True), ("TPE2", ", ".join(_artists(alb)), "Albumkünstler", True),
                    ("TDRC", date[:10] if full else date[:4], "Datum" if full else "Jahr", True),
                    ("TRCK", f"{t.get('track_number')}/{total}" if t.get("track_number") else "", "Titelnummer", True),
                    ("TPOS", str(t.get("disc_number") or ""), "CD-Nummer", bool(t.get("disc_number") and int(t.get("disc_number") or 1) > 1)),
                    ("TCON", genre, "Genre", True),
                    ("TIT2", c["title"] + (f" ({c['mix']})" if c["mix"] else ""), "Titel", bool(opts.get("names"))),
                    ("TPE1", ", ".join(c["artists"]), "Künstler", bool(opts.get("names")))]
            if opts.get("ids", True):
                vals += [(k, v, k.split(":", 1)[1], True) for k, v in (c.get("ids") or {}).items()]
            for key, val, label, wanted in vals:
                val = str(val or "").strip()
                if not val:
                    continue
                cur = f.text(key).strip()
                if cur == val:
                    continue
                sel = wanted and (overwrite or not cur)
                ctx.propose(f, key, val, f"{label} (Spotify)", note=note, group=name, checked=sel,
                            hint="" if sel else "schon gefüllt" if cur else "in den Optionen abgewählt",
                            link=c.get("url", ""), link_label="Spotify")
            if opts.get("own"):
                for key, val, label, stamp in own_fields(c):
                    if stamp and all(f.text(k).strip() == v for k, v, _l, st in own_fields(c) if not st):
                        continue
                    if f.text(key).strip() == val:
                        continue
                    ctx.propose(f, key, val, f"{label} (Spotify)", note=note, group=name, checked=True, hint=OWN_HINT)
            cov = opts.get("cover", "missing")
            has = f.get("APIC:3") is not None
            if imgs and cov != "no" and (cov == "replace" or not has):
                if not cover:
                    try:
                        cover = cl.raw(imgs[0].get("url", "")) or b""
                    except HttpError as ex:
                        ctx.log(f"Cover: {ex}")
                        cover = b"-"
                if cover[:3] in (b"\xff\xd8\xff", b"\x89PN"):
                    ctx.propose(f, "APIC:3", "Cover von Spotify", "Cover", kind="cover", data=cover, group=name,
                                checked=True, hint="ersetzt vorhandenes Cover" if has else "")
    ctx.progress(len(groups), len(groups), "fertig")
    return {"message": f"{found} von {len(groups)} Album/Alben gefunden, {matched} von {len(files)} Titel(n) zugeordnet (Quelle: Spotify).",
            "table": {"cols": ["Datei", "Album", "Ergebnis"], "rows": rows_out[:2000]}}


# =========================================================================== #384 SP1: Entdecken – neue Veröffentlichungen
def _ids_path(ctx):
    import os
    return os.path.join(ctx.data_dir, "kuenstler-ids.json")


def _artist_id(ctx, cl, name: str) -> str:
    """Künstler-ID zu einem Namen (Suche, höchstens 10 Treffer; gleicher Name bevorzugt) – zwischengespeichert, damit
    jede Suche nur einmal kostet."""
    import json as _json
    import os
    import time
    key = om.norm(name)
    try:
        with open(_ids_path(ctx), encoding="utf-8") as fh:
            cache = _json.load(fh)
    except (OSError, ValueError):
        cache = {}
    hit = cache.get(key)
    if isinstance(hit, str) and hit:
        return hit
    if isinstance(hit, dict) and time.time() - float(hit.get("none") or 0) < 7 * 86400:
        return ""                                        # nicht gefunden – erst nach 7 Tagen wieder suchen
    d = get(ctx, "/search", cl, q=name, type="artist", limit=10) or {}
    items = (d.get("artists") or {}).get("items") or []
    pick = next((a for a in items if str(a.get("name", "")).lower() == name.lower()), None)
    aid = (pick or {}).get("id", "")
    cache[key] = aid or {"none": time.time()}
    os.makedirs(ctx.data_dir, exist_ok=True)
    with open(_ids_path(ctx) + ".part", "w", encoding="utf-8") as fh:
        _json.dump(cache, fh, ensure_ascii=False)
    os.replace(_ids_path(ctx) + ".part", _ids_path(ctx))
    return aid


def _recent(date: str, days: int) -> bool:
    import time
    date = str(date or "")
    if len(date) == 4:
        date += "-12-31"
    elif len(date) == 7:
        date += "-28"
    try:
        return time.mktime(time.strptime(date[:10], "%Y-%m-%d")) >= time.time() - days * 86400
    except ValueError:
        return False


def discover_artist(ctx, name: str, days: int = 60, max_releases: int = 5) -> list:
    """Neue Singles/Alben eines Künstlers (``/artists/{id}/albums``, Ersatz für das entfernte /browse/new-releases)
    → Einträge für Entdecken (je Titel; ``/albums/{id}/tracks`` nur für neue Veröffentlichungen)."""
    cl = client(ctx)
    aid = _artist_id(ctx, cl, name)
    if not aid:
        return []
    rel = get(ctx, f"/artists/{aid}/albums", cl, include_groups="single,album", limit=10) or {}
    new = sorted([a for a in rel.get("items") or [] if _recent(a.get("release_date"), days)],
                 key=lambda a: str(a.get("release_date") or ""), reverse=True)[:max_releases]
    out = []
    for alb in new:
        ctx.check_cancel()
        imgs = alb.get("images") or []
        for t in pages(ctx, f"/albums/{alb['id']}/tracks", cl, max_items=50):
            if not t.get("id") or not t.get("name"):
                continue
            title, mix = om.split_title(t["name"])
            out.append({"key": f"spotify:{t['id']}", "src": "spotify", "id": t["id"], "artist": ", ".join(_artists(t)),
                        "title": title, "mix": mix, "label": "", "date": str(alb.get("release_date") or "")[:10],
                        "preview": "", "url": (t.get("external_urls") or {}).get("spotify") or f"https://open.spotify.com/track/{t['id']}",
                        "release": alb.get("name", ""), "cover": imgs[-1].get("url", "") if imgs else "", "seed": name})
    return out


# =========================================================================== #384 SP6: „In deiner Spotify-Bibliothek“
def library_contains(ctx, uris: list) -> dict:
    """Welche URIs stehen schon in deiner Bibliothek? (``GET /me/library/contains``, je 40) → {uri: bool}"""
    ok, why = ready(ctx)
    if not ok:
        raise ValueError(f"Spotify: {why}.")
    cl = client(ctx)
    uris = [u for u in dict.fromkeys(uris or []) if _uri_ok(u)]
    out = {}
    for i in range(0, len(uris), 40):
        part = uris[i:i + 40]
        d = get(ctx, "/me/library/contains", cl, uris=",".join(part))
        vals = d if isinstance(d, list) else []
        out.update({u: bool(vals[j]) if j < len(vals) else False for j, u in enumerate(part)})
    return out


def library_save(ctx, uris: list) -> dict:
    """Auf Klick: Titel in deiner Bibliothek (Lieblingssongs) speichern (``PUT /me/library``, je 40). Entfernt nie."""
    ok, why = ready(ctx)
    if not ok:
        raise ValueError(f"Spotify: {why}.")
    need_scopes(ctx, "user-library-modify")
    uris = [u for u in dict.fromkeys(uris or []) if _uri_ok(u)]
    for i in range(0, len(uris), 40):
        ctx.check_cancel()
        send(ctx, "PUT", "/me/library", None, uris=",".join(uris[i:i + 40]))
    ctx.log(f"{len(uris)} Titel in der Spotify-Bibliothek gespeichert.")
    return {"saved": len(uris), "message": f"{len(uris)} Titel in deiner Spotify-Bibliothek gespeichert."}


# =========================================================================== Entdecken
def followed_artists(ctx, top=False) -> list:
    cl = client(ctx)
    names = [a.get("name", "") for a in pages(ctx, "/me/following", cl, key="artists", type="artist")]
    if top:
        names += [a.get("name", "") for a in (get(ctx, "/me/top/artists", cl, limit=20).get("items") or [])]
    return [n for n in names if n]


def add_to_discover(names) -> int:
    import discover
    d = discover.load()
    before = len(d["follow"]["artists"])
    d["follow"]["artists"] = discover._names(d["follow"]["artists"] + list(names))
    discover.save(d)
    return len(d["follow"]["artists"]) - before


# =========================================================================== Aktionen
def status(ctx):
    a = app(ctx)
    if not a.configured():
        return "keine Client-ID – unter „Anmelden …“ eintragen"
    return "angemeldet" if a.logged_in() else "Client-ID gespeichert, nicht angemeldet – „Anmelden …“"


def run(action, ctx, files, opts):
    a = app(ctx)
    try:
        if action == "logout":
            a.logout()
            if opts.get("clear"):
                a.save_credentials({"clear": True})
            return {"message": "Abgemeldet."}
        if action == "login":
            a.save_credentials({k: opts.get(k) for k in ("client_id", "client_secret", "redirect")})
            if not a.configured():
                return {"message": "Bitte die Client-ID deiner Spotify-App eintragen."}
            if opts.get("method") == "paste":
                if not (opts.get("url") or "").strip():
                    url = a.auth_url()
                    if not oauthkit.open_browser(url):
                        ctx.log(f"Diese Adresse im Browser öffnen: {url}")
                    return {"message": "Spotify ist im Browser geöffnet. Nach der Zustimmung die Adresse aus der "
                                       "Adresszeile kopieren, hier einfügen und nochmals „Anmelden“."}
                a.finish(opts["url"])
            else:
                a.login_browser()
            me = _me(ctx, client(ctx))
            return {"message": f"Bei Spotify angemeldet als {me.get('display_name') or me.get('id') or '?'}."}
        if action == "test":
            ok, why = ready(ctx)
            if not ok:
                return {"message": f"Spotify: {why}."}
            me = _me(ctx, client(ctx))
            return {"message": f"Spotify: in Ordnung – angemeldet als {me.get('display_name') or me.get('id') or '?'}."}
        if action == "album":                            # #384 SP4
            return run_album(ctx, files, opts)
        if action == "follow":
            ok, why = ready(ctx)
            if not ok:
                return {"message": f"Spotify: {why}."}
            names = followed_artists(ctx, bool(opts.get("top")))
            n = add_to_discover(names)
            return {"message": f"{len(names)} Künstler gelesen, {n} neu in „Entdecken“ übernommen."}
    except (OAuthError, HttpError) as ex:
        return {"message": f"Spotify: {ex}"}
    raise ValueError(f"Unbekannte Aktion: {action}")
