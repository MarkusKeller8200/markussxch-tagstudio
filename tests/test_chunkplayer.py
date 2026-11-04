"""#448: Player für WAV/AIFF – AIFF wird als virtuelle WAV-Datei ausgeliefert (Browser spielen AIFF nicht)."""
import io
import os
import random
import shutil
import struct
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import media  # noqa: E402
from test_chunktags import ext80, make_wav, riff_chunk  # noqa: E402


def aiff(path, samples: bytes, ch=2, bits=16, form=b"AIFF", comp=b"NONE", rate=44100, offset=0, extra=b""):
    width = (bits + 7) // 8
    frames = len(samples) // (ch * width)
    comm = struct.pack(">HIH", ch, frames, bits) + ext80(rate)
    if form == b"AIFC":
        comm += comp + b"\x00\x00"
    ssnd = struct.pack(">II", offset, 0) + b"\x00" * offset + samples
    body = form + riff_chunk(b"COMM", comm, False) + extra + riff_chunk(b"SSND", ssnd, False)
    with open(path, "wb") as f:
        f.write(b"FORM" + struct.pack(">I", len(body)) + body)


def swap(b: bytes, w: int) -> bytes:
    return b"".join(b[i:i + w][::-1] for i in range(0, len(b), w))


class TestAiffAsWav(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ts_aiffplay_")
        self.srv = media.MediaServer()
        rnd = random.Random(7)
        self.raw = bytes(rnd.getrandbits(8) for _ in range(2 * 2 * 3000))   # 3000 Frames, Stereo 16 bit

    def tearDown(self):
        self.srv.stop()
        shutil.rmtree(self.dir, ignore_errors=True)

    def full(self, path):
        v = media.aiff_view(path)
        return media.aiff_read(path, v, 0, v["size"] - 1)

    def frames_of(self, data):
        with wave.open(io.BytesIO(data)) as w:
            return w.getnchannels(), w.getsampwidth(), w.getframerate(), w.readframes(w.getnframes())

    def test_16bit_big_endian(self):
        p = os.path.join(self.dir, "a.aiff")
        aiff(p, self.raw, extra=riff_chunk(b"NAME", b"x", False))
        self.assertEqual(self.frames_of(self.full(p)), (2, 2, 44100, swap(self.raw, 2)))

    def test_widths_and_aifc_types(self):
        for bits, w in ((24, 3), (32, 4)):
            p = os.path.join(self.dir, f"b{bits}.aif")
            raw = self.raw[: len(self.raw) // (2 * w) * 2 * w]
            aiff(p, raw, bits=bits)
            self.assertEqual(self.frames_of(self.full(p))[3], swap(raw, w), bits)
        p = os.path.join(self.dir, "s.aifc")                                   # sowt = schon Little-Endian
        aiff(p, self.raw, form=b"AIFC", comp=b"sowt", offset=4)
        self.assertEqual(self.frames_of(self.full(p))[3], self.raw)
        p = os.path.join(self.dir, "u8.aiff")                                  # 8 bit: vorzeichenbehaftet → vorzeichenlos
        aiff(p, bytes([0, 127, 128, 255]) * 10, ch=1, bits=8)
        self.assertEqual(self.frames_of(self.full(p))[3], bytes([128, 255, 0, 127]) * 10)
        p = os.path.join(self.dir, "f.aifc")                                   # Gleitkomma → WAV-Format 3
        aiff(p, self.raw, form=b"AIFC", comp=b"fl32", bits=32)
        v = media.aiff_view(p)
        self.assertEqual(struct.unpack("<H", v["header"][20:22])[0], 3)
        p = os.path.join(self.dir, "x.aifc")
        aiff(p, self.raw, form=b"AIFC", comp=b"ulaw")
        with self.assertRaises(ValueError):
            media.aiff_view(p)
        with self.assertRaises(ValueError):
            self.srv.register(p)

    def test_any_range_equals_full(self):
        p = os.path.join(self.dir, "r.aiff")
        aiff(p, self.raw, bits=24)
        full = self.full(p)
        v = media.aiff_view(p)
        rnd = random.Random(3)
        for _ in range(200):
            a = rnd.randrange(0, v["size"])
            b = rnd.randrange(a, v["size"])
            self.assertEqual(media.aiff_read(p, v, a, b), full[a:b + 1], (a, b))

    def test_http_served_as_wav_with_ranges(self):
        p = os.path.join(self.dir, "h.aiff")
        aiff(p, self.raw)
        url = self.srv.register(p)
        self.assertTrue(url.endswith(".wav"))
        full = self.full(p)
        with urllib.request.urlopen(url, timeout=10) as r:
            self.assertEqual((r.status, r.headers["Content-Type"]), (200, "audio/wav"))
            self.assertEqual(r.read(), full)
        req = urllib.request.Request(url, headers={"Range": "bytes=41-1000"})
        with urllib.request.urlopen(req, timeout=10) as r:
            self.assertEqual(r.status, 206)
            self.assertEqual(r.headers["Content-Range"], f"bytes 41-1000/{len(full)}")
            self.assertEqual(r.read(), full[41:1001])
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(urllib.request.Request(url, headers={"Range": f"bytes={len(full)}-"}), timeout=10)
        self.assertEqual(cm.exception.code, 416)

    def test_view_follows_file_change(self):
        p = os.path.join(self.dir, "c.aiff")
        aiff(p, self.raw)
        v1 = media.aiff_view(p)
        aiff(p, self.raw[:4000])
        os.utime(p, ns=(1, 1))
        self.assertNotEqual(media.aiff_view(p)["len"], v1["len"])

    def test_wav_served_unchanged(self):
        p = os.path.join(self.dir, "w.wav")
        make_wav(p)
        url = self.srv.register(p)
        with urllib.request.urlopen(url, timeout=10) as r, open(p, "rb") as fh:
            self.assertEqual((r.headers["Content-Type"], r.read()), ("audio/wav", fh.read()))

    def test_wave_key_ignores_tag_changes(self):
        import waveform
        from id3tags import MP3File
        p = os.path.join(self.dir, "k.aiff")
        aiff(p, self.raw)
        f = MP3File(p)
        k1 = waveform.key_for(f)
        f.set_text("TIT2", "anders")
        f.save()
        self.assertEqual(waveform.key_for(MP3File(p)), k1)
        q = os.path.join(self.dir, "k.wav")
        make_wav(q)
        g = MP3File(q)
        k2 = waveform.key_for(g)
        g.set_text("TIT2", "anders")
        g.save()
        self.assertEqual(waveform.key_for(MP3File(q)), k2)


if __name__ == "__main__":
    unittest.main()
