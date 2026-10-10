"""Tests für Audio-Merkmale (features.py + Sitzung + Export)."""
import os
import time
import unittest

from helpers import write_mp3, text, txxx
from test_tagger_tools import Base

import features
import tagger
from id3tags import MP3File


class TestFeatures(unittest.TestCase):
    def test_number_and_normalize(self):
        n = features.number
        self.assertEqual(n("78"), 78)
        self.assertEqual(n("78.4"), 78)
        self.assertEqual(n("0.78"), 78)
        self.assertEqual(n("0,5"), 50)
        self.assertEqual(n("1"), 1)          # ganze Zahl bleibt
        self.assertEqual(n("1.0"), 100)      # Anteil
        self.assertEqual(n("65 %"), 65)
        self.assertIsNone(n("101"))
        self.assertIsNone(n("-3"))
        self.assertIsNone(n("hoch"))
        self.assertIsNone(n(""))
        self.assertEqual(features.normalize(" 7 "), "7")
        self.assertEqual(features.normalize(""), "")
        with self.assertRaises(ValueError):
            features.normalize("200")
        self.assertEqual(len(features.FEATURES), 10)

    def test_scale_10(self):
        """#11: Werte in den Dateien 0–10 (Lexicon), Anzeige und Eingabe 0–100."""
        try:
            self.assertEqual(features.set_scale(10), 10)
            n = features.number
            self.assertEqual(n("7"), 70)
            self.assertEqual(n("7.5"), 75)
            self.assertEqual(n("0,4"), 4)
            self.assertIsNone(n("70"))                 # passt nicht zur Skala
            self.assertEqual(n("70", 100), 70)
            self.assertEqual(features.normalize("75"), "7.5")
            self.assertEqual(features.normalize("70"), "7")
            self.assertEqual(features.display("7"), "70")
            self.assertEqual(features.display("hoch"), "hoch")
        finally:
            features.set_scale(100)
        self.assertEqual(features.SCALE, 100)
        self.assertEqual(features.normalize("75"), "75")
        self.assertEqual(features.display("0.75"), "0.75")


class TestFeatureSession(Base):
    def setUp(self):
        super().setUp()
        write_mp3(os.path.join(self.B, "4.mp3"), [text("TIT2", "y"), txxx("Energy", "0.81"), txxx("DANCEABILITY", "90")],
                  audio_seed=4)

    def test_file_level(self):
        f = MP3File(os.path.join(self.B, "4.mp3"))
        self.assertEqual(features.get(f, "ENERGY"), "0.81")
        self.assertEqual(features.values(f)["ENERGY"], 81)
        self.assertTrue(features.set_value(f, "ENERGY", "70"))
        self.assertEqual(features.find_keys(f, "ENERGY"), ["TXXX:ENERGY"])   # alte Schreibweise entfernt
        self.assertEqual(f.text("TXXX:ENERGY"), "70")
        self.assertFalse(features.set_value(f, "ENERGY", "70"))
        self.assertTrue(features.set_value(f, "ENERGY", ""))
        self.assertEqual(features.find_keys(f, "ENERGY"), [])
        f.save()
        f2 = MP3File(f.path)
        self.assertEqual(features.get(f2, "DANCEABILITY"), "90")
        self.assertEqual(features.get(f2, "ENERGY"), "")

    def test_session(self):
        from session import Session
        s = Session()
        s.start_tag_load(self.dir, True)
        while not s.task_status()["done"]:
            time.sleep(0.02)
        st = s.tagger_settings()
        self.assertEqual(st["features"][0][0], "ENERGY")
        rows = {r["name"]: r for r in s.tag_rows()["rows"]}
        i4 = rows["4.mp3"]["i"]
        self.assertEqual(rows["4.mp3"]["feat"]["ENERGY"], 81)
        allidx = list(range(len(s.tag_files)))
        d = s.tag_detail(allidx)
        self.assertTrue(d["features"]["ENERGY"]["mixed"])
        self.assertEqual(d["features"]["LIVENESS"], {"value": "", "mixed": False, "num": None})
        one = s.tag_detail([i4])
        self.assertEqual(one["features"]["DANCEABILITY"]["num"], 90)
        self.assertNotIn("TXXX:Energy", [x["key"] for x in one["fields"]])   # nicht unter „Weitere Felder“
        d = s.tag_feature_set(allidx, "ENERGY", "55")
        self.assertEqual(d["features"]["ENERGY"], {"value": "55", "mixed": False, "num": 55})
        self.assertEqual(d["meta"]["unsaved"], len(allidx))
        self.assertIn("error", s.tag_feature_set(allidx, "ENERGY", "300"))
        with self.assertRaises(ValueError):
            s.tag_feature_set(allidx, "QUATSCH", "1")
        s.do_undo()
        self.assertEqual(s.tag_detail([i4])["features"]["ENERGY"]["num"], 81)
        self.assertFalse(s.tagger_settings()["features_open"] is None)
        s.tag_features_open(False)
        self.assertFalse(Session().tagger_settings()["features_open"])

    def test_scale_and_columns_in_session(self):
        from session import Session
        s = Session()
        try:
            self.assertEqual(s.set_feat_scale(10)["scale"], 10)
            self.assertEqual(Session().settings_page()["feat_scale"], 10)     # gemerkt
            s.start_tag_load(self.B, False)
            while not s.task_status()["done"]:
                time.sleep(0.02)
            i = [os.path.basename(f.path) for f in s.tag_files].index("4.mp3")
            self.assertIsNone(s.tag_rows()["rows"][i]["feat"]["DANCEABILITY"])   # „90“ ist bei 0–10 ungültig
            s.tag_feature_set([i], "ENERGY", "65")
            self.assertEqual(s.tag_files[i].text("TXXX:ENERGY"), "6.5")
            self.assertEqual(s.tag_rows()["rows"][i]["feat"]["ENERGY"], 65)
        finally:
            s.set_feat_scale(100)
        s.set_ui("tg_feat_cols", ["ENERGY", "NOPE", "ENERGY", "VALENCE"])
        self.assertEqual(s.ui["tg_feat_cols"], ["ENERGY", "VALENCE"])
        with self.assertRaises(ValueError):
            s.set_ui("tg_feat_cols", "ENERGY")

    def test_export_columns(self):
        files = [MP3File(os.path.join(self.B, "4.mp3"))]
        head, rows = tagger.export_table(files)
        i = head.index("Energy")
        self.assertEqual(rows[0][i], 81)
        self.assertEqual(rows[0][head.index("Liveness")], "")


if __name__ == "__main__":
    unittest.main()
