"""Tests für Tonarten / Camelot (keys.py + Sitzung)."""
import os
import time
import unittest

from helpers import write_mp3, text
from test_tagger_tools import Base

import keys


class TestParse(unittest.TestCase):
    def test_camelot_and_openkey(self):
        p = keys.parse_key
        for s in ("8A", "08a", "8 A", " 8A "):
            self.assertEqual(p(s), "8A")
        self.assertEqual(p("12B"), "12B")
        self.assertEqual(p("1m"), "8A")     # Open Key 1m = a-Moll
        self.assertEqual(p("1d"), "8B")     # Open Key 1d = C-Dur
        self.assertEqual(p("6d"), "1B")     # H-Dur
        self.assertIsNone(p("13A"))
        self.assertIsNone(p(""))
        self.assertIsNone(p(None))
        self.assertIsNone(p("o"))

    def test_musical(self):
        p = keys.parse_key
        cases = {"Am": "8A", "A min": "8A", "A minor": "8A", "a": "8A", "Amin": "8A", "C": "8B", "Cmaj": "8B",
                 "C major": "8B", "G": "9B", "Em": "9A", "F#m": "11A", "Gbm": "11A", "F♯m": "11A", "Db": "3B",
                 "C#": "3B", "D♭": "3B", "Ebm": "2A", "D#m": "2A", "Abm": "1A", "G#m": "1A", "B": "1B",
                 "Bb": "6B", "Bbm": "3A", "E": "12B", "C#m": "12A", "Dbm": "12A", "Fm": "4A", "F": "7B"}
        for s, c in cases.items():
            self.assertEqual(p(s), c, s)

    def test_german(self):
        p = keys.parse_key
        cases = {"a-Moll": "8A", "A-Dur": "11B", "Fis-Moll": "11A", "Es-Dur": "5B", "es-moll": "2A",
                 "H-Moll": "10A", "B-Dur": "6B", "As-Dur": "4B", "Cis-Moll": "12A", "C Dur": "8B"}
        for s, c in cases.items():
            self.assertEqual(p(s), c, s)

    def test_all_codes_roundtrip(self):
        for code, mus, ok in keys.wheel():
            self.assertEqual(keys.parse_key(code), code)
            self.assertEqual(keys.parse_key(mus), code, mus)
            self.assertEqual(keys.parse_key(ok), code, ok)
        self.assertEqual(len(keys.wheel()), 24)

    def test_format_and_compatible(self):
        self.assertEqual(keys.format_key("8A", "musical"), "Am")
        self.assertEqual(keys.format_key("8A", "openkey"), "1m")
        self.assertEqual(keys.format_key("1B", "openkey"), "6d")
        self.assertEqual(keys.format_key("1A", "camelot"), "01A")    # führende Null
        self.assertEqual(keys.format_key("12B", "camelot"), "12B")
        self.assertEqual(keys.plan_notation([1], "camelot", lambda f, k: "1A")[0][0][3], "01A")   # 1A → 01A umschreiben
        self.assertEqual(keys.plan_notation([1], "camelot", lambda f, k: "01A")[0], [])
        self.assertEqual(keys.format_key("2B", "musical"), "F#")
        self.assertEqual(keys.format_key("", "musical"), "")
        self.assertEqual(keys.compatible("8A"), ["8A", "9A", "7A", "8B"])
        self.assertEqual(keys.compatible("12B"), ["12B", "1B", "11B", "12A"])
        self.assertEqual(keys.compatible("1A"), ["1A", "2A", "12A", "1B"])
        self.assertLess(keys.sort_value("1A"), keys.sort_value("1B"))
        self.assertLess(keys.sort_value("1B"), keys.sort_value("2A"))
        self.assertEqual(keys.sort_value(None), 999)


class TestSession(Base):
    def test_key_session(self):
        from session import Session
        write_mp3(os.path.join(self.B, "4.mp3"), [text("TIT2", "y"), text("TKEY", "Am")], audio_seed=4)
        write_mp3(os.path.join(self.B, "5.mp3"), [text("TIT2", "z"), text("TKEY", "irgendwas")], audio_seed=5)
        s = Session()
        s.start_tag_load(self.dir, True)
        while not s.task_status()["done"]:
            time.sleep(0.02)
        rows = s.tag_rows()["rows"]
        byname = {r["name"]: r for r in rows}
        self.assertEqual(byname["4.mp3"]["camelot"], "8A")
        self.assertIsNone(byname["5.mp3"]["camelot"])
        st = s.tagger_settings()["keys"]
        self.assertEqual(st["notation"], "camelot")
        self.assertEqual(len(st["wheel"]), 24)

        i4, i5 = byname["4.mp3"]["i"], byname["5.mp3"]["i"]
        self.assertEqual(s.tag_detail([i4])["common"]["TKEY"]["camelot"], "8A")
        pv = s.tag_key_convert([i4, i5], "camelot", False)
        self.assertEqual((pv["count"], pv["unknown_count"]), (1, 1))
        d = s.tag_key_convert([i4, i5], "camelot", True)
        self.assertEqual(d["rows"][0]["TKEY"], "08A")     # Camelot immer zweistellig
        s.do_undo()
        self.assertEqual(s.tag_rows()["rows"][i4]["TKEY"], "Am")

        s.tag_key_notation("openkey")
        d = s.tag_key_set([0, 1], "9A")
        self.assertEqual(d["common"]["TKEY"], {"value": "2m", "mixed": False, "camelot": "9A"})
        s.tag_key_notation("musical")
        self.assertEqual(s.tag_key_set([0], "10A")["common"]["TKEY"]["value"], "Bm")
        self.assertEqual(s.tag_key_set([0], "")["common"]["TKEY"]["value"], "")
        with self.assertRaises(ValueError):
            s.tag_key_set([0], "Quatsch")
        with self.assertRaises(ValueError):
            s.tag_key_notation("x")
        self.assertEqual(Session().tagger_settings()["keys"]["notation"], "musical")   # gemerkt


if __name__ == "__main__":
    unittest.main()
