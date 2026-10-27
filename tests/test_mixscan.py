"""Mix analysieren (#261): Index nachführen, Tracklist-Abgleich, Bericht – und (mit NumPy/SciPy/FFmpeg) die Erkennung
in einem synthetischen Mix mit Tempoänderung mit und ohne Keylock. Die Erkennung läuft im Workflow „Mix-Analyse-Test“
(Umgebung wie im Plugin); im normalen Testlauf ohne NumPy wird sie übersprungen."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUG = os.path.join(ROOT, "plugins", "mixscan")


def load(name):
    spec = importlib.util.spec_from_file_location("mixscan_" + name, os.path.join(PLUG, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plugin = load("plugin")

try:
    import numpy as np  # noqa: F401
    import scipy  # noqa: F401
    sys.path.insert(0, PLUG)
    import fp
    try:
        import imageio_ffmpeg
        FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        FFMPEG = shutil.which("ffmpeg") or ""
    HAVE = bool(FFMPEG)
except ImportError:
    HAVE = False


class TestPlugin(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def touch(self, *parts, data=b"x"):
        p = os.path.join(self.d, *parts)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(data)
        return p

    def test_scan_and_plan(self):
        a = self.touch("lib", "A - Eins.mp3")
        b = self.touch("lib", "sub", "B - Zwei.flac")
        self.touch("lib", ".versteckt", "C.mp3")
        self.touch("lib", "cover.jpg")
        paths = plugin.scan([os.path.join(self.d, "lib")])
        self.assertEqual(paths, [a, b])
        self.assertEqual(plugin.scan([os.path.join(self.d, "lib")], limit=1), [a])
        m = {"next": 1, "files": {}}
        todo, drop = plugin.plan(m, paths)
        self.assertEqual((todo, drop), ([(1, a), (2, b)], []))
        for p in paths:
            m["files"][p]["keys"] = 10
        self.assertEqual(plugin.plan(m, paths), ([], []))                 # unverändert → nichts zu tun
        self.touch("lib", "A - Eins.mp3", data=b"xx")                       # geändert
        todo, drop = plugin.plan(m, [a])                                   # b nicht mehr gewählt
        self.assertEqual((todo, drop), ([(1, a)], [2]))
        self.assertNotIn(b, m["files"])

    def test_merge_rows_and_versions(self):
        """Messung 27.10.2026: „Hypnotic“ in Stücken (auch Dub Mix) → ein Abschnitt; Remix ≠ Extended Mix."""
        rows = [{"start": 325, "end": 345, "artist": "Path Of Youth", "title": "Hypnotic (Extended Mix)", "hits": 300, "blocks": 4, "conf": 0.99},
                {"start": 365, "end": 455, "artist": "Path Of Youth", "title": "Hypnotic (Extended Mix)", "hits": 900, "blocks": 18, "conf": 0.99},
                {"start": 475, "end": 490, "artist": "Path Of Youth", "title": "Hypnotic (Dub Mix)", "hits": 120, "blocks": 3, "conf": 0.73},
                {"start": 550, "end": 785, "artist": "Nelly Furtado, Nora En Pure, HAYLA", "title": "FADED (Nora En Pure Remix)", "hits": 2000, "blocks": 47, "conf": 0.9}]
        out = plugin.merge_rows(rows)
        self.assertEqual([(r["start"], r["end"], r["title"]) for r in out],
                         [(325, 490, "Hypnotic (Extended Mix)"), (550, 785, "FADED (Nora En Pure Remix)")])
        self.assertEqual(out[0]["also"], ["Path Of Youth - Hypnotic (Dub Mix)"])
        c = plugin.compare("Nora En Pure - Space (Paradoks Remix)\nPath Of Youth - Hypnotic (Original Mix)",
                           [{"artist": "Nora En Pure", "title": "Space (Extended Mix)"}, {"artist": "Path Of Youth", "title": "Hypnotic (Extended Mix)"}])
        self.assertEqual(c["hit"], ["Path Of Youth - Hypnotic (Original Mix)"])                 # Original = Extended
        self.assertEqual(c["other"], ["Nora En Pure - Space (Paradoks Remix) → Nora En Pure - Space (Extended Mix)"])
        self.assertEqual((c["miss"], c["extra"]), ([], []))
        # Messung 520: Länderzusatz und „Remix, Extended“
        c = plugin.compare("NTO - I Cared For You (Tim Engelhardt Remix)\nCon's Universe - Evenfall (Extended Mix)",
                           [{"artist": "NTO (FR), Mont Rouge", "title": "I Cared For You (Tim Engelhardt Remix, Extended)"},
                            {"artist": "Con's Universe", "title": "Evenfall (Original Mix)"}])
        self.assertEqual(len(c["hit"]), 2)

    def test_tracklist_times(self):
        """Zeitmarken aus kopierten YouTube-Tracklisten (Markdown-Links) und Abweichung je Titel."""
        text = ("[00:00](https://www.youtube.com/watch?v=x&t=0s) Intro\n"
                "[04:56](https://www.youtube.com/watch?v=x&t=296s) Path Of Youth - Hypnotic (Original Mix)\n"
                "1:02:10 Estiva - Chemicals (Extended Mix) **\nOhne Zeit - Titel")
        self.assertEqual(plugin.tracklist_times(text), [296, 3730, None])
        c = plugin.compare(text, [{"artist": "Path Of Youth", "title": "Hypnotic (Extended Mix)", "track_start": 295.0, "start": 325}])
        self.assertEqual(c["timing"], [{"name": "Path Of Youth - Hypnotic (Original Mix)", "list": 296, "calc": 295.0, "seen": 325, "diff": -1}])
        self.assertIn("Estiva - Chemicals (Extended Mix)", c["miss"])                       # „**“ entfernt
        t = plugin.report_text("/m", {"duration": 4000, "secs": 1}, [], c, "1 Titel")
        self.assertIn("Hypnotic (Original Mix): Tracklist 04:56 · berechnet 04:55 (-1 s) · erkannt ab 05:25", t)

    def test_near_misses(self):
        blocks = [{"start": 0, "cands": [[90, 1, 1.0, "lock", 0], [12, 2, 1.0, "lock", 0]]},
                  {"start": 5, "cands": [[80, 1, 1.0, "lock", 0], [17, 2, 1.0, "lock", 0], [9, 3, 1.0, "lock", 0]]}]
        near = plugin.near_misses(blocks, {1}, {2: "/x/A - Zwei.wav", 3: "/x/B - Drei.wav"})
        self.assertEqual([(x["name"], x["hits"], x["at"], x["blocks"]) for x in near],
                         [("A - Zwei", 17, 5, 2), ("B - Drei", 9, 5, 1)])
        t = plugin.report_text("/m.mp3", {"duration": 60, "secs": 1}, [], None, "3 Titel", near, True)
        self.assertIn("nicht mitgezählt", t)
        self.assertIn("A - Zwei: höchstens 17 Treffer (bei 00:05), 2× unter den Besten", t)

    def test_track_name_from_filename(self):
        self.assertEqual(plugin.track_name("/x/Mara Lind - Golden Hour (Extended Mix).wav"), ("Mara Lind", "Golden Hour (Extended Mix)"))
        self.assertEqual(plugin.track_name("/x/ohne.wav"), ("", "ohne"))

    def test_compare_and_report(self):
        found = [{"artist": "Mara Lind", "title": "Golden Hour (Extended Mix)"}, {"artist": "Kai Ost", "title": "Fremd"}]
        c = plugin.compare("01. Mara Lind - Golden Hour\n02. Lena Berg - Glas\nID - ID", found)
        self.assertEqual((c["expected"], c["hit"], c["miss"], c["extra"]),
                         (2, ["Mara Lind - Golden Hour"], ["Lena Berg - Glas"], ["Kai Ost - Fremd"]))
        rows = [{"start": 0, "end": 35, "artist": "Mara Lind", "title": "Golden Hour", "tempo": 3.0, "keylock": True, "conf": 0.9},
                {"start": 35, "end": 60, "artist": "Kai Ost", "title": "Fremd", "tempo": -6.0, "keylock": False, "conf": 0.5}]
        t = plugin.report_text("/mix.mp3", {"duration": 3700, "secs": 12}, rows, c, "2 Titel")
        self.assertIn("00:00–00:35  Mara Lind - Golden Hour  (Tempo +3.0 %, Sicherheit 90 %)", t)
        self.assertIn("ohne Keylock", t)
        self.assertIn("unsicher", t)
        self.assertIn("1 von 2 erkannt (50 %)", t)
        self.assertIn("1:01:40", t)
        with open(os.path.join(PLUG, "plugin.json"), encoding="utf-8") as fh:
            self.assertIn(f"Plugin {json.load(fh)['version']})", t)


# =========================================================================== Erkennung (NumPy, SciPy, FFmpeg)
SR = 22050


def synth(seed, secs=50):
    """Einfacher Club-Titel: Kick, Hi-Hat, Akkorde, Bass, Melodie – je Seed andere Tonart, Folge und Tempo."""
    import numpy as np
    rng = np.random.default_rng(seed)
    bpm = rng.uniform(120, 130)
    beat = 60 / bpm
    n = int(SR * secs)
    y = np.zeros(n + SR * 2)
    root = 110 * 2 ** (rng.integers(0, 12) / 12)
    scale = [0, 2, 3, 5, 7, 8, 10]
    prog = rng.integers(0, 7, 4)
    melody = rng.integers(0, 7, 16)
    on = rng.random(16) < 0.7

    def note(f, dur, harm, decay):
        t = np.arange(int(SR * dur)) / SR
        return sum(np.sin(2 * np.pi * f * k * t + rng.random() * 6) / k for k in range(1, harm + 1)) * np.exp(-decay * t)
    kl = int(SR * 0.25)
    kick = np.sin(2 * np.pi * np.cumsum(np.linspace(150, 45, kl)) / SR) * np.exp(-np.linspace(0, 8, kl))
    t, b = 0.0, 0
    while t < secs:
        i = int(t * SR)
        y[i:i + kl] += kick
        hat = rng.standard_normal(int(SR * 0.04)) * np.exp(-np.linspace(0, 10, int(SR * 0.04))) * 0.15
        j = int((t + beat / 2) * SR)
        y[j:j + len(hat)] += hat
        deg = prog[(b // 4) % 4]
        if b % 4 == 0:
            for dd in (0, 2, 4):
                st = scale[(deg + dd) % 7] + 12 * ((deg + dd) // 7)
                x = note(root * 2 * 2 ** (st / 12), beat * 4, 5, 0.6) * 0.12
                y[i:i + len(x)] += x
        x = note(root / 2 * 2 ** (scale[deg] / 12), beat / 2, 8, 4) * 0.35
        y[j:j + len(x)] += x
        for h in (0, 1):
            m = (b * 2 + h) % 16
            if on[m]:
                x = note(root * 4 * 2 ** ((scale[melody[m] % 7] + 12) / 12), beat / 2, 4, 5) * 0.2
                s0 = int((t + h * beat / 2) * SR)
                y[s0:s0 + len(x)] += x
        t += beat
        b += 1
    y = y[:n]
    return y / (abs(y).max() * 1.1)


def write_wav(path, y):
    import numpy as np
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((y * 32767).astype("<i2").tobytes())


@unittest.skipUnless(HAVE, "Erkennung nur mit NumPy, SciPy und FFmpeg (Workflow „Mix-Analyse-Test“)")
class TestRecognition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp()
        cls.files = []
        for s in range(24):
            p = os.path.join(cls.d, f"t{s:02d}.wav")
            write_wav(p, synth(s))
            cls.files.append(p)
        cls.index = fp.Index.build([(i, *fp.fingerprint(fp.decode(p, FFMPEG))) for i, p in enumerate(cls.files)])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d, ignore_errors=True)

    def mix(self, spec, name, extra=()):
        """spec: [(Datei, Faktor, "lock"|"pitch")] – je 36 s ab Sekunde 8, 8 s überblendet, Rauschen und EQ."""
        args, flt = [], ""
        for i, (path, fac, mode) in enumerate(spec):
            args += ["-ss", "8", "-t", "36", "-i", path]
            f = f"atempo={fac}" if mode == "lock" else f"asetrate={SR}*{fac},aresample={SR}"
            flt += f"[{i}:a]{f}[s{i}];"
        cur = "s0"
        for k in range(1, len(spec)):
            flt += f"[{cur}][s{k}]acrossfade=d=8[x{k}];"
            cur = f"x{k}"
        flt += f"anoisesrc=c=pink:a=0.03:r={SR}:d=600:seed=7[n];[{cur}][n]amix=inputs=2:duration=first,highpass=f=60,volume=1.5[out]"
        out = os.path.join(self.d, name)
        subprocess.run([FFMPEG, "-v", "error", "-y", *args, "-filter_complex", flt, "-map", "[out]", "-b:a", "192k", out], check=True)
        return out

    def test_mix_with_tempo_and_pitch(self):
        spec = [(self.files[3], 1.0, "lock"), (self.files[17], 1.04, "lock"), (self.files[8], 0.95, "lock"),
                (self.files[21], 1.07, "pitch"), (self.files[12], 0.96, "pitch")]
        segs = [s for s in fp.segments(fp.query(self.index, fp.decode(self.mix(spec, "mix.mp3"), FFMPEG))) if s["conf"] >= 0.6]
        self.assertEqual([s["track"] for s in segs], [3, 17, 8, 21, 12])
        for s, (_p, fac, mode) in zip(segs, spec):
            self.assertAlmostEqual(s["tempo"], (fac - 1) * 100, delta=1.6)
            if fac != 1.0:
                self.assertEqual(s["keylock"], mode == "lock")
        self.assertLess(segs[1]["start"], segs[2]["start"])
        # Titelanfang im Mix (berechnet): jeder Titel beginnt bei Sekunde 8 → Mixzeit des Abschnitts − 8/Tempo.
        # Synthetische Titel wiederholen sich exakt in 4-Takt-Phrasen – dort ist der Anfang mehrdeutig; mindestens
        # drei von fünf müssen auf 2 s stimmen.
        t, ok = 0.0, 0
        for s, (_p, fac, _m) in zip(segs, spec):
            ok += abs(s["track_start"] - (t - 8 / fac)) <= 2
            t += 36 / fac - 8
        self.assertGreaterEqual(ok, 3)

    def test_mix_in_index_is_excluded(self):
        """Messung 27.10.2026: Liegt der Mix im indexierten Ordner, fand er sich selbst – mit exclude zählt er nicht."""
        spec = [(self.files[5], 1.02, "lock"), (self.files[9], 0.97, "lock")]
        mix = self.mix(spec, "self.mp3")
        y = fp.decode(mix, FFMPEG)
        n = len(self.files)
        idx = fp.Index.build([(i, *fp.fingerprint(fp.decode(p, FFMPEG))) for i, p in enumerate(self.files)]
                             + [(n, *fp.fingerprint(y))])
        self_only = [s["track"] for s in fp.segments(fp.query(idx, y)) if s["conf"] >= 0.6]
        self.assertEqual(self_only, [n])                                            # ohne exclude: nur der Mix selbst
        segs = [s["track"] for s in fp.segments(fp.query(idx, y, exclude=[n])) if s["conf"] >= 0.6]
        self.assertEqual(segs, [5, 9])

    def test_unknown_tracks_not_reported(self):
        extra = []
        for s in (100, 101, 102):
            p = os.path.join(self.d, f"u{s}.wav")
            write_wav(p, synth(s))
            extra.append(p)
        mix = self.mix([(extra[0], 1.03, "lock"), (extra[1], 0.97, "lock"), (extra[2], 1.0, "lock")], "unk.mp3")
        segs = [s for s in fp.segments(fp.query(self.index, fp.decode(mix, FFMPEG))) if s["conf"] >= 0.6]
        self.assertEqual(segs, [])


if __name__ == "__main__":
    unittest.main()
