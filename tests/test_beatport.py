"""Tests für das Beatport-Plugin mit nachgebauter Beatport-API (kein Netz nötig)."""
import json
import os
import time
import unittest
import urllib.parse

from helpers import write_mp3, text
from test_tagger_tools import Base

import plugins

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64

TRACKS = {
    1001: {"id": 1001, "name": "Nordlicht", "mix_name": "Extended Mix", "bpm": 124, "isrc": "CHA012100001",
           "artists": [{"id": 1, "name": "Mara Lind"}], "remixers": [],
           "key": {"name": "A Minor", "camelot_number": 8, "camelot_letter": "A"},
           "genre": {"name": "Melodic House & Techno"}, "sub_genre": {"name": "Melodic House"},
           "publish_date": "2021-05-14", "catalog_number": "POL042",
           "release": {"id": 77, "name": "Nachtfahrt EP", "label": {"name": "Polar Records"},
                       "image": {"uri": "https://geo-media.beatport.com/image/abc.jpg",
                                 "dynamic_uri": "https://geo-media.beatport.com/image_size/{w}x{h}/abc.jpg"}}},
    1002: {"id": 1002, "name": "Nordlicht", "mix_name": "Original Mix", "bpm": 98,
           "artists": [{"id": 9, "name": "Ganz Anderer"}], "key": {"name": "C Major"},
           "genre": {"name": "Pop"}, "release": {"id": 78, "name": "X", "label": {"name": "Y"}}},
    1003: {"id": 1003, "name": "Kaltes Glas", "mix_name": "Original Mix", "bpm": 120,
           "artists": [{"id": 1, "name": "Mara Lind"}], "remixers": [{"id": 5, "name": "Oskar Vey"}],
           "key": {"name": "F# Minor"}, "genre": {"name": "Deep House"},
           "publish_date": "2021-05-14", "release": {"id": 77, "name": "Nachtfahrt EP", "label": {"name": "Polar Records"}}},
}


class FakeBeatport:
    def __init__(self):
        self.calls = []
        self.password = "geheim"
        self.web = set()
        self.token_n = 0
        self.valid = set()

    def _tok(self, web=False):
        self.token_n += 1
        t = f"AT{self.token_n}"
        self.valid.add(t)
        if web:                                                    # #295: Token wie die Webseite (Anmeldung → Code)
            self.web.add(t)
        d = {"access_token": t, "expires_in": 3600, "refresh_token": f"RT{self.token_n}"}
        if not web:
            d["scope"] = "app:externaltrusted user:dj"             # #296: Scope der eigenen App
        return 200, {}, json.dumps(d).encode()

    def __call__(self, method, url, *, headers=None, data=None, opener=None, follow=True):
        u = urllib.parse.urlparse(url)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        if isinstance(data, bytes) and data:                      # Formular (offizieller Weg, eigener API-Zugang)
            q.update({k: v[0] for k, v in urllib.parse.parse_qs(data.decode()).items()})
        self.calls.append((method, u.path, q))
        auth = (headers or {}).get("Authorization", "")
        if u.netloc == "geo-media.beatport.com":
            return 200, {}, JPEG
        p = u.path
        if p == "/v4/docs/":
            return 200, {}, b'<html><script src="/static/main.abc.js"></script></html>'
        if p == "/static/main.abc.js":
            return 200, {}, b"var x={API_CLIENT_ID: 'CID123',y:1}"
        if p == "/v4/auth/login/":
            if data and data.get("password") == self.password:
                return 200, {}, json.dumps({"username": "marku", "email": "m@example.org"}).encode()
            return 401, {}, json.dumps({"detail": "Ungültige Zugangsdaten"}).encode()
        if p == "/v4/auth/o/authorize/":
            assert q["client_id"] == "CID123"
            return 302, {"Location": "https://api.beatport.com/v4/auth/o/post-message/?code=CODE1"}, b""
        if p == "/v4/auth/o/revoke/":
            self.valid.discard(q.get("token"))
            return 200, {}, b""
        if p == "/v4/auth/o/token/":
            if q.get("grant_type") == "password":                  # eigene App: Client-ID + Secret + Benutzer
                if (q.get("client_id"), q.get("client_secret"), q.get("password")) == ("MYAPP", "S3CRET", self.password):
                    return self._tok()
                return 401, {}, json.dumps({"error": "invalid_grant", "error_description": "Invalid credentials"}).encode()
            if q.get("grant_type") == "authorization_code" and q.get("code") == "CODE1":
                return self._tok(web=True)
            if q.get("grant_type") == "refresh_token" and q.get("refresh_token", "").startswith("RT"):
                return self._tok()
            return 400, {}, b"{}"
        if not auth.startswith("Bearer ") or auth[7:] not in self.valid:
            return 401, {}, b"{}"
        if p == "/v4/my/account/":
            return 200, {}, json.dumps({"username": "marku", "email": "m@example.org"}).encode()
        if p == "/v4/catalog/search/":
            words = set(q["q"].lower().split())
            hits = [dict(t, release={"id": t["release"]["id"], "name": t["release"]["name"]})   # gekürzt
                    for t in TRACKS.values() if t["name"].lower().split()[0] in words]
            return 200, {}, json.dumps({"tracks": hits}).encode()
        if p.startswith("/v4/catalog/tracks/") and p.rstrip("/").split("/")[-1].isdigit():
            t = TRACKS.get(int(p.rstrip("/").split("/")[-1]))
            return (200, {}, json.dumps(t).encode()) if t else (404, {}, b"{}")
        if p == "/v4/my/downloads/" and not q.get("track_id"):
            return 200, {}, json.dumps({"results": [
                dict(TRACKS[1001], order_item_download_id=501, audio_format={"name": "mp3"}, purchase_date="2026-10-20T10:00:00Z"),
                {"id": 2001, "name": "Frisch gekauft", "mix_name": "Extended Mix", "artists": [{"name": "Mara Lind"}],
                 "order_item_download_id": 502, "audio_format": {"name": "mp3"}, "release": "Frisch EP",   # wie TrackDownloadList
                 "purchase_date": "2026-10-22T09:15:00Z", "received_status": True},
                {"id": 2002, "name": "Vorbestellt", "artists": [{"name": "X"}], "pre_order": True, "order_item_download_id": 503}]}).encode()
        if p == "/v4/catalog/tracks/purchase-download/" and auth[7:] not in self.web:      # #295: eigene App → 403
            return 403, {"Content-Type": "application/json"}, json.dumps({"detail": "forbidden"}).encode()
        if p == "/v4/catalog/tracks/purchase-download/" and q.get("order_item_download_id") == "502":   # #292
            return 200, {}, json.dumps({"location": "https://dl.beatport.com/sig/abc.mp3"}).encode()
        if p == "/v4/my/downloads/502/":
            return 200, {}, json.dumps({"id": 502, "download_url": "https://dl.beatport.com/sig/abc.mp3"}).encode()
        if p == "/v4/my/beatport/artists/":                    # #288: Antwort ohne Schema – mit Namen
            return 200, {}, json.dumps({"results": [{"id": 1, "name": "Mara Lind"}, {"id": 5, "name": "Oskar Vey"}]}).encode()
        if p == "/v4/my/beatport/labels/":                     # … oder nur IDs
            return 200, {}, json.dumps({"results": [77]}).encode()
        if p == "/v4/catalog/labels/" and q.get("id"):
            return 200, {}, json.dumps({"results": [{"id": 77, "name": "Polar Records"}]}).encode()
        if p == "/v4/my/playlists/":                       # #284: eigene Playlists (Form nach API v4, Seiten)
            return 200, {}, json.dumps({"results": [{"id": 7, "name": "Peak Time", "track_count": 2},
                                                    {"id": 8, "name": "Leer", "track_count": 0}]}).encode()
        if p == "/v4/my/playlists/7/":
            return 200, {}, json.dumps({"id": 7, "name": "Peak Time"}).encode()
        if p == "/v4/my/playlists/7/tracks/":
            return 200, {}, json.dumps({"results": [{"position": 2, "track": TRACKS[1003]},
                                                    {"position": 1, "track": TRACKS[1001]}]}).encode()
        if p == "/v4/catalog/tracks/" and q.get("id"):            # Katalog-Angaben für Käufe (id=1,2,…)
            more = {2001: {"id": 2001, "name": "Frisch gekauft", "isrc": "CHA012600001", "catalog_number": "NEU001",
                           "release": {"id": 90, "name": "Frisch EP", "label": {"name": "Polar Records"}}}}
            hits = [x for x in (TRACKS.get(int(i)) or more.get(int(i)) for i in q["id"].split(",")) if x]
            return 200, {}, json.dumps({"results": hits}).encode()
        if p == "/v4/catalog/tracks/":
            hits = [t for t in TRACKS.values() if t.get("isrc") == q.get("isrc")]
            return 200, {}, json.dumps({"results": hits}).encode()
        return 404, {}, b"{}"


class TestBeatport(Base):
    def setUp(self):
        super().setUp()
        # Datei 1: Nordlicht, Genre gesetzt; Datei 2: Kaltes Glas ohne Genre; Datei 3: unbekannt
        write_mp3(os.path.join(self.B, "n.mp3"), [text("TIT2", "Nordlicht (Extended Mix)"), text("TPE1", "Mara Lind"),
                                                  text("TCON", "Synthpop")], audio_seed=11)
        write_mp3(os.path.join(self.B, "k.mp3"), [text("TIT2", "Kaltes Glas"), text("TPE1", "Mara Lind")], audio_seed=12)
        write_mp3(os.path.join(self.B, "u.mp3"), [text("TIT2", "Gibt es nicht"), text("TPE1", "Niemand")], audio_seed=13)
        from session import Session
        self.s = Session()
        self.s.start_tag_load(self.B, False)
        self.wait()
        self.fake = FakeBeatport()
        mod = self.s.plugins.get("beatport").load()
        self.assertIsNotNone(mod, self.s.plugins.get("beatport").error)
        self.mod = mod
        self._orig = mod.request
        mod.request = self.fake
        mod.MIN_INTERVAL = 0
        self.idx = {os.path.basename(f.path): i for i, f in enumerate(self.s.tag_files)}

    def tearDown(self):
        self.mod.request = self._orig
        super().tearDown()

    def wait(self):
        for _ in range(500):
            st = self.s.task_status()
            if st.get("done"):
                return st
            time.sleep(0.02)
        self.fail("hängt")

    def act(self, aid, idx=None, **opts):
        r = self.s.start_plugin_action("beatport", aid, idx or [], opts)
        self.assertTrue(r["ok"], r)
        return self.wait()

    def login(self):
        st = self.act("login", method="login", username="marku", password="geheim")
        self.assertIsNone(st["error"], st)
        return st

    def test_page_and_login(self):
        info = {p["id"]: p for p in self.s.plugins_list()["plugins"]}["beatport"]
        self.assertEqual(info["state"], "ready")
        self.assertEqual(info["status_text"], "Nicht angemeldet.")
        self.assertEqual(sorted(a["id"] for a in info["actions"] if a["where"] == "page"), ["download", "follow", "login", "logout", "purchases", "settings", "test", "write_check"])
        # ohne Login: Abruf scheitert verständlich
        st = self.act("fetch", [0])
        self.assertIn("Nicht bei Beatport angemeldet", st["error"])
        st = self.act("login", method="login", username="marku", password="falsch")
        self.assertIn("Anmeldung abgelehnt", st["error"])
        st = self.login()
        self.assertIn("marku", st["result"]["message"])
        # Passwort nie gespeichert – weder in den Optionen noch im Token
        cfg = json.dumps(self.s.cfg)
        self.assertNotIn("geheim", cfg)
        with open(os.path.join(plugins.data_root(), "beatport", "token.bin"), "rb") as fh:
            raw = fh.read()
        self.assertNotIn(b"geheim", raw)
        self.assertEqual(self.s.plugin_form("beatport", "login")["options"][2]["value"], "")
        info = {p["id"]: p for p in self.s.plugins_list()["plugins"]}["beatport"]
        self.assertIn("marku", info["status_text"])
        self.assertIn("marku", self.act("test")["result"]["message"])
        self.assertIn("Abgemeldet", self.act("logout")["result"]["message"])

    def test_download(self):
        """#117: fehlende Käufe laden – Adresse aus /my/downloads/{id}/, Datei unverändert, nicht doppelt."""
        self.login()
        audio = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb" * 500

        class Resp:
            headers = {"Content-Type": "audio/mpeg", "Content-Disposition": 'attachment; filename="Mara Lind - Frisch gekauft (Extended Mix).mp3"'}

            def __init__(self):
                self.left = audio

            def read(self, n=-1):
                out, self.left = self.left[:n], self.left[n:]
                return out

            def close(self):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        seen = []
        orig = self.mod._urlopen
        self.mod._urlopen = lambda req, timeout: (seen.append((req.full_url, req.headers)), Resp())[1]
        try:
            inbox = os.path.join(self.dir, "Eingang")
            os.makedirs(inbox)
            st = self.act("download", dest=inbox, folders=self.B, count=5)
            self.assertIsNone(st["error"], st)
            self.assertIn("1 Datei(en) geladen", st["result"]["message"], st["result"].get("log"))
            f = os.path.join(inbox, "Mara Lind - Frisch gekauft (Extended Mix).mp3")
            with open(f, "rb") as fh:
                self.assertEqual(fh.read(), audio)                                     # unverändert
            self.assertEqual(seen[0][0], "https://dl.beatport.com/sig/abc.mp3")
            self.assertNotIn("Authorization", seen[0][1])                              # signierte Adresse ohne Token
            tried = [c[1] for c in self.fake.calls if "download" in c[1] and c[1] != "/v4/my/downloads/"]
            self.assertEqual(tried, ["/v4/catalog/tracks/purchase-download/"])           # #292: Weg der Webseite zuerst
            st = self.act("download", dest=inbox, folders=self.B, count=5)
            self.assertIn("nichts zu laden", st["result"]["message"])                  # nicht doppelt
            self.assertEqual(len(seen), 1)
        finally:
            self.mod._urlopen = orig

    def test_refresh_keeps_login_on_server_error(self):
        """4.9.1 (#299): Erneuerung mit 503/HTML behält die Anmeldung, 400/401 gilt als abgelehnt."""
        self.login()
        import plugins
        ctx = plugins.Context(self.s.plugins.get("beatport"), self.s)
        tok = self.mod.load_token(ctx)
        orig = self.mod.request
        try:
            self.mod.request = lambda *a, **k: (503, {}, b"<html>busy</html>")
            with self.assertRaises(self.mod.HttpError):
                self.mod.refresh(ctx, tok, save=False)
            self.mod.request = lambda *a, **k: (200, {}, b"<html>kein json</html>")
            with self.assertRaises(self.mod.HttpError):
                self.mod.refresh(ctx, tok, save=False)
            self.mod.request = lambda *a, **k: (400, {}, b'{"error": "invalid_grant"}')
            self.assertIsNone(self.mod.refresh(ctx, tok, save=False))
        finally:
            self.mod.request = orig
        self.assertIsNotNone(self.mod.load_token(ctx))

    def test_auth_header_not_redirected(self):
        """4.9.1 (#299): Token nur an die erste Adresse, nie an eine Weiterleitung."""
        import urllib.request
        seen = []

        class Op:
            def open(self, req, timeout=None):
                seen.append(req)
                raise urllib.error.URLError("aus")
        with self.assertRaises(self.mod.HttpError):
            self._orig("GET", "https://api.beatport.com/v4/x/", headers={"Authorization": "Bearer T"}, opener=Op())
        self.assertNotIn("Authorization", seen[0].headers)
        self.assertEqual(seen[0].unredirected_hdrs.get("Authorization"), "Bearer T")

    def test_token_scope(self):
        """#296: Scope aus der Token-Antwort oder aus dem JWT lesen und beim Anmelden/Testen/Download protokollieren."""
        import base64
        b64 = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")   # noqa: E731
        jwt = f"{b64({'alg': 'RS256'})}.{b64({'scope': 'app:externaltrusted user:dj openid', 'sub': '1'})}.sig"
        self.assertEqual(self.mod.token_scope({"access_token": jwt}), "app:externaltrusted user:dj openid")
        self.assertEqual(self.mod.token_scope({"access_token": "x", "scope": "a b"}), "a b")
        self.assertEqual(self.mod.token_scope({"access_token": "kein.jwt.!!"}), "")
        self.assertEqual(self.mod.scope_text({"access_token": "AT1"}), "Berechtigungen (Scope): unbekannt")
        st = self.act("login", method="app", client_id="MYAPP", client_secret="S3CRET", username="marku", password="geheim")
        self.assertIn("Berechtigungen (Scope): app:externaltrusted user:dj", st["result"]["message"])
        self.assertIn("app:externaltrusted user:dj", self.act("test")["result"]["message"])
        with open(os.path.join(plugins.log_dir(), "beatport.log"), encoding="utf-8") as fh:
            log = fh.read()
        self.assertIn("Berechtigungen (Scope): app:externaltrusted user:dj", log)
        self.assertNotRegex(log, r"\bAT\d+\b")                                            # nie der Token selbst

    def test_access_check(self):
        """#297: „Zugriff prüfen“ – jeder lesende Endpunkt einmal mit der aktuellen Anmeldung, eingeordnet."""
        self.assertFalse(self.s.start_service_access("gibtsnicht")["ok"])
        r = self.s.start_service_access("beatport")
        self.assertTrue(r["ok"], r)
        st = self.wait()
        self.assertIn("Nicht bei Beatport angemeldet", st["error"] or "")               # ohne Anmeldung: klare Meldung
        self.act("login", method="app", client_id="MYAPP", client_secret="S3CRET", username="marku", password="geheim")
        self.s.start_service_access("beatport")
        st = self.wait()
        self.assertIsNone(st["error"], st)
        res = st["result"]
        by = {x["path"]: x for x in res["rows"]}
        self.assertEqual(res["info"], "eigener API-Zugang – Berechtigungen (Scope): app:externaltrusted user:dj")
        self.assertEqual((by["/my/account/"]["access"], by["/my/account/"]["status"]), ("ok", 200))
        self.assertEqual(by["/catalog/tracks/purchase-download/"]["access"], "denied")      # Scope reicht nicht
        self.assertEqual(by["/catalog/tracks/purchase-download/"]["detail"], "forbidden")
        self.assertEqual(by["/my/playlists/{myplaylists_pk}/tracks/"]["access"], "ok")     # ID aus /my/playlists/
        self.assertEqual(by["/my/playlists/{id}/"]["access"], "ok")
        self.assertIn(("/v4/my/playlists/7/tracks/"), [c[1] for c in self.fake.calls])
        self.assertEqual(by["/catalog/charts/{id}/"]["access"], "skip")                    # Liste ohne Treffer
        self.assertEqual(by["/catalog/genres/"]["access"], "notfound")
        paths = set(by)
        self.assertFalse(any(p.startswith("/auth/") or p.rstrip("/").endswith("/download") for p in paths))
        self.assertFalse(any(m != "GET" for m in (x["method"] for x in res["rows"])))
        self.assertEqual(sum(res["counts"].values()), len(res["rows"]))
        with open(res["logfile"], encoding="utf-8") as fh:
            log = fh.read()
        self.assertIn("Zugriff prüfen: eigener API-Zugang", log)
        self.assertIn("/catalog/tracks/purchase-download/: kein Zugriff (HTTP 403) – forbidden", log)
        self.assertNotRegex(log + json.dumps(res), r"\bAT\d+\b")                        # nie der Token

    def test_session_login_download(self):
        """#295: eigener API-Zugang wird beim Download abgelehnt → Sitzungs-Anmeldung wie die Webseite, Token nur im
        Speicher, dann derselbe Download-Weg (purchase-download)."""
        self.mod._SESSION.clear()
        self.addCleanup(self.mod._SESSION.clear)
        st = self.act("login", method="app", client_id="MYAPP", client_secret="S3CRET", username="marku", password="geheim")
        self.assertIsNone(st["error"], st)
        inbox = os.path.join(self.dir, "00_New")
        os.makedirs(inbox)
        self.s.purch_set_dest(inbox)
        self.s.start_purch_refresh()
        self.wait()
        self.assertEqual(self.s.purch_state()["sessions"], {"beatport": {"active": False, "username": ""}})
        r = self.s.start_purch_download(["beatport:2001"])
        self.assertTrue(r["ok"], r)
        res = self.wait()["result"]
        self.assertEqual((res["downloaded"], res["manual"]), (0, []))
        self.assertEqual(res["need_login"], [{"store": "beatport", "name": "Beatport", "keys": ["beatport:2001"]}])
        with self.assertRaises(Exception):
            self.s.purch_session_login("beatport", "marku", "falsch")
        tok_file = os.path.join(os.path.join(plugins.data_root(), "beatport"), "token.bin")
        with open(tok_file, "rb") as fh:
            before = fh.read()
        r = self.s.purch_session_login("beatport", "marku", "geheim")
        self.assertEqual((r["ok"], r["sessions"]["beatport"]), (True, {"active": True, "username": "marku"}))
        with open(tok_file, "rb") as fh:
            self.assertEqual(fh.read(), before)                                           # gespeicherter Zugang bleibt
        audio = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb" * 200

        class Resp:
            headers = {"Content-Type": "audio/mpeg", "Content-Disposition": 'attachment; filename="x.mp3"'}

            def __init__(self):
                self.left = audio

            def read(self, n=-1):
                out, self.left = self.left[:n], self.left[n:]
                return out

            def close(self):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        orig = self.mod._urlopen
        self.mod._urlopen = lambda req, timeout: Resp()
        try:
            r = self.s.start_purch_download(["beatport:2001"])
            res = self.wait()["result"]
        finally:
            self.mod._urlopen = orig
        self.assertEqual((res["downloaded"], res["need_login"]), (1, []))
        with open(os.path.join(os.path.join(plugins.data_root(), "beatport"), "app.bin"), "rb") as fh:
            self.assertNotIn(b"geheim", fh.read())                                        # Passwort nirgends gespeichert
        for root, _d, files in os.walk(os.path.join(plugins.data_root(), "beatport")):
            for f in files:
                with open(os.path.join(root, f), "rb") as fh:
                    self.assertNotIn(b"geheim", fh.read(), f)
        self.assertEqual(self.s.purch_session_logout("beatport")["sessions"]["beatport"]["active"], False)

    def test_purchases_page(self):
        """#285: Seite „Käufe“ – Käufe sammeln, mit der Bibliothek abgleichen, fehlende in den Eingang laden."""
        src = self.s.purch_state()["sources"]
        self.assertEqual([(x["id"], x["ready"]) for x in src], [("beatport", False)])        # nicht angemeldet
        self.login()
        inbox = os.path.join(self.dir, "00_New")
        os.makedirs(inbox)
        self.s.purch_set_dest(inbox)
        r = self.s.start_purch_refresh()
        self.assertTrue(r["ok"], r)
        res = self.wait()["result"]
        self.assertEqual((res["new"], res["count"]["library"], res["count"]["missing"], res["errors"]), (3, 1, 2, []))
        rows = {r["id"]: r for r in self.s.purch_state()["rows"]}
        n = rows["1001"]
        self.assertEqual((n["status"], n["key"], n["catalog"], n["mix"], n["bought"], n["store"]),
                         ("library", "8A", "POL042", "Extended Mix", "2026-10-20 10:00:00", "beatport"))
        self.assertTrue(n["url"].startswith("https://www.beatport.com/track/"))
        self.assertTrue(n["file"].endswith("n.mp3"))
        self.assertTrue(rows["2002"]["preorder"])
        f = rows["2001"]                                                                         # aus dem Katalog ergänzt
        self.assertEqual((f["catalog"], f["isrc"], f["label"], f["release"], f["bought"], f["received"]),
                         ("NEU001", "CHA012600001", "Polar Records", "Frisch EP", "2026-10-22 09:15:00", True))
        audio = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb" * 500

        class Resp:
            headers = {"Content-Type": "audio/mpeg", "Content-Disposition": 'attachment; filename="Mara Lind - Frisch gekauft (Extended Mix).mp3"'}

            def __init__(self):
                self.left = audio

            def read(self, n=-1):
                out, self.left = self.left[:n], self.left[n:]
                return out

            def close(self):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        orig = self.mod._urlopen
        self.mod._urlopen = lambda req, timeout: Resp()
        try:
            r = self.s.start_purch_download()
            self.assertTrue(r["ok"], r)
            res = self.wait()["result"]
        finally:
            self.mod._urlopen = orig
        self.assertEqual(res["downloaded"], 1)                                                   # Vorbestellung nicht
        self.assertTrue(os.path.isfile(os.path.join(inbox, "Mara Lind - Frisch gekauft (Extended Mix).mp3")))
        rows = {r["id"]: r for r in self.s.purch_state()["rows"]}
        self.assertEqual(rows["2001"]["status"], "inbox")
        self.s.start_purch_refresh()                                                            # erneut: nichts neu
        res = self.wait()["result"]
        self.assertEqual((res["new"], res["count"]["inbox"]), (0, 1))
        dl = [c[2] for c in self.fake.calls if c[1] == "/v4/my/downloads/"]
        self.assertNotIn("purchase_date", dl[0])                                                # erstes Mal: alles
        self.assertEqual(dl[-1].get("purchase_date"), "2026-10-19:")                            # dann nur neue (letzter Kauf −3 Tage)
        self.assertNotIn("/v4/my/library/", [c[1] for c in self.fake.calls])
        self.s.start_purch_refresh(None, True)                                                  # „Alle neu holen“
        self.wait()
        self.assertNotIn("purchase_date", [c[2] for c in self.fake.calls if c[1] == "/v4/my/downloads/"][-1])
        # Variante 1 scheitert (keine Download-Adresse) → Hinweis auf die Download-Seite (Variante 2)
        orig_rd = self.mod.resolve_download
        self.mod.resolve_download = lambda client, t, log, seen=None: ""
        try:
            r = self.s.start_purch_download(["beatport:2001"])
            self.assertTrue(r["ok"], r)
            res = self.wait()["result"]
        finally:
            self.mod.resolve_download = orig_rd
        self.assertEqual((res["downloaded"], len(res["failed"])), (0, 1))
        self.assertEqual(res["manual"], [{"store": "beatport", "name": "Beatport", "url": "https://www.beatport.com/library/downloads"}])

    def test_own_api_access(self):
        """Offizieller Zugang mit eigener Beatport-App: Password Grant, Refresh per Formular, Abmelden zieht zurück."""
        st = self.act("login", method="app", client_id="MYAPP", client_secret="falsch", username="marku", password="geheim")
        self.assertIn("abgelehnt", st["error"])
        st = self.act("login", method="app", client_id="MYAPP", client_secret="S3CRET", username="marku", password="geheim")
        self.assertIsNone(st["error"], st)
        self.assertIn("eigenen API-Zugang", st["result"]["message"])
        ctx = plugins.Context(self.s.plugins.get("beatport"), self.s)
        tok = self.mod.load_token(ctx)
        self.assertTrue(tok["app"])
        self.assertEqual(self.mod.load_app(ctx)["client_id"], "MYAPP")
        self.assertIn("eigener API-Zugang", self.mod.status(ctx))
        cfg = json.dumps(self.s.cfg.get("plugin_options") or {})
        self.assertNotIn("MYAPP", cfg)                                                      # nie in der Einstellungsdatei
        self.assertNotIn("S3CRET", cfg)
        # ohne Felder: gespeicherte Client-ID und Secret gelten
        st = self.act("login", method="app", username="marku", password="geheim")
        self.assertIsNone(st["error"], st)
        # Token abgelaufen → Erneuern per Formular mit Client-ID und Secret
        tok = self.mod.load_token(ctx)
        tok["expires_at"] = 0
        self.mod.save_token(ctx, tok)
        self.assertEqual(self.mod.Client(ctx).get("/my/account/")["username"], "marku")
        ref = [c for c in self.fake.calls if c[1] == "/v4/auth/o/token/" and c[2].get("grant_type") == "refresh_token"][-1]
        self.assertEqual((ref[2]["client_id"], ref[2]["client_secret"]), ("MYAPP", "S3CRET"))
        # Abmelden: zurückziehen, Token weg; App-Daten nur auf Wunsch
        st = self.act("logout")
        self.assertIn("zurückgezogen", st["result"]["message"])
        self.assertIsNone(self.mod.load_token(ctx))
        self.assertIsNotNone(self.mod.load_app(ctx))
        self.act("logout", forget_app=True)
        self.assertIsNone(self.mod.load_app(ctx))

    def test_account_paths(self):
        """Konto laut offizieller Beschreibung: GET /my/account/ (myaccount kennt nur PUT/PATCH) – nie schreiben."""
        self.login()
        st = self.act("test")
        self.assertIn("marku", st["result"]["message"])
        paths = [c[1] for c in self.fake.calls]
        self.assertIn("/v4/my/account/", paths)
        self.assertNotIn("/v4/my/account/myaccount/", paths)
        self.assertFalse([c for c in self.fake.calls if c[0] in ("PUT", "PATCH", "DELETE")])

    def test_follow_to_discover(self):
        """#288: gefolgte Künstler und Labels aus „My Beatport“ in „Entdecken“ übernehmen (nur lesen, keine Doppelten)."""
        import discover
        self.login()
        d = discover.load()
        d["follow"]["artists"] = ["Mara Lind"]
        discover.save(d)
        st = self.act("follow", artists=True, labels=True)
        self.assertIsNone(st["error"], st)
        self.assertIn("2 Künstler und 1 Labels gelesen, 1 Künstler und 1 Labels neu", st["result"]["message"])
        f = discover.load()["follow"]
        self.assertEqual((sorted(f["artists"]), f["labels"]), (["Mara Lind", "Oskar Vey"], ["Polar Records"]))
        st = self.act("follow", artists=True, labels=True)
        self.assertIn("0 Künstler und 0 Labels neu", st["result"]["message"])
        self.assertFalse([c for c in self.fake.calls if c[0] != "GET" and "/my/beatport" in c[1]])

    def test_token_paste_and_refresh(self):
        self.fake.valid.add("PASTED")
        tok = json.dumps({"access_token": "PASTED", "expires_in": 3600, "refresh_token": "RT0"})
        st = self.act("login", method="token", token=tok)
        self.assertIsNone(st["error"], st)
        self.assertNotIn("PASTED", json.dumps(self.s.cfg))       # Token nicht in den Einstellungen
        # Token abgelaufen → wird erneuert
        ctx = plugins.Context(self.s.plugins.get("beatport"))
        t = self.mod.load_token(ctx)
        t["expires_at"] = time.time() - 10
        self.mod.save_token(ctx, t)
        self.assertIsNone(self.act("test")["error"])
        self.assertTrue(any(q.get("grant_type") == "refresh_token" for _m, _p, q in self.fake.calls))
        self.assertIn("ungültig", self.act("login", method="token", token="{kaputt")["error"].replace("kein gültiger", "ungültig"))

    def test_fetch_preview_apply(self):
        self.login()
        idx = [self.idx["n.mp3"], self.idx["k.mp3"], self.idx["u.mp3"]]
        st = self.act("fetch", idx, mode="empty", bpm=True, key=True, genre=True, genre_mode="sub", label=True,
                      date="year", isrc=True, remixer=True, names=False, cover="missing", ids=True)
        self.assertIsNone(st["error"], st)
        res = st["result"]
        self.assertIn("2 sicher gefunden", res["message"])
        self.assertIn("1 nicht gefunden", res["message"])
        rows = res["proposals"]
        by = {(r["name"], r["label"]): r for r in rows}
        self.assertEqual(by[("n.mp3", "BPM")]["new"], "124")          # Extended Mix gewählt, nicht 1002
        self.assertEqual(by[("n.mp3", "Tonart")]["new"], "08A")
        g = by[("n.mp3", "Genre")]                                       # gefüllt → gelistet, nicht angehakt
        self.assertFalse(g["checked"])
        self.assertEqual(g["old"], "Synthpop")
        self.assertIn("schon gefüllt", g["hint"])
        self.assertIn("schon gefüllte", res["message"])
        self.assertEqual(by[("k.mp3", "Genre")]["new"], "Deep House")
        self.assertEqual(by[("k.mp3", "Tonart")]["new"], "11A")
        self.assertEqual(by[("n.mp3", "Label")]["new"], "Polar Records")
        self.assertEqual(by[("n.mp3", "Katalognummer")]["new"], "POL042")
        self.assertEqual(by[("n.mp3", "Jahr")]["new"], "2021")
        self.assertEqual(by[("n.mp3", "ISRC")]["new"], "CHA012100001")
        self.assertEqual(by[("k.mp3", "Remixer")]["new"], "Oskar Vey")
        self.assertEqual(by[("n.mp3", "Beatport-ID")]["new"], "1001")
        self.assertEqual(by[("n.mp3", "Cover")]["kind"], "cover")      # Testdateien haben kein Cover
        self.assertTrue(all(r["checked"] for r in rows if not r["hint"]))
        self.assertTrue(any("Beatport liefert BPM, Tonart, Genre" in l for l in res["log"]))
        self.assertIn("Mara Lind – Nordlicht (Extended Mix)", by[("n.mp3", "BPM")]["note"])
        # nur einen Teil übernehmen
        pick = [r["id"] for r in rows if r["label"] in ("BPM", "Tonart", "Cover")]
        r = self.s.plugin_apply(res["proposals_token"], pick)
        self.assertTrue(r["ok"])
        f = self.s.tag_files[self.idx["n.mp3"]]
        self.assertEqual(f.text("TBPM"), "124")
        self.assertEqual(f.text("TKEY"), "08A")
        self.assertIsNotNone(f.get("APIC:3"))
        self.assertEqual(f.text("TPUB"), "")
        self.assertFalse(self.s.plugin_apply(res["proposals_token"], pick)["ok"])   # verbraucht
        self.s.do_undo()
        self.assertEqual(f.text("TBPM"), "")
        self.assertEqual(self.s.unsaved(), 0)

    def test_overwrite_notation_and_saved_id(self):
        self.login()
        self.s.tag_key_notation("musical")
        i = self.idx["n.mp3"]
        st = self.act("fetch", [i], mode="overwrite", bpm=True, key=True, genre=True, genre_mode="both", label=False,
                      date="no", isrc=False, remixer=False, names=True, cover="no", ids=True)
        by = {r["label"]: r for r in st["result"]["proposals"]}
        self.assertEqual(by["Tonart"]["new"], "Am")
        self.assertEqual(by["Genre"]["old"], "Synthpop")
        self.assertEqual(by["Genre"]["new"], "Melodic House & Techno; Melodic House")
        # Alle gelieferten Felder werden gezeigt: gleiche grau/nicht wählbar, abgewählte ungehakt
        self.assertTrue(by["Titel"]["same"])       # schon „Nordlicht (Extended Mix)“
        self.assertFalse(by["Titel"]["checked"])
        self.assertTrue(by["Künstler"]["same"])
        self.assertEqual(by["Album"]["new"], "Nachtfahrt EP")
        self.assertTrue(by["Album"]["checked"])
        self.assertFalse(by["Label"]["checked"])   # label=False → gezeigt, nicht angehakt
        self.assertIn("abgewählt", by["Label"]["hint"])
        self.assertTrue(by["Cover"]["same"])       # cover="no" → nur Info
        want = [r["id"] for r in st["result"]["proposals"] if r["checked"]]
        res = self.s.plugin_apply(st["result"]["proposals_token"], want + [by["Titel"]["id"], by["Cover"]["id"]])
        self.assertEqual(res["count"], len(want))  # gleiche/Info-Zeilen werden nie angewendet
        # zweiter Lauf: direkt über gespeicherte ID, ohne Suche
        self.fake.calls.clear()
        st = self.act("fetch", [i], mode="overwrite", bpm=True, key=False, genre=False, label=False, date="no",
                      isrc=False, remixer=False, names=False, cover="no", ids=True)
        self.assertFalse(any(p == "/v4/catalog/search/" for _m, p, _q in self.fake.calls))
        self.assertFalse([r for r in st["result"]["proposals"] if r["checked"]])
        self.assertIn("0 vorausgewählt", st["result"]["message"])

    def test_same_value_and_existing(self):
        m = self.mod
        self.assertTrue(m.same_value("TKEY", "Am", "8A"))
        self.assertTrue(m.same_value("TBPM", "124.00", "124"))
        self.assertTrue(m.same_value("TDRC", "2021-05-14", "2021"))
        self.assertFalse(m.same_value("TBPM", "122", "124"))
        self.login()
        f = self.s.tag_files[self.idx["n.mp3"]]
        f.set_text("TBPM", "124.0")
        f.set_text("TKEY", "Am")
        st = self.act("fetch", [self.idx["n.mp3"]], mode="empty", bpm=True, key=True, genre=False, label=False,
                      date="no", isrc=False, remixer=False, names=False, cover="no", ids=False)
        by = {r["label"]: r for r in st["result"]["proposals"]}
        self.assertFalse(by["BPM"]["checked"])     # 124.0 = 124 → gezeigt, nicht angehakt
        self.assertIn("Schreibweise", by["BPM"]["hint"])
        self.assertFalse(by["Tonart"]["checked"])  # Am = 8A
        self.assertFalse([r for r in by.values() if r["checked"]])
        self.assertIn("4 Feld(er) stimmen bereits überein", st["result"]["message"])   # BPM, Tonart, Titel, Künstler
        # #142: Standard „nur noch nicht vorhandene“ – vorhandene Felder werden gar nicht gezeigt
        f.set_text("TBPM", "122")
        st = self.act("fetch", [self.idx["n.mp3"]], bpm=True, key=True, genre=True, genre_mode="sub", label=False,
                      date="no", isrc=False, remixer=False, names=False, cover="no", ids=False)
        labels = {r["label"] for r in st["result"]["proposals"]}
        self.assertNotIn("BPM", labels)                # 122 vorhanden, Beatport 124 → unverändert, ausgeblendet
        self.assertNotIn("Tonart", labels)
        self.assertIn("ISRC", labels)                 # fehlt in der Datei → gezeigt (abgewählt)
        self.assertIn("ausgeblendet", st["result"]["message"])
        self.assertEqual(self.mod.ACTIONS[0]["options"][0]["default"], "missing")

    def test_matching_helpers(self):
        m = self.mod
        self.assertEqual(m.split_title("Song (Extended Mix)"), ("Song", "Extended Mix"))
        self.assertEqual(m.split_title("Song [Radio Edit]"), ("Song", "Radio Edit"))
        self.assertEqual(m.split_title("Song (Live)"), ("Song (Live)", ""))
        info = {"title": "Nordlicht", "mix": "Extended Mix", "artist": "Mara Lind", "isrc": "", "duration": 0, "bpid": ""}
        self.assertGreater(m.score(info, TRACKS[1001]), m.score(info, TRACKS[1002]))
        self.assertGreaterEqual(m.score(info, TRACKS[1001]), m.SURE)
        self.assertLess(m.score(info, TRACKS[1002]), m.MAYBE)
        self.assertEqual(m.score(dict(info, isrc="CHA012100001"), TRACKS[1001]), 1.0)
        self.assertEqual(m.key_text({"key": {"name": "Eb Minor"}}, "camelot"), "02A")
        # 3.0.1: nicht-lateinische Titel sind nicht automatisch „gleich“
        jp = {"title": "東京", "mix": "", "artist": "ヨアソビ", "isrc": "", "duration": 0, "bpid": ""}
        ru = {"name": "Москва", "mix_name": "", "artists": [{"name": "Иван"}]}
        self.assertLess(m.score(jp, ru), m.MAYBE)
        self.assertGreaterEqual(m.score(jp, {"name": "東京", "mix_name": "", "artists": [{"name": "ヨアソビ"}]}), m.SURE)
        self.assertEqual(m.norm("Beyoncé & Jay-Z"), "beyonce and jay z")
        self.assertEqual(m._retry_after("3"), 3.0)
        self.assertEqual(m._retry_after("kaputt"), 5.0)
        self.assertLessEqual(m._retry_after("Wed, 21 Oct 2099 07:28:00 GMT"), 30.0)
        self.assertEqual(m.cover_url(TRACKS[1001]), "https://geo-media.beatport.com/image_size/1400x1400/abc.jpg")

    def test_playlists_import(self):
        self.assertEqual(self.s.dj_sources()["sources"], [s for s in self.s.dj_sources()["sources"] if s["id"] != "beatport"])
        with self.assertRaises(ValueError):
            self.mod.playlists(plugins.Context(self.s.plugins.get("beatport"), self.s))            # nicht angemeldet
        self.login()
        self.assertIn("beatport", [x["id"] for x in self.s.dj_sources()["sources"]])
        r = self.s.start_dj_source_list("beatport")
        self.assertTrue(r["ok"], r)
        res = self.wait()["result"]
        self.assertEqual([(p["id"], p["name"]) for p in res["playlists"]], [("7", "Peak Time"), ("8", "Leer")])
        r = self.s.start_pl_source_import("beatport", ["7"])
        self.assertTrue(r["ok"], r)
        res = self.wait()["result"]
        self.assertEqual(res["lists"][0]["count"], 2)
        st = self.s.pl_state(self.s._pls().find_source("beatport", "7")["id"])
        items = st["pl"]["items"]
        self.assertEqual([x["title"].split(" (")[0] for x in items], ["Nordlicht", "Kaltes Glas"])  # Reihenfolge nach position
        self.assertTrue(items[0]["url"].startswith("https://www.beatport.com/track/"))
        self.assertGreaterEqual(res["linked"], 1)                                               # Nordlicht im Tagger
        linked = [x for x in st["pl"]["items"] if x["path"]]
        # erneut holen: Verknüpfungen bleiben
        r = self.s.start_pl_source_import("beatport", ["7"])
        res = self.wait()["result"]
        self.assertGreaterEqual(res["kept"], len(linked))
        self.assertFalse([c for c in self.fake.calls if c[0] != "GET" and "/my/playlists" in c[1]])  # nur lesen


if __name__ == "__main__":
    unittest.main()
