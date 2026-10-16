"""#221: Beatgrid der eigenen Analyse im MP3 (TXXX:TAGSTUDIO_BEATGRID) – Format, Übernehmen, Lesen, Vorrang Serato."""
import os
import time
from unittest import mock

from helpers import geob, text, write_mp3
from test_serato import grid
from test_tagger_tools import Base

import beattag


class TestBeatTag(Base):
    def test_format(self):
        t = beattag.fmt({"bpm": 124.99812, "first": 0.12345, "conf": 0.871}, "2026-10-17")
        self.assertEqual(t, "bpm=124.998; first=0.1235; conf=0.87; src=analyse; date=2026-10-17")
        self.assertEqual(beattag.parse(t)["bpm"], 124.998)
        self.assertIsNone(beattag.parse("bpm=12; first=0"))                      # ausserhalb
        self.assertIsNone(beattag.parse("Unsinn"))
        with self.assertRaises(ValueError):
            beattag.fmt({"bpm": 500, "first": 0})

    def test_session_apply_and_read(self):
        import waveform
        p = mock.patch.object(waveform, "DIR", os.path.join(self.dir, "wave"))
        p.start()
        self.addCleanup(p.stop)
        write_mp3(os.path.join(self.B, "a.mp3"), [text("TIT2", "Analysiert"), text("TBPM", "125")], audio_seed=1)
        write_mp3(os.path.join(self.B, "s.mp3"), [text("TIT2", "Serato"), geob("Serato BeatGrid", grid([], 0.25, 126.0))], audio_seed=2)
        write_mp3(os.path.join(self.B, "n.mp3"), [text("TIT2", "Nicht analysiert")], audio_seed=3)
        from session import Session
        s = Session()
        s.start_tag_load(self.B, False)
        for _ in range(500):
            if s.task_status().get("done"):
                break
            time.sleep(0.02)
        idx = {os.path.basename(f.path): i for i, f in enumerate(s.tag_files)}
        a, sr, n = idx["a.mp3"], idx["s.mp3"], idx["n.mp3"]
        for i in (a, sr):
            s.wave_save(waveform.key_for(s.tag_files[i]), [1] * 100, [1] * 100, {"bpm": 124.5, "first": 0.2, "conf": 0.9})
        pre = s.tag_beatgrid([a, sr, n])
        self.assertEqual(pre["count"], 1)
        src = {r["name"]: r["source"] for r in pre["rows"]}
        self.assertIn("Serato", src["s.mp3"])
        self.assertIn("keine Analyse", src["n.mp3"])
        self.assertFalse(s.tag_files[a].is_modified())                             # Vorschau ändert nichts
        s.tag_beatgrid([a, sr, n], apply=True)
        fa = s.tag_files[a]
        self.assertTrue(fa.text(beattag.KEY).startswith("bpm=124.500; first=0.2000; conf=0.90"))
        self.assertFalse(s.tag_files[sr].is_modified())                            # Serato unberührt
        s.do_undo()                                                                 # Rückgängig nimmt es zurück
        self.assertEqual(fa.text(beattag.KEY), "")
        s.tag_beatgrid([a], apply=True)
        # Lesen: Status, Player-Raster (auch ohne Cache)
        self.assertEqual(s.tag_grid_status([a], fresh=True)["status"][a], "tag")
        os.remove(waveform._file(waveform.key_for(fa)))
        g = s.media_extra("tag", a)["grid"]
        self.assertEqual((g["source"], g["bpm"], g["from_tag"]), ("Analyse (Tag)", 124.5, True))
        self.assertEqual(s.tag_grid_status([sr], fresh=True)["status"][sr], "serato_diff")   # #223: Cache weicht ab
        # nochmals: schon gespeichert → übersprungen, ausser „ersetzen“
        self.assertEqual(s.tag_beatgrid([a])["count"], 0)
        # #223: mit „auch Serato“ wird das eigene Raster zum Vergleich gespeichert – Serato bleibt unberührt und massgebend
        import serato
        before = serato.of_file(s.tag_files[sr]).get("BeatGrid")
        pre = s.tag_beatgrid([sr], serato=True)
        self.assertEqual(pre["count"], 1)
        self.assertIn("zum Vergleich", pre["rows"][0]["source"])
        s.tag_beatgrid([sr], apply=True, serato=True)
        fs = s.tag_files[sr]
        self.assertTrue(fs.text(beattag.KEY).startswith("bpm=124.500"))
        self.assertEqual(serato.of_file(fs).get("BeatGrid"), before)
        os.remove(waveform._file(waveform.key_for(fs)))                              # nur noch der Tag
        self.assertEqual(s.tag_grid_status([sr], fresh=True)["status"][sr], "serato_diff")
        g = s.media_extra("tag", sr)["grid"]
        self.assertEqual((g["source"], g["check"]["from"], g["check"]["own"]["bpm"]), ("Serato", "tag", 124.5))
