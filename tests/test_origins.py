"""Tests für die Herkunft der Tags (#22): origins.py und Sitzungs-Aufrufe."""
import os
import shutil
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import core  # noqa: E402
import origins  # noqa: E402
from helpers import geob, text, txxx, write_mp3, frame  # noqa: E402


class TestOrigins(unittest.TestCase):
    def test_builtin(self):
        o = origins.Origins()
        for key, sid in (("TXXX:MusicBrainz Album Id", "musicbrainz"), ("UFID:http://musicbrainz.org", "musicbrainz"),
                         ("GEOB:Serato Markers2", "serato"), ("GEOB:CuePoints", "mik"), ("TXXX:EnergyLevel", "mik"),
                         ("PRIV:TRAKTOR4", "traktor"), ("COMM:iTunNORM", "itunes"), ("TXXX:BEATPORT_TRACK_ID", "beatport"),
                         ("txxx:musicbrainz artist id", "musicbrainz"), ("TXXX:replaygain_track_gain#2", "replaygain"),
                         ("TIT2", None), ("TXXX:ENERGY", None),
                         # #39
                         ("GEOB:Energy", "mik"), ("GEOB:Key", "mik"), ("GEOB:PlatinumNotes", "platinum"),
                         ("TXXX:Meter", "beatunes"), ("TXXX:MOOD_ACOUSTIC", "beatunes"),
                         ("TXXX:MOOD_DANCEABILITY", "beatunes"), ("TXXX:MOOD_ELECTRONIC", "beatunes"),
                         ("TXXX:SPOTIFY_TRACK_ID", "spotify"), ("WXXX:Spotify", "spotify"),
                         ("TXXX:DISCOGS_RELEASE_ID", "discogs"), ("TXXX:Discogs Style", "discogs")):
            self.assertEqual(o.of(key), sid, key)
        self.assertIn("GEOB:Serato*", o.patterns("serato"))

    def test_custom_and_plugin_first(self):
        o = origins.Origins([{"pattern": "TXXX:VDJ*", "source": "VirtualDJ"}, {"pattern": "GEOB:Serato Autotags", "source": "serato"},
                             {"pattern": "TXXX:SERATO_X", "source": "Mixed In Key"}, {"pattern": "", "source": "x"}],
                            [("TXXX:BEATPORT_TRACK_ID", "Beatport (inoffiziell)")])
        self.assertEqual(o.of("TXXX:VDJ Cue"), "u:VirtualDJ")
        self.assertEqual(o.catalog()["u:VirtualDJ"]["kind"], "custom")
        self.assertEqual(o.of("TXXX:SERATO_X"), "mik")            # Name einer bekannten Quelle → deren id
        self.assertEqual(o.of("TXXX:BEATPORT_TRACK_ID"), "p:Beatport (inoffiziell)")
        self.assertEqual(o.of("TXXX:BEATPORT_GENRE"), "beatport")
        self.assertEqual(len(origins.clean_custom([{"pattern": "A", "source": "B"}, {"pattern": "a", "source": "C"}])), 1)


class TestSessionOrigins(unittest.TestCase):
    def test_detail_view_and_remove(self):
        from session import Session
        d = tempfile.mkdtemp(prefix="ts_or_")
        old = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = core.CONFIG_OLD = os.path.join(d, "cfg.json")
        try:
            lib = os.path.join(d, "lib")
            os.makedirs(lib)
            for n in "ab":
                write_mp3(os.path.join(lib, f"{n}.mp3"), [text("TIT2", n), txxx("MusicBrainz Album Id", "x"),
                          geob("Serato Markers2", b"\x01\x01AAAA"), geob("Serato Overview", b"\x01\x05"),
                          frame("PRIV", b"TRAKTOR4\x00abc"), txxx("BEATPORT_TRACK_ID", "1")])
            s = Session()
            self.assertIn("serato", s.settings()["origins"])
            s.start_tag_load(lib, False)
            while not s.task_status()["done"]:
                time.sleep(0.02)
            src = {f["key"]: f["src"] for f in s.tag_detail([0])["fields"]}
            self.assertEqual(src["GEOB:Serato Markers2"], "serato")
            self.assertEqual(src["PRIV:TRAKTOR4"], "traktor")
            self.assertEqual(s.settings()["origins"]["id3v4"]["name"], "v2.4")
            self.assertEqual(src["TXXX:BEATPORT_TRACK_ID"], "p:Beatport (inoffiziell)")   # aus plugin.json „fields“
            pv = s.tag_origin_remove([0, 1], "serato")
            self.assertEqual((pv["count"], pv["files"], len(pv["keys"])), (4, 2, 2))
            r = s.tag_origin_remove([0, 1], "serato", True)
            self.assertIn("4 Feld(er) von Serato entfernt", r["message"])
            self.assertFalse([f for f in s.tag_detail([1])["fields"] if f["src"] == "serato"])
            s.do_undo()
            self.assertEqual(len([f for f in s.tag_detail([1])["fields"] if f["src"] == "serato"]), 2)
            o = s.set_tag_origins([{"pattern": "TXXX:MusicBrainz Album Id", "source": "Meine App"}])
            self.assertIn("u:Meine App", o["catalog"])
            self.assertEqual({f["key"]: f["src"] for f in s.tag_detail([0])["fields"]}["TXXX:MusicBrainz Album Id"], "u:Meine App")
            # Vergleich zeigt die Herkunft ebenfalls
            lib2 = os.path.join(d, "lib2")
            shutil.copytree(lib, lib2)
            s2 = Session()
            s2.start_load(lib, lib2, False, "filename")
            while not s2.task_status()["done"]:
                time.sleep(0.02)
            s2.select(0)
            rows = {r["key"]: r["src"] for r in s2.view()["rows"]}
            self.assertEqual((rows["PRIV:TRAKTOR4"], rows["TXXX:MusicBrainz Album Id"], rows["TIT2"]),
                             ("traktor", "u:Meine App", None))     # Standardfeld ohne Kennzeichen (#40)
            s2.set_origin_std_badge(True)
            rows = {r["key"]: r["src"] for r in s2.view()["rows"]}
            self.assertEqual(rows["TIT2"], "id3v4")                     # auf Wunsch mit ID3-Version (#38)
            # #45: im Vergleich nur rechts entfernen, mit Rückgängig
            s2.select(0)
            pv = s2.compare_origin_remove("serato", "R", "all")
            self.assertEqual((pv["count"], pv["files"], pv["pairs"]), (4, 2, 2))
            self.assertEqual(s2.compare_origin_remove("serato", "both", "cur")["count"], 4)
            s2.compare_origin_remove("serato", "R", "all", apply=True)
            self.assertIsNone(s2.pairs[0][1].get("GEOB:Serato Markers2"))
            self.assertIsNotNone(s2.pairs[0][0].get("GEOB:Serato Markers2"))
            s2.do_undo()
            self.assertIsNotNone(s2.pairs[0][1].get("GEOB:Serato Markers2"))
            with self.assertRaises(ValueError):
                s2.compare_origin_remove("serato", "X", "all")
        finally:
            core.CONFIG, core.CONFIG_OLD = old
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
