"""SoundCloud (#280) – nur lesen: eigene Playlists, Likes und hochgeladene Titel als Playlists, Titel-Daten mit Link
für „Online-Metadaten“, gefolgte Künstler für „Entdecken“.

Zugang über eine **eigene SoundCloud-App** (Selbstregistrierung seit Mai 2026 mit Artist Pro) und OAuth 2.1 mit PKCE;
SoundCloud verlangt dazu Client-ID **und** Client-Secret. Beides und der Token liegen verschlüsselt im Datenordner des
Plugins. Refresh-Token sind nur einmal gültig – der neue wird sofort gespeichert.
Nur Standardbibliothek.
"""
import urllib.parse

import oauthkit
import onlinematch as om
import servicekit as sk
from onlinematch import HttpError
from oauthkit import OAuthError

SOURCE = {"id": "soundcloud", "name": "SoundCloud", "order": 45, "role": "metadata"}
API = "https://api.soundcloud.com"
INTERVALS = {"api.soundcloud.com": 0.3}
LIKES, UPLOADS = "likes", "uploads"
CFG = {"name": "SoundCloud", "authorize": "https://secure.soundcloud.com/authorize",
       "token": "https://secure.soundcloud.com/oauth/token", "scopes": [], "header": "OAuth", "secret": True,
       "redirect": "http://127.0.0.1:8766/callback"}
MAX_ITEMS = 5000

ACTIONS = [
    {"id": "login", "label": "Anmelden …", "where": "page", "run_label": "Anmelden", "needs_selection": False,
     "description": "Zugangsdaten deiner eigenen SoundCloud-App eintragen (leer = unverändert, verschlüsselt gespeichert) und die Anmeldeseite im Browser öffnen. TagStudio liest nur – es ändert nichts in deinem Konto.",
     "options": [{"type": "info", "title": "SoundCloud-App anlegen",
          "label": "1. Bei SoundCloud anmelden (Artist Pro nötig). 2. In „SoundCloud for Developers“ eine App "
                   "registrieren und als Redirect URI genau die Adresse unten eintragen (Standard "
                   "http://127.0.0.1:8766/callback). 3. Client-ID und Client-Secret kopieren und hier einfügen.",
          "links": [["SoundCloud: App registrieren", "https://developers.soundcloud.com/docs/api/register-app"],
                    ["SoundCloud: API-Dokumentation", "https://developers.soundcloud.com/docs/api"]]},
         {"key": "client_id", "type": "password", "label": "Client-ID"},
         {"key": "client_secret", "type": "password", "label": "Client-Secret"},
         {"key": "redirect", "type": "text", "label": "Redirect URI (wie in der SoundCloud-App)", "default": CFG["redirect"]},
         {"key": "method", "type": "select", "label": "Methode",
          "choices": [["browser", "Im Browser anmelden (automatisch)"], ["paste", "Adresse einfügen (wenn automatisch nicht geht)"]],
          "default": "browser"},
         {"key": "url", "type": "text", "label": "Adresse aus der Adresszeile nach der Anmeldung",
          "show_if": {"method": "paste"}},
         {"type": "info", "show_if": {"method": "paste"},
          "label": "Zuerst ohne Adresse „Anmelden“ – der Browser öffnet SoundCloud. Nach der Zustimmung die Adresse "
                   "(http://127.0.0.1:…?code=…) aus der Adresszeile kopieren, hier einfügen und nochmals „Anmelden“."}]},
    {"id": "logout", "label": "Abmelden …", "where": "page", "run_label": "Abmelden", "needs_selection": False,
     "description": "Gespeicherte Anmeldung löschen.", "options": [{"key": "clear", "type": "check", "label": "Auch die Zugangsdaten der App löschen", "default": False}]},
    {"id": "test", "label": "Verbindung testen", "where": "page", "run_label": "Testen", "needs_selection": False,
     "description": "Prüft Zugang und Anmeldung bei SoundCloud.", "options": []},
    {"id": "follow", "label": "Gefolgte Künstler in „Entdecken“ übernehmen …", "where": "page", "run_label": "Übernehmen",
     "needs_selection": False,
     "description": "Liest die Konten, denen du auf SoundCloud folgst, und ergänzt sie in „Entdecken“ › Gefolgte Künstler.",
     "options": []},
]


def app(ctx) -> oauthkit.App:
    return oauthkit.App(ctx, CFG)


def client(ctx):
    return sk.client(ctx, INTERVALS)


def ready(ctx):
    a = app(ctx)
    if not a.configured():
        return False, "Client-ID oder Client-Secret fehlt (Plugin SoundCloud › „Anmelden …“)"
    if not a.logged_in():
        return False, "nicht angemeldet (Plugin SoundCloud › „Anmelden …“)"
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
    return app(ctx).get(url, cl or client(ctx))


MAX_PAGES = 500


def pages(ctx, path, cl=None, limit=200, max_items=MAX_ITEMS, **params) -> list:
    """Listen mit linked_partitioning ({collection, next_href}) bzw. einfache Listen."""
    cl = cl or client(ctx)
    d = get(ctx, path, cl, limit=limit, linked_partitioning="true", **params)
    out, seen, before = [], set(), -1
    while d:
        if isinstance(d, list):
            out += d
            break
        out += d.get("collection") or []
        nxt = d.get("next_href")
        if not nxt or len(out) >= max_items or nxt in seen or len(out) == before or len(seen) >= MAX_PAGES:
            break                                       # Ende, gleiche Seite nochmals oder leere Seite: nicht endlos laden
        seen.add(nxt)
        before = len(out)
        ctx.check_cancel()
        d = get(ctx, nxt, cl)
    return out[:max_items]


# =========================================================================== Titel → Eintrag / Kandidat
def _meta(t) -> dict:
    return t.get("publisher_metadata") or {}


def _artist(t) -> str:
    return _meta(t).get("artist") or t.get("metadata_artist") or (t.get("user") or {}).get("username", "")


def ref_of(t) -> dict:
    title, mix = om.split_title(t.get("title", ""))
    return {"artist": _artist(t), "title": title, "mix": mix, "isrc": (_meta(t).get("isrc") or "").upper(),
            "dur": int((t.get("duration") or 0) / 1000), "source": "soundcloud", "url": t.get("permalink_url", "")}


def _cand(t) -> dict:
    title, mix = om.split_title(t.get("title", ""))
    m = _meta(t)
    art = (t.get("artwork_url") or "").replace("-large.", "-t500x500.")
    url = t.get("permalink_url", "")
    date = t.get("release_date") or (t.get("created_at") or "")[:10].replace("/", "-")
    return {"source": "soundcloud", "source_name": "SoundCloud", "id": str(t.get("id", "")), "title": title, "mix": mix,
            "artists": [a.strip() for a in _artist(t).split(",") if a.strip()], "length": (t.get("duration") or 0) / 1000 or None,
            "isrc": (m.get("isrc") or "").upper(), "album": m.get("release_title") or "", "label": t.get("label_name") or "",
            "date": date, "genre": t.get("genre") or "", "bpm": t.get("bpm") or 0, "cover": art, "url": url,
            "ids": {k: v for k, v in (("TXXX:SOUNDCLOUD_TRACK_ID", str(t.get("id") or "")), ("TXXX:SOUNDCLOUD_URL", url)) if v}}


def candidates(ctx, cl, info, opts=None) -> list:
    if not ready(ctx)[0] or not info.get("title"):
        return []
    q = " ".join(x for x in (om.first_artist(info) if info.get("artist") else "", info["title"], info.get("mix", "")) if x)
    d = get(ctx, "/tracks", cl, q=q, limit=10, linked_partitioning="true") or {}
    rows = d.get("collection") if isinstance(d, dict) else d
    return [_cand(t) for t in rows or [] if isinstance(t, dict)]


def details(ctx, cl, c) -> dict:
    return c                          # Suche liefert den ganzen Titel


def test_query(ctx, info):
    ok, why = ready(ctx)
    if not ok:
        raise ValueError(f"SoundCloud: {why}.")
    cands = candidates(ctx, client(ctx), info)
    ctx.log(f"Suche: {len(cands)} Titel")
    return cands


def api_request(ctx, ep, params):
    import services
    a = app(ctx)
    url = services.build_url({"base": API}, ep, params)
    st, h, body, _n = om.get_retry(url, {"User-Agent": sk.USER_AGENT, "Accept": "application/json; charset=utf-8", **a.headers()})
    if st == 401 and a.refresh():
        st, h, body, _n = om.get_retry(url, {"User-Agent": sk.USER_AGENT, "Accept": "application/json", **a.headers()})
    ctx.secrets = a.secrets()
    return st, h, body, url


# =========================================================================== Playlists
def playlists(ctx) -> list:
    ok, why = ready(ctx)
    if not ok:
        raise ValueError(f"SoundCloud: {why}.")
    cl = client(ctx)
    out = [{"id": LIKES, "name": "Likes", "path": [], "depth": 0, "type": "likes"},
           {"id": UPLOADS, "name": "Eigene Titel", "path": [], "depth": 0, "type": "uploads"}]
    for p in pages(ctx, "/me/playlists", cl, show_tracks="false"):
        out.append({"id": str(p.get("urn") or p.get("id")), "name": p.get("title") or str(p.get("id")), "path": [],
                    "depth": 0, "type": "playlist"})
    return out


def playlist_files(ctx, pid) -> dict:
    cl = client(ctx)
    if pid == LIKES:
        name, rows = "Likes", pages(ctx, "/me/likes/tracks", cl)
    elif pid == UPLOADS:
        name, rows = "Eigene Titel", pages(ctx, "/me/tracks", cl)
    else:
        p = get(ctx, f"/playlists/{urllib.parse.quote(str(pid), safe=':')}", cl, show_tracks="true") or {}
        name, rows = p.get("title") or f"Playlist {pid}", p.get("tracks") or []
    items = [{"ref": ref_of(t)} for t in rows if isinstance(t, dict) and t.get("title")]
    return {"name": name, "files": [], "items": items, "missing": 0}


# =========================================================================== Entdecken
def followed_artists(ctx) -> list:
    return [u.get("username", "") for u in pages(ctx, "/me/followings", client(ctx)) if u.get("username")]


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
        return "Client-ID/Secret fehlen – unter „Anmelden …“ eintragen"
    return "angemeldet" if a.logged_in() else "Zugangsdaten gespeichert, nicht angemeldet – „Anmelden …“"


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
                return {"message": "Bitte Client-ID und Client-Secret deiner SoundCloud-App eintragen."}
            if opts.get("method") == "paste":
                if not (opts.get("url") or "").strip():
                    url = a.auth_url()
                    if not oauthkit.open_browser(url):
                        ctx.log(f"Diese Adresse im Browser öffnen: {url}")
                    return {"message": "SoundCloud ist im Browser geöffnet. Nach der Zustimmung die Adresse aus der "
                                       "Adresszeile kopieren, hier einfügen und nochmals „Anmelden“."}
                a.finish(opts["url"])
            else:
                a.login_browser()
            me = get(ctx, "/me") or {}
            return {"message": f"Bei SoundCloud angemeldet als {me.get('username') or '?'}."}
        if action == "test":
            ok, why = ready(ctx)
            if not ok:
                return {"message": f"SoundCloud: {why}."}
            me = get(ctx, "/me") or {}
            return {"message": f"SoundCloud: in Ordnung – angemeldet als {me.get('username') or '?'}."}
        if action == "follow":
            ok, why = ready(ctx)
            if not ok:
                return {"message": f"SoundCloud: {why}."}
            names = followed_artists(ctx)
            n = add_to_discover(names)
            return {"message": f"{len(names)} Konten gelesen, {n} neu in „Entdecken“ übernommen."}
    except (OAuthError, HttpError) as ex:
        return {"message": f"SoundCloud: {ex}"}
    raise ValueError(f"Unbekannte Aktion: {action}")
