"""Tests für Bewertung (POPM, #96/#97) und Like (TXXX:TAGSTUDIO, #95)."""
import os
import shutil
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import core  # noqa: E402
import ratings  # noqa: E402
from helpers import frame, text, txxx, write_mp3  # noqa: E402
from id3tags import MP3File  # noqa: E402


class TestRatings(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ts_rt_")
        self._old = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = core.CONFIG_OLD = os.path.join(self.dir, "cfg.json")

    def tearDown(self):
        core.CONFIG, core.CONFIG_OLD = self._old
        shutil.rmtree(self.dir, ignore_errors=True)

    def mp3(self, name, frames):
        p = os.path.join(self.dir, name)
        write_mp3(p, frames)
        return p

    def test_new_popm(self):
        f = MP3File(self.mp3("a.mp3", [text("TIT2", "A")]))
        self.assertEqual(ratings.get_rating(f), 0)
        self.assertFalse(ratings.set_rating(f, 0))                  # nichts anzulegen
        self.assertTrue(ratings.set_rating(f, 4))
        f.save()
        g = MP3File(f.path)
        self.assertEqual(ratings.get_rating(g), 4)
        it = g.get(f"POPM:{ratings.POPM_EMAIL}")
        self.assertEqual(it.payload, ratings.POPM_EMAIL.encode() + b"\x00\xc4")
        with self.assertRaises(ValueError):
            ratings.set_rating(g, 6)

    def test_existing_popm_and_fmps(self):
        counter = b"\x00\x00\x00\x07"
        p = self.mp3("b.mp3", [frame("POPM", b"MusicBee\x00\x40" + counter), txxx("FMPS_Rating", "0.4")])
        f = MP3File(p)
        self.assertEqual(ratings.get_rating(f), 2)
        ratings.set_rating(f, 5)
        f.save()
        g = MP3File(p)
        self.assertEqual(g.get("POPM:MusicBee").payload, b"MusicBee\x00\xff" + counter)   # Zähler bleibt
        self.assertEqual(g.text("TXXX:FMPS_Rating"), "1")
        self.assertNotIn(f"POPM:{ratings.POPM_EMAIL}", g.items)       # kein zweiter Frame
        ratings.set_rating(g, 0)
        self.assertEqual((ratings.get_rating(g), g.text("TXXX:FMPS_Rating")), (0, "0"))

    def test_fmps_only(self):
        f = MP3File(self.mp3("c.mp3", [txxx("FMPS_Rating", "0.6")]))
        self.assertEqual(ratings.get_rating(f), 3)

    def test_like(self):
        p = self.mp3("d.mp3", [txxx("TAGSTUDIO", '{"x":1}')])
        f = MP3File(p)
        self.assertFalse(ratings.get_like(f))
        self.assertTrue(ratings.set_like(f, True))
        self.assertFalse(ratings.set_like(f, True))
        f.save()
        g = MP3File(p)
        self.assertTrue(ratings.get_like(g))
        self.assertEqual(g.text("TXXX:TAGSTUDIO"), '{"x":1,"like":true}')
        ratings.set_like(g, False)
        self.assertEqual(g.text("TXXX:TAGSTUDIO"), '{"x":1}')
        h = MP3File(self.mp3("e.mp3", []))
        ratings.set_like(h, True)
        ratings.set_like(h, False)
        self.assertNotIn("TXXX:TAGSTUDIO", h.items)                 # leer → Feld weg

    def test_session(self):
        from session import Session
        lib = os.path.join(self.dir, "lib")
        os.makedirs(lib)
        for i in range(2):
            write_mp3(os.path.join(lib, f"0{i}.mp3"), [text("TIT2", f"T{i}")], audio_seed=i)
        s = Session()
        s.set_list_cache(False)
        s.start_tag_load(lib, False)
        while not s.task_status()["done"]:
            time.sleep(0.01)
        d = s.tag_set_rating([0, 1], stars=3)
        self.assertEqual(d["rating"], {"value": 3, "mixed": False, "like": False})
        self.assertIn("2 Datei(en)", d["message"])
        self.assertEqual([r["rating"] for r in d["rows"]], [3, 3])
        r = s.player_mark("tag", 1, like="toggle")
        self.assertEqual((r["ok"], r["like"], r["rating"]), (True, True, 3))
        self.assertEqual(s.tag_detail([0, 1])["rating"]["like"], None)   # gemischt
        self.assertTrue(s.media_info("tag", 1)["like"])
        s.do_undo()
        self.assertFalse(ratings.get_like(s.tag_files[1]))
        self.assertFalse(s.player_mark("side", "L", stars=1)["ok"])     # kein Vergleich geladen


if __name__ == "__main__":
    unittest.main()
