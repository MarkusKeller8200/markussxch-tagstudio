"""Tests für das Beatport-Plugin mit nachgebauter Beatport-API (kein Netz nötig)."""
import json
import os
import time
import unittest
import urllib.parse

from helpers import write_mp3, text, txxx
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

    def _tok(self):
        self.token_n += 1
        t = f"AT{self.token_n}"
        self.valid.add(t)
        return 200, {}, json.dumps({"access_token": t, "expires_in": 3600, "refresh_token": f"RT{self.token_n}"}).encode()

    def __call__(self, method, url, *, headers=None, data=None, opener=None, follow=True):
        u = urllib.parse.urlparse(url)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
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
        if p == "/v4/auth/o/token/":
            if q.get("grant_type") == "authorization_code" and q.get("code") == "CODE1":
                return self._tok()
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
        self.assertEqual(sorted(a["id"] for a in info["actions"] if a["where"] == "page"), ["login", "logout", "test"])
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


if __name__ == "__main__":
    unittest.main()
