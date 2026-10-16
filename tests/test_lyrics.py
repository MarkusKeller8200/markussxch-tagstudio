"""#183: Plugin „Liedtexte“ (LRCLIB) mit nachgebautem Dienst – kein Netz nötig.
Antworten im dokumentierten LRCLIB-Format (https://lrclib.net/docs). Testtexte sind frei erfunden."""
import json
import os
import time
import unittest
import urllib.parse

from helpers import write_mp3, text
from test_tagger_tools import Base

import id3tags
from id3tags import MP3File

SYNCED = "[ar:Mara Lind]\n[00:12.30]Erste Zeile im Nebel\n[00:15.80]Zweite Zeile am Ufer\n[01:02.05][01:30.50]Refrain hier\n"
PLAIN = "Erste Zeile im Nebel\nZweite Zeile am Ufer\nRefrain hier"
REC = {"id": 4711, "trackName": "Nordlicht", "artistName": "Mara Lind", "albumName": "Nachtfahrt EP", "duration": 372,
       "instrumental": False, "plainLyrics": PLAIN, "syncedLyrics": SYNCED}
REC_REMIX = dict(REC, id=4712, trackName="Nordlicht (Club Remix)", duration=410, syncedLyrics="[00:01.00]Remix")
REC_INSTR = {"id": 900, "trackName": "Kaltes Glas", "artistName": "Mara Lind", "albumName": "", "duration": 340,
             "instrumental": True, "plainLyrics": None, "syncedLyrics": None}


class FakeLrclib:
    def __init__(self):
        self.calls = []
        self.down = False                      # LRCLIB antwortet mit 503 (überlastet/Wartung)

    def __call__(self, url, headers=None):
        u = urllib.parse.urlparse(url)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        self.calls.append((u.path, q, dict(headers or {})))
        js = lambda d, st=200: (st, {}, json.dumps(d).encode())        # noqa: E731
        if u.netloc != "lrclib.net":
            return 404, {}, b""
        if self.down:
            return 503, {"Retry-After": "0"}, b"Service Unavailable"
        if u.path == "/api/search" and q.get("q", "").lower() == "mara lind morgenrot":   # nur per Freitext auffindbar
            return js([dict(REC, id=5000, trackName="Morgenrot", syncedLyrics="[00:01.00]Morgen")])
        if u.path == "/api/get":
            if not q.get("album_name"):
                return js({"code": 400, "name": "QueryValidationFailed"}, 400)
            if q.get("track_name") == "Nordlicht" and q.get("artist_name") == "Mara Lind":
                return js(REC)
            return js({"code": 404, "name": "TrackNotFound"}, 404)
        if u.path == "/api/search":
            t = (q.get("track_name") or q.get("q") or "").lower()
            if "nordlicht" in t:
                return js([REC_REMIX, REC])
            if "kaltes" in t:
                return js([REC_INSTR])
            return js([])
        return 404, {}, b""


class TestLrc(unittest.TestCase):
    def test_parse_and_sylt(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("lyr", os.path.join(os.path.dirname(__file__), "..", "plugins", "lyrics", "plugin.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        lines = m.parse_lrc(SYNCED)
        self.assertEqual(lines, [(12300, "Erste Zeile im Nebel"), (15800, "Zweite Zeile am Ufer"),
                                 (62050, "Refrain hier"), (90500, "Refrain hier")])     # Kopfzeile übergangen
        self.assertEqual(m.parse_lrc("[1:02.5]x\n[00:01.123]y"), [(1123, "y"), (62500, "x")])  # Zehntel, Tausendstel
        self.assertEqual(m.plain_from_lrc(SYNCED), "Erste Zeile im Nebel\nZweite Zeile am Ufer\nRefrain hier\nRefrain hier")
        desc = id3tags._describe_frame("SYLT", m.sylt_payload(lines, "deu"))
        self.assertIn("4 Zeile(n)", desc)
        self.assertIn("[0:12.3] Erste Zeile im Nebel", desc)
        self.assertEqual(m.clean_lang("DEU"), "deu")
        self.assertEqual(m.clean_lang("de"), "eng")


class TestLyricsPlugin(Base):
    def setUp(self):
        super().setUp()
        write_mp3(os.path.join(self.B, "n.mp3"), [text("TIT2", "Nordlicht"), text("TPE1", "Mara Lind"),
                                                 text("TALB", "Nachtfahrt EP")], audio_seed=11)
        write_mp3(os.path.join(self.B, "o.mp3"), [text("TIT2", "Nordlicht"), text("TPE1", "Mara Lind")], audio_seed=12)
        write_mp3(os.path.join(self.B, "k.mp3"), [text("TIT2", "Kaltes Glas"), text("TPE1", "Mara Lind")], audio_seed=13)
        write_mp3(os.path.join(self.B, "u.mp3"), [text("TIT2", "Gibt es nicht"), text("TPE1", "Niemand")], audio_seed=14)
        from session import Session
        self.s = Session()
        self.s.start_tag_load(self.B, False)
        self.wait()
        p = self.s.plugins.get("lyrics")
        self.assertIsNotNone(p, "Plugin fehlt")
        mod = p.load()
        self.assertIsNotNone(mod, p.error)
        self.mod, self._orig = mod, mod.http_get
        self.fake = FakeLrclib()
        mod.http_get = self.fake
        self._iv = dict(mod.INTERVALS)
        for k in mod.INTERVALS:
            mod.INTERVALS[k] = 0
        self.idx = {os.path.basename(f.path): i for i, f in enumerate(self.s.tag_files)}

    def tearDown(self):
        self.mod.http_get = self._orig
        self.mod.INTERVALS.update(self._iv)
        super().tearDown()

    def wait(self):
        for _ in range(500):
            st = self.s.task_status()
            if st.get("done"):
                return st
            time.sleep(0.02)
        self.fail("hängt")

    def act(self, aid, names=(), **opts):
        r = self.s.start_plugin_action("lyrics", aid, [self.idx[n] for n in names], opts)
        self.assertTrue(r["ok"], r)
        st = self.wait()
        self.assertIsNone(st["error"], st)
        return st["result"]

    def apply(self, res, rows):
        r = self.s.plugin_apply(res["proposals_token"], [x["id"] for x in rows])
        self.assertTrue(r["ok"], r)
        return r

    def test_fetch_match_and_fallback(self):
        res = self.act("fetch", ["n.mp3", "o.mp3", "k.mp3", "u.mp3"], what="both", id=True)
        self.assertIn("2 gefunden", res["message"])
        self.assertIn("1 ohne Text (instrumental)", res["message"])
        self.assertIn("1 nicht gefunden", res["message"])
        # mit Album: genaue Abfrage; ohne Album: gleich die Suche (kein 400er als „nicht gefunden“)
        gets = [c for c in self.fake.calls if c[0] == "/api/get"]
        self.assertEqual(len(gets), 1)
        self.assertEqual(gets[0][1]["duration"], str(int(round(self.s.tag_files[self.idx["n.mp3"]].duration))))
        self.assertTrue(all(c[2].get("User-Agent", "").startswith("TagStudio/") for c in self.fake.calls))
        by = {(r["name"], r["label"]): r for r in res["proposals"]}
        self.assertEqual(by[("n.mp3", "Liedtext (USLT)")]["new"], PLAIN)
        self.assertIn("4 Zeilen", by[("n.mp3", "Synchronisierter Liedtext (SYLT)")]["new"])
        self.assertEqual(by[("n.mp3", "LRCLIB-ID")]["new"], "4711")
        self.assertNotIn(("n.mp3", "LRC-Datei"), by)                     # .lrc nur mit Einstellung
        # Suche: Original statt Remix gewählt (Länge/Titel)
        self.assertEqual(by[("o.mp3", "LRCLIB-ID")]["new"], "4711")
        self.assertNotIn("k.mp3", {r["name"] for r in res["proposals"]})

    def test_trail_freetext_and_outage(self):
        write_mp3(os.path.join(self.B, "m.mp3"), [text("TIT2", "Morgenrot"), text("TPE1", "Mara Lind")], audio_seed=21)
        self.s.start_tag_load(self.B, False)
        self.wait()
        self.idx = {os.path.basename(f.path): i for i, f in enumerate(self.s.tag_files)}
        res = self.act("fetch", ["m.mp3", "u.mp3"], what="both", id=True)
        log = "\n".join(res["log"])
        self.assertIn("Freitext „Mara Lind Morgenrot“: 1 Treffer", log)            # 3. Stufe gefunden
        self.assertIn("genaue Abfrage übersprungen (Album fehlt)", log)
        self.assertIn("u.mp3: nicht gefunden – gesucht:", log)                     # nachvollziehbar
        self.assertIn("Suche Titel + Künstler „Gibt es nicht · Niemand“: 0 Treffer", log)
        self.assertIn("steht im Protokoll", res["message"])
        self.assertEqual({r["name"] for r in res["proposals"]}, {"m.mp3"})
        # Ausfall: klar gemeldet, nach drei Ausfällen in Folge nicht weiter anfragen
        self.fake.down = True
        names = ["n.mp3", "o.mp3", "k.mp3", "u.mp3", "m.mp3"]
        res = self.act("fetch", names, what="both", id=True)
        self.assertIn("5 nicht abgefragt – LRCLIB war nicht erreichbar", res["message"])
        self.assertNotIn("nicht gefunden", res["message"])
        self.assertIn("LRCLIB nicht erreichbar – lrclib.net: HTTP 503 (Dienst überlastet oder in Wartung)", "\n".join(res["log"]))
        n_before = len(self.fake.calls)
        self.act("fetch", names, what="both", id=True)
        self.assertLessEqual(len(self.fake.calls) - n_before, 3 * 3)              # höchstens 3 Titel × 3 Versuche
        res = self.act("test")
        self.assertIn("LRCLIB nicht erreichbar", res["message"])

    def test_versions(self):
        m = self.mod
        info = {"title": "Nordlicht", "mix": "", "artist": "Mara Lind", "duration": 0}
        orig = {"title": "Nordlicht", "mix": "", "artists": ["Mara Lind"]}
        ext = {"title": "Nordlicht", "mix": "Extended Mix", "artists": ["Mara Lind"]}
        remix = {"title": "Nordlicht", "mix": "Club Remix", "artists": ["Mara Lind"]}
        live = {"title": "Nordlicht", "mix": "Live", "artists": ["Mara Lind"]}
        self.assertEqual(m.version_score(info, orig), m.version_score(info, ext))   # Extended = gleicher Text
        self.assertLess(m.version_score(info, remix), m.version_score(info, orig) - 0.1)
        self.assertLess(m.version_score(info, live), m.SURE)
        c, _s = m.best(info, [remix, orig])
        self.assertIs(c, orig)
        c, _s = m.best(dict(info, mix="Club Remix"), [orig, remix])
        self.assertIs(c, remix)

    def test_apply_save_and_protect_existing(self):
        f = self.s.tag_files[self.idx["n.mp3"]]
        f.set_text("USLT:", "Eigener Text")
        res = self.act("fetch", ["n.mp3"], what="both", id=False)
        by = {r["label"]: r for r in res["proposals"]}
        self.assertFalse(by["Liedtext (USLT)"]["checked"])                # vorhandener Text: nie vorausgewählt
        self.assertIn("nur mit Häkchen", by["Liedtext (USLT)"]["hint"])
        self.assertTrue(by["Synchronisierter Liedtext (SYLT)"]["checked"])
        self.apply(res, [r for r in res["proposals"] if r["checked"]])
        self.assertEqual(f.text("USLT:"), "Eigener Text")
        self.assertIsNotNone(f.get("SYLT"))
        self.s.start_save()
        self.wait()
        g = MP3File(f.path)
        self.assertEqual(g.text("USLT:"), "Eigener Text")
        self.assertIn("[0:15.8] Zweite Zeile am Ufer", g.get("SYLT").display())
        # erneut: SYLT vorhanden → nicht vorausgewählt; USLT mit Häkchen ersetzen
        res = self.act("fetch", ["n.mp3"], what="both", id=False)
        by = {r["label"]: r for r in res["proposals"]}
        self.assertFalse(by["Synchronisierter Liedtext (SYLT)"]["checked"])
        self.apply(res, [by["Liedtext (USLT)"]])
        self.assertEqual(self.s.tag_files[self.idx["n.mp3"]].text("USLT:"), PLAIN)

    def test_lrc_only_with_setting(self):
        mp3 = self.s.tag_files[self.idx["n.mp3"]].path
        lrc = os.path.splitext(mp3)[0] + ".lrc"
        res = self.act("settings", (), lrc=True, lang="deu")
        self.assertIn(".lrc-Datei ja", res["message"])
        self.assertIn(".lrc-Datei: ja", self.mod.status(self._ctx()))
        res = self.act("fetch", ["n.mp3"], what="synced", id=False)
        by = {r["label"]: r for r in res["proposals"]}
        self.assertNotIn("Liedtext (USLT)", by)                            # nur synchronisiert gewählt
        self.assertIn("(deu)", by["Synchronisierter Liedtext (SYLT)"]["new"])
        self.assertTrue(by["LRC-Datei"]["checked"])
        self.assertFalse(os.path.exists(lrc))                              # erst beim Übernehmen
        self.apply(res, [by["LRC-Datei"]])
        with open(lrc, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), SYNCED.strip() + "\n")
        # vorhandene .lrc: nicht vorausgewählt
        res = self.act("fetch", ["n.mp3"], what="synced", id=False)
        self.assertFalse({r["label"]: r for r in res["proposals"]}["LRC-Datei"]["checked"])
        # Begleitdatei nur neben dem eigenen MP3 und nur .lrc
        self.assertFalse(self.s._sidecar_ok(mp3, os.path.join(self.dir, "n.lrc")))
        self.assertFalse(self.s._sidecar_ok(mp3, os.path.splitext(mp3)[0] + ".txt"))
        self.assertTrue(self.s._sidecar_ok(mp3, lrc))
        self.act("settings", (), lrc=False, lang="xx")
        self.assertIn(".lrc-Datei: nein · Sprache: eng", self.mod.status(self._ctx()))

    def _ctx(self):
        import plugins
        return plugins.Context(self.s.plugins.get("lyrics"))


if __name__ == "__main__":
    unittest.main()
