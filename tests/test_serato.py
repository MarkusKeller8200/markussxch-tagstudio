"""Tests für serato.py (#76): Serato-Daten lesbar machen."""
import os
import shutil
import struct
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import serato  # noqa: E402
from helpers import geob, text, write_mp3  # noqa: E402
from test_cues_wave import SERATO  # noqa: E402


def grid(non_terminal, last_pos, bpm):
    data = b"\x01\x00" + struct.pack(">I", len(non_terminal) + 1)
    for pos, beats in non_terminal:
        data += struct.pack(">fI", pos, beats)
    return data + struct.pack(">ff", last_pos, bpm) + b"\x00"


AUTOTAGS = b"\x01\x01" + b"124.00\x00" + b"-3.257\x00" + b"0.000\x00"
OVERVIEW = b"\x01\x05" + b"".join(bytes([k % 16] * 16) for k in range(240))
ANALYSIS = b"\x02\x01"


class TestSerato(unittest.TestCase):
    def test_autotags_analysis(self):
        a = serato.decode("Serato Autotags", AUTOTAGS)
        self.assertEqual((a["bpm"], a["autogain"], a["gain"]), (124.0, -3.257, 0.0))
        self.assertIn("BPM 124.00", a["summary"])
        self.assertEqual(serato.decode("Serato Analysis", ANALYSIS)["version"], "2.1")

    def test_beatgrid_single_and_multi(self):
        g = serato.decode("Serato BeatGrid", grid([], 0.123, 124.0))
        self.assertEqual((g["bpm"], g["first"], len(g["markers"])), (124.0, 0.123, 1))
        g = serato.decode("Serato BeatGrid", grid([(0.5, 64)], 0.5 + 64 * 60 / 128, 120.0))
        self.assertAlmostEqual(g["markers"][0]["bpm"], 128.0, places=2)
        self.assertAlmostEqual(g["bpm"], 128.0, places=2)
        self.assertEqual(len(g["rows"]), 2)
        self.assertEqual(serato.decode("Serato BeatGrid", b"\x01\x00\x00\x00\x00\x00")["markers"], [])

    def test_markers2_overview(self):
        m = serato.decode("Serato Markers2", SERATO)
        self.assertIn("2 Cue(s), 1 Loop(s)", m["summary"])
        self.assertEqual(m["color"], "#FFFFFF")                               # COLOR-Eintrag im Testdatensatz
        self.assertTrue(any("Intro" in v for _k, v in m["rows"]))
        o = serato.decode("Serato Overview", OVERVIEW)
        self.assertEqual(len(o["bars"]), 240)
        self.assertEqual(max(o["bars"]), 1.0)

    def test_broken_and_unknown(self):
        d = serato.decode("Serato BeatGrid", b"\x09\x09xyz")
        self.assertIn("nicht lesbar", d["error"])
        self.assertIsNone(serato.decode("Irgendwas", b"x"))
        self.assertTrue(serato.decode("Serato Markers_", b"\x02\x05")["old"])

    def test_of_file_and_session_view(self):
        d = tempfile.mkdtemp(prefix="ts_serato_")
        old = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = d
        import core
        cfg = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = core.CONFIG_OLD = os.path.join(d, "cfg.json")
        try:
            p = os.path.join(d, "a.mp3")
            write_mp3(p, [text("TIT2", "X"), geob("Serato BeatGrid", grid([], 0.25, 126.0)),
                          geob("Serato Autotags", AUTOTAGS), geob("Serato Markers2", SERATO)], audio_frames=400)
            from id3tags import MP3File
            f = MP3File(p)
            got = serato.of_file(f)
            self.assertEqual(got["BeatGrid"]["bpm"], 126.0)
            self.assertIn("Autotags", got)
            from session import Session
            s = Session()
            s.start_tag_load(d, False)
            import time
            while not s.task_status()["done"]:
                time.sleep(0.02)
            det = s.tag_detail([0])
            texts = {x["key"]: x["text"] for x in det["fields"]}
            self.assertTrue(texts["GEOB:Serato BeatGrid"].startswith("Serato BeatGrid: Beatgrid: 1 Marker, 126.0 BPM"))
            v = s.tag_blob(0, "GEOB:Serato Autotags")
            self.assertEqual(v["serato"]["bpm"], 124.0)
            # #76 Schritt 2: Beatgrid für den Player – Serato vor BPM-Tag
            g = s.media_extra("tag", 0)["grid"]
            self.assertEqual((g["bpm"], g["first"], g["source"], g["exact"]), (126.0, 0.25, "Serato", True))
            from session_player import PlayerMixin
            f2 = MP3File(p)
            f2.items.pop("GEOB:Serato BeatGrid", None)
            f2.set_text("TBPM", "120")
            g2 = PlayerMixin._beat_grid(f2, [{"kind": "cue", "pos": 1.75}])
            self.assertEqual((g2["bpm"], g2["exact"]), (120.0, False))
            self.assertAlmostEqual(g2["first"], 0.25)                   # 1,75 s im Raster von 0,5 s
            f2.set_text("TBPM", "")
            self.assertIsNone(PlayerMixin._beat_grid(f2, []))
        finally:
            core.CONFIG, core.CONFIG_OLD = cfg
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
