"""Tests für Cue-Punkte (cues.py: Serato Markers2, Mixed In Key) und den Wellenform-Cache (waveform.py)."""
import base64
import json
import os
import shutil
import struct
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import cues  # noqa: E402
import waveform  # noqa: E402
from helpers import geob, text, txxx, write_mp3  # noqa: E402


def serato_markers2(entries) -> bytes:
    """GEOB-Daten wie Serato DJ sie schreibt: 01 01 + Base64 (72er-Zeilen), Base64 ohne „=“ und mit Nullen."""
    body = b"\x01\x01"
    for kind, idx, pos, end, rgb, name in entries:
        if kind == "CUE":
            d = b"\x00" + bytes([idx]) + struct.pack(">I", pos) + b"\x00" + bytes(rgb) + b"\x00\x00" + name.encode() + b"\x00"
        elif kind == "LOOP":
            d = (b"\x00" + bytes([idx]) + struct.pack(">II", pos, end) + b"\xff\xff\xff\xff\x00"
                 + bytes(rgb) + b"\x00" + name.encode() + b"\x00")
        else:
            d = b"\x00\xff\xff\xff"
        body += kind.encode() + b"\x00" + struct.pack(">I", len(d)) + d
    body += b"\x00"
    b64 = base64.b64encode(body).rstrip(b"=")
    lines = b"\n".join(b64[i:i + 72] for i in range(0, len(b64), 72))
    return b"\x01\x01" + lines + b"\x00" * 40


SERATO = serato_markers2([("COLOR", 0, 0, 0, (0, 0, 0), ""),
                          ("CUE", 0, 1500, 0, (0xCC, 0x00, 0x00), "Intro"),
                          ("CUE", 2, 20250, 0, (0x00, 0xCC, 0x00), ""),
                          ("LOOP", 0, 8000, 12000, (0x27, 0xAA, 0xE1), "Loop A")])
MIK = base64.b64encode(json.dumps({"algorithm": 1, "source": "mixedinkey",
                                   "cues": [{"name": "Energy 5", "time": 1500.0}, {"name": "Energy 7", "time": 30000}]}).encode())


class TestCues(unittest.TestCase):
    def test_serato(self):
        c = cues.serato_markers2(SERATO)
        self.assertEqual([(x["kind"], x["index"], x["pos"], x["color"], x["name"]) for x in c],
                         [("cue", 0, 1.5, "#CC0000", "Intro"), ("cue", 2, 20.25, "#00CC00", ""),
                          ("loop", 0, 8.0, "#27AAE1", "Loop A")])
        self.assertEqual(c[2]["end"], 12.0)
        self.assertEqual(cues.serato_markers2(b"\x01\x01!!kaputt!!"), [])
        self.assertEqual(cues.serato_markers2(b"garbage"), [])

    def test_mik_units(self):
        self.assertEqual([x["pos"] for x in cues.mik_cuepoints(MIK, 60)], [1.5, 30.0])        # ms
        sec = json.dumps({"cues": [{"name": "A", "time": 1.5}, {"name": "B", "time": 30.25}]})
        self.assertEqual([x["pos"] for x in cues.mik_cuepoints(sec, 60)], [1.5, 30.25])       # Sekunden
        self.assertEqual(cues.mik_cuepoints(b"kein json"), [])

    def test_read_file_merges_sources(self):
        from id3tags import MP3File
        d = tempfile.mkdtemp(prefix="ts_cue_")
        try:
            p = os.path.join(d, "a.mp3")
            write_mp3(p, [text("TIT2", "X"), geob("Serato Markers2", SERATO), geob("CuePoints", MIK)], audio_frames=2400)
            f = MP3File(p)
            self.assertGreater(f.duration, 40)
            c = cues.read(f)
            # 1,5 s kommt aus beiden Quellen → einmal (Serato mit Farbe, Name von Serato)
            self.assertEqual([(x["pos"], x["source"]) for x in c],
                             [(1.5, "Serato"), (8.0, "Serato"), (20.25, "Serato"), (30.0, "Mixed In Key")])
            self.assertEqual(c[0]["name"], "Intro")
            p2 = os.path.join(d, "b.mp3")
            write_mp3(p2, [txxx("CuePoints", MIK.decode())], audio_frames=2400)
            self.assertEqual([x["name"] for x in cues.read(MP3File(p2))], ["Energy 5", "Energy 7"])
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestWaveCache(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ts_wave_")
        self.old = waveform.DIR
        waveform.DIR = os.path.join(self.dir, "cache")

    def tearDown(self):
        waveform.DIR = self.old
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_key_ignores_tags_and_name(self):
        from id3tags import MP3File
        a, b = os.path.join(self.dir, "a.mp3"), os.path.join(self.dir, "anders.mp3")
        write_mp3(a, [text("TIT2", "Eins")], audio_seed=3)
        write_mp3(b, [text("TIT2", "Ganz anderer Titel"), txxx("X", "y" * 900)], padding=50, audio_seed=3)
        self.assertEqual(waveform.key_for(MP3File(a)), waveform.key_for(MP3File(b)))
        write_mp3(b, [text("TIT2", "Eins")], audio_seed=4)
        self.assertNotEqual(waveform.key_for(MP3File(a)), waveform.key_for(MP3File(b)))

    def test_save_load_validate(self):
        k = "ab" * 16
        self.assertIsNone(waveform.load(k))
        waveform.save(k, list(range(100)), [x // 2 for x in range(100)])
        self.assertEqual(waveform.load(k), {"peaks": list(range(100)), "rms": [x // 2 for x in range(100)]})
        for bad in ([1] * 5, [300] * 100, ["a"] * 100, [True] * 100):
            with self.assertRaises(ValueError):
                waveform.save(k, bad, bad)
        with self.assertRaises(ValueError):
            waveform.save("../../etc", [1] * 100, [1] * 100)
        self.assertIsNone(waveform.load("../x"))

    def test_prune(self):
        for n in range(5):
            waveform.save(f"{n:02x}" + "1" * 30, [1] * 20, [1] * 20)
        self.assertEqual(waveform.prune(3), 2)
        self.assertEqual(waveform.prune(3), 0)


class TestSessionExtra(unittest.TestCase):
    def test_media_extra_and_wave_save(self):
        import core
        from session import Session
        d = tempfile.mkdtemp(prefix="ts_mx_")
        old = (core.CONFIG, core.CONFIG_OLD, waveform.DIR)
        core.CONFIG = core.CONFIG_OLD = os.path.join(d, "cfg.json")
        waveform.DIR = os.path.join(d, "wave")
        try:
            write_mp3(os.path.join(d, "a.mp3"), [text("TIT2", "X"), geob("Serato Markers2", SERATO)], audio_frames=2400)
            s = Session()
            s.start_tag_load(d, False)
            while not s.task_status()["done"]:
                time.sleep(0.02)
            x = s.media_extra("tag", 0)
            self.assertEqual(len(x["cues"]), 3)
            self.assertIsNone(x["wave"])
            self.assertEqual(s.wave_save(x["wave_key"], [9] * 50, [3] * 50), {"ok": True})
            self.assertEqual(s.media_extra("tag", 0)["wave"]["peaks"], [9] * 50)
            self.assertFalse(s.wave_save(x["wave_key"], [999], [1])["ok"])
        finally:
            core.CONFIG, core.CONFIG_OLD, waveform.DIR = old
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
