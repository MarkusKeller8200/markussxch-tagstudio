"""Spotify (#280) – nur lesen: eigene Playlists und Lieblingssongs als Playlists, Titel-Daten mit ISRC und Link für
„Online-Metadaten“, gefolgte Künstler für „Entdecken“.

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
SCOPES = ["playlist-read-private", "playlist-read-collaborative", "user-library-read", "user-follow-read",
          "user-top-read", "user-read-recently-played"]
CFG = {"name": "Spotify", "authorize": "https://accounts.spotify.com/authorize",
       "token": "https://accounts.spotify.com/api/token", "scopes": SCOPES, "header": "Bearer", "secret": False,
       "redirect": "http://127.0.0.1:8765/callback"}
MAX_ITEMS = 5000

ACTIONS = [
    {"id": "login", "label": "Anmelden …", "where": "page", "run_label": "Anmelden", "needs_selection": False,
     "description": "Zugangsdaten deiner eigenen Spotify-App eintragen (leer = unverändert, verschlüsselt gespeichert) und die Anmeldeseite im Browser öffnen. TagStudio liest nur – es ändert nichts in deinem Konto.",
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
            "disc": str(t.get("disc_number") or ""), "url": url,
            "ids": {k: v for k, v in (("TXXX:SPOTIFY_TRACK_ID", t.get("id", "")), ("TXXX:SPOTIFY_URL", url)) if v}}


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
    return out


def playlist_files(ctx, pid) -> dict:
    """Titel einer Playlist als Einträge ohne Datei → {name, files: [], items, missing: 0}"""
    cl = client(ctx)
    if pid == LIKED:
        name, rows = "Lieblingssongs", pages(ctx, "/me/tracks", cl)
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
