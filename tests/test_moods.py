"""Stimmung (Mood) als Feld mit Mehrfachwerten (#12): TMOO (v2.4) bzw. TXXX:MOOD (v2.3)."""
import os
import time

from helpers import write_mp3, text, txxx
from test_tagger_tools import Base


class TestMoods(Base):
    def setUp(self):
        super().setUp()
        write_mp3(os.path.join(self.B, "v4.mp3"), [text("TIT2", "Vier"), text("TMOO", "Dark\x00Driving")], audio_seed=51)
        write_mp3(os.path.join(self.B, "v3.mp3"), [text("TIT2", "Drei", ver=3), txxx("mood", "Happy; Dark", ver=3)],
                  ver=3, audio_seed=52)
        write_mp3(os.path.join(self.B, "leer.mp3"), [text("TIT2", "Leer")], audio_seed=53)
        from session import Session
        self.s = Session()
        self.s.start_tag_load(self.B, False)
        for _ in range(500):
            if self.s.task_status().get("done"):
                break
            time.sleep(0.02)
        self.idx = {os.path.basename(f.path): i for i, f in enumerate(self.s.tag_files)}

    def f(self, n):
        return self.s.tag_files[self.idx[n]]

    def test_read_and_common(self):
        import moods
        self.assertEqual(moods.values(self.f("v4.mp3")), ["Dark", "Driving"])
        self.assertEqual(moods.values(self.f("v3.mp3")), ["Happy", "Dark"])      # „;“ getrennt, TXXX klein geschrieben
        d = self.s.tag_detail([self.idx["v4.mp3"], self.idx["v3.mp3"]])
        self.assertEqual(d["mood"]["all"], ["Dark"])
        self.assertEqual(sorted(d["mood"]["some"]), [["Driving", 1], ["Happy", 1]])
        one = self.s.tag_detail([self.idx["v4.mp3"]])
        self.assertFalse([x for x in one["fields"] if x["key"] in ("TMOO", "TXXX:MOOD")])   # nicht bei „Weitere Felder“

    def test_edit_undo_and_save(self):
        import moods
        idx = [self.idx["v4.mp3"], self.idx["v3.mp3"], self.idx["leer.mp3"]]
        d = self.s.tag_mood(idx, ["Hypnotic"], ["dark"])
        self.assertIn("3 Datei(en)", d["message"])
        self.assertEqual(moods.values(self.f("v4.mp3")), ["Driving", "Hypnotic"])
        self.assertEqual(moods.values(self.f("leer.mp3")), ["Hypnotic"])
        v3 = self.f("v3.mp3")
        self.assertEqual(moods.keys(v3), ["TXXX:MOOD"])                         # v2.3: TXXX:MOOD, Schreibweise vereinheitlicht
        self.assertEqual(moods.values(v3), ["Happy", "Hypnotic"])
        self.assertEqual(self.s.tag_detail(idx)["mood"]["all"], ["Hypnotic"])
        self.s.do_undo()
        self.assertEqual(moods.values(self.f("v4.mp3")), ["Dark", "Driving"])
        # Vorschläge: Werte im Ordner zuerst (häufigste), dann eigene Liste und Vorgaben
        self.s.set_mood_list("Sunrise\nDark")
        sug = [x["value"] for x in self.s.tag_mood_suggest()]
        self.assertEqual(sug[0], "Dark")
        self.assertIn("Sunrise", sug)
        self.assertIn("Uplifting", sug)
        self.assertEqual(len(sug), len({v.lower() for v in sug}))

    def test_v24_writes_tmoo_and_cleans_txxx(self):
        import moods
        f = self.f("v4.mp3")
        f.set_text("TXXX:MOOD", "Old")
        self.assertEqual(moods.values(f), ["Dark", "Driving", "Old"])
        self.assertTrue(moods.set_values(f, ["Warm-up"]))
        self.assertEqual((moods.keys(f), f.text("TMOO")), (["TMOO"], "Warm-up"))
        self.assertTrue(moods.set_values(f, ["warm-up "]))                     # andere Schreibweise = Änderung
        self.assertTrue(moods.set_values(f, []))
        self.assertEqual(moods.keys(f), [])


if __name__ == "__main__":
    import unittest
    unittest.main()
