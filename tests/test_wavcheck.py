"""Testroutine WAV (#156): Aufbau lesen, LIST/INFO, ID3-Chunk schreiben und wieder lesen, Audio unverändert."""
import os
import shutil
import struct
import sys
import tempfile
import unittest
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import wavcheck  # noqa: E402


def make_wav(path, info=None, extra=b""):
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(bytes(range(256)) * 400)
    if info or extra:
        body = b"INFO"
        for k, v in (info or {}).items():
            d = v.encode() + b"\x00"
            body += k.encode() + struct.pack("<I", len(d)) + d + (b"\x00" if len(d) & 1 else b"")
        chunk = (b"LIST" + struct.pack("<I", len(body)) + body if info else b"") + extra
        with open(path, "ab") as f:
            f.write(chunk)
        with open(path, "r+b") as f:
            size = os.path.getsize(path)
            f.seek(4)
            f.write(struct.pack("<I", size - 8))


class TestWavCheck(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ts_wav_")
        self.p = os.path.join(self.dir, "t.wav")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_report_info(self):
        make_wav(self.p, {"INAM": "Nordlicht", "IART": "Mara Lind"})
        r = wavcheck.report(self.p)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["info"], {"INAM": "Nordlicht", "IART": "Mara Lind"})
        self.assertIsNone(r["id3"])
        self.assertIn("PCM 16 Bit", r["format"])

    def test_write_id3_keeps_audio_and_info(self):
        make_wav(self.p, {"INAM": "Nordlicht"})
        before = wavcheck.audio_hash(self.p)
        wavcheck.write_id3(self.p, wavcheck.build_id3({"TIT2": "Nordlicht", "TPE1": "Mara Lind", "TBPM": "124",
                                                         "TXXX:CATALOGNUMBER": "POL042"}))
        r = wavcheck.report(self.p)
        self.assertTrue(r["ok"], r["problems"])
        self.assertEqual(r["id3"]["fields"]["TPE1"], "Mara Lind")
        self.assertEqual(r["id3"]["fields"]["TXXX:CATALOGNUMBER"], "POL042")
        self.assertEqual(r["info"], {"INAM": "Nordlicht"})
        self.assertEqual(wavcheck.audio_hash(self.p), before)
        with wave.open(self.p, "rb") as w:
            self.assertEqual(w.getnframes(), 25600)
        # zweites Schreiben ersetzt den Chunk (kein zweiter id3-Chunk), ungerade Länge wird aufgefüllt
        wavcheck.write_id3(self.p, wavcheck.build_id3({"TIT2": "X"}))
        r = wavcheck.report(self.p)
        self.assertEqual(sum(1 for c in r["chunks"] if c.startswith("id3")), 1)
        self.assertTrue(r["ok"], r["problems"])

    def test_roundtrip_and_broken(self):
        make_wav(self.p, {"IART": "A"})
        self.assertTrue(wavcheck.roundtrip(self.p)["ok"])
        with open(self.p, "r+b") as f:                  # RIFF-Grösse verfälschen
            f.seek(4)
            f.write(struct.pack("<I", 12))
        self.assertFalse(wavcheck.report(self.p)["ok"])
        nowav = os.path.join(self.dir, "x.wav")
        with open(nowav, "wb") as f:
            f.write(b"ID3" + b"\x00" * 50)
        self.assertIn("keine RIFF/WAVE-Datei", wavcheck.report(nowav)["problems"])
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(wavcheck.main([self.p]), 1)
        self.assertIn("RIFF-Grösse", out.getvalue())


if __name__ == "__main__":
    unittest.main()
