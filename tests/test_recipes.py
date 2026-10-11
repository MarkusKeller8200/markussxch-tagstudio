"""#111: Tag-Rezepte – Aktionen bauen aufeinander auf, Vorschau, Anwenden mit Rückgängig, Speichern als v2.4 + v1."""
import os
import time

from helpers import write_mp3, text, txxx, comm
from test_tagger_tools import Base

import recipes
from id3tags import MP3File, MV


class TestRecipes(Base):
    def setUp(self):
        super().setUp()
        self.p = os.path.join(self.B, "r.mp3")
        write_mp3(self.p, [text("TIT2", "Golden_Hour%20(Extended  Mix)", 3), text("TPE1", "DJ Koze feat. MC Fly vs Max", 3),
                           txxx("FILETYPE", "MP3 / WAV", 3), txxx("COMMENT", "Beatport", 3), comm("", "x", 3),
                           text("TCON", "House / House", 3)], ver=3, audio_seed=71)

    def test_default_recipe(self):
        f = MP3File(self.p)
        r = recipes.defaults()[0]
        p = recipes.plan([f], r)
        ch = {k: new for k, _o, new in p[0]["changes"]}
        self.assertEqual(ch["TIT2"], "Golden Hour (Extended Mix)")
        self.assertEqual(ch["TPE1"], "Dj Koze Feat. Mc Fly Vs Max")
        self.assertEqual(ch["TXXX:FILETYPE"], "MP3")
        self.assertIsNone(ch["TXXX:COMMENT"])
        self.assertIsNone(ch["COMM:"])
        self.assertEqual((p[0]["version"], p[0]["v1"]), (4, "write"))
        recipes.apply(p)
        f.save()
        g = MP3File(self.p)
        self.assertEqual((g.version, g.had_v1, g.text("TIT2")), (4, True, "Golden Hour (Extended Mix)"))
        self.assertIsNone(g.get("COMM:"))

    def test_actions(self):
        f = MP3File(self.p)
        r = {"name": "x", "actions": [{"type": "words", "words": ["DJ", "feat."]}, {"type": "dedupe"},
                                      {"type": "set", "field": "TXXX:ORIG", "value": "%TPE1% – %TIT2%"},
                                      {"type": "case", "mode": "upper", "fields": ["TCON"]}]}
        p = recipes.plan([f], recipes.clean([r])[0])
        ch = {k: new for k, _o, new in p[0]["changes"]}
        self.assertNotIn("TPE1", ch)                                     # schon richtig geschrieben
        self.assertNotIn("TIT2", ch)
        self.assertTrue(ch["TXXX:ORIG"].startswith("DJ Koze feat."))
        self.assertEqual(ch["TCON"], "HOUSE")                           # „House / House“ → ein Wert
        self.assertEqual([recipes.describe(a) for a in r["actions"]][0], "Wörter so schreiben: DJ, feat. (alle Textfelder)")

    def test_session(self):
        from session import Session
        s = Session()
        self.assertEqual(s.recipes()["recipes"][0]["id"], "beatport-download")
        s.start_tag_load(self.B, False)
        while not s.task_status()["done"]:
            time.sleep(0.02)
        i = [os.path.basename(f.path) for f in s.tag_files].index("r.mp3")
        prev = s.tag_recipe([i], "beatport-download")
        self.assertEqual(prev["files"], 1)
        self.assertTrue(any(r["label"] == "ID3" and "v1" in r["new"] for r in prev["rows"]))
        d = s.tag_recipe([i], "beatport-download", apply=True)
        self.assertIn("1 Datei(en) geändert", d["message"])
        self.assertEqual(s.tag_files[i].text("TIT2"), "Golden Hour (Extended Mix)")
        s.do_undo()
        self.assertEqual(s.tag_files[i].text("TIT2"), "Golden_Hour%20(Extended  Mix)")
        saved = s.recipes_save([{"name": "Eigenes", "actions": [{"type": "remove", "fields": ["TCON"]}, {"type": "bogus"}]}])
        self.assertEqual([len(r["actions"]) for r in saved["recipes"]], [1])
        self.assertEqual(s.recipes_reset()["recipes"][0]["id"], "beatport-download")


if __name__ == "__main__":
    import unittest
    unittest.main()
