"""Plugin „Mixed In Key übernehmen“ (#147): Tonart, BPM und Energie aus den von MIK beschriebenen Feldern."""
import os
import time

from helpers import write_mp3, text, txxx, comm
from test_tagger_tools import Base


class TestMik(Base):
    def setUp(self):
        super().setUp()
        write_mp3(os.path.join(self.B, "c.mp3"), [text("TIT2", "Nordlicht"), text("TPE1", "Mara Lind"),
                                                  comm("", "10A - Energy 7"), text("TBPM", "124.00")], audio_seed=21)
        write_mp3(os.path.join(self.B, "t.mp3"), [text("TIT2", "8A - 6 - Kaltes Glas (Extended Mix)"), text("TPE1", "Mara Lind"),
                                                  text("TIT1", "Energy 5 Peak"), text("TKEY", "Am")], audio_seed=22)
        write_mp3(os.path.join(self.B, "s.mp3"), [text("TIT2", "Golden Hour - 3B"), text("TPE1", "A - Ha"),
                                                  txxx("EnergyLevel", "9"), text("TPUB", "Energy 9")], audio_seed=23)
        write_mp3(os.path.join(self.B, "n.mp3"), [text("TIT2", "E - Lysium"), text("TPE1", "Niemand")], audio_seed=24)
        from session import Session
        self.s = Session()
        self.s.start_tag_load(self.B, False)
        self.wait()
        self.idx = {os.path.basename(f.path): i for i, f in enumerate(self.s.tag_files)}

    def wait(self):
        for _ in range(500):
            st = self.s.task_status()
            if st.get("done"):
                return st
            time.sleep(0.02)
        self.fail("hängt")

    def run_mik(self, **opts):
        base = dict(key=True, energy=True, bpm=True, clean_title=True, clean_comment=True, clean_group=True)
        base.update(opts)
        r = self.s.start_plugin_action("mik", "import", sorted(self.idx.values()), base)
        self.assertTrue(r["ok"], r)
        st = self.wait()
        self.assertIsNone(st["error"], st)
        return st["result"]

    def test_import_and_clean(self):
        res = self.run_mik()
        self.assertRegex(res["message"], r"^3 von \d+ Titel")
        by = {(r["name"], r["label"]): r for r in res["proposals"]}
        # Kommentar „10A - Energy 7“ → TKEY, ENERGY 70, Kommentar leer (entfernen), BPM gerundet
        self.assertEqual(by[("c.mp3", "Tonart")]["new"], "10A")
        self.assertEqual(by[("c.mp3", "Energie (ENERGY)")]["new"], "70")
        self.assertEqual(by[("c.mp3", "Kommentar bereinigen")]["new"], "")
        self.assertEqual(by[("c.mp3", "BPM")]["new"], "124")
        # Titel-Präfix mit Energie; TKEY „Am“ ist schon richtig (= 8A) – Schreibweise wird angeglichen
        self.assertEqual(by[("t.mp3", "Titel bereinigen")]["new"], "Kaltes Glas (Extended Mix)")
        self.assertEqual(by[("t.mp3", "Tonart")]["new"], "08A")
        self.assertEqual(by[("t.mp3", "Energie (ENERGY)")]["new"], "60")      # Titel vor Gruppierung
        self.assertEqual(by[("t.mp3", "Gruppierung bereinigen")]["new"], "Peak")
        # Titel-Endung „- 3B“, Energie aus TXXX:EnergyLevel, Label „Energy 9“ leeren; „A - Ha“ ist kein Präfix
        self.assertEqual(by[("s.mp3", "Tonart")]["new"], "03B")
        self.assertEqual(by[("s.mp3", "Titel bereinigen")]["new"], "Golden Hour")
        self.assertEqual(by[("s.mp3", "Energie (ENERGY)")]["new"], "90")
        self.assertEqual(by[("s.mp3", "Label bereinigen")]["new"], "")
        self.assertNotIn(("s.mp3", "Künstler bereinigen"), by)
        self.assertFalse([k for k in by if k[0] == "n.mp3"])                 # „E - Lysium“: kein Treffer
        # übernehmen
        ids = [r["id"] for r in res["proposals"] if r["checked"]]
        out = self.s.plugin_apply(res["proposals_token"], ids)
        self.assertTrue(out["ok"], out)
        c = self.s.tag_files[self.idx["c.mp3"]]
        self.assertEqual((c.text("TKEY"), c.text("TXXX:ENERGY"), c.text("TBPM"), c.text("COMM:")), ("10A", "70", "124", ""))

    def test_options_off(self):
        res = self.run_mik(clean_title=False, clean_comment=False, clean_group=False, energy=False)
        checked = {(r["name"], r["label"]) for r in res["proposals"] if r["checked"]}
        self.assertIn(("c.mp3", "Tonart"), checked)
        self.assertNotIn(("c.mp3", "Kommentar bereinigen"), checked)
        self.assertNotIn(("c.mp3", "Energie (ENERGY)"), checked)


if __name__ == "__main__":
    import unittest
    unittest.main()
