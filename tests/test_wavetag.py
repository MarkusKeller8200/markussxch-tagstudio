"""#222 (W1): eigene Wellenform im MP3 – GEOB „TagStudio Overview“, nur auf Wunsch, Serato nie anfassen."""
import os
import time
from unittest import mock

from helpers import geob, text, write_mp3
from test_tagger_tools import Base

import wavetag


class TestWaveTag(Base):
    def test_format(self):
        data = wavetag.encode([10] * 20, [5] * 20)
        self.assertEqual(data[:5], b"TSOV\x01")
        self.assertEqual(wavetag.decode(data), {"peaks": [10] * 20, "rms": [5] * 20})
        self.assertIsNone(wavetag.decode(b"SERATO" + data))                       # fremdes Format
        self.assertIsNone(wavetag.decode(data[:30]))                              # abgeschnitten
        with self.assertRaises(ValueError):
            wavetag.encode([1] * 20, [1] * 19)
        with self.assertRaises(ValueError):
            wavetag.encode([300] * 20, [1] * 20)

    def wait(self, s):
        for _ in range(500):
            if s.task_status().get("done"):
                return
            time.sleep(0.02)

    def test_save_only_when_enabled_and_read_back(self):
        import waveform
        p = mock.patch.object(waveform, "DIR", os.path.join(self.dir, "wave"))
        p.start()
        self.addCleanup(p.stop)
        serato_ov = b"\x01\x05" + bytes(range(200)) * 3
        path = os.path.join(self.B, "w.mp3")
        write_mp3(path, [text("TIT2", "Welle"), geob("Serato Overview", serato_ov)], audio_seed=4)
        from session import Session
        s = Session()
        s.start_tag_load(self.B, False)
        self.wait(s)
        i = next(i for i, f in enumerate(s.tag_files) if f.path == path)
        f = s.tag_files[i]
        s.wave_save(waveform.key_for(f), list(range(100)), [7] * 100)
        self.assertFalse(s.settings_page()["wave_in_file"])                       # Standard aus
        # Standard: Speichern schreibt keine Wellenform
        s.tag_set([i], "TIT2", "Welle 2")
        s.start_save()
        self.wait(s)
        from id3tags import MP3File
        self.assertIsNone(MP3File(path).get(wavetag.KEY))
        # eingeschaltet: beim nächsten Speichern als GEOB, Serato byte-genau unverändert
        s.set_wave_in_file(True)
        self.assertTrue(s.settings_page()["wave_in_file"])
        s.tag_set([i], "TIT2", "Welle 3")
        s.start_save()
        self.wait(s)
        g = MP3File(path)
        self.assertEqual(wavetag.of_file(g), {"peaks": list(range(100)), "rms": [7] * 100})
        import blobs
        self.assertEqual(blobs.split(g.get("GEOB:Serato Overview"))["data"], serato_ov)
        import origins
        self.assertEqual(origins.Origins().of(wavetag.KEY), "tagstudio")
        # Cache geleert → der Player liest die Wellenform aus dem MP3 und legt sie wieder in den Cache
        s2 = Session()
        s2.start_tag_load(self.B, False)
        self.wait(s2)
        j = next(j for j, x in enumerate(s2.tag_files) if x.path == path)
        os.remove(waveform._file(waveform.key_for(s2.tag_files[j])))
        w = s2.media_extra("tag", j)["wave"]
        self.assertEqual(w["peaks"], list(range(100)))
        self.assertIsNotNone(waveform.load(waveform.key_for(s2.tag_files[j])))
        # ohne Wellenform im Cache bleibt ein vorhandenes Feld unverändert
        self.assertFalse(wavetag.embed(s2.tag_files[j], None))
        with self.assertRaises(ValueError):
            s.set_wave_in_file("ja")
