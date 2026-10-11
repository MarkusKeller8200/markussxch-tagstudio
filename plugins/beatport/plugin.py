"""Beatport (inoffiziell) – Metadaten von Beatport API v4 holen.

Anmeldung wie im beets-Plugin „beatport4“: Login mit dem eigenen Beatport-Konto über die öffentliche client_id
der API-Dokumentation (OAuth authorization_code) oder Token aus dem Browser einfügen. Das Passwort wird nie
gespeichert; der Token liegt verschlüsselt (Windows: DPAPI, nur dein Benutzerkonto kann ihn lesen).

Nur Standardbibliothek. Alle Änderungen werden als Vorschläge zurückgegeben (Vorschau mit Häkchen).
"""
import difflib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

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
             "choices": [["login", "Benutzername und Passwort"], ["token", "Token aus dem Browser einfügen"]], "default": "login"},
            {"key": "username", "type": "text", "label": "Benutzername / E-Mail", "show_if": {"method": "login"}},
            {"key": "password", "type": "password", "label": "Passwort", "show_if": {"method": "login"}},
            {"key": "token", "type": "textarea", "label": "Token (JSON)", "secret": True, "show_if": {"method": "token"}},
            {"type": "info", "show_if": {"method": "token"}, "label": "Token-Methode: auf api.beatport.com/v4/docs anmelden, Entwicklertools (F12) → Netzwerk → Anfrage „token“ → Antwort kopieren und hier einfügen."},
        ],
    },
    {"id": "logout", "label": "Abmelden", "where": "page", "run_label": "Abmelden", "needs_selection": False,
     "description": "Gespeicherten Token löschen.", "options": []},
    {"id": "test", "label": "Verbindung testen", "where": "page", "run_label": "Testen", "needs_selection": False,
     "description": "Prüft die Anmeldung bei Beatport.", "options": []},
]


# =========================================================================== Token sicher ablegen
def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    if not fn(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("Windows-Verschlüsselung (DPAPI) fehlgeschlagen.")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _token_path(ctx):
    return os.path.join(ctx.data_dir, "token.bin")


def save_token(ctx, tok: dict):
    raw = json.dumps(tok).encode("utf-8")
    if sys.platform.startswith("win"):
        raw = b"DPAPI" + _dpapi(raw, True)
    path = _token_path(ctx)
    with open(path, "wb") as fh:
        fh.write(raw)
    if not sys.platform.startswith("win"):
        os.chmod(path, 0o600)


def load_token(ctx):
    try:
        with open(_token_path(ctx), "rb") as fh:
            raw = fh.read()
        if raw.startswith(b"DPAPI"):
            raw = _dpapi(raw[5:], False)
        tok = json.loads(raw.decode("utf-8"))
        return tok if isinstance(tok, dict) and tok.get("access_token") else None
    except (OSError, ValueError):
        return None


def delete_token(ctx):
    try:
        os.remove(_token_path(ctx))
        return True
    except OSError:
        return False


def _norm_token(data) -> dict:
    if isinstance(data, str):
        data = json.loads(data)
    tok = {"access_token": str(data["access_token"]), "refresh_token": str(data.get("refresh_token") or "")}
    tok["expires_at"] = float(data["expires_at"]) if data.get("expires_at") else time.time() + int(data.get("expires_in") or 3600)
    if data.get("username"):
        tok["username"] = data["username"]
    return tok


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
    req = urllib.request.Request(url, data=body, headers=h, method=method)
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


def refresh(ctx, tok):
    if not tok.get("refresh_token"):
        return None
    q = urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": tok["refresh_token"],
                                "client_id": client_id(ctx)})
    st, _h, body = request("POST", f"{API}/auth/o/token/?{q}", data=b"",
                        headers={"Content-Type": "application/x-www-form-urlencoded"})
    if st >= 400:
        return None
    new = _norm_token(json.loads(body))
    new["username"] = tok.get("username", "")
    save_token(ctx, new)
    return new


class Client:
    def __init__(self, ctx):
        self.ctx = ctx
        self.tok = load_token(ctx)
        if not self.tok:
            raise RuntimeError("Nicht bei Beatport angemeldet – auf der Plugin-Seite bei „Beatport“ auf „Anmelden …“ klicken.")

    def get(self, path, **params):
        if self.tok["expires_at"] - 30 < time.time():
            self.tok = refresh(self.ctx, self.tok) or self._expired()
        url = API + (path if path.startswith("/") else "/" + path)
        if params:
            url += "?" + urllib.parse.urlencode(params)
        for attempt in range(3):
            st, h, body = request("GET", url, headers={"Authorization": f"Bearer {self.tok['access_token']}"})
            if st == 401 and attempt == 0:
                self.tok = refresh(self.ctx, self.tok) or self._expired()
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
    return f"Angemeldet als {who}" + ("" if left > 0 else " (Token abgelaufen – wird bei Bedarf erneuert)") + "."


def _notation():
    try:
        import core
        return core.load_config().get("key_notation", "camelot")
    except Exception:  # noqa: BLE001
        return "camelot"


def run(action, ctx, files, opts):
    if action == "logout":
        return {"message": "Abgemeldet – Token gelöscht." if delete_token(ctx) else "Es war kein Token gespeichert."}
    if action == "login":
        ctx.status("Melde bei Beatport an …")
        if opts.get("method") == "token":
            if not opts.get("token", "").strip():
                raise ValueError("Bitte den Token (JSON) einfügen.")
            try:
                tok = _norm_token(opts["token"].strip())
            except (ValueError, KeyError, TypeError) as ex:
                raise ValueError("Das ist kein gültiger Token – erwartet wird die JSON-Antwort mit „access_token“.") from ex
        else:
            if not opts.get("username") or not opts.get("password"):
                raise ValueError("Bitte Benutzername und Passwort eingeben.")
            tok = login(ctx, opts["username"].strip(), opts["password"])
        save_token(ctx, tok)
        acc = Client(ctx).get("/my/account/") or {}
        tok["username"] = acc.get("username") or tok.get("username", "")
        save_token(ctx, tok)
        return {"message": f"Angemeldet als {tok['username'] or 'Beatport-Konto'}. Das Passwort wurde nicht gespeichert."}
    if action == "test":
        acc = Client(ctx).get("/my/account/") or {}
        return {"message": f"Verbindung in Ordnung – angemeldet als {acc.get('username', '?')}."}
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
