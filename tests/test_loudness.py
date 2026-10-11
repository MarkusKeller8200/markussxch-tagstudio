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


if __name__ == "__main__":
    unittest.main()
