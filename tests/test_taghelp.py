"""#158: Hilfe – Tag-Übersicht, Bibliotheks-Scan mit Zählern, Feld-Filter."""
import os
import time

from helpers import write_mp3, text, txxx, geob
from test_tagger_tools import Base

import taghelp


class TestTagHelp(Base):
    def setUp(self):
        super().setUp()
        write_mp3(os.path.join(self.B, "a.mp3"), [text("TIT2", "A"), text("TPE1", "X"), txxx("ENERGY", "70"),
                                                  txxx("CATALOGNUMBER", "C1"), geob("Serato Markers2", b"x")], audio_seed=61)
        write_mp3(os.path.join(self.B, "b.mp3"), [text("TIT2", "B"), txxx("ENERGY", "60"), txxx("MEINFELD", "1")],
                  audio_seed=62)
        write_mp3(os.path.join(self.B, "c.mp3"), [text("TIT2", "C")], audio_seed=63)
        from session import Session
        self.s = Session()

    def wait(self):
        for _ in range(500):
            st = self.s.task_status()
            if st.get("done"):
                return st
            time.sleep(0.02)
        self.fail("hängt")

    def test_overview_without_scan(self):
        d = self.s.help_tags(self.B)
        ids = [c["id"] for c in d["chapters"]]
        self.assertEqual(ids[:3], ["ident", "people", "music"])
        self.assertIn("analysis", ids)
        self.assertIn("custom", ids)
        rows = {r["key"]: r for c in d["chapters"] if c.get("kind") != "analysis" for r in c["rows"]}
        self.assertEqual(rows["TPE1"]["meaning"], "Hauptkünstler / Interpreten")
        self.assertTrue(rows["TBPM"]["dj"])
        self.assertIsNone(rows["TPE1"]["count"])
        prog = next(c for c in d["chapters"] if c["id"] == "programs")["rows"]
        self.assertTrue(any(r["key"] == "GEOB:Serato*" and r["src"] == "serato" for r in prog))
        self.assertEqual(len(d["software"]), 7)
        # alle ID3v2.4-Frames kommen in den Kapiteln 1–10 vor
        import id3frames
        v24 = {f for f, (_a, v, _l) in id3frames.SPEC.items() if "4" in v} - {"CHAP", "CTOC"}
        chap = {k for c in taghelp.CHAPTERS for k in c[3]}
        self.assertEqual(sorted(v24 - chap), [])

    def test_scan_counts_cache_and_filter(self):
        r = self.s.start_tag_scan(self.B)
        self.assertTrue(r["ok"], r)
        st = self.wait()
        self.assertIsNone(st["error"], st)
        self.assertEqual(st["result"]["files"], 4)                   # Base: 3.mp3
        d = self.s.help_tags(self.B)
        self.assertEqual(d["scan"]["files"], 4)
        rows = {r["key"]: r for c in d["chapters"] if c.get("kind") != "analysis" for r in c["rows"]}
        self.assertEqual(rows["TIT2"]["count"], 4)
        self.assertEqual(rows["TPE1"]["count"], 1)
        self.assertEqual(rows["TXXX"]["count"], 2)
        custom = {r["key"]: r["count"] for r in next(c for c in d["chapters"] if c["id"] == "custom")["rows"]}
        self.assertEqual((custom["TXXX:ENERGY"], custom["TXXX:CATALOGNUMBER"], custom["TXXX:MEINFELD"]), (2, 1, 1))
        self.assertEqual(rows["TXXX:CATALOGNUMBER"]["src"] if "TXXX:CATALOGNUMBER" in rows else
                         next(r for r in next(c for c in d["chapters"] if c["id"] == "custom")["rows"]
                              if r["key"] == "TXXX:CATALOGNUMBER")["src"], "beatport")
        prog = {r["key"]: r["count"] for r in next(c for c in d["chapters"] if c["id"] == "programs")["rows"]}
        self.assertEqual(prog["GEOB:Serato*"], 1)
        ana = {r["key"]: r["count"] for r in next(c for c in d["chapters"] if c["id"] == "analysis")["rows"] if r["key"]}
        self.assertEqual(ana["TXXX:ENERGY"], 2)
        self.assertTrue(taghelp.cached(self.B))
        self.assertTrue(os.path.isfile(taghelp._cache_path(self.B)))
        # Feld-Filter im Tagger
        self.s.start_tag_load(self.B, False)
        self.wait()
        names = [os.path.basename(f.path) for f in self.s.tag_files]
        f = self.s.tag_field_filter("TXXX:ENERGY")
        self.assertEqual(sorted(names[i] for i in f["has"]), ["a.mp3", "b.mp3"])
        self.assertEqual([names[i] for i in self.s.tag_field_filter("GEOB:Serato*")["has"]], ["a.mp3"])
        self.assertEqual(len(self.s.tag_field_filter("TXXX")["has"]), 2)

    def test_docs(self):
        d = self.s.help_docs()
        self.assertIn("TagStudio", d["readme"]["text"])
        self.assertIn("| Frame |", d["id3"]["text"])
        self.assertEqual(d["readme"]["lang"], "de")
        en = self.s.help_docs("en")                                             # #219: englische Fassungen
        for k in ("readme", "id3", "plugins"):
            self.assertEqual(en[k]["lang"], "en", k)
        self.assertIn("Features at a glance", en["readme"]["text"])
        self.assertIn("Principles", en["id3"]["text"])
        self.assertIn("Where do plugins live?", en["plugins"]["text"])
        gsw = self.s.help_docs("gsw-u-sd-chzh")                                 # Zürichdeutsch: deutsche Dokumente
        self.assertEqual(gsw["readme"]["text"], d["readme"]["text"])
        self.assertTrue(d["readme"]["text"].startswith("# MarKusSXCH TagStudio – Handbuch"))   # #373: docs/HANDBUCH.md
        self.assertTrue(en["readme"]["text"].startswith("# MarKusSXCH TagStudio – Manual"))
        import session_help
        from unittest import mock
        with mock.patch.dict(session_help.DOCS, {"readme": ("Handbuch", os.path.join("docs", "GIBTSNICHT.md"))}):
            old = self.s.help_docs("en")["readme"]                              # älteres Paket: Handbuch im README
        self.assertEqual(old["lang"], "en")
        self.assertIn("MarKusSXCH TagStudio", old["text"])


if __name__ == "__main__":
    import unittest
    unittest.main()
