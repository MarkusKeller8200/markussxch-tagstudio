"""Beatport – Metadaten, Playlists und Käufe über die offizielle Beatport-API v4.

Standard (Entscheid User 25.10.2026, #289): eigener offizieller API-Zugang (Client-ID + Secret, Password Grant laut
Anmelde-Doku). Ausweichweg (inoffiziell): Login wie im beets-Plugin „beatport4“ über die öffentliche client_id der
API-Dokumentation (OAuth authorization_code) oder Token aus dem Browser einfügen. Genutzt werden nur Endpunkte der
offiziellen Beschreibung – ausser dem Download gekaufter Dateien (nicht dokumentiert, Variante 1 mit Hinweis auf die
Download-Seite). Das Passwort wird nie gespeichert; Token und App-Daten liegen verschlüsselt (Windows: DPAPI,
macOS: Schlüsselbund – #287).

Nur Standardbibliothek. Alle Änderungen werden als Vorschläge zurückgegeben (Vorschau mit Häkchen).
"""
import difflib
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

import secretstore

from id3tags import MV

API = "https://api.beatport.com/v4"
USER_AGENT = "MarKusSXCH-TagStudio (+https://github.com/MarkusKeller8200/markussxch-tagstudio)"
TIMEOUT = 30
MIN_INTERVAL = 0.35          # höchstens ~3 Anfragen pro Sekunde
SURE, MAYBE = 0.80, 0.62     # Trefferschwellen

GENRE_MODES = [["sub", "Subgenre (sonst Hauptgenre)"], ["main", "Hauptgenre"], ["both", "Hauptgenre; Subgenre"]]

ACTIONS = [
    {
        "id": "fetch", "label": "Beatport-Daten holen …", "where": "tagger", "run_label": "Suchen",
        "description": "Sucht die markierten Titel auf Beatport und schlägt Änderungen vor. Du bestätigst danach jede Änderung.",
        "options": [
            {"key": "mode", "type": "select", "label": "Vorhandene Werte",
             "choices": [["missing", "Nur noch nicht vorhandene Felder (vorhandene ausblenden)"],
                         ["empty", "Nur leere Felder füllen (vorhandene zum Vergleich zeigen)"],
                         ["overwrite", "Überschreiben (Vorschau zeigt alt → neu)"]],
             "default": "missing"},                                                        # #142
            {"key": "bpm", "type": "check", "label": "BPM", "default": True},
            {"key": "key", "type": "check", "label": "Tonart (in deiner Schreibweise: Camelot / Am / Open Key)", "default": True},
            {"key": "genre", "type": "check", "label": "Genre", "default": True},
            {"key": "genre_mode", "type": "select", "label": "Genre aus", "choices": GENRE_MODES, "default": "sub",
             "show_if": {"genre": True}},
            {"key": "label", "type": "check", "label": "Label (TPUB) und Katalognummer", "default": True},
            {"key": "date", "type": "select", "label": "Erscheinungsdatum",
             "choices": [["year", "Nur Jahr"], ["full", "Volles Datum (JJJJ-MM-TT)"], ["no", "Nicht übernehmen"]], "default": "year"},
            {"key": "isrc", "type": "check", "label": "ISRC", "default": True},
            {"key": "remixer", "type": "check", "label": "Remixer (TPE4)", "default": True},
            {"key": "names", "type": "check", "label": "Titel, Künstler, Album übernehmen (Titel mit Mix-Name)", "default": False},
            {"key": "cover", "type": "select", "label": "Cover",
             "choices": [["missing", "Nur wenn keins vorhanden"], ["replace", "Ersetzen"], ["no", "Nicht übernehmen"]], "default": "missing"},
            {"key": "ids", "type": "check", "label": "Beatport-ID speichern (TXXX:BEATPORT_TRACK_ID) – spätere Abgleiche ohne Suche", "default": True},
        ],
    },
    {
        "id": "login", "label": "Anmelden …", "where": "page", "run_label": "Anmelden", "needs_selection": False,
        "description": "Mit deinem Beatport-Konto anmelden. Das Passwort wird nur für die Anmeldung benutzt und nie gespeichert.",
        "options": [
            {"key": "method", "type": "select", "label": "Methode",
             "choices": [["app", "Eigener API-Zugang (Client-ID und Secret) – empfohlen"],
                         ["login", "Benutzername und Passwort (inoffiziell, Ausweichweg)"],
                         ["token", "Token aus dem Browser einfügen (inoffiziell)"]], "default": "app"},
            {"key": "client_id", "type": "text", "label": "Client-ID deiner Beatport-App", "secret": True, "show_if": {"method": "app"}},
            {"key": "client_secret", "type": "password", "label": "Client-Secret", "show_if": {"method": "app"}},
            {"type": "info", "show_if": {"method": "app"},
             "label": "Offizieller Zugang mit deiner eigenen Beatport-App (Password Grant). Client-ID und Secret werden "
                      "verschlüsselt gespeichert – bleiben die Felder leer, gelten die schon gespeicherten. Das Passwort "
                      "wird nur für die Anmeldung benutzt und nie gespeichert."},
            {"key": "username", "type": "text", "label": "Benutzername / E-Mail", "show_if": {"method": ["login", "app"]}},
            {"key": "password", "type": "password", "label": "Passwort", "show_if": {"method": ["login", "app"]}},
            {"key": "token", "type": "textarea", "label": "Token (JSON)", "secret": True, "show_if": {"method": "token"}},
            {"type": "info", "show_if": {"method": "token"}, "label": "Token-Methode: auf api.beatport.com/v4/docs anmelden, Entwicklertools (F12) → Netzwerk → Anfrage „token“ → Antwort kopieren und hier einfügen."},
        ],
    },
    {"id": "follow", "label": "Gefolgte Künstler und Labels in „Entdecken“ übernehmen …", "where": "page",
     "run_label": "Übernehmen", "needs_selection": False,
     "description": "Liest die Künstler und Labels, denen du auf Beatport folgst („My Beatport“), und ergänzt sie in "
                    "„Entdecken“. Vorhandene bleiben, nichts wird entfernt; bei Beatport wird nichts geändert.",
     "options": [{"key": "artists", "type": "check", "label": "Gefolgte Künstler", "default": True},
                 {"key": "labels", "type": "check", "label": "Gefolgte Labels", "default": True}]},
    {"id": "logout", "label": "Abmelden", "where": "page", "run_label": "Abmelden", "needs_selection": False,
     "description": "Gespeicherten Token löschen (beim eigenen API-Zugang wird er bei Beatport auch zurückgezogen).",
     "options": [{"key": "forget_app", "type": "check", "label": "Client-ID und Secret des eigenen API-Zugangs ebenfalls löschen",
                  "default": False}]},
    {"id": "test", "label": "Verbindung testen", "where": "page", "run_label": "Testen", "needs_selection": False,
     "description": "Prüft die Anmeldung bei Beatport.", "options": []},
    {"id": "purchases", "label": "Gekaufte Titel abgleichen …", "where": "page", "run_label": "Abgleichen",
     "needs_selection": False,
     "description": "Liest die gekauften Titel deines Beatport-Kontos und prüft, welche in deinen Ordnern "
                    "schon vorhanden sind (Ergebnis als CSV-Liste) und markiert sie in „Entdecken“ als gekauft. Laden: „Fehlende Käufe herunterladen …“.",
     "options": [
         {"key": "folders", "type": "folders", "label": "Ordner zum Abgleich (z. B. Bibliothek und Eingang)"},
         {"key": "max", "type": "number", "label": "Höchstens so viele Käufe lesen", "default": 2000},
         {"type": "info", "label": "Abgleich über Beatport-ID (TXXX:BEATPORT_TRACK_ID), ISRC oder Künstler + Titel + Mix."},
     ]},
    {"id": "download", "label": "Fehlende Käufe herunterladen …", "where": "page", "run_label": "Herunterladen",
     "needs_selection": False,
     "description": "Lädt gekaufte Titel, die in deinen Ordnern noch fehlen, unverändert in den Zielordner (z. B. den "
                    "Eingangsordner von „Vorbereiten“). Beatport hat dafür keine offizielle Schnittstelle – der Weg wird "
                    "vorsichtig ermittelt und protokolliert. Zuerst mit 1 Titel testen.",
     "options": [
         {"key": "dest", "type": "folder", "label": "Zielordner (z. B. Eingangsordner)"},
         {"key": "folders", "type": "folders", "label": "Ordner zum Abgleich (vorhandene werden nicht geladen)"},
         {"key": "count", "type": "number", "label": "Höchstens so viele Titel laden", "default": 1},
         {"type": "info", "label": "Geladen wird im gekauften Format (audio_format). Bereits geladene Titel merkt sich "
                                  "TagStudio und lädt sie nicht doppelt. Details im Protokoll (Plugins › Protokolle › beatport.log)."},
     ]},
    {"id": "settings", "label": "Einstellungen …", "where": "page", "run_label": "Speichern", "needs_selection": False,
     "description": "Playlists in deinem Beatport-Konto anlegen – „Download Tracks“ (je 100 Titel) und eine Playlist je "
                    "Kaufdatum auf der Seite „Käufe“. Ändert dein Beatport-Konto, aber nur, wenn du dort auf den Knopf klickst.",
     "options": [
         {"key": "playlists_write", "type": "check", "label": "Playlists in Beatport anlegen und befüllen (Käufe)", "default": False},
         {"key": "buy_prefix", "type": "text", "label": "Präfix für Playlists je Kaufdatum", "default": "TagStudio_BUY_"},
         {"type": "info", "label": "TagStudio verändert nur Playlists, deren Name mit „TagStudio_“ beginnt, und löscht nie "
                                  "ohne Rückfrage. „Schreibzugriff prüfen“ fragt Beatport nur nach den erlaubten Methoden."},
     ]},
    {"id": "write_check", "label": "Schreibzugriff prüfen", "where": "page", "run_label": "Prüfen", "needs_selection": False,
     "description": "Fragt Beatport (OPTIONS, ändert nichts), ob Playlists über die API angelegt und befüllt werden können.",
     "options": []},
]


# =========================================================================== Token sicher ablegen
def _token_path(ctx):
    return os.path.join(ctx.data_dir, "token.bin")


def _load_json(path, key):
    try:
        raw = secretstore.read(path)
        d = json.loads(raw.decode("utf-8")) if raw else None
        return d if isinstance(d, dict) and d.get(key) else None
    except (OSError, ValueError):
        return None


def _save_json(ctx, path, d: dict):
    if secretstore.write(path, json.dumps(d).encode("utf-8")) == "file" and secretstore.last_note():
        ctx.log(secretstore.last_note())


def save_token(ctx, tok: dict):
    _save_json(ctx, _token_path(ctx), tok)


def load_token(ctx):
    return _load_json(_token_path(ctx), "access_token")


def delete_token(ctx):
    return secretstore.delete(_token_path(ctx))


def _app_path(ctx):
    return os.path.join(ctx.data_dir, "app.bin")


def save_app(ctx, cid: str, secret: str):
    """Eigener API-Zugang (Client-ID, Secret) – wie der Token über secretstore (DPAPI / Schlüsselbund, #287)."""
    _save_json(ctx, _app_path(ctx), {"client_id": cid, "client_secret": secret})


def load_app(ctx) -> dict | None:
    return _load_json(_app_path(ctx), "client_id")


def delete_app(ctx) -> bool:
    return secretstore.delete(_app_path(ctx))


def _norm_token(data) -> dict:
    if isinstance(data, str):
        data = json.loads(data)
    tok = {"access_token": str(data["access_token"]), "refresh_token": str(data.get("refresh_token") or "")}
    tok["expires_at"] = float(data["expires_at"]) if data.get("expires_at") else time.time() + int(data.get("expires_in") or 3600)
    if data.get("username"):
        tok["username"] = data["username"]
    if data.get("app"):
        tok["app"] = True
    if data.get("scope"):
        tok["scope"] = str(data["scope"])
    return tok


def token_scope(tok) -> str:
    """#296: Berechtigungen (Scope) eines Tokens – aus der Token-Antwort oder aus dem Token selbst (JWT, Mittelteil
    base64url; gelesen wird nur „scope“, nichts wird geprüft oder weitergegeben). "" = unbekannt."""
    if not isinstance(tok, dict):
        return ""
    if tok.get("scope"):
        return str(tok["scope"])
    parts = str(tok.get("access_token") or "").split(".")
    if len(parts) != 3:
        return ""
    import base64
    try:
        pl = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return ""
    sc = pl.get("scope") or pl.get("scp") if isinstance(pl, dict) else ""
    return " ".join(sc) if isinstance(sc, list) else str(sc or "")


def scope_text(tok) -> str:
    return f"Berechtigungen (Scope): {token_scope(tok) or 'unbekannt'}"


# =========================================================================== HTTP
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class HttpError(Exception):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status = status


_last = [0.0]


def request(method, url, *, headers=None, data=None, opener=None, follow=True):
    """Liefert (Status, Header, Body-Bytes). Fehlerstatus werden nicht als Ausnahme geworfen."""
    wait = MIN_INTERVAL - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    h = {"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.9, */*;q=0.5"}
    h.update(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8") if not isinstance(data, bytes) else data
        h.setdefault("Content-Type", "application/json")
    auth = h.pop("Authorization", None)
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    if auth:                                            # nie an eine Weiterleitung (anderer Host) mitschicken
        req.add_unredirected_header("Authorization", auth)
    op = opener or urllib.request.build_opener(*([] if follow else [_NoRedirect()]))
    try:
        with op.open(req, timeout=TIMEOUT) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read() if e.fp else b""
    except urllib.error.URLError as e:
        raise HttpError(0, f"Beatport nicht erreichbar: {e.reason}") from e


# =========================================================================== Anmeldung
def fetch_client_id(ctx):
    """Öffentliche client_id aus der Beatport-API-Dokumentation lesen (wird zwischengespeichert)."""
    cache = os.path.join(ctx.data_dir, "client_id.txt")
    st, _h, html = request("GET", API + "/docs/")
    if st != 200:
        raise HttpError(st, f"Beatport-Dokumentation nicht erreichbar (HTTP {st}).")
    for src in re.findall(r"src=.(.*?\.js)", html.decode("utf-8", "replace")):
        url = src if src.startswith("http") else "https://api.beatport.com" + src
        st, _h, js = request("GET", url)
        m = re.search(r"API_CLIENT_ID: ?'([^']+)'", js.decode("utf-8", "replace")) if st == 200 else None
        if m:
            with open(cache, "w", encoding="utf-8") as fh:
                fh.write(m.group(1))
            return m.group(1)
    raise HttpError(0, "Beatport-client_id nicht gefunden – Beatport hat die Dokumentation wohl geändert.")


def client_id(ctx, fresh=False):
    cache = os.path.join(ctx.data_dir, "client_id.txt")
    if not fresh:
        try:
            with open(cache, encoding="utf-8") as fh:
                cid = fh.read().strip()
            if cid:
                return cid
        except OSError:
            pass
    return fetch_client_id(ctx)


def login(ctx, username, password):
    cid = client_id(ctx, fresh=True)
    redirect = API + "/auth/o/post-message/"
    import http.cookiejar
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), _NoRedirect())
    st, _h, body = request("POST", API + "/auth/login/", data={"username": username, "password": password}, opener=opener)
    try:
        data = json.loads(body or b"{}")
    except ValueError:
        data = {}
    if st >= 400 or "username" not in data:
        msg = data.get("detail") or data.get("non_field_errors") or data or f"HTTP {st}"
        raise HttpError(st, f"Anmeldung abgelehnt: {msg}")
    q = urllib.parse.urlencode({"response_type": "code", "client_id": cid, "redirect_uri": redirect})
    st, h, body = request("GET", f"{API}/auth/o/authorize/?{q}", opener=opener)
    loc = h.get("Location") or h.get("location")
    if not loc:
        txt = body.decode("utf-8", "replace")
        m = re.search(r"<p>(.*?)</p>", txt)
        raise HttpError(st, f"Beatport-Autorisierung fehlgeschlagen: {m.group(1) if m else f'HTTP {st}'}")
    code = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query).get("code", [None])[0]
    if not code:
        raise HttpError(st, "Kein Autorisierungscode von Beatport erhalten.")
    q = urllib.parse.urlencode({"code": code, "grant_type": "authorization_code", "redirect_uri": redirect, "client_id": cid})
    st, _h, body = request("POST", f"{API}/auth/o/token/?{q}", data=b"", opener=opener,
                        headers={"Content-Type": "application/x-www-form-urlencoded"})
    if st >= 400:
        raise HttpError(st, f"Token-Austausch fehlgeschlagen (HTTP {st}).")
    tok = _norm_token(json.loads(body))
    tok["username"] = data.get("username", "")
    return tok


def _form(d: dict) -> bytes:
    return urllib.parse.urlencode(d).encode("utf-8")


def login_app(ctx, cid, secret, username, password):
    """Offizieller Zugang mit eigener App (Password Grant laut Beatport-Doku): Formular an /auth/o/token/."""
    st, _h, body = request("POST", API + "/auth/o/token/", data=_form({
        "client_id": cid, "client_secret": secret, "username": username, "password": password, "grant_type": "password"}),
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        data = json.loads(body or b"{}")
    except ValueError:
        data = {}
    if st >= 400 or not data.get("access_token"):
        msg = data.get("error_description") or data.get("detail") or data.get("error") or f"HTTP {st}"
        raise HttpError(st, f"Anmeldung mit eigenem API-Zugang abgelehnt: {msg}")
    tok = _norm_token(data)
    tok["app"] = True
    tok["username"] = username
    return tok


def revoke(ctx, tok) -> bool:
    """Token bei Beatport zurückziehen (nur eigener API-Zugang)."""
    app = load_app(ctx) if tok and tok.get("app") else None
    if not app:
        return False
    q = urllib.parse.urlencode({"client_id": app["client_id"], "token": tok["access_token"]})
    try:
        st, _h, _b = request("POST", f"{API}/auth/o/revoke/?{q}", data=b"",
                             headers={"Content-Type": "application/x-www-form-urlencoded"})
    except HttpError:
        return False
    return st < 400


def refresh(ctx, tok, save=True):
    if not tok.get("refresh_token"):
        return None
    app = load_app(ctx) if tok.get("app") else None
    if tok.get("app") and not app:
        return None
    if app:                                            # offizieller Weg: Formular mit Client-ID (und Secret)
        form = {"grant_type": "refresh_token", "refresh_token": tok["refresh_token"], "client_id": app["client_id"]}
        if app.get("client_secret"):
            form["client_secret"] = app["client_secret"]
        st, _h, body = request("POST", API + "/auth/o/token/", data=_form(form),
                               headers={"Content-Type": "application/x-www-form-urlencoded",
                                        "Authorization": f"Bearer {tok['access_token']}"})
    else:
        q = urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": tok["refresh_token"],
                                    "client_id": client_id(ctx)})
        st, _h, body = request("POST", f"{API}/auth/o/token/?{q}", data=b"",
                               headers={"Content-Type": "application/x-www-form-urlencoded"})
    if st in (400, 401):                               # Erneuerung abgelehnt (abgelaufen/zurückgezogen)
        return None
    if st >= 400:                                      # Beatport gerade nicht verfügbar: Anmeldung behalten
        raise HttpError(st, f"Token-Erneuerung: HTTP {st} – später nochmals versuchen.")
    try:
        new = _norm_token(json.loads(body))
    except (ValueError, KeyError, TypeError) as e:
        raise HttpError(st, "Token-Erneuerung: unerwartete Antwort von Beatport.") from e
    new["username"] = tok.get("username", "")
    if tok.get("app"):
        new["app"] = True
    if save:
        save_token(ctx, new)
    return new


def account(client) -> dict:
    return client.account()


class Client:
    def __init__(self, ctx):
        self.ctx = ctx
        self.tok = load_token(ctx)
        if not self.tok:
            raise RuntimeError("Nicht bei Beatport angemeldet – auf der Plugin-Seite bei „Beatport“ auf „Anmelden …“ klicken.")

    def get(self, path, **params):
        if self.tok["expires_at"] - 30 < time.time():
            self.tok = self._refresh() or self._expired()
        url = API + (path if path.startswith("/") else "/" + path)
        if params:
            url += "?" + urllib.parse.urlencode(params)
        for attempt in range(3):
            st, h, body = request("GET", url, headers={"Authorization": f"Bearer {self.tok['access_token']}"})
            if st == 401 and attempt == 0:
                self.tok = self._refresh() or self._expired()
                continue
            if st == 429:
                time.sleep(_retry_after(h.get("Retry-After")))
                continue
            if st == 404:
                return None
            if st >= 400:
                raise HttpError(st, f"Beatport meldet HTTP {st} für {path}")
            data = json.loads(body or b"null")
            return data.get("results", data) if isinstance(data, dict) and "results" in data else data
        raise HttpError(429, "Beatport begrenzt gerade die Anfragen – bitte später erneut versuchen.")

    def account(self) -> dict:
        """Eigenes Konto: GET /my/account/ (laut offizieller Beschreibung; /my/account/myaccount/ ist nur PUT/PATCH)."""
        try:
            acc = self.get("/my/account/")
        except HttpError:
            acc = None
        if isinstance(acc, list):
            acc = acc[0] if acc and isinstance(acc[0], dict) else {}
        return acc if isinstance(acc, dict) else {}

    def _refresh(self):
        return refresh(self.ctx, self.tok)

    def _expired(self):
        delete_token(self.ctx)
        raise RuntimeError("Die Beatport-Anmeldung ist abgelaufen – bitte auf der Plugin-Seite neu anmelden.")

    def search_tracks(self, query, n=8):
        res = self.get("/catalog/search/", q=query, type="tracks", per_page=n)
        if isinstance(res, dict):
            res = res.get("tracks") or []
        return [t for t in (res or []) if isinstance(t, dict)]

    def track(self, tid):
        return self.get(f"/catalog/tracks/{tid}/")

    def by_isrc(self, isrc):
        res = self.get("/catalog/tracks/", isrc=isrc, per_page=5)
        return [t for t in (res or []) if isinstance(t, dict)] if isinstance(res, list) else []


# =========================================================================== #284: Beatport-Playlists (nur lesen)
# Inoffizielle API v4 wie bei den Käufen (#117): bekannte Pfade werden probiert, die Feldnamen der ersten Antwort ins
# Protokoll geschrieben (Plugins › Beatport › Protokoll). Entscheid B1 (25.10.2026): eigene Playlists.
PLAYLIST_PATHS = ["/my/playlists/"]
PLAYLIST_TRACK_PATHS = ["/my/playlists/{id}/tracks/"]
PAGE = 100


def ready(ctx):
    """Für Playlists und Online-Metadaten: angemeldet?"""
    return (True, "") if load_token(ctx) else (False, "nicht angemeldet (Plugin Beatport › „Anmelden …“)")


def _items(res) -> list:
    if isinstance(res, list):
        return res
    if isinstance(res, dict):
        for k in ("results", "playlists", "tracks", "items"):
            if isinstance(res.get(k), list):
                return res[k]
    return []


def _pages(client, path, limit=5000, log=None):
    """Alle Seiten einer Liste (page/per_page). log: Feldnamen der ersten Seite."""
    out, page = [], 1
    while len(out) < limit:
        res = client.get(path, page=page, per_page=PAGE)
        if res is None:
            if page == 1:
                raise HttpError(404, f"Beatport kennt {path} nicht")
            break
        items = _items(res)
        if log and page == 1 and items and isinstance(items[0], dict):
            log(f"{path}: Felder je Eintrag: {', '.join(sorted(items[0].keys()))}")
        out += [x for x in items if isinstance(x, dict)]
        if len(items) < PAGE:
            break
        page += 1
    return out[:limit]


def track_ref(t) -> dict:
    """Beatport-Titel → Eintrag ohne Datei (Playlists, Abgleich mit der Bibliothek, Einkaufsliste mit Link)."""
    return {"artist": ", ".join(artists_of(t)), "title": t.get("name") or "", "mix": t.get("mix_name") or "",
            "isrc": str(t.get("isrc") or "").upper(), "dur": int((t.get("length_ms") or 0) / 1000), "source": "beatport",
            "url": f"https://www.beatport.com/track/{t.get('slug') or 'track'}/{t['id']}" if t.get("id") else ""}


def playlists(ctx) -> list:
    """Eigene Beatport-Playlists: [{id, name, path, depth, type}]."""
    ok, why = ready(ctx)
    if not ok:
        raise ValueError(f"Beatport: {why}.")
    c = Client(ctx)
    for path in PLAYLIST_PATHS:
        try:
            rows = _pages(c, path, 1000, ctx.log)
        except HttpError as ex:
            ctx.log(f"{path}: {ex}")
            continue
        out = []
        for p in rows:
            if p.get("id") is None:
                continue
            n = p.get("track_count") or p.get("tracks_count") or p.get("count")
            out.append({"id": str(p["id"]), "name": p.get("name") or f"Playlist {p['id']}", "path": [], "depth": 0,
                        "type": "playlist", **({"count": n} if isinstance(n, int) else {})})
        return out
    raise ValueError("Beatport hat keine Playlists geliefert – Details im Protokoll (Plugins › Beatport).")


def playlist_files(ctx, pid) -> dict:
    """Titel einer Beatport-Playlist als Einträge ohne Datei → {name, files: [], items, missing: 0}."""
    c = Client(ctx)
    name = f"Playlist {pid}"
    meta = None
    try:
        meta = c.get(f"/my/playlists/{pid}/")
    except HttpError as ex:
        ctx.log(f"/my/playlists/{pid}/: {ex}")
    if isinstance(meta, dict) and meta.get("name"):
        name = meta["name"]
    for path in PLAYLIST_TRACK_PATHS:
        path = path.format(id=pid)
        try:
            rows = _pages(c, path, 5000, ctx.log)
        except HttpError as ex:
            ctx.log(f"{path}: {ex}")
            continue
        rows.sort(key=lambda r: r.get("position") if isinstance(r.get("position"), int) else 10 ** 9)
        items = []
        for r in rows:
            t = r.get("track") if isinstance(r.get("track"), dict) else r
            if t.get("name"):
                items.append({"ref": track_ref(t)})
        return {"name": name, "files": [], "items": items, "missing": 0}
    raise ValueError(f"Beatport hat die Titel von „{name}“ nicht geliefert – Details im Protokoll (Plugins › Beatport).")


# =========================================================================== #334/#335: Playlists anlegen (schreibend)
# Nur auf Klick des Users und nur mit eingeschalteter Einstellung. Beatport v4 ist eine Django-REST-API: OPTIONS
# liefert die erlaubten Methoden und Felder, ohne etwas zu ändern – darauf stützt sich die Prüfung, bevor geschrieben
# wird. Verändert werden nur Playlists, deren Name mit OWN_PREFIX beginnt.
OWN_PREFIX = "TagStudio_"
PL_MAX = 100                       # Beatport lädt höchstens 100 Titel auf einmal herunter
SETTINGS_DEFAULT = {"playlists_write": False, "buy_prefix": "TagStudio_BUY_"}


def _settings_path(ctx):
    return os.path.join(ctx.data_dir, "settings.json")


def load_settings(ctx) -> dict:
    out = dict(SETTINGS_DEFAULT)
    try:
        with open(_settings_path(ctx), encoding="utf-8") as fh:
            d = json.load(fh)
        if isinstance(d, dict):
            out["playlists_write"] = bool(d.get("playlists_write", False))
            out["buy_prefix"] = clean_prefix(d.get("buy_prefix"))
    except (OSError, ValueError):
        pass
    return out


def clean_prefix(v) -> str:
    """Präfix für Playlists je Kaufdatum: muss mit „TagStudio_“ beginnen (sonst wird es vorangestellt)."""
    v = re.sub(r"[^\w\-]+", "_", str(v or "").strip())[:40] or SETTINGS_DEFAULT["buy_prefix"]
    return v if v.startswith(OWN_PREFIX) else OWN_PREFIX + v


def save_settings(ctx, opts) -> dict:
    cur = load_settings(ctx)
    d = {"playlists_write": bool(opts.get("playlists_write", cur["playlists_write"])),
         "buy_prefix": clean_prefix(opts.get("buy_prefix", cur["buy_prefix"]))}
    tmp = _settings_path(ctx) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh)
    os.replace(tmp, _settings_path(ctx))
    return d


def store_settings(ctx, update=None) -> dict:
    """Für die Seite „Käufe“: Einstellungen des Plugins (Schreiben an/aus, Präfix); update speichert Teile davon."""
    return save_settings(ctx, update) if isinstance(update, dict) and update else load_settings(ctx)


def _send(c, method, path, data=None):
    """Schreibende bzw. OPTIONS-Anfrage mit der Anmeldung → (Status, Antwort als JSON oder None)."""
    if c.tok["expires_at"] - 30 < time.time():
        c.tok = c._refresh() or c._expired()
    url = API + (path if path.startswith("/") else "/" + path)
    for attempt in range(3):
        st, h, body = request(method, url, headers={"Authorization": f"Bearer {c.tok['access_token']}"}, data=data)
        if st == 401 and attempt == 0:
            c.tok = c._refresh() or c._expired()
            continue
        if st == 429:
            time.sleep(_retry_after(h.get("Retry-After")))
            continue
        try:
            js = json.loads(body or b"null")
        except ValueError:
            js = None
        return st, js, h
    return 429, None, {}


def _allowed(c, path) -> tuple[set, dict]:
    """OPTIONS: erlaubte Methoden (Allow-Header bzw. DRF-„actions“) und Felder für POST/PUT."""
    st, js, h = _send(c, "OPTIONS", path)
    allow = {m.strip().upper() for m in str((h or {}).get("Allow") or (h or {}).get("allow") or "").split(",") if m.strip()}
    acts = js.get("actions") if isinstance(js, dict) and isinstance(js.get("actions"), dict) else {}
    allow |= {m.upper() for m in acts}
    return (allow if st and st < 400 else set()), acts


def _check(c, log=None) -> dict:
    """Schreibzugriff ermitteln (nichts wird geändert)."""
    out = {"create": False, "add": False, "remove": False, "delete": False, "name_field": "name",
           "tracks_field": "track_ids", "probe": ""}
    allow, acts = _allowed(c, "/my/playlists/")
    out["create"] = "POST" in allow
    fields = acts.get("POST") if isinstance(acts.get("POST"), dict) else {}
    if fields and "name" not in fields:
        out["name_field"] = next((k for k in fields if "name" in k), "name")
    mine = []
    try:
        mine = _pages(c, "/my/playlists/", 200)
    except HttpError:
        pass
    if mine:
        pid = mine[0].get("id")
        out["probe"] = str(mine[0].get("name") or pid)
        a2, acts2 = _allowed(c, f"/my/playlists/{pid}/tracks/bulk/")
        out["add"] = "POST" in a2
        f2 = acts2.get("POST") if isinstance(acts2.get("POST"), dict) else {}
        tf = next((k for k in f2 if "track" in k.lower()), "")
        if tf:
            out["tracks_field"] = tf
        a3, _ = _allowed(c, f"/my/playlists/{pid}/")
        out["delete"] = "DELETE" in a3
        items = []
        try:
            items = _items(c.get(f"/my/playlists/{pid}/tracks/", per_page=1))
        except HttpError:
            pass
        if items and isinstance(items[0], dict) and items[0].get("id") is not None:
            a4, _ = _allowed(c, f"/my/playlists/{pid}/tracks/{items[0]['id']}/")
            out["remove"] = "DELETE" in a4
        else:
            out["remove"] = out["add"]          # ohne Titel nicht prüfbar – wird beim Leeren erneut versucht
    if log:
        log(f"Schreibzugriff Playlists: {json.dumps(out, ensure_ascii=False)}")
    return out


def store_playlist_check(ctx) -> dict:
    """„Schreibzugriff prüfen“: was erlaubt Beatport für eigene Playlists? → {ok, text, …}"""
    ok, why = ready(ctx)
    if not ok:
        raise ValueError(f"Beatport: {why}.")
    c = Client(ctx)
    r = _check(c, ctx.log)
    yes = lambda b: "ja" if b else "nein"          # noqa: E731
    txt = (f"Playlist anlegen: {yes(r['create'])} · Titel hinzufügen: {yes(r['add'])} · Titel entfernen: "
           f"{yes(r['remove'])} · Playlist löschen: {yes(r['delete'])}")
    if not r["probe"]:
        txt += " (ohne eigene Playlist sind Hinzufügen/Löschen nicht prüfbar)"
    r.update(ok=r["create"] and (r["add"] or not r["probe"]), text=txt + ". " + scope_text(c.tok))
    return r


def _need_write(ctx) -> Client:
    ok, why = ready(ctx)
    if not ok:
        raise ValueError(f"Beatport: {why}.")
    if not load_settings(ctx)["playlists_write"]:
        raise ValueError("Playlists in Beatport sind ausgeschaltet – Plugins › Beatport › „Einstellungen …“ einschalten.")
    return Client(ctx)


def store_playlist_list(ctx, prefix=OWN_PREFIX) -> list:
    """Eigene Playlists, deren Name mit prefix beginnt → [{id, name, count, url}]."""
    c = Client(ctx)
    out = []
    for p in _pages(c, "/my/playlists/", 2000):
        name = str(p.get("name") or "")
        if p.get("id") is not None and name.startswith(prefix):
            n = p.get("track_count") or p.get("tracks_count") or p.get("count")
            out.append({"id": str(p["id"]), "name": name, "count": n if isinstance(n, int) else None,
                        "url": f"https://www.beatport.com/library/playlists/{p['id']}"})
    return out


def _track_ids(c, pid) -> dict:
    """Titel einer eigenen Playlist → {Beatport-Track-ID: Eintrags-ID}."""
    out = {}
    for r in _pages(c, f"/my/playlists/{pid}/tracks/", 5000):
        t = r.get("track") if isinstance(r.get("track"), dict) else r
        if t.get("id") is not None:
            out[str(t["id"])] = str(r.get("id") if isinstance(r.get("track"), dict) else t["id"])
    return out


def store_playlist_put(ctx, name, track_ids, replace=False) -> dict:
    """Playlist „name“ (muss mit TagStudio_ beginnen) anlegen bzw. wiederverwenden und die Titel eintragen.
    replace: Titel, die nicht (mehr) dazugehören, entfernen – sonst nur ergänzen. Nie mehr als PL_MAX neue auf einmal.
    → {id, name, url, added, removed, total, created, note}"""
    name = str(name or "")
    if not name.startswith(OWN_PREFIX):
        raise ValueError("TagStudio verändert nur Playlists, deren Name mit „TagStudio_“ beginnt.")
    c = _need_write(ctx)
    chk = getattr(ctx, "_bp_check", None) or _check(c, ctx.log)
    ctx._bp_check = chk
    want = [str(i) for i in dict.fromkeys(track_ids or []) if str(i).strip()]
    have_pl = next((p for p in store_playlist_list(ctx, name) if p["name"] == name), None)
    created = False
    if have_pl is None:
        if not chk["create"]:
            raise ValueError("Beatport erlaubt das Anlegen von Playlists über die API nicht (Schreibzugriff prüfen).")
        st, js, _h = _send(c, "POST", "/my/playlists/", {chk["name_field"]: name})
        if st >= 400 or not isinstance(js, dict) or js.get("id") is None:
            ctx.log(f"POST /my/playlists/: HTTP {st} {str(js)[:300]}")
            raise ValueError(f"Beatport hat die Playlist „{name}“ nicht angelegt (HTTP {st}) – Details im Protokoll.")
        pid, created, cur = str(js["id"]), True, {}
    else:
        pid = have_pl["id"]
        cur = _track_ids(c, pid)
    add = [i for i in want if i not in cur]
    removed, note = 0, ""
    if replace:
        drop = [entry for tid, entry in cur.items() if tid not in set(want)]
        for entry in drop:
            st, js, _h = _send(c, "DELETE", f"/my/playlists/{pid}/tracks/{entry}/")
            if st in (200, 202, 204):
                removed += 1
            else:
                note = f"Alte Titel konnten nicht entfernt werden (HTTP {st}) – bitte in Beatport leeren."
                ctx.log(f"DELETE /my/playlists/{pid}/tracks/{entry}/: HTTP {st}")
                break
    added = 0
    for k in range(0, len(add), PL_MAX):
        part = add[k:k + PL_MAX]
        body = {chk["tracks_field"]: [int(x) if x.isdigit() else x for x in part]}
        st, js, _h = _send(c, "POST", f"/my/playlists/{pid}/tracks/bulk/", body)
        if st >= 400:
            ctx.log(f"POST /my/playlists/{pid}/tracks/bulk/: HTTP {st} {str(js)[:300]}")
            raise ValueError(f"Beatport hat die Titel nicht in „{name}“ eingetragen (HTTP {st}) – Details im Protokoll.")
        added += len(part)
    ctx.log(f"Playlist {name} ({pid}): +{added} −{removed}{' (neu)' if created else ''}")
    return {"id": pid, "name": name, "url": f"https://www.beatport.com/library/playlists/{pid}", "added": added,
            "removed": removed, "total": len(want) if replace else len(cur) + added, "created": created, "note": note}


def store_playlist_delete(ctx, prefix) -> dict:
    """Playlists löschen, deren Name mit prefix beginnt (nur TagStudio_…; die Oberfläche fragt vorher).
    → {deleted: [Namen], failed: [Texte]}"""
    prefix = str(prefix or "")
    if not prefix.startswith(OWN_PREFIX):
        raise ValueError("TagStudio löscht nur Playlists, deren Name mit „TagStudio_“ beginnt.")
    c = _need_write(ctx)
    deleted, failed = [], []
    for p in store_playlist_list(ctx, prefix):
        st, _js, _h = _send(c, "DELETE", f"/my/playlists/{p['id']}/")
        if st in (200, 202, 204):
            deleted.append(p["name"])
        else:
            failed.append(f"{p['name']}: HTTP {st}")
            ctx.log(f"DELETE /my/playlists/{p['id']}/: HTTP {st}")
    return {"deleted": deleted, "failed": failed}


# =========================================================================== Abgleich
_MIX_RE = re.compile(r"\s*[\(\[]([^\)\]]*(mix|edit|remix|version|dub|rework|bootleg|vip)[^\)\]]*)[\)\]]\s*$", re.I)
_FEAT_RE = re.compile(r"\s*[\(\[]?\b(feat\.?|ft\.?|featuring)\b.*$", re.I)


def _retry_after(v) -> float:
    """Retry-After als Sekunden oder HTTP-Datum → Wartezeit (max. 30 s, sonst 5 s)."""
    try:
        return max(0.0, min(30.0, float(v)))
    except (TypeError, ValueError):
        pass
    try:
        import email.utils
        when = email.utils.parsedate_to_datetime(str(v)).timestamp()
        return max(0.0, min(30.0, when - time.time()))
    except (TypeError, ValueError, IndexError, OverflowError):
        return 5.0


def norm(s):
    """Für den Vergleich: Akzente weg, Kleinbuchstaben, nur Buchstaben/Ziffern. Nicht-lateinische Schrift
    (Kyrillisch, Japanisch …) bleibt erhalten – sonst würden zwei solche Titel als „gleich“ (leer) gelten."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    s = s.replace("ß", "ss").replace("&", " and ")
    s = re.sub(r"[\W_]+", " ", s)
    return " ".join(s.split())


def split_title(title):
    """'Song (Extended Mix)' → ('Song', 'Extended Mix')."""
    m = _MIX_RE.search(title or "")
    if m:
        return title[:m.start()].strip(), m.group(1).strip()
    return (title or "").strip(), ""


def file_info(f):
    title, artist = f.text("TIT2"), f.text("TPE1")
    if not title:
        base = os.path.splitext(os.path.basename(f.path))[0]
        base = re.sub(r"^\d+[\s._-]+", "", base)
        if " - " in base:
            a, t = base.split(" - ", 1)
            artist, title = artist or a, t
        else:
            title = base
    name, mix = split_title(title)
    return {"title": name, "mix": mix, "artist": artist.replace(MV, ", "), "isrc": f.text("TSRC").strip().upper(),
            "duration": float(getattr(f, "duration", 0) or 0), "bpid": f.text("TXXX:BEATPORT_TRACK_ID").strip()}


def artists_of(t, key="artists"):
    return [a.get("name", "") for a in (t.get(key) or []) if isinstance(a, dict)]


def score(info, t):
    """0–1: wie gut passt Beatport-Titel t zur Datei?"""
    if info["isrc"] and (t.get("isrc") or "").upper() == info["isrc"]:
        return 1.0
    a, b = norm(_FEAT_RE.sub("", info["title"])), norm(_FEAT_RE.sub("", t.get("name", "")))
    ts = difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0   # leer = unbekannt, nicht „gleich“
    fa = norm(_FEAT_RE.sub("", info["artist"]))
    cand = [norm(a) for a in artists_of(t)] + [norm(", ".join(artists_of(t)))]
    as_ = max([difflib.SequenceMatcher(None, fa, c).ratio() for c in cand] + [0.0]) if fa else 0.5
    if fa and any(c and (c in fa or fa in c) for c in cand[:-1]):
        as_ = max(as_, 0.9)
    parts = [(ts, 0.5), (as_, 0.3)]
    length = (t.get("length_ms") or 0) / 1000
    if info["duration"] and length:
        d = abs(info["duration"] - length)
        parts.append((1.0 if d <= 3 else 0.7 if d <= 8 else 0.3 if d <= 20 else 0.0, 0.2))
    s = sum(v * w for v, w in parts) / sum(w for _v, w in parts)
    mix = norm(t.get("mix_name", ""))
    if info["mix"]:
        s += 0.05 if norm(info["mix"]) == mix else -0.05
    if fa and as_ < 0.5:          # anderer Künstler: gleicher Titel reicht nicht
        s *= 0.6
    if ts < 0.6:                  # anderer Titel: Künstler allein reicht nicht
        s *= 0.6
    return max(0.0, min(1.0, s))


def best_match(client, info):
    if info["bpid"].isdigit():
        t = client.track(info["bpid"])
        if t:
            return t, 1.0, "über gespeicherte Beatport-ID"
    cands = []
    if info["isrc"]:
        cands = client.by_isrc(info["isrc"])
    if not cands:
        q = " ".join(x for x in (_FEAT_RE.sub("", info["artist"]).split(",")[0], info["title"], info["mix"]) if x)
        cands = client.search_tracks(q)
        if not cands and info["mix"]:
            cands = client.search_tracks(f"{info['artist']} {info['title']}")
    if not cands:
        return None, 0.0, ""
    scored = sorted(((score(info, t), t) for t in cands), key=lambda x: -x[0])
    s, t = scored[0]
    if s >= MAYBE and t.get("id") and not (t.get("release") or {}).get("label"):
        full = client.track(t["id"])     # Suchergebnisse sind gekürzt – vollen Datensatz holen
        t = full or t
    return t, s, ""


# =========================================================================== #204: Integration
def api_request(ctx, ep, params):
    """API-Tester: GET mit dem eigenen Token (bei Bedarf erneuert). Der Token wird in der Anzeige geschwärzt."""
    import services
    cl = Client(ctx)
    if cl.tok["expires_at"] - 30 < time.time():
        cl.tok = refresh(ctx, cl.tok) or cl._expired()
    url = services.build_url({"base": API}, ep, params)
    st, h, body = request("GET", url, headers={"Authorization": f"Bearer {cl.tok['access_token']}"})
    if st == 401:
        cl.tok = refresh(ctx, cl.tok) or cl._expired()
        st, h, body = request("GET", url, headers={"Authorization": f"Bearer {cl.tok['access_token']}"})
    ctx.secrets = [cl.tok.get("access_token"), cl.tok.get("refresh_token")]
    return st, h, body, url


def access_info(ctx) -> str:
    """#297: Text für „Zugriff prüfen“ – mit welchem Zugang und welchem Scope geprüft wird."""
    c = Client(ctx)
    return f"{'eigener API-Zugang' if c.tok.get('app') else 'Ausweichweg'} – {scope_text(c.tok)}"


def test_query(ctx, info):
    """Testabfrage ohne Track: wie „Beatport-Daten holen“ – zuerst ISRC, sonst Suche Künstler + Titel + Mix."""
    cl = Client(ctx)
    cands = cl.by_isrc(info["isrc"]) if info.get("isrc") else []
    ctx.log(f"ISRC {info['isrc']}: {len(cands)} Treffer" if info.get("isrc") else "ohne ISRC")
    if not cands:
        q = " ".join(x for x in (_FEAT_RE.sub("", info["artist"]).split(",")[0], info["title"], info["mix"]) if x)
        cands = cl.search_tracks(q, n=10)
        ctx.log(f"Suche „{q}“: {len(cands)} Treffer")
    out = []
    for t in cands:
        rel = t.get("release") or {}
        out.append({"_raw": t, "source_name": "Beatport", "id": t.get("id"), "title": t.get("name") or "",
                    "mix": t.get("mix_name") or "", "artists": artists_of(t), "album": rel.get("name") or "",
                    "label": (rel.get("label") or {}).get("name") or "", "isrc": t.get("isrc") or "",
                    "date": t.get("publish_date") or t.get("new_release_date") or "",
                    "length": (t.get("length_ms") or 0) / 1000 or None,
                    "url": f"https://www.beatport.com/track/{t.get('slug') or 'x'}/{t.get('id')}" if t.get("id") else "",
                    "extra": " · ".join(x for x in (f"{t['bpm']} BPM" if t.get("bpm") else "",
                                                    (t.get("key") or {}).get("name") or "",
                                                    (t.get("genre") or {}).get("name") or "") if x)})
    return out


def test_score(info, c):
    return score({**info, "bpid": ""}, c["_raw"])


# =========================================================================== Felder
def key_text(t, notation):
    import keys
    k = t.get("key") or {}
    code = None
    if k.get("camelot_number") and k.get("camelot_letter"):
        code = f"{int(k['camelot_number'])}{str(k['camelot_letter']).upper()}"
    if not code and k.get("name"):
        code = keys.parse_key(k["name"].replace("♯", "#").replace("♭", "b"))
    return keys.format_key(code, notation) if code else ""


def genre_text(t, mode):
    main = (t.get("genre") or {}).get("name", "") if isinstance(t.get("genre"), dict) else ""
    sub = (t.get("sub_genre") or {}).get("name", "") if isinstance(t.get("sub_genre"), dict) else ""
    if mode == "main":
        return main
    if mode == "both":
        return "; ".join(x for x in (main, sub) if x)
    return sub or main


def cover_url(t, size=1400):
    img = ((t.get("release") or {}).get("image") or {})
    dyn = img.get("dynamic_uri")
    if dyn and "{w}" in dyn:
        return dyn.format(w=size, h=size)
    return img.get("uri")


def same_value(key, old, new):
    """Gleicher Inhalt trotz anderer Schreibweise? (Tonart 8A = Am, BPM 124 = 124.0, Jahr 2021 = 2021-05-14 …)"""
    o, n = (old or "").strip(), (new or "").strip()
    if o.lower() == n.lower():
        return True
    if key == "TKEY":
        import keys
        return bool(keys.parse_key(o)) and keys.parse_key(o) == keys.parse_key(n)
    if key == "TBPM":
        try:
            return round(float(o.replace(",", "."))) == round(float(n))
        except ValueError:
            return False
    if key == "TDRC":
        return len(n) == 4 and o[:4] == n
    if key in ("TPE1", "TPE4"):
        return norm(o) == norm(n)
    return False


def proposals_for(ctx, f, t, opts, note, checked, notation, group, stats):
    """Alle Felder, die Beatport liefert, in die Vorschau – auch gleiche und abgewählte.
    Angehakt wird nur, was nach den Optionen übernommen werden soll."""
    mode = opts.get("mode", "missing")
    empty_only = mode in ("empty", "missing")
    hide_existing = mode == "missing"                    # #142: vorhandene Felder gar nicht erst zeigen
    lk = {"link": f"https://www.beatport.com/track/{t.get('slug') or 'track'}/{t['id']}" if t.get("id") else "",
          "link_label": "Beatport"}                      # #144: Treffer auf Beatport ansehen

    def prop(key, val, label, wanted=True):
        val = "" if val is None else str(val).strip()
        if not val:
            stats["missing"].add(label)
            return
        cur = f.text(key).strip()
        if cur and hide_existing:                        # #142: schon vorhanden → nicht anfassen, nicht zeigen
            stats["same" if cur == val else "filled"] += 1
            return
        if cur == val:                                   # identisch: nur anzeigen
            stats["same"] += 1
            ctx.propose(f, key, val, label, note=note, checked=False, group=group, **lk, hint="gleich", show_same=True)
            return
        if not wanted:                                   # in den Optionen abgewählt: zeigen, nicht anhaken
            stats["off"] += 1
            ctx.propose(f, key, val, label, note=note, checked=False, group=group, **lk,
                        hint="in den Optionen abgewählt – bei Bedarf anhaken")
            return
        if cur and same_value(key, cur, val):            # gleicher Wert, andere Schreibweise
            stats["same"] += 1
            ctx.propose(f, key, val, label, note=note, checked=False, group=group, **lk,
                        hint="gleicher Wert, andere Schreibweise")
            return
        if cur and empty_only:      # gefüllt: zeigen, aber nicht vorauswählen
            stats["filled"] += 1
            ctx.propose(f, key, val, label, note=note, checked=False, group=group, **lk,
                        hint="schon gefüllt – nur bei Bedarf anhaken")
            return
        ctx.propose(f, key, val, label, note=note, checked=checked, group=group, **lk)

    if t.get("bpm"):
        prop("TBPM", int(round(float(t["bpm"]))), "BPM", opts.get("bpm"))
    prop("TKEY", key_text(t, notation), "Tonart", opts.get("key"))
    prop("TCON", genre_text(t, opts.get("genre_mode", "sub")), "Genre", opts.get("genre"))
    rel = t.get("release") or {}
    prop("TPUB", (rel.get("label") or {}).get("name", ""), "Label", opts.get("label"))
    prop("TXXX:CATALOGNUMBER", t.get("catalog_number") or rel.get("catalog_number") or "", "Katalognummer", opts.get("label"))
    date = t.get("publish_date") or t.get("new_release_date") or rel.get("new_release_date") or ""
    dmode = opts.get("date", "year")
    if dmode == "full" and re.match(r"\d{4}-\d{2}-\d{2}", date):
        prop("TDRC", date[:10], "Datum")
    elif date[:4].isdigit():
        prop("TDRC", date[:4], "Jahr", dmode != "no")
    prop("TSRC", (t.get("isrc") or "").upper(), "ISRC", opts.get("isrc"))
    prop("TPE4", ", ".join(artists_of(t, "remixers")), "Remixer", opts.get("remixer"))
    mix = t.get("mix_name") or ""
    names = bool(opts.get("names"))
    prop("TIT2", f"{t.get('name', '')} ({mix})" if mix else t.get("name", ""), "Titel", names)
    prop("TPE1", ", ".join(artists_of(t)), "Künstler", names)
    prop("TALB", rel.get("name", ""), "Album", names)
    if t.get("id"):
        prop("TXXX:BEATPORT_TRACK_ID", t["id"], "Beatport-ID", opts.get("ids"))
    cov = opts.get("cover", "missing")
    has = f.get("APIC:3") is not None
    url = cover_url(t)
    if url and cov != "no" and (cov == "replace" or not has):
        try:
            st, _h, data = request("GET", url)
            if st == 200 and data[:3] in (b"\xff\xd8\xff", b"\x89PN"):
                ctx.propose(f, "APIC:3", "Cover von Beatport (1400 px)", "Cover", note=note,
                            checked=checked and not has, kind="cover", data=data, group=group,
                            hint="ersetzt vorhandenes Cover" if has else "")
        except HttpError as ex:
            ctx.log(f"Cover für {os.path.basename(f.path)} nicht geladen: {ex}")
    elif url:                       # Cover geliefert, aber nicht geladen: als Info zeigen
        ctx.propose(f, "APIC:3", "Beatport-Cover verfügbar (1400 px)", "Cover", note=note, checked=False, kind="cover",
                    data=None, group=group,
                    hint="Datei hat schon ein Cover – Option Cover → „Ersetzen“ lädt es" if has
                    else "Option Cover → „Nur wenn keins vorhanden“ lädt es")


# =========================================================================== Aktionen
def status(ctx):
    tok = load_token(ctx)
    if not tok:
        return "Nicht angemeldet."
    who = tok.get("username") or "Beatport-Konto"
    left = tok.get("expires_at", 0) - time.time()
    if tok.get("app"):
        return f"Angemeldet als {who} (eigener API-Zugang)." if left > 0 else \
            f"Angemeldet als {who} (eigener API-Zugang, Token abgelaufen – wird bei Bedarf erneuert)."
    return f"Angemeldet als {who} (inoffizieller Ausweichweg)." if left > 0 else \
        f"Angemeldet als {who} (inoffizieller Ausweichweg, Token abgelaufen – wird bei Bedarf erneuert)."


def _notation():
    try:
        import core
        return core.load_config().get("key_notation", "camelot")
    except Exception:  # noqa: BLE001
        return "camelot"


def run(action, ctx, files, opts):
    if action == "logout":
        tok = load_token(ctx)
        revoked = revoke(ctx, tok) if tok else False
        had = delete_token(ctx)
        forgot = bool(opts.get("forget_app")) and delete_app(ctx)
        if not had:
            msg = "Es war kein Token gespeichert – Client-ID und Secret gelöscht." if forgot else "Es war kein Token gespeichert."
        elif revoked:
            msg = ("Abgemeldet – Token bei Beatport zurückgezogen und gelöscht, Client-ID und Secret ebenfalls gelöscht."
                   if forgot else "Abgemeldet – Token bei Beatport zurückgezogen und gelöscht.")
        else:
            msg = "Abgemeldet – Token, Client-ID und Secret gelöscht." if forgot else "Abgemeldet – Token gelöscht."
        return {"message": msg}
    if action == "login":
        ctx.status("Melde bei Beatport an …")
        if opts.get("method") == "token":
            if not opts.get("token", "").strip():
                raise ValueError("Bitte den Token (JSON) einfügen.")
            try:
                tok = _norm_token(opts["token"].strip())
            except (ValueError, KeyError, TypeError) as ex:
                raise ValueError("Das ist kein gültiger Token – erwartet wird die JSON-Antwort mit „access_token“.") from ex
        elif opts.get("method") == "app":
            app = load_app(ctx) or {}
            cid = str(opts.get("client_id") or "").strip() or app.get("client_id", "")
            secret = str(opts.get("client_secret") or "").strip() or app.get("client_secret", "")
            if not cid or not secret:
                raise ValueError("Bitte Client-ID und Client-Secret deiner Beatport-App eingeben.")
            if not opts.get("username") or not opts.get("password"):
                raise ValueError("Bitte Benutzername und Passwort eingeben.")
            tok = login_app(ctx, cid, secret, opts["username"].strip(), opts["password"])
            save_app(ctx, cid, secret)
        else:
            if not opts.get("username") or not opts.get("password"):
                raise ValueError("Bitte Benutzername und Passwort eingeben.")
            tok = login(ctx, opts["username"].strip(), opts["password"])
        save_token(ctx, tok)
        acc = account(Client(ctx))
        tok["username"] = acc.get("username") or tok.get("username", "")
        save_token(ctx, tok)
        who = tok["username"] or "Beatport-Konto"
        ctx.log(f"Anmeldung als {who} ({'eigener API-Zugang' if tok.get('app') else 'Ausweichweg'}) – {scope_text(tok)}")
        if tok.get("app"):
            return {"message": f"Angemeldet als {who} über deinen eigenen API-Zugang. Das Passwort wurde nicht gespeichert. {scope_text(tok)}."}
        return {"message": f"Angemeldet als {who}. Das Passwort wurde nicht gespeichert. {scope_text(tok)}."}
    if action == "test":
        c = Client(ctx)
        acc = account(c)
        ctx.log(scope_text(c.tok))
        return {"message": f"Verbindung in Ordnung – angemeldet als {acc.get('username', '?')}. {scope_text(c.tok)}."}
    if action == "follow":
        return run_follow(ctx, opts)
    if action == "purchases":
        return run_purchases(ctx, opts)
    if action == "download":
        return run_download(ctx, opts)
    if action == "settings":
        s = save_settings(ctx, opts)
        return {"message": ("Playlists in Beatport: eingeschaltet." if s["playlists_write"] else
                            "Playlists in Beatport: ausgeschaltet.") + f" Präfix: {s['buy_prefix']}"}
    if action == "write_check":
        r = store_playlist_check(ctx)
        return {"message": r["text"]}
    if action != "fetch":
        raise ValueError(f"Unbekannte Aktion: {action}")

    client = Client(ctx)
    notation = _notation()
    found = unsure = missing = 0
    tot_same = tot_filled = tot_off = 0
    for i, f in enumerate(files):
        name = os.path.basename(f.path)
        ctx.progress(i, len(files), f"Suche {name}")
        info = file_info(f)
        if not info["title"]:
            ctx.log(f"{name}: kein Titel – übersprungen")
            missing += 1
            continue
        try:
            t, s, how = best_match(client, info)
        except HttpError as ex:
            if ex.status in (0, 429):
                raise RuntimeError(str(ex)) from ex
            ctx.log(f"{name}: {ex}")
            missing += 1
            continue
        if not t or s < MAYBE:
            missing += 1
            ctx.log(f"{name}: nicht gefunden" + (f" (bester Kandidat nur {round(s * 100)} %)" if t else ""))
            continue
        sure = s >= SURE
        found += sure
        unsure += not sure
        hit = f"{', '.join(artists_of(t))} – {t.get('name', '')}" + (f" ({t['mix_name']})" if t.get("mix_name") else "")
        note = f"{hit} · {round(s * 100)} %" + (f" · {how}" if how else "") + ("" if sure else " · unsicher")
        before = len(ctx.proposals)
        stats = {"same": 0, "filled": 0, "off": 0, "missing": set()}
        proposals_for(ctx, f, t, opts, note, sure, notation, name, stats)
        tot_same += stats["same"]
        tot_filled += stats["filled"]
        tot_off += stats["off"]
        ctx.log(f"{name}: {hit} ({round(s * 100)} %) – Beatport liefert "
                + ", ".join(_present(t)) + (f"; ohne Wert: {', '.join(sorted(stats['missing']))}" if stats["missing"] else "")
                + f"; {stats['same']} gleich, {sum(1 for p in ctx.proposals[before:] if not p['same'])} Vorschlag/Vorschläge")
    ctx.progress(len(files), len(files), "fertig")
    msg = f"{found} sicher gefunden"
    if unsure:
        msg += f", {unsure} unsicher (nicht vorausgewählt)"
    if missing:
        msg += f", {missing} nicht gefunden"
    n = sum(1 for p in ctx.proposals if p["checked"])
    m = sum(1 for p in ctx.proposals if not p["same"])
    extra = ""
    hidden = opts.get("mode", "missing") == "missing"
    if tot_same:
        extra += f" {tot_same} Feld(er) stimmen bereits überein" + ("." if hidden else " (grau).")
    if tot_filled:
        extra += (f" {tot_filled} schon vorhandene Feld(er) bleiben unverändert (ausgeblendet)." if hidden else
                  f" {tot_filled} schon gefüllte Feld(er) mit anderem Wert sind gelistet, aber nicht angehakt.")
    if tot_off:
        extra += f" {tot_off} in den Optionen abgewählte Feld(er) sind gelistet, aber nicht angehakt."
    if not ctx.proposals:
        return {"message": f"{msg}. Beatport hat keine Felder geliefert."}
    return {"message": f"{msg}. {m} mögliche Änderung(en), {n} vorausgewählt." + extra}


# =========================================================================== #117 Käufe abgleichen
PURCHASE_PATHS = ["/my/downloads/"]          # offizielle Doku: /v4/my/downloads/ (kein /my/library/, #285)


def purchases(client, limit=2000, log=None, **filters):
    """Gekaufte Titel des Kontos (Machbarkeit: mehrere bekannte Pfade der inoffiziellen API v4 probieren)."""
    for path in PURCHASE_PATHS:
        out, page = [], 1
        try:
            while len(out) < limit:
                res = client.get(path, page=page, per_page=100, **filters)
                if res is None:
                    break
                items = res if isinstance(res, list) else (res.get("results") or res.get("tracks") or []) \
                    if isinstance(res, dict) else []
                if not items:
                    break
                for it in items:
                    t = it.get("track") if isinstance(it, dict) and isinstance(it.get("track"), dict) else it
                    if isinstance(t, dict) and t.get("id"):
                        if t is not it:                       # #285: Angaben der Bestellung (Kaufdatum) mitnehmen
                            t = {**t, "_order": {k: v for k, v in it.items() if k != "track" and not isinstance(v, (dict, list))}}
                        out.append(t)
                if log and page == 1:
                    log(f"{path}: Felder je Eintrag: {', '.join(sorted(items[0].keys())) if isinstance(items[0], dict) else type(items[0]).__name__}")
                if len(items) < 100:
                    break
                page += 1
        except HttpError as ex:
            if log:
                log(f"{path}: {ex}")
            continue
        if out:
            return path, out[:limit]
    return "", []


def _local_index(folders, ctx):
    import core
    by_id, by_isrc, by_name = {}, {}, {}
    n = 0
    for folder in folders:
        if not os.path.isdir(folder):
            ctx.log(f"Ordner nicht gefunden: {folder}")
            continue
        files, _e = core.load_files(folder, True, None, None, None, True)
        for f in files:
            n += 1
            tid = f.text("TXXX:BEATPORT_TRACK_ID").strip()
            if tid:
                by_id[tid] = f.path
            if f.text("TSRC").strip():
                by_isrc[f.text("TSRC").strip().upper()] = f.path
            info = file_info(f)
            by_name[(norm(info["artist"]), norm(info["title"]), norm(info.get("mix") or ""))] = f.path
    return by_id, by_isrc, by_name, n


def run_purchases(ctx, opts):
    client = Client(ctx)
    ctx.status("Lese gekaufte Titel …")
    path, items = purchases(client, int(opts.get("max") or 2000), ctx.log)
    if not items:
        return {"message": "Keine gekauften Titel über die bekannten Schnittstellen gefunden – Details im Protokoll "
                           "(bitte an Claude weitergeben, #117)."}
    bought = 0
    try:                                     # #162: Käufe in „Entdecken“ als gekauft markieren
        import discover
        bought = discover.mark_bought(items)
    except Exception as ex:  # noqa: BLE001
        ctx.log(f"Entdecken: {ex}")
    folders = [x.strip() for x in str(opts.get("folders") or "").splitlines() if x.strip()]
    by_id, by_isrc, by_name, nloc = _local_index(folders, ctx) if folders else ({}, {}, {}, 0)
    rows, have = [], 0
    for t in items:
        artist = ", ".join(artists_of(t))
        mix = t.get("mix_name") or ""
        hit = by_id.get(str(t.get("id"))) or by_isrc.get(str(t.get("isrc") or "").upper()) \
            or by_name.get((norm(artist), norm(t.get("name", "")), norm(mix)))
        have += bool(hit)
        rows.append([str(t.get("id")), artist, t.get("name", ""), mix, t.get("isrc") or "",
                     (t.get("release") or {}).get("name", ""), "vorhanden" if hit else "fehlt", hit or ""])
    import csv
    out = os.path.join(ctx.data_dir, "gekaufte-titel.csv")
    with open(out, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["Beatport-ID", "Künstler", "Titel", "Mix", "ISRC", "Release", "Status", "Datei"])
        w.writerows(rows)
    ctx.output(out)
    return {"message": f"{len(items)} gekaufte Titel gelesen ({path}); {have} vorhanden, {len(items) - have} fehlen"
                       + (f" (verglichen mit {nloc} Dateien)" if folders else " (kein Ordner zum Abgleich angegeben)")
                       + ". Liste als CSV gespeichert."
                       + (f" In „Entdecken“ {bought} Titel als gekauft markiert." if bought else "")}


def _present(t):
    """Welche Felder hat Beatport für diesen Titel geliefert? (fürs Protokoll)"""
    rel = t.get("release") or {}
    out = []
    for lab, ok in (("BPM", t.get("bpm")), ("Tonart", (t.get("key") or {}).get("name")), ("Genre", t.get("genre")),
                    ("Subgenre", t.get("sub_genre")), ("Label", (rel.get("label") or {}).get("name")),
                    ("Katalognr.", t.get("catalog_number") or rel.get("catalog_number")),
                    ("Datum", t.get("publish_date") or t.get("new_release_date")), ("ISRC", t.get("isrc")),
                    ("Remixer", t.get("remixers")), ("Cover", (rel.get("image") or {}).get("uri"))):
        if ok:
            out.append(lab)
    return out or ["nichts"]


# =========================================================================== Download gekaufter Titel (#117)
from plugins import Cancelled  # noqa: E402 – Abbruch wie bei ctx.check_cancel()
EXT = {"mp3": ".mp3", "aiff": ".aiff", "aif": ".aiff", "wav": ".wav", "flac": ".flac", "aac": ".m4a", "m4a": ".m4a"}
AUDIO_TYPES = ("audio/", "application/octet-stream", "application/zip", "application/x-zip", "binary/octet-stream")


_SKIP_KEYS = ("sample", "image", "preview", "artist", "release", "label", "genre", "key", "remixer")


def _usable(u) -> bool:
    """Kandidat für eine Download-Adresse? Keine API-Links, Vorhör-Ausschnitte, Bilder oder Webseiten von Titeln."""
    if not isinstance(u, str) or not u.startswith("https://"):
        return False
    low = u.lower()
    return "/v4/" not in low and not any(x in low for x in ("sample", "image", "/track/", "/release/", "/artist/"))


def _find_url(obj, depth=0):
    """Download-Adresse in einer JSON-Antwort (Schlüssel wie location/download_url/url), ohne Vorhör-Ausschnitte."""
    if depth > 4:
        return ""
    if isinstance(obj, str):
        return obj if _usable(obj) else ""
    if isinstance(obj, dict):
        for k in ("location", "download_url", "download", "url", "link", "href"):
            if _usable(obj.get(k)):
                return obj[k]
        for k, v in obj.items():
            if any(x in str(k).lower() for x in _SKIP_KEYS):
                continue
            u = _find_url(v, depth + 1)
            if u:
                return u
    if isinstance(obj, list):
        for v in obj[:5]:
            u = _find_url(v, depth + 1)
            if u:
                return u
    return ""


def _fmt_key(t) -> str:
    af = t.get("audio_format")
    if isinstance(af, dict):
        af = af.get("name") or af.get("format") or af.get("id") or ""
    return str(af or "mp3").lower()


def download_candidates(t) -> list[tuple[str, dict]]:
    """Mögliche Wege zur Download-Adresse (inoffiziell, Reihenfolge = Wahrscheinlichkeit). Zuerst der Weg der
    Beatport-Webseite (#292, beobachtet 25.10.2026): GET /catalog/tracks/purchase-download/?order_item_download_id=…
    mit dem Token → signierte Adresse der Datei. order_item_download_id steht offiziell in /my/downloads/."""
    odid, tid, fmt = t.get("order_item_download_id"), t.get("id"), _fmt_key(t)
    out = []
    if odid:
        out += [("/catalog/tracks/purchase-download/", {"order_item_download_id": odid}),(f"/my/downloads/{odid}/", {}), (f"/my/downloads/{odid}/download/", {})]
    if tid:
        out += [(f"/catalog/tracks/{tid}/download/", {"quality": fmt})]
    return out


# ---- #295: Sitzungs-Anmeldung für den Download – wie die Webseite, Token nur im Speicher (nie auf Platte)
_SESSION: dict = {}


class SessionClient(Client):
    """Client mit dem Token der Sitzungs-Anmeldung: erneuert nur im Speicher, löscht beim Ablauf nur die Sitzung."""

    def __init__(self, ctx, tok):            # noqa: D107 – bewusst ohne load_token
        self.ctx = ctx
        self.tok = tok
        self.session = True

    def _refresh(self):
        new = refresh(self.ctx, self.tok, save=False)
        if new:
            _SESSION["tok"] = new
        return new

    def _expired(self):
        _SESSION.clear()
        raise RuntimeError("Die Sitzungs-Anmeldung bei Beatport ist abgelaufen – beim Herunterladen erneut anmelden.")


def store_login(ctx, username, password) -> dict:
    """Anmelden nur für diese Sitzung (Ablauf wie die Beatport-Webseite: Anmeldung → Code → Token). Das Passwort wird
    nicht gespeichert, der Token nur im Speicher gehalten – nach dem Beenden von TagStudio ist er weg."""
    username, password = str(username or "").strip(), str(password or "")
    if not username or not password:
        raise ValueError("Benutzername und Passwort angeben.")
    tok = login(ctx, username, password)
    _SESSION.clear()
    _SESSION["tok"] = tok
    ctx.log(f"Sitzungs-Anmeldung als {tok.get('username') or username} – nur für diese Sitzung, nichts gespeichert. {scope_text(tok)}")
    return {"ok": True, "username": tok.get("username") or username}


def store_logout(ctx) -> dict:
    _SESSION.clear()
    return {"ok": True}


def store_session(ctx) -> dict:
    tok = _SESSION.get("tok") or {}
    return {"active": bool(tok), "username": tok.get("username", "")}


def resolve_download(client, t, log, seen=None) -> str:
    """Download-Adresse ermitteln; jeder Versuch wird mit Status und Feldnamen protokolliert (ohne Token).
    seen["denied"] = True, wenn Beatport den Token für den Download-Weg der Webseite ablehnt (401/403)."""
    for path, params in download_candidates(t):
        url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
        st, h, body = request("GET", url, headers={"Authorization": f"Bearer {client.tok['access_token']}"}, follow=False)
        if seen is not None and st in (401, 403) and path == "/catalog/tracks/purchase-download/":
            seen["denied"] = True
        if st in (301, 302, 303, 307, 308) and h.get("Location", h.get("location", "")).startswith("https://"):
            log(f"{path}: HTTP {st} → Weiterleitung")
            return h.get("Location") or h.get("location")
        ctype = (h.get("Content-Type") or h.get("content-type") or "").lower()
        data = None
        if st == 200 and ("json" in ctype or (body or b"").lstrip()[:1] in (b"{", b"[")):
            try:
                data = json.loads(body or b"null")
            except ValueError:
                data = None
        if st == 200 and data is not None:
            u = _find_url(data)
            keys = ", ".join(sorted(data.keys())) if isinstance(data, dict) else type(data).__name__
            log(f"{path}: HTTP 200, Felder: {keys}" + (" → Adresse gefunden" if u else ""))
            if u:
                return u
        else:
            log(f"{path}: HTTP {st}{' ' + ctype if ctype else ''}")
    return ""


def _safe(s):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(s or "")).strip().rstrip(".")[:150]


def target_name(t, ext) -> str:
    title = t.get("name") or "Titel"
    mix = t.get("mix_name")
    return _safe(f"{', '.join(artists_of(t)) or 'Unbekannt'} - {title}{f' ({mix})' if mix else ''}") + ext


def fetch_file(url, dest_dir, t, client, cancel=None) -> list[str]:
    """Datei laden (signierte Adresse ohne Anmeldung; bei 401/403 mit Token nur für beatport.com) und unverändert
    ablegen. ZIP: enthaltene Audiodateien entpacken. → abgelegte Pfade"""
    import shutil
    import tempfile
    import zipfile
    host = urllib.parse.urlparse(url).hostname or ""

    def open_url(auth):
        h = {"User-Agent": USER_AGENT}
        req = urllib.request.Request(url, headers=h)
        if auth and (host == "beatport.com" or host.endswith(".beatport.com")):
            # nur für die erste Adresse – eine Weiterleitung (z. B. CDN) bekommt den Token nicht
            req.add_unredirected_header("Authorization", f"Bearer {client.tok['access_token']}")
        return _urlopen(req, 120)

    try:
        r = open_url(False)
    except urllib.error.HTTPError as e:
        if e.code not in (401, 403):
            raise HttpError(e.code, f"Download: HTTP {e.code}") from e
        r = open_url(True)
    ctype = (r.headers.get("Content-Type") or "").lower()
    if not any(ctype.startswith(a) for a in AUDIO_TYPES):
        r.close()
        raise HttpError(0, f"Download liefert keine Audiodatei ({ctype or 'ohne Typ'}).")
    cd = r.headers.get("Content-Disposition") or ""
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd)
    name = _safe(urllib.parse.unquote(m.group(1))) if m else ""
    os.makedirs(dest_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".part", dir=dest_dir)
    try:
        with os.fdopen(fd, "wb") as out, r:
            while True:
                if cancel is not None and cancel():
                    raise Cancelled()
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                out.write(chunk)
        if zipfile.is_zipfile(tmp):
            got = []
            with zipfile.ZipFile(tmp) as z:
                for zi in z.infolist():
                    base = os.path.basename(zi.filename)
                    if zi.is_dir() or base.startswith(".") or os.path.splitext(base)[1].lower() not in EXT.values():
                        continue
                    if zi.file_size > MAX_ZIP_MEMBER:
                        raise HttpError(0, f"Download: {base} ist unerwartet gross – nicht entpackt.")
                    dst = _unique(os.path.join(dest_dir, _safe(base)))
                    part = dst + ".part"
                    try:
                        with z.open(zi) as src, open(part, "wb") as fh:
                            shutil.copyfileobj(src, fh)
                        os.replace(part, dst)               # erst vollständig unter dem richtigen Namen
                    finally:
                        if os.path.exists(part):
                            os.remove(part)
                    got.append(dst)
            return got
        ext = os.path.splitext(name)[1].lower() if name else ""
        if ext not in EXT.values():
            ext = EXT.get(_fmt_key(t).split("-")[0].split(" ")[0], ".mp3")
        dst = _unique(os.path.join(dest_dir, name if name and name.lower().endswith(ext) else target_name(t, ext)))
        os.replace(tmp, dst)
        tmp = ""
        return [dst]
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)


MAX_ZIP_MEMBER = 2 << 30                               # 2 GB je Audiodatei im ZIP


def _urlopen(req, timeout):
    """Datei-Download (in Tests ersetzbar)."""
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 – Adresse stammt von Beatport


def _unique(path):
    stem, ext = os.path.splitext(path)
    k, cand = 1, path
    while os.path.exists(cand):
        k += 1
        cand = f"{stem} ({k}){ext}"
    return cand


def _done_path(ctx):
    return os.path.join(ctx.data_dir, "geladen.json")


def _save_done(ctx, done: dict):
    """Liste der geladenen Käufe atomar schreiben (ein Abbruch darf sie nicht leeren)."""
    path = _done_path(ctx)
    with open(path + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(done, fh, ensure_ascii=False, indent=1)
    os.replace(path + ".tmp", path)


def run_download(ctx, opts):
    dest = str(opts.get("dest") or "").strip()
    if not dest or not os.path.isdir(dest):
        raise RuntimeError("Bitte einen vorhandenen Zielordner wählen (z. B. den Eingangsordner von „Vorbereiten“).")
    client = Client(ctx)
    ctx.status("Lese gekaufte Titel …")
    path, items = purchases(client, 5000, ctx.log)
    if not items:
        return {"message": "Keine gekauften Titel gefunden – Details im Protokoll."}
    try:
        with open(_done_path(ctx), encoding="utf-8") as fh:
            done = json.load(fh)
    except (OSError, ValueError):
        done = {}
    folders = [x.strip() for x in str(opts.get("folders") or "").splitlines() if x.strip()] + [dest]
    by_id, by_isrc, by_name, _n = _local_index(folders, ctx)
    todo = []
    for t in items:
        tid = str(t.get("id"))
        if tid in done or t.get("pre_order") or t.get("enabled") is False:
            continue
        artist, mix = ", ".join(artists_of(t)), t.get("mix_name") or ""
        if by_id.get(tid) or by_isrc.get(str(t.get("isrc") or "").upper()) \
                or by_name.get((norm(artist), norm(t.get("name", "")), norm(mix))):
            continue
        todo.append(t)
    limit = max(1, int(opts.get("count") or 1))
    ctx.log(f"Download: {len(items)} Käufe, {len(todo)} fehlen, lade höchstens {limit}.")
    got, failed = [], []
    for k, t in enumerate(todo[:limit]):
        ctx.check_cancel()
        label = f"{', '.join(artists_of(t))} – {t.get('name', '')}"
        ctx.progress(k, min(limit, len(todo)), label)
        try:
            url = resolve_download(client, t, ctx.log)
            if not url:
                failed.append(f"{label}: keine Download-Adresse gefunden")
                continue
            paths = fetch_file(url, dest, t, client, ctx.cancelled)
            for p in paths:
                ctx.output(p)
            got += paths
            done[str(t.get("id"))] = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "files": [os.path.basename(p) for p in paths]}
            _save_done(ctx, done)
        except Cancelled:
            raise
        except Exception as ex:  # noqa: BLE001
            failed.append(f"{label}: {ex}")
    for f in failed:
        ctx.log(f)
    msg = f"{len(got)} Datei(en) geladen nach {dest}; {max(0, len(todo) - limit)} weitere fehlen noch." if got else \
        "Nichts geladen."
    if failed:
        msg += f" {len(failed)} Fehler – Details im Protokoll (bitte an Claude weitergeben, #117)."
    if not todo:
        msg = "Alle gekauften Titel sind schon vorhanden – nichts zu laden."
    return {"message": msg}


# =========================================================================== #285: Seite „Käufe“ (Store-Rahmen)
_BOUGHT_KEYS = ("purchase_date", "purchased_at", "purchased", "date_purchased", "order_date", "ordered_at",
                "order_created", "created", "date_created", "created_at")


def bought_date(t) -> str:
    """Kaufdatum aus dem Titel bzw. der Bestellung (Feldname je nach Antwort) → „JJJJ-MM-TT…“ oder ""."""
    for src in (t, t.get("_order") or {}):
        for k in _BOUGHT_KEYS:
            v = src.get(k)
            if isinstance(v, str) and re.match(r"^\d{4}-\d{2}-\d{2}", v):
                return v[:19].replace("T", " ") if "T" in v[:19] else v[:19]
    return ""


def store_item(t, cat=None) -> dict:
    """Beatport-Kauf → Eintrag für die Seite „Käufe“ (purchases.clean_item). Laut offizieller Doku hat ein Kauf
    (TrackDownloadList) kein ISRC, keine Katalognummer und kein Label, „release“ ist nur der Name – cat: derselbe
    Titel aus /catalog/tracks/ zum Ergänzen."""
    rel = t.get("release") if isinstance(t.get("release"), dict) else {"name": t.get("release") or ""}
    cat = cat or {}
    crel = cat.get("release") if isinstance(cat.get("release"), dict) else {}
    out = {"id": t.get("id"), "title": t.get("name") or "", "mix": t.get("mix_name") or "",
            "artist": ", ".join(artists_of(t)), "dur": (t.get("length_ms") or 0) / 1000,
            "key": key_text(t, "camelot"), "bpm": t.get("bpm"),
            "catalog": t.get("catalog_number") or rel.get("catalog_number") or cat.get("catalog_number")
            or crel.get("catalog_number") or "",
            "isrc": t.get("isrc") or cat.get("isrc") or "",
            "label": (rel.get("label") or {}).get("name") or (crel.get("label") or {}).get("name") or "",
            "release": rel.get("name") or crel.get("name") or "",
            "genre": (t.get("genre") or {}).get("name") or "",
            "url": f"https://www.beatport.com/track/{t.get('slug') or 'track'}/{t['id']}" if t.get("id") else "",
            "bought": bought_date(t), "preorder": bool(t.get("pre_order")),
            "received": bool(t.get("received_status")),
            "dl": {k: t.get(k) for k in ("id", "order_item_download_id", "audio_format", "name", "mix_name", "artists")
                   if t.get(k) is not None}}
    return out


def catalog_details(c, ids, log=None) -> dict:
    """Katalog-Angaben (ISRC, Katalognummer, Label) für viele Titel: /catalog/tracks/?id=1,2,… (je 100)."""
    out, ids = {}, [str(i) for i in dict.fromkeys(ids) if i]
    for k in range(0, len(ids), 100):
        part = ids[k:k + 100]
        try:
            res = c.get("/catalog/tracks/", id=",".join(part), per_page=100)
        except HttpError as ex:
            if log:
                log(f"/catalog/tracks/?id=…: {ex}")
            break
        for t in _items(res):
            if isinstance(t, dict) and t.get("id") is not None:
                out[str(t["id"])] = t
    return out


def store_purchases(ctx, since="") -> dict:
    """Käufe des Kontos für die Seite „Käufe“ → {"name", "items", "since"}. since="JJJJ-MM-TT": nur Käufe ab diesem
    Tag (Filter purchase_date laut offizieller Doku von /v4/my/downloads/), sonst alle."""
    ok, why = ready(ctx)
    if not ok:
        raise ValueError(f"Beatport: {why}.")
    c = Client(ctx)
    ctx.status("Beatport: gekaufte Titel lesen …")
    since = since if re.match(r"^\d{4}-\d{2}-\d{2}$", str(since or "")) else ""
    path, items = purchases(c, 20000, ctx.log, **({"purchase_date": since + ":"} if since else {}))
    if not path and since:
        return {"name": "Beatport", "items": [], "since": since}           # seit dem letzten Mal nichts Neues
    if not path:
        raise ValueError("Beatport hat keine gekauften Titel geliefert – Details im Protokoll (Plugins › Beatport).")
    ctx.log(f"{len(items)} Käufe über {path}")
    if items and not any(bought_date(t) for t in items[:20]):
        ctx.log("Kein Kaufdatum gefunden – Felder: " + ", ".join(sorted(set(items[0]) | set(items[0].get("_order") or {}))))
    try:                                                   # #162: Käufe in „Entdecken“ als gekauft markieren
        import discover
        discover.mark_bought(items)
    except Exception as ex:  # noqa: BLE001
        ctx.log(f"Entdecken: {ex}")
    need = [t.get("id") for t in items if not (t.get("isrc") and t.get("catalog_number"))]
    if need:
        ctx.status(f"Beatport: Katalog-Angaben für {len(need)} Titel holen …")
    cat = catalog_details(c, need, ctx.log) if need else {}
    return {"name": "Beatport", "items": [store_item(t, cat.get(str(t.get("id")))) for t in items], "since": since}


DOWNLOAD_PAGE = "https://www.beatport.com/library/downloads"


def store_download(ctx, items, dest) -> dict:
    """Gewählte Käufe in den Ordner dest laden → {"files": {id: [Pfade]}, "failed": [Text], "manual": URL|""}.
    Die offizielle API hat keinen Download-Endpunkt (OpenAPI-Beschreibung, 25.10.2026): versucht werden die
    undokumentierten Wege (#117, Variante 1 laut User). Ohne Adresse → „manual“ = Download-Seite bei Beatport
    (Variante 2: dort laden, mit „Abholen“ übernehmen)."""
    if not dest or not os.path.isdir(dest):
        raise ValueError("Zielordner nicht gefunden.")
    sess = _SESSION.get("tok")
    if sess:
        c = SessionClient(ctx, dict(sess))
        ctx.log(f"Download mit Sitzungs-Anmeldung ({sess.get('username', '')}) – {scope_text(sess)}")
    else:
        try:
            c = Client(ctx)
        except RuntimeError as ex:                     # nicht angemeldet → Sitzungs-Anmeldung anbieten (#295)
            ctx.log(str(ex))
            return {"files": {}, "failed": [], "manual": "", "need_login": True}
        ctx.log(f"Download mit gespeichertem Zugang ({'eigener API-Zugang' if c.tok.get('app') else 'Ausweichweg'}) – {scope_text(c.tok)}")
    seen: dict = {}
    try:
        with open(_done_path(ctx), encoding="utf-8") as fh:
            done = json.load(fh)
    except (OSError, ValueError):
        done = {}
    files, failed, no_url = {}, [], 0
    for k, it in enumerate(items):
        ctx.check_cancel()
        t = it.get("dl") or {}
        label = f"{it.get('artist', '')} – {it.get('title', '')}"
        ctx.progress(k, len(items), label)
        try:
            url = resolve_download(c, t, ctx.log, seen)
            if not url:
                failed.append(f"{label}: keine Download-Adresse gefunden")
                no_url += 1
                continue
            got = fetch_file(url, dest, t, c, ctx.cancelled)
            files[str(it["id"])] = got
            done[str(it["id"])] = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "files": [os.path.basename(p) for p in got]}
            _save_done(ctx, done)
        except Cancelled:
            raise
        except Exception as ex:  # noqa: BLE001
            failed.append(f"{label}: {ex}")
    for f in failed:
        ctx.log(f)
    need = bool(seen.get("denied")) and not sess
    if need:
        ctx.log("Beatport lehnt den gespeicherten Token für den Download ab – Sitzungs-Anmeldung wie auf der Webseite anbieten.")
    elif no_url:
        ctx.log(f"{no_url} Titel ohne Download-Adresse – bitte über {DOWNLOAD_PAGE} laden (Variante 2).")
    return {"files": files, "failed": failed, "manual": DOWNLOAD_PAGE if no_url else "", "need_login": need}


# =========================================================================== #288: „My Beatport“ → Entdecken
def _names_of(rows, kind) -> tuple[list, list]:
    """Antwort ohne festes Schema (offizielle Beschreibung nennt keins): Einträge mit Namen oder nur IDs."""
    names, ids = [], []
    for r in rows:
        if isinstance(r, dict):
            obj = r.get(kind[:-1]) if isinstance(r.get(kind[:-1]), dict) else r      # {"artist": {...}} oder direkt
            if obj.get("name"):
                names.append(str(obj["name"]))
            elif obj.get("id") is not None:
                ids.append(obj["id"])
        elif isinstance(r, (int, str)) and str(r).isdigit():
            ids.append(int(r))
    return names, ids


def followed(ctx, kind) -> list[str]:
    """Namen der auf Beatport gefolgten Künstler bzw. Labels (kind "artists"/"labels"): GET /my/beatport/<kind>/;
    liefert Beatport nur IDs, werden die Namen über /catalog/<kind>/?id=… nachgeschlagen. Nur lesen."""
    c = Client(ctx)
    res = c.get(f"/my/beatport/{kind}/", page=1, per_page=100)
    rows = _items(res) if not (isinstance(res, dict) and isinstance(res.get(kind), list)) else res[kind]
    if isinstance(res, dict) and not rows and res:
        ctx.log(f"/my/beatport/{kind}/: Felder {', '.join(sorted(res))}")
    if rows and isinstance(rows[0], dict):
        ctx.log(f"/my/beatport/{kind}/: Felder je Eintrag {', '.join(sorted(rows[0]))}")
    more = rows
    page = 1
    while isinstance(res, (dict, list)) and len(more) == 100 and page < 50:     # weitere Seiten
        page += 1
        res = c.get(f"/my/beatport/{kind}/", page=page, per_page=100)
        more = _items(res)
        rows += more
    names, ids = _names_of(rows, kind)
    for k in range(0, len(ids), 100):
        for o in _items(c.get(f"/catalog/{kind}/", id=",".join(str(i) for i in ids[k:k + 100]), per_page=100)):
            if isinstance(o, dict) and o.get("name"):
                names.append(str(o["name"]))
    return list(dict.fromkeys(n.strip() for n in names if n.strip()))


def add_to_discover(artists=(), labels=()) -> tuple[int, int]:
    import discover
    d = discover.load()
    a0, l0 = len(d["follow"]["artists"]), len(d["follow"]["labels"])
    d["follow"]["artists"] = discover._names(d["follow"]["artists"] + list(artists))
    d["follow"]["labels"] = discover._names(d["follow"]["labels"] + list(labels))
    discover.save(d)
    return len(d["follow"]["artists"]) - a0, len(d["follow"]["labels"]) - l0


def run_follow(ctx, opts) -> dict:
    ok, why = ready(ctx)
    if not ok:
        return {"message": f"Beatport: {why}."}
    arts = followed(ctx, "artists") if opts.get("artists", True) else []
    labs = followed(ctx, "labels") if opts.get("labels", True) else []
    na, nl = add_to_discover(arts, labs)
    return {"message": f"{len(arts)} Künstler und {len(labs)} Labels gelesen, {na} Künstler und {nl} Labels neu in „Entdecken“ übernommen."}
