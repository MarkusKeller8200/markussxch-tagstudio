"""#191: Beatgrid-Status je Titel aus Tags und Wellenform-Cache (ohne Dekodieren, nur lesen)."""
import os
import time

from helpers import text, write_mp3
from helpers import geob  # noqa: E402
from test_serato import grid
from test_tagger_tools import Base


class TestGridStatus(Base):
    def wait(self, s):
        for _ in range(500):
            st = s.task_status()
            if st.get("done"):
                return st
            time.sleep(0.02)

    def test_status_and_cache(self):
        write_mp3(os.path.join(self.B, "s.mp3"), [text("TIT2", "Serato"), text("TBPM", "126"),
                                                  geob("Serato BeatGrid", grid([], 0.25, 126.0))], audio_seed=1)
        write_mp3(os.path.join(self.B, "a.mp3"), [text("TIT2", "Analyse")], audio_seed=2)
        write_mp3(os.path.join(self.B, "b.mp3"), [text("TIT2", "BPM"), text("TBPM", "124")], audio_seed=3)
        write_mp3(os.path.join(self.B, "n.mp3"), [text("TIT2", "Nichts")], audio_seed=4)
        write_mp3(os.path.join(self.B, "x.mp3"), [text("TIT2", "Ohne Schlag"), text("TBPM", "999")], audio_seed=5)
        from session import Session
        import waveform
        from unittest import mock
        p = mock.patch.object(waveform, "DIR", os.path.join(self.dir, "wave"))      # Cache nur im Testordner
        p.start()
        self.addCleanup(p.stop)
        s = Session()
        s.start_tag_load(self.B, False)
        self.wait(s)
        idx = {os.path.basename(f.path): i for i, f in enumerate(s.tag_files)}
        self.assertTrue(all(r["grid"] == "" for r in s.tag_rows()["rows"]))          # noch nicht geprüft
        st = s.tag_grid_status()["status"]
        self.assertEqual({n: st[i] for n, i in idx.items() if n != "3.mp3"},
                         {"s.mp3": "serato", "a.mp3": "none", "b.mp3": "bpm", "n.mp3": "none", "x.mp3": "none"})
        # Analyse im Cache (wie nach dem Abspielen bzw. „Beatgrid analysieren“)
        ka = waveform.key_for(s.tag_files[idx["a.mp3"]])
        self.assertTrue(s.wave_save(ka, [1] * 100, [1] * 100, {"bpm": 125.0, "first": 0.1})["ok"])
        kx = waveform.key_for(s.tag_files[idx["x.mp3"]])
        s.wave_save(kx, [1] * 100, [1] * 100, None)                                     # analysiert, kein Schlag
        self.assertEqual(s.tag_grid_status([idx["a.mp3"]])["status"][idx["a.mp3"]], "none")   # Zwischenspeicher
        st = s.tag_grid_status([idx["a.mp3"], idx["x.mp3"]], fresh=True)["status"]
        self.assertEqual((st[idx["a.mp3"]], st[idx["x.mp3"]]), ("analyse", "nobeat"))
        rows = {r["name"]: r["grid"] for r in s.tag_rows()["rows"]}
        self.assertEqual((rows["a.mp3"], rows["s.mp3"]), ("analyse", "serato"))      # in den Zeilen mitgeliefert
        self.assertFalse(any(f.is_modified() for f in s.tag_files))                   # nur lesen
