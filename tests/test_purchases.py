"""Käufe (#285, #290): Abgleich mit der Bibliothek – dieselbe Datei unter zwei Pfaden, Zuordnen von Hand."""
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import playlists  # noqa: E402
import purchases  # noqa: E402


class TestMatch(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ts_pur_")
        self.a = os.path.join(self.dir, "S", "Lib", "Mara Lind - Nordlicht (Extended Mix).mp3")
        self.b = os.path.join(self.dir, "NAS", "Lib", "Mara Lind - Nordlicht (Extended Mix).mp3")   # gleiche Datei, 2. Pfad
        self.c = os.path.join(self.dir, "S", "Lib", "Mara Lind - Nordlicht (Radio Edit).mp3")
        for p in (self.a, self.b, self.c):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as fh:
                fh.write(b"x" * (100 if p != self.c else 50))
        self.st = purchases.Store(os.path.join(self.dir, "data"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def entry(self, path, title, size, isrc=""):
        return playlists.lib_entry(path, "Mara Lind", title, isrc, 300, "", size)

    def test_same_file_two_paths(self):
        ix = playlists.LibIndex([self.entry(self.a, "Nordlicht (Extended Mix)", 100, "CHA1"),
                                 self.entry(self.b, "Nordlicht (Extended Mix)", 100, "CHA1")])
        self.assertEqual((len(ix), len(ix.dupes)), (1, 1))
        self.st.merge("beatport", "Beatport", [
            {"id": 1, "title": "Nordlicht", "mix": "Extended Mix", "artist": "Mara Lind", "dur": 300, "isrc": "CHA1"},
            {"id": 2, "title": "Nordlicht", "mix": "Extended Mix", "artist": "Mara Lind", "dur": 300}])
        count = self.st.match(ix)
        self.assertEqual(count["library"], 2)                       # vorher: „unklar – mehrere Treffer“
        # verschiedene Dateien mit gleichem Namen bleiben getrennt (andere Grösse)
        ix = playlists.LibIndex([self.entry(self.a, "Nordlicht (Extended Mix)", 100),
                                 self.entry(self.b, "Nordlicht (Extended Mix)", 99)])
        self.assertEqual((len(ix), len(ix.dupes)), (2, 0))
        self.assertEqual(self.st.match(ix)["unclear"], 2)

    def test_link_by_hand(self):
        self.st.merge("beatport", "Beatport", [{"id": 7, "title": "Nordlicht", "mix": "Club Mix", "artist": "Mara Lind"}])
        ix = playlists.LibIndex([self.entry(self.c, "Nordlicht (Radio Edit)", 50)])
        self.st.match(ix)
        it = self.st.data["items"]["beatport:7"]
        self.assertEqual(it["status"], "unclear")
        self.assertTrue(it["reason"].startswith("anderer Mix"))
        self.assertEqual(it["cands"], [self.c])
        self.st.link("beatport:7", self.c)
        self.assertEqual(self.st.match(ix)["library"], 1)            # bleibt bei weiteren Abgleichen
        self.assertEqual(self.st.data["items"]["beatport:7"]["reason"], "von Hand zugeordnet")
        self.st.merge("beatport", "Beatport", [{"id": 7, "title": "Nordlicht", "mix": "Club Mix", "artist": "Mara Lind"}])
        self.assertTrue(self.st.data["items"]["beatport:7"]["linked"])   # auch nach Aktualisieren
        self.st.link("beatport:7", "")
        self.assertEqual(self.st.match(ix)["unclear"], 1)
        with self.assertRaises(ValueError):
            self.st.link("beatport:7", os.path.join(self.dir, "gibt-es-nicht.mp3"))


if __name__ == "__main__":
    unittest.main()


class TestStrictAndCorrect(unittest.TestCase):
    """#338: Zuweisung „streng“, Art der Unklarheit, Ähnlichkeit der Künstler, Korrekturfenster."""

    def e(self, path, artist, title, isrc="", dur=300, sub=""):
        return playlists.lib_entry(path, artist, title, isrc, dur, sub)

    def test_strict_mix_isrc_artist(self):
        ref = {"artist": "Mara Lind", "title": "Nordlicht", "mix": "Original Mix", "isrc": "CHA1", "dur": 300}
        ix = [self.e("/a.mp3", "Mara Lind", "Nordlicht (Extended Mix)", "CHA1")]
        self.assertEqual(playlists.match_ref(ref, ix)["kind"], "isrc")                       # bisher: ISRC genügt
        r = playlists.match_ref(ref, ix, strict=True)
        self.assertEqual((r["status"], r["kind"]), ("unclear", "mix"))                       # streng: anderer Mix
        self.assertEqual(playlists.match_ref(dict(ref, mix="Extended Mix"), ix, strict=True)["status"], "sure")
        noart = [self.e("/b.mp3", "", "Nordlicht")]
        self.assertEqual(playlists.match_ref(dict(ref, isrc=""), noart)["status"], "sure")
        self.assertNotEqual(playlists.match_ref(dict(ref, isrc=""), noart, strict=True)["status"], "sure")
        two = [self.e("/c.mp3", "Mara Lind", "Nordlicht"), self.e("/d.mp3", "Mara Lind", "Nordlicht (Original Mix)")]
        self.assertEqual(playlists.match_ref(dict(ref, isrc=""), two)["kind"], "multi")
        other = [self.e("/e.mp3", "Oskar Vey", "Nordlicht")]
        self.assertEqual(playlists.match_ref(dict(ref, isrc=""), other)["kind"], "artist")
        self.assertEqual(playlists.match_ref(dict(ref, isrc="", title="Ganz anders"), other)["kind"], "missing")

    def test_artist_similarity(self):
        self.assertEqual(playlists.artist_similarity("A & B", "A, B"), 1.0)
        self.assertEqual(playlists.artist_similarity("Mara Lind feat. Oskar", "Oskar & Mara Lind"), 1.0)
        self.assertGreater(playlists.artist_similarity("Mara Lind", "Mara Lynd"), 0.8)
        self.assertLess(playlists.artist_similarity("Mara Lind", "Oskar Vey"), 0.5)
        self.assertEqual(playlists.artist_similarity("", "X"), 0.0)


class TestCorrectSession(unittest.TestCase):
    def setUp(self):
        import core
        self.home = tempfile.mkdtemp()
        self._env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.home
        self._cfg = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = os.path.join(self.home, ".tagstudio.json")
        core.CONFIG_OLD = os.path.join(self.home, ".mp3tagcompare.json")

    def tearDown(self):
        import core
        core.CONFIG, core.CONFIG_OLD = self._cfg
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.home, ignore_errors=True)

    def test_candidates_and_fix(self):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from helpers import write_mp3, text
        from id3tags import MP3File
        from session import Session
        lib = os.path.join(self.home, "Lib")
        os.makedirs(lib)
        p = os.path.join(lib, "Mara Lind - Nordlicht.mp3")
        write_mp3(p, [text("TPE1", "Mara Lind"), text("TIT2", "Nordlicht (Radio Edit)")])
        s = Session()
        st = s._purch()
        st.merge("beatport", "Beatport", [{"id": 7, "title": "Nordlicht", "mix": "Extended Mix", "artist": "Mara Lind"}])
        st.match(playlists.LibIndex([playlists.lib_entry(p, "Mara Lind", "Nordlicht (Radio Edit)")]), strict=True)
        key = next(iter(st.data["items"]))
        c = s.purch_candidates(key)
        self.assertEqual((c["kind"], c["mix_key"], len(c["cands"])), ("mix", "extended", 1))
        self.assertEqual((c["cands"][0]["mix"], c["cands"][0]["artist_sim"]), ("radio", 100))
        s.set_purch_strict(True)
        self.assertTrue(s.purch_state()["strict"])
        with open(os.path.join(lib, "schon da.mp3"), "wb") as fh:
            fh.write(b"x")
        r = s.purch_fix_file(key, p, "Nordlicht", "Extended Mix", "schon da")             # Ziel existiert → nichts
        self.assertFalse(r["ok"])
        self.assertTrue(os.path.isfile(p))
        r = s.purch_fix_file(key, p, "Nordlicht", "Extended Mix", "Mara Lind - Nordlicht (Extended Mix)")
        self.assertTrue(r["ok"] and r["sure"])
        self.assertTrue(r["path"].endswith("(Extended Mix).mp3") and os.path.isfile(r["path"]))
        f = MP3File(r["path"])
        self.assertEqual((f.text("TIT2"), f.text("TIT3")), ("Nordlicht", "Extended Mix"))
        it = s._purch().data["items"][key]
        self.assertEqual((it["status"], it["file"], it.get("linked")), ("library", r["path"], True))


class TestBeatportPlaylistPlan(TestCorrectSession):
    """#334/#335: Aufteilung in Playlists (je 100, je Kaufdatum) – ohne Beatport (Plugin nur nachgebildet)."""

    def test_plan(self):
        from session import Session
        s = Session()
        st = s._purch()
        items = [{"id": i, "title": f"T{i}", "artist": "A", "bought": f"2026-10-{20 + i % 2} 10:00:00"} for i in range(1, 231)]
        items.append({"id": 999, "title": "Vorab", "artist": "A", "preorder": True, "bought": "2026-10-22"})
        st.merge("beatport", "Beatport", items)
        for it in st.data["items"].values():
            it["status"] = "missing"
        calls = []
        s.plugins.call_playlist = lambda pid, fn, *a, **kw: calls.append((fn, a)) or (
            {"playlists_write": True, "buy_prefix": "TagStudio_BUY_"} if fn == "store_settings" else {})
        pv = s.purch_dl_playlist_preview()
        self.assertEqual((pv["count"], [c["count"] for c in pv["chunks"]]), (230, [100, 100, 30]))   # ohne Vorbestellung
        self.assertTrue(pv["chunks"][2]["name"].startswith("TagStudio_DOWNLOAD_") and pv["chunks"][2]["name"].endswith("_3"))
        keys = list(st.data["items"])[:3]
        self.assertEqual(s.purch_dl_playlist_preview(keys)["count"], 3)
        b = s.purch_buy_playlists_preview()
        self.assertEqual([(r["name"], r["count"]) for r in b["rows"]],
                         [("TagStudio_BUY_2026_10_21", 115), ("TagStudio_BUY_2026_10_20", 115)])   # #360: ungeteilt
        b = s.purch_buy_playlists_preview(None, "2026-10-21", "2026-10-21")
        self.assertEqual({r["date"] for r in b["rows"]}, {"2026-10-21"})
        s.plugins.call_playlist = lambda *a, **kw: (_ for _ in ()).throw(ValueError("Plugin aus"))
        self.assertFalse(s.purch_bp_settings()["available"])

    def test_reset(self):
        """#362: erneut zum Download freigeben – Vorschau zählt markierte bzw. fehlende, ohne Download-ID gesondert;
        nach dem Freigeben gilt der Einkauf nicht mehr als „beim Store heruntergeladen“."""
        from session import Session
        s = Session()
        st = s._purch()
        st.merge("beatport", "Beatport", [{"id": 1, "title": "A", "artist": "X", "received": True, "dl": {"order_item_download_id": 11}},
                                          {"id": 2, "title": "B", "artist": "X", "dl": {}},
                                          {"id": 3, "title": "C", "artist": "X", "preorder": True}])
        for it in st.data["items"].values():
            it["status"] = "missing"
        calls = []

        def fake(pid, fn, *a, **kw):
            calls.append((fn, a))
            if fn == "store_settings":
                return {"playlists_write": False, "buy_prefix": "TagStudio_BUY_"}
            if fn == "store_reset_download":
                return {"reset": ["1"], "failed": [], "skipped": ["B"], "url": "u"}
            return {}
        s.plugins.call_playlist = fake
        pv = s.purch_reset_preview()
        self.assertEqual((pv["count"], pv["no_id"], pv["available"]), (2, 1, True))          # ohne Vorbestellung
        self.assertEqual(s.purch_reset_preview(["beatport:1"])["count"], 1)
        self.assertTrue(s.start_purch_reset()["ok"])
        r = None
        for _ in range(200):
            t = s.task_status()
            if t.get("done"):
                r = t["result"]
                break
            time.sleep(0.02)
        self.assertEqual(r["reset"], ["1"])
        self.assertEqual([len(a[0]) for fn, a in calls if fn == "store_reset_download"], [2])
        self.assertFalse(st.data["items"]["beatport:1"].get("received"))


class TestEndSessions(unittest.TestCase):
    def test_end_store_sessions(self):
        """#366: beim Beenden nur aktive Sitzungen abmelden; Fehler halten das Beenden nicht auf."""
        from session import Session
        s = Session()
        calls = []
        s.plugins.store_sources = lambda: [{"id": "beatport"}, {"id": "other"}]

        def fake(pid, fn, *a, **kw):
            calls.append((pid, fn))
            if fn == "store_session":
                return {"active": pid == "beatport"}
            if fn == "store_logout" and pid == "beatport":
                return {"ok": True}
            raise RuntimeError("nicht unterstützt")
        s.plugins.call_playlist = fake
        self.assertEqual(s.end_store_sessions(), ["beatport"])
        self.assertIn(("beatport", "store_logout"), calls)
        self.assertNotIn(("other", "store_logout"), calls)


if __name__ == "__main__":
    unittest.main()
