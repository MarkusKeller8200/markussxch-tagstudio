"""#119: Lautheit messen (EBU R128 über FFmpeg) – Vorschläge und angeglichene Kopie."""
import os
import shutil
import subprocess
import time
import unittest

from test_tagger_tools import Base

HAVE = shutil.which("ffmpeg") is not None


@unittest.skipUnless(HAVE, "FFmpeg fehlt")
class TestLoudness(Base):
    def setUp(self):
        super().setUp()
        self.p = os.path.join(self.B, "ton.mp3")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=8",
                        "-b:a", "128k", "-id3v2_version", "3", "-metadata", "title=Ton", self.p], check=True)
        from session import Session
        self.s = Session()
        self.s.start_tag_load(self.B, False)
        self.wait()
        self.i = [os.path.basename(f.path) for f in self.s.tag_files].index("ton.mp3")

    def wait(self):
        for _ in range(1500):
            st = self.s.task_status()
            if st.get("done"):
                return st
            time.sleep(0.02)
        self.fail("hängt")

    def test_measure_and_copy(self):
        r = self.s.start_plugin_action("loudness", "measure", [self.i],
                                       {"lufs": True, "peak": True, "rg": True, "normalize": True, "target": -14})
        self.assertTrue(r["ok"], r)
        st = self.wait()
        self.assertIsNone(st["error"], st)
        res = st["result"]
        by = {p["label"]: p for p in res["proposals"]}
        lufs = float(by["LUFS_I"]["new"])
        self.assertTrue(-25 < lufs < -10, lufs)
        self.assertIn("dB", by["ReplayGain Gain"]["new"])
        self.assertIn("1 angeglichene Kopie", res["message"])
        copy = os.path.join(self.B, "Angeglichen", "ton.mp3")
        self.assertTrue(os.path.isfile(copy))
        from id3tags import MP3File
        self.assertEqual(MP3File(copy).text("TIT2"), "Ton")               # Tags übernommen
        out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", copy, "-af", "ebur128", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
        import re
        i = float(re.findall(r"I:\s*(-?[\d.]+) LUFS", out)[-1])
        self.assertAlmostEqual(i, -14, delta=1.0)
        self.assertEqual(MP3File(self.p).text("TIT2"), "Ton")             # Original unverändert

    def test_clipping(self):
        p = os.path.join(self.B, "laut.mp3")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
                        "-af", "volume=30dB,aformat=sample_fmts=s16", "-b:a", "320k", p], check=True)
        self.s.start_tag_load(self.B, False)
        self.wait()
        names = [os.path.basename(f.path) for f in self.s.tag_files]
        r = self.s.start_plugin_action("loudness", "measure", [names.index("laut.mp3"), names.index("ton.mp3")],
                                       {"lufs": False, "peak": False, "clip": True})
        self.assertTrue(r["ok"], r)
        res = self.wait()["result"]
        self.assertIn("1 übersteuert", res["message"])
        clip = [p for p in res["proposals"] if p["label"] == "CLIPPING"]
        self.assertEqual(len(clip), 1)
        self.assertGreater(float(clip[0]["new"]), 10)
        self.assertEqual(clip[0]["name"], "laut.mp3")

    def test_parse_clip(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("ld", os.path.join(os.path.dirname(__file__), "..", "plugins", "loudness", "plugin.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        d = m.parse("n_samples: 1000\nhistogram_0db: 5\n  I:  -9.0 LUFS\n")
        self.assertAlmostEqual(d["clip_pct"], 0.5)
        self.assertEqual(d["I"], -9.0)


class TestLoudnessSafety(unittest.TestCase):
    """4.9.1: FFmpeg lässt sich abbrechen; angeglichene Kopien überschreiben nichts."""

    def mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("ld2", os.path.join(os.path.dirname(__file__), "..", "plugins", "loudness", "plugin.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_cancel_kills_process(self):
        import sys
        import time
        m = self.mod()
        t0 = time.time()
        with self.assertRaises(m.Cancelled):
            m._run([sys.executable, "-c", "import time; time.sleep(20)"], lambda: time.time() - t0 > 0.6)
        self.assertLess(time.time() - t0, 8)

    def test_unique_names(self):
        import tempfile
        m = self.mod()
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "Titel.mp3")
            self.assertEqual(m._unique(p, set()), p)
            open(p, "wb").close()
            self.assertEqual(m._unique(p, set()), os.path.join(d, "Titel (2).mp3"))
            made = {os.path.normcase(os.path.abspath(os.path.join(d, "Titel (2).mp3")))}
            self.assertEqual(m._unique(p, made), os.path.join(d, "Titel (3).mp3"))


if __name__ == "__main__":
    unittest.main()
