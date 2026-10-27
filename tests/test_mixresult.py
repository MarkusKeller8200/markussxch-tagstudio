"""Mix analysieren – Ergebnisse (#387): Tracklist-Zeit, Lücken, Text, CUE, Playlist, Ablage und Sitzung."""
import os
import shutil
import tempfile
import unittest

import mixresult


def rows():
    return [{"start": 85, "end": 310, "track_start": 25, "path": "/m/a.mp3", "artist": "Dan Sushi", "title": "Shadows",
             "tempo": -2.0, "keylock": True, "conf": 0.94, "hits": 99},
            {"start": 360, "end": 390, "track_start": 276, "path": "/m/b.mp3", "artist": "Boxer", "title": "Verde",
             "tempo": 2.0, "keylock": False, "conf": 0.58, "also": ["Boxer - Verde (Dub)"]},
            {"start": 615, "end": 815, "path": "", "artist": "", "title": "Ohne Datei", "tempo": 0, "conf": 0.8}]


class TestLogic(unittest.TestCase):
    def test_new_cleans_and_sorts(self):
        r = mixresult.new("/x/Purified 520.mp3", 1200, list(reversed(rows())), compare={"hit": ["a"], "miss": ["DJ Paulus - Mirage"], "expected": 3})
        self.assertRegex(r["id"], r"^mx_[0-9a-f]{12}$")
        self.assertEqual(r["name"], "Purified 520")
        self.assertEqual([x["title"] for x in r["rows"]], ["Shadows", "Verde", "Ohne Datei"])
        self.assertNotIn("hits", r["rows"][0])
        self.assertEqual(r["compare"]["miss"], ["DJ Paulus - Mirage"])
        self.assertIsNone(mixresult.clean_row({"start": "x"}))

    def test_mark_is_middle_of_transition(self):
        self.assertEqual(mixresult.mark({"start": 85, "track_start": 25}), 55)      # Messung 7: Tracklist 00:48
        self.assertEqual(mixresult.mark({"start": 85}), 85)
        self.assertEqual(mixresult.mark({"start": 85, "track_start": 25, "at": 48}), 48)
        self.assertEqual(mixresult.parse_time("1:02:10"), 3730)
        self.assertEqual(mixresult.parse_time("04:56"), 296)
        self.assertIsNone(mixresult.parse_time("vier"))

    def test_gaps_text_and_cue(self):
        r = mixresult.new("/x/Mix.mp3", 1000, rows())
        g = mixresult.with_gaps(r)
        self.assertTrue(g[0]["gap"])                       # 0–85 s ohne Titel
        self.assertEqual([e.get("n") for e in g if not e.get("gap")], [0, 1, 2])
        self.assertTrue(g[-1]["gap"] and g[-1]["end"] == 1000)
        txt = mixresult.to_text(r)
        self.assertIn("[00:55] Dan Sushi - Shadows", txt)
        self.assertIn("[05:18] Boxer - Verde", txt)
        self.assertIn("[00:00] ID - ID", txt)
        cue = mixresult.to_cue(r, "/x/Mix.cue")
        self.assertIn('FILE "Mix.mp3" MP3', cue)
        self.assertIn("TRACK 01 AUDIO", cue)
        self.assertIn("    INDEX 01 00:00:00", cue)
        self.assertIn('PERFORMER "Dan Sushi"', cue)
        self.assertIn("INDEX 01 00:55:00", cue)
        self.assertIn('FILE "/x/Mix.mp3" MP3', mixresult.to_cue(r, "/anders/Mix.cue"))   # nicht neben dem Mix: voller Pfad
        r["rows"][0]["drop"] = True
        self.assertNotIn("Shadows", mixresult.to_text(r))

    def test_items(self):
        r = mixresult.new("/x/Mix.mp3", 1000, rows())
        it = mixresult.to_items(r)
        self.assertEqual(it[0]["path"], "/m/a.mp3")
        self.assertEqual(it[0]["note"], "00:55 · -2.0 % · 94 %")
        self.assertEqual(it[2]["ref"]["title"], "Ohne Datei")

    def test_store(self):
        d = tempfile.mkdtemp()
        try:
            r = mixresult.save(d, mixresult.new("/x/Mix.mp3", 1000, rows()))
            self.assertEqual(mixresult.load(d, r["id"])["rows"][1]["title"], "Verde")
            lst = mixresult.listing(d)
            self.assertEqual((lst[0]["count"], lst[0]["sure"], lst[0]["exists"]), (3, 2, False))
            with self.assertRaises(ValueError):
                mixresult.load(d, "../böse")
            mixresult.remove(d, r["id"])
            self.assertEqual(mixresult.listing(d), [])
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestSession(unittest.TestCase):
    def setUp(self):
        import core
        self.home = tempfile.mkdtemp()
        self._env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.home
        self._cfg = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = os.path.join(self.home, ".tagstudio.json")
        core.CONFIG_OLD = os.path.join(self.home, ".mp3tagcompare.json")
        from session import Session
        self.s = Session()
        self.mix = os.path.join(self.home, "Mix 520.mp3")
        self.trk = os.path.join(self.home, "a.mp3")
        for p in (self.mix, self.trk):
            with open(p, "wb") as fh:
                fh.write(b"\xff\xfb\x90\x00" * 50)
        rs = rows()
        rs[0]["path"] = self.trk
        self.rid = self.s._mix_store({"mix": self.mix, "duration": 1000, "rows": rs, "version": "1.0",
                                      "compare": {"hit": ["x"], "miss": ["DJ Paulus - Mirage (Extended Mix)"], "expected": 2}})

    def tearDown(self):
        import core
        core.CONFIG, core.CONFIG_OLD = self._cfg
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.home, ignore_errors=True)

    def test_get_edit_and_playlist(self):
        d = self.s.mix_get(self.rid)
        self.assertTrue(d["mix_exists"])
        self.assertEqual([l.get("title") for l in d["lines"] if not l.get("gap")], ["Shadows", "Verde", "Ohne Datei"])
        self.assertTrue(d["lines"][1]["exists"])
        self.assertFalse(d["lines"][2]["exists"])
        d = self.s.mix_set_time(self.rid, 1, "05:36")
        self.assertIn("[05:36] Boxer - Verde", d["text"])
        with self.assertRaises(ValueError):
            self.s.mix_set_time(self.rid, 1, "99:99:99")
        d = self.s.mix_drop(self.rid, 2)
        self.assertEqual(d["dropped"][0]["title"], "Ohne Datei")
        r = self.s.mix_to_playlist(self.rid)
        pl = self.s._pls().get(r["playlist"])
        self.assertEqual((pl["folder"], pl["name"], len(pl["items"])), ("Mixe", "Mix 520", 2))
        self.assertEqual(self.s.mix_get(self.rid)["playlist"], pl["id"])
        self.s.mix_drop(self.rid, 1)
        r2 = self.s.mix_to_playlist(self.rid)                               # zweites Mal: dieselbe Playlist nachführen
        self.assertEqual(r2["playlist"], pl["id"])
        self.assertEqual(len(self.s._pls().get(pl["id"])["items"]), 1)

    def test_export_audio_ideas_delete(self):
        dest = os.path.join(self.home, "out.cue")
        self.assertEqual(self.s.mix_cue_beside(self.rid), os.path.join(self.home, "Mix 520.cue"))
        r = self.s.mix_export_write(self.rid, "cue", dest)
        self.assertTrue(r["ok"])
        self.assertTrue(self.s.mix_export_write(self.rid, "cue", dest)["exists"])          # nie ungefragt ersetzen
        with open(dest, encoding="utf-8-sig") as fh:
            self.assertIn('FILE "Mix 520.mp3" MP3', fh.read())
        self.assertEqual(self.s.mix_export_name(self.rid, "txt"), "Mix 520.txt")
        self.assertTrue(self.s.mix_audio(self.rid, None)["url"].endswith(".mp3"))
        self.assertTrue(self.s.mix_audio(self.rid, 0)["url"].startswith("http://127.0.0.1:"))
        with self.assertRaises(ValueError):
            self.s.mix_audio(self.rid, 2)                                                   # Datei fehlt
        r = self.s.mix_missing_to_ideas(self.rid, "", "Aus Mixen")
        self.assertEqual((r["name"], r["added"]), ("Aus Mixen", 1))
        self.assertEqual(self.s.mix_list()["items"][0]["count"], 3)
        self.assertFalse(self.s.mix_list()["ready"])                                         # Plugin ohne Umgebung
        self.assertEqual(self.s.mix_delete(self.rid)["items"], [])
        self.assertTrue(os.path.isfile(self.mix))                                            # Mix bleibt

    def test_plugin_result_is_stored(self):
        # start_plugin_action legt ein „mix_result“ als Ergebnis ab und gibt die Kennung zurück
        import mixresult as mr
        before = len(mr.listing(self.s._mix_dir()))
        rid = self.s._mix_store({"mix": self.mix, "duration": 10, "rows": []})
        self.assertEqual(len(mr.listing(self.s._mix_dir())), before + 1)
        self.assertEqual(self.s.mix_get(rid)["lines"], [])


if __name__ == "__main__":
    unittest.main()
