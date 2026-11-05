"""#451: Konverter MP3 ↔ WAV/AIFF mit Tags (FFmpeg nötig für die eigentliche Umwandlung)."""
import hashlib
import os
import subprocess
import time
import unittest

from helpers import geob, text, txxx, write_mp3
from test_tagger_tools import Base

import convert
import chunktags
from id3tags import MP3File, Item, Cover

FF = convert.find_ffmpeg()
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def sine_mp3(path, secs=2):
    subprocess.run([FF, "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={secs}",
                    "-ac", "2", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "192k", path], check=True)
    f = MP3File(path)
    f.set_text("TIT2", "Umwandeln Test")
    f.set_text("TPE1", "Künstlerin")
    f.set_text("TBPM", "124")
    f.set_text("TKEY", "8A")
    f.set_text("TXXX:ENERGY", "7")
    f.set("APIC:3", Item.new_cover(Cover(PNG, "image/png")))
    f.save()


class TestConvertPlan(Base):
    def test_plan_rules(self):
        a = os.path.join(self.A, "1.mp3")
        exp = os.path.join(self.dir, "Export")
        rows = convert.plan([a], "wav", exp)
        self.assertEqual(rows[0]["dst"], os.path.join(exp, "1.wav"))
        self.assertEqual(rows[0]["problem"], "")
        self.assertEqual(convert.plan([a], "wav", None)[0]["dst"], os.path.join(self.A, "1.wav"))   # neben dem Original
        self.assertEqual(convert.plan([a], "mp3", exp)[0]["problem"], "ist schon in diesem Format")
        self.assertIn("ungespeichert", convert.plan([a], "aiff", exp, dirty=[a])[0]["problem"])
        os.makedirs(exp)
        open(os.path.join(exp, "1.wav"), "wb").close()
        self.assertIn("nicht überschrieben", convert.plan([a], "wav", exp)[0]["problem"])
        with self.assertRaises(ValueError):
            convert.plan([a], "ogg", exp)

    def test_ffmpeg_cmd(self):
        c = convert.ffmpeg_cmd("ff", "a.wav", "o.mp3", "mp3", 320, 16, 44100)
        self.assertIn("320k", c)
        self.assertIn("libmp3lame", c)
        self.assertIn("pcm_s24be", convert.ffmpeg_cmd("ff", "a.mp3", "o.aiff", "aiff", 320, 24, 0))
        self.assertIn("pcm_s16le", convert.ffmpeg_cmd("ff", "a.mp3", "o.wav", "wav", 320, 16, 0))

    def test_session_preview_defaults(self):
        from session import Session
        s = Session()
        s.tag_files = [MP3File(os.path.join(self.A, "1.mp3"))]
        pv = s.convert_preview([0])
        self.assertEqual((pv["target"], pv["dest"], pv["bitrate"]), ("wav", "export", 320))
        self.assertEqual(pv["kinds"], ["mp3"])
        with self.assertRaises(ValueError):
            s.convert_preview([0], "mp3", "export", 999)
        self.assertEqual(s.convert_preview([0], "mp3")["rows"][0]["problem"], "ist schon in diesem Format")
        write_mp3(os.path.join(self.A, "s.mp3"), [text("TIT2", "x"), geob("Serato Markers2", b"\x01\x01")])
        s.tag_files.append(MP3File(os.path.join(self.A, "s.mp3")))
        self.assertTrue(s.convert_preview([0, 1])["serato"])


@unittest.skipUnless(FF, "FFmpeg fehlt")
class TestConvertRun(Base):
    def test_mp3_wav_mp3_and_aiff(self):
        src = os.path.join(self.dir, "Titel.mp3")
        sine_mp3(src)
        h = sha(src)
        out = os.path.join(self.dir, "out")
        w = convert.convert_one(src, os.path.join(out, "Titel.wav"), "wav")
        a = convert.convert_one(src, os.path.join(out, "Titel.aiff"), "aiff")
        self.assertEqual(sha(src), h)                                           # Original unverändert
        for p, kind in ((w, "wav"), (a, "aiff")):
            f = MP3File(p)
            self.assertIsInstance(f, chunktags.ChunkFile)
            self.assertEqual(f.container, kind)
            self.assertEqual((f.text("TIT2"), f.text("TPE1"), f.text("TBPM"), f.text("TKEY"), f.text("TXXX:ENERGY")),
                             ("Umwandeln Test", "Künstlerin", "124", "8A", "7"))
            self.assertEqual(f.items["APIC:3"].cover.data, PNG)
            self.assertAlmostEqual(f.duration, 2.0, delta=0.1)
            self.assertEqual((f.samplerate, f.bits), (44100, 16))
        for p in (w, a):                                                       # und zurück
            back = convert.convert_one(p, os.path.join(out, "zurück", os.path.basename(p) + ".mp3"), "mp3", 256)
            g = MP3File(back)
            self.assertIs(type(g), MP3File)
            self.assertEqual(g.text("TIT2"), "Umwandeln Test")
            self.assertEqual(g.items["APIC:3"].cover.data, PNG)
            self.assertAlmostEqual(g.duration, 2.0, delta=0.15)
            self.assertAlmostEqual(g.bitrate, 256, delta=8)
        with self.assertRaises(FileExistsError):
            convert.convert_one(src, w, "wav")
        self.assertEqual([n for n in os.listdir(out) if n.startswith(".tagstudio_conv_")], [])

    def test_flac_alac_aac_targets(self):
        """#456: Ziele FLAC, M4A (ALAC), M4A (AAC); FLAC → WAV → FLAC ist bitgleich; Felder ohne Gegenstück gemeldet."""
        src = os.path.join(self.dir, "Quelle.mp3")
        sine_mp3(src)
        f = MP3File(src)
        it = Item("POPM", "POPM:x", payload=b"x\x00\xff")
        it.kind = "raw"
        f.items["POPM:x"] = it
        self.assertIn("POPM:x", convert.lost_keys(f, "flac"))
        self.assertEqual(convert.lost_keys(f, "wav"), [])
        out = os.path.join(self.dir, "o")
        notes = []
        fl = convert.convert_one(f, os.path.join(out, "Q.flac"), "flac", notes=notes)
        self.assertIn("POPM:x", notes)
        al = convert.convert_one(src, os.path.join(out, "QA.m4a"), "alac")
        aa = convert.convert_one(src, os.path.join(out, "QC.m4a"), "m4a", 192)
        for p, codec in ((fl, "FLAC"), (al, "ALAC"), (aa, "AAC")):
            g = MP3File(p)
            self.assertEqual(g.codec, codec, p)
            self.assertEqual((g.text("TIT2"), g.text("TKEY"), g.text("TXXX:ENERGY")), ("Umwandeln Test", "8A", "7"), p)
            self.assertEqual(g.items["APIC:3"].cover.data, PNG, p)
            self.assertAlmostEqual(g.duration, 2.0, delta=0.15)
        w = convert.convert_one(fl, os.path.join(out, "Q.wav"), "wav")
        back = convert.convert_one(w, os.path.join(out, "zurück", "Q.flac"), "flac")

        def pcm(p):
            r = subprocess.run([FF, "-loglevel", "error", "-i", p, "-f", "s16le", "-"], capture_output=True, check=True)
            return hashlib.sha256(r.stdout).hexdigest()
        self.assertEqual(pcm(back), pcm(fl))                                     # verlustfrei hin und zurück
        self.assertTrue(convert.is_lossy_source(MP3File(aa)))
        self.assertFalse(convert.is_lossy_source(MP3File(al)))

    def test_session_job_to_export(self):
        src = os.path.join(self.B, "Job.mp3")
        sine_mp3(src, 1)
        from session import Session
        s = Session()
        s.tag_files = [MP3File(src)]
        exp = os.path.join(self.dir, "Export")
        s.export_dir = lambda: exp
        os.makedirs(exp)
        r = s.start_convert([0], "aiff", "export", 320)
        self.assertTrue(r.get("ok", True), r)
        for _ in range(500):
            if s.task_status().get("done"):
                break
            time.sleep(0.05)
        res = s.task_status()["result"]
        self.assertEqual(res["errors"], [])
        self.assertEqual(res["done"], [os.path.join(exp, "Job.aiff")])
        self.assertEqual(MP3File(res["done"][0]).text("TIT2"), "Umwandeln Test")
        import core
        self.assertEqual(core.load_config()["convert"], {"target": "aiff", "dest": "export", "bitrate": 320})


if __name__ == "__main__":
    unittest.main()
