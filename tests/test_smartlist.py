"""Smartlists (#272): Regeln prüfen, Werte lesen, filtern, sortieren; Sitzung mit Datenbasis, Aktualisieren, Einfrieren."""
import datetime
import os
import random
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import smartlist  # noqa: E402
from helpers import comm, frame, text, txxx, write_mp3  # noqa: E402


def popm(stars_byte):
    return frame("POPM", b"Windows Media Player 9 Series\x00" + bytes([stars_byte]) + b"\x00\x00\x00\x00")


def v(**kw):
    base = {"artist": "", "title": "", "album": "", "genre": "", "label": "", "comment": "", "year": None, "bpm": None,
            "key": None, "rating": 0.0, "like": False, "mood": [], "energy": None, "added": None, "edited": None,
            "origin": [], "path": kw.get("title", "")}
    base.update(kw)
    return base


class TestClean(unittest.TestCase):
    def test_clean_rules(self):
        r = smartlist.clean({"base": {"kind": "x"}, "match": "any", "sort": "bpm", "desc": 1, "limit": "50",
                             "rules": [{"f": "bpm", "op": "between", "a": "128", "b": "124,0"},
                                       {"f": "nope", "op": "is", "a": 1},
                                       {"f": "genre", "op": "contains", "a": "  "},
                                       {"f": "key", "op": "fits", "a": "Am"},
                                       {"f": "added", "op": "after", "a": "2026-13-01"},
                                       {"f": "like", "op": "yes"}]})
        self.assertEqual(r["base"], {"kind": "library", "pid": ""})
        self.assertEqual((r["match"], r["sort"], r["desc"], r["limit"]), ("any", "bpm", True, 50))
        self.assertEqual(r["rules"], [{"f": "bpm", "op": "between", "a": 124.0, "b": 128.0},
                                      {"f": "key", "op": "fits", "a": ["8A"]}, {"f": "like", "op": "yes"}])
        with self.assertRaises(ValueError):
            smartlist.clean({"base": {"kind": "playlist"}})
        with self.assertRaises(ValueError):
            smartlist.clean("x")
        self.assertEqual(smartlist.clean({"limit": 999999})["limit"], smartlist.LIMIT_MAX)
        self.assertEqual(smartlist.clean(smartlist.default_rules())["rules"][0]["f"], "bpm")


class TestApply(unittest.TestCase):
    def setUp(self):
        now = datetime.datetime(2026, 10, 25, 12, 0).astimezone().timestamp()
        self.now = now
        self.rows = [
            v(title="A", bpm=124.0, rating=4.0, key="8A", genre="Tech House; House", mood=["Dark"], energy=70.0,
              added=now - 3 * 86400, origin=["beatport"], like=True),
            v(title="B", bpm=126.0, rating=5.0, key="9A", genre="Techno", energy=90.0, added=now - 40 * 86400),
            v(title="C", bpm=130.0, rating=4.0, key="3B", genre="House", comment="Opener"),
            v(title="D", bpm=None, rating=0.0, key=None),
        ]

    def run_(self, rules, **kw):
        r = smartlist.clean({"rules": rules, **kw})
        return [x["title"] for x in smartlist.apply(self.rows, r, self.now)]

    def test_rules(self):
        self.assertEqual(self.run_([{"f": "bpm", "op": "between", "a": 124, "b": 128},
                                    {"f": "rating", "op": "gte", "a": 4}]), ["A", "B"])
        self.assertEqual(self.run_([{"f": "bpm", "op": "between", "a": 124, "b": 128},
                                    {"f": "rating", "op": "gte", "a": 4}], match="any"), ["A", "B", "C"])
        self.assertEqual(self.run_([{"f": "genre", "op": "is", "a": "house"}]), ["A", "C"])
        self.assertEqual(self.run_([{"f": "genre", "op": "contains", "a": "tech"}]), ["A", "B"])
        self.assertEqual(self.run_([{"f": "genre", "op": "not_contains", "a": "tech"}]), ["C", "D"])
        self.assertEqual(self.run_([{"f": "key", "op": "fits", "a": "8A"}]), ["A", "B"])
        self.assertEqual(self.run_([{"f": "key", "op": "is", "a": "3B, 9A"}]), ["B", "C"])
        self.assertEqual(self.run_([{"f": "key", "op": "empty"}]), ["D"])
        self.assertEqual(self.run_([{"f": "rating", "op": "empty"}]), ["D"])
        self.assertEqual(self.run_([{"f": "like", "op": "yes"}]), ["A"])
        self.assertEqual(self.run_([{"f": "mood", "op": "contains", "a": "dark"}]), ["A"])
        self.assertEqual(self.run_([{"f": "energy", "op": "lte", "a": 75}]), ["A"])
        self.assertEqual(self.run_([{"f": "added", "op": "days", "a": 7}]), ["A"])
        self.assertEqual(self.run_([{"f": "added", "op": "before", "a": "2026-10-01"}]), ["B"])
        self.assertEqual(self.run_([{"f": "origin", "op": "has", "a": "beatport"}]), ["A"])
        self.assertEqual(self.run_([{"f": "text", "op": "contains", "a": "opener"}]), ["C"])
        self.assertEqual(self.run_([]), ["A", "B", "C", "D"])                     # ohne Regeln: alles

    def test_sort_limit(self):
        self.assertEqual(self.run_([], sort="bpm", desc=True), ["C", "B", "A", "D"])   # fehlende ans Ende
        self.assertEqual(self.run_([], sort="key"), ["C", "A", "B", "D"])
        self.assertEqual(self.run_([], sort="title", limit=2), ["A", "B"])
        r = smartlist.clean({"sort": "random"})
        got = [x["title"] for x in smartlist.apply(self.rows, r, self.now, random.Random(1))]
        self.assertEqual(sorted(got), ["A", "B", "C", "D"])


class TestValues(unittest.TestCase):
    def test_values_from_file(self):
        from id3tags import MP3File
        d = tempfile.mkdtemp(prefix="ts_sm_")
        try:
            p = os.path.join(d, "a.mp3")
            write_mp3(p, [text("TIT2", "Nacht"), text("TPE1", "DJ"), text("TCON", "House"), text("TBPM", "125"),
                          text("TKEY", "Am"), text("TDRC", "2024-05-01"), popm(196), txxx("ENERGY", "8"),
                          txxx("MOOD", "Dark"), txxx("TAGSTUDIO_ADDED", "2026-10-20T10:00:00+02:00"),
                          comm("", "Warm-up")])
            f = MP3File(p)
            f.load()
            val = smartlist.values(f, lambda k: "beatport" if k == "TBPM" else None)
            self.assertEqual((val["title"], val["bpm"], val["key"], val["year"], val["rating"]),
                             ("Nacht", 125.0, "8A", 2024.0, 4.0))
            self.assertEqual((val["comment"], val["mood"], val["origin"]), ("Warm-up", ["Dark"], ["beatport"]))
            self.assertIsNotNone(val["added"])
            self.assertIn(val["energy"], (8.0, 80.0))
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestSession(unittest.TestCase):
    def setUp(self):
        import core
        self.dir = tempfile.mkdtemp(prefix="ts_sms_")
        self._env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.dir
        self._cfg = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = core.CONFIG_OLD = os.path.join(self.dir, "cfg.json")
        self.base = os.path.join(self.dir, "Musik")
        self.lib = os.path.join(self.base, "01_Library")
        os.makedirs(self.lib)
        for n, (name, bpm, stars) in enumerate([("a", "124", 196), ("b", "126", 255), ("c", "130", 196), ("d", "125", 64)]):
            write_mp3(os.path.join(self.lib, f"{name}.mp3"),
                      [text("TIT2", name.upper()), text("TPE1", "DJ"), text("TBPM", bpm), popm(stars)], audio_seed=n + 1)
        import json
        with open(core.CONFIG, "w", encoding="utf-8") as fh:
            json.dump({"base_dir": self.base}, fh)

    def tearDown(self):
        import core
        core.CONFIG, core.CONFIG_OLD = self._cfg
        for k, val in self._env.items():
            if val is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = val
        shutil.rmtree(self.dir, ignore_errors=True)

    def wait(self, s, res):
        self.assertNotEqual(res.get("ok"), False, res)
        while not s.task_status()["done"]:
            time.sleep(0.02)
        st = s.task_status()
        self.assertIsNone(st.get("error"), st)
        return st["result"]

    def test_library_refresh_freeze(self):
        from session import Session
        s = Session()
        info = s.pl_smart_info()
        self.assertIn("bpm", [f["id"] for f in info["fields"]])
        rules = {"base": {"kind": "library"}, "rules": [{"f": "bpm", "op": "between", "a": 124, "b": 128},
                                                        {"f": "rating", "op": "gte", "a": 4}], "sort": "bpm", "desc": True}
        st = s.pl_smart_save("", "Peak", "Smart", rules)
        pid = st["sel"]
        self.assertEqual(st["pl"]["kind"], "smart")
        self.assertTrue(s.pl_smart_stale(pid))
        r = self.wait(s, s.start_pl_smart_refresh(pid))
        self.assertEqual((r["count"], r["scanned"], r["changed"]), (2, 4, True))
        st = s.pl_state(pid)
        self.assertEqual([x["title"] for x in st["pl"]["items"]], ["B", "A"])
        self.assertFalse(s.pl_smart_stale(pid))
        mirror = os.path.join(self.base, "03_Playlists", "Smart", "Peak.m3u8")
        with open(mirror, encoding="utf-8") as fh:
            self.assertIn("b.mp3", fh.read())                                   # S4: M3U8 geschrieben
        with self.assertRaises(ValueError):
            s.pl_add_paths(pid, [os.path.join(self.lib, "c.mp3")], "add")        # von Hand gesperrt
        # Regel ändern → nach Aktualisieren stimmt die Liste
        rules["rules"][1]["a"] = 5
        s.pl_smart_save(pid, "Peak", "Smart", rules)
        self.wait(s, s.start_pl_smart_refresh(pid))
        self.assertEqual([x["title"] for x in s.pl_state(pid)["pl"]["items"]], ["B"])
        r = self.wait(s, s.start_pl_smart_refresh(pid))
        self.assertFalse(r["changed"])
        # Einfrieren → normale Playlist
        st = s.pl_smart_freeze(pid)
        self.assertEqual((st["pl"]["kind"], st["pl"]["rules"]), ("manual", None))
        s.pl_add_paths(pid, [os.path.join(self.lib, "c.mp3")], "add")
        self.assertEqual(len(s.pl_state(pid)["pl"]["items"]), 2)
        s.pl_undo(pid)
        s.pl_undo(pid)
        self.assertEqual(s.pl_state(pid)["pl"]["kind"], "smart")                 # Einfrieren rückgängig

    def test_tagger_and_playlist_base(self):
        from session import Session
        s = Session()
        s.start_tag_load(self.lib, False)
        while not s.task_status()["done"]:
            time.sleep(0.02)
        idx = sorted(i for i, f in enumerate(s.tag_files) if os.path.basename(f.path) in ("c.mp3", "d.mp3"))
        base = s.pl_create("Auswahl", "", idx)["sel"]
        pid = s.pl_smart_save("", "Aus Auswahl", "", {"base": {"kind": "playlist", "pid": base},
                                                       "rules": [{"f": "bpm", "op": "gte", "a": 125}]})["sel"]
        self.wait(s, s.start_pl_smart_refresh(pid))
        self.assertEqual(sorted(x["title"] for x in s.pl_state(pid)["pl"]["items"]), ["C", "D"])
        with self.assertRaises(ValueError):
            s.pl_smart_save("", "Kette", "", {"base": {"kind": "playlist", "pid": pid}})
        # Tagger als Basis: ungespeicherte Änderung zählt sofort
        tid = s.pl_smart_save("", "Tagger", "", {"base": {"kind": "tagger"}, "rules": [{"f": "bpm", "op": "eq", "a": 99}]})["sel"]
        i = next(i for i, f in enumerate(s.tag_files) if f.path.endswith("a.mp3"))
        s.tag_set([i], "TBPM", "99")
        self.wait(s, s.start_pl_smart_refresh(tid))
        self.assertEqual([x["title"] for x in s.pl_state(tid)["pl"]["items"]], ["A"])


if __name__ == "__main__":
    unittest.main()
