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
        self.token_n = 0
        self.valid = set()
        self.old_account = False

    def _tok(self):
        self.token_n += 1
        t = f"AT{self.token_n}"
        self.valid.add(t)
        return 200, {}, json.dumps({"access_token": t, "expires_in": 3600, "refresh_token": f"RT{self.token_n}"}).encode()

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
                return self._tok()
            if q.get("grant_type") == "refresh_token" and q.get("refresh_token", "").startswith("RT"):
                return self._tok()
            return 400, {}, b"{}"
        if not auth.startswith("Bearer ") or auth[7:] not in self.valid:
            return 401, {}, b"{}"
        if p == "/v4/my/account/myaccount/" and not self.old_account:     # offizieller Pfad (Doku)
            return 200, {}, json.dumps({"username": "marku", "email": "m@example.org"}).encode()
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
                 "order_item_download_id": 502, "audio_format": {"name": "mp3"}},
                {"id": 2002, "name": "Vorbestellt", "artists": [{"name": "X"}], "pre_order": True, "order_item_download_id": 503}]}).encode()
        if p == "/v4/my/downloads/502/":
            return 200, {}, json.dumps({"id": 502, "download_url": "https://dl.beatport.com/sig/abc.mp3"}).encode()
        if p == "/v4/my/playlists/":                       # #284: eigene Playlists (Form nach API v4, Seiten)
            return 200, {}, json.dumps({"results": [{"id": 7, "name": "Peak Time", "track_count": 2},
                                                    {"id": 8, "name": "Leer", "track_count": 0}]}).encode()
        if p == "/v4/my/playlists/7/":
            return 200, {}, json.dumps({"id": 7, "name": "Peak Time"}).encode()
        if p == "/v4/my/playlists/7/tracks/":
            return 200, {}, json.dumps({"results": [{"position": 2, "track": TRACKS[1003]},
                                                    {"position": 1, "track": TRACKS[1001]}]}).encode()
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
        self.assertEqual(sorted(a["id"] for a in info["actions"] if a["where"] == "page"), ["download", "login", "logout", "purchases", "test"])
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
            st = self.act("download", dest=inbox, folders=self.B, count=5)
            self.assertIn("nichts zu laden", st["result"]["message"])                  # nicht doppelt
            self.assertEqual(len(seen), 1)
        finally:
            self.mod._urlopen = orig

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
        """Konto: zuerst offizieller Pfad /my/account/myaccount/, sonst der bisherige /my/account/."""
        self.login()
        self.assertIn("/v4/my/account/myaccount/", [c[1] for c in self.fake.calls])
        self.fake.old_account = True
        st = self.act("test")
        self.assertIn("marku", st["result"]["message"])

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
