"""Live-Test der Online-Dienste (#6, #7): echte Abfragen bei MusicBrainz, Deezer und iTunes.

Läuft nur mit ONLINE_TESTS=1 (Workflow „Online-Test“ in GitHub Actions) – prüft, ob die Antworten der Dienste
noch zu den Feldzuordnungen des Plugins passen. Ohne Netz bzw. ohne die Variable wird übersprungen.
"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import onlinematch as om  # noqa: E402

LIVE = os.environ.get("ONLINE_TESTS") == "1"
INFO = {"title": "One More Time", "mix": "", "artist": "Daft Punk", "isrc": "", "duration": 320, "album": ""}


def plugin():
    spec = importlib.util.spec_from_file_location("online_plugin", os.path.join(ROOT, "plugins", "online", "plugin.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(LIVE, "nur mit ONLINE_TESTS=1 (Netz nötig)")
class TestLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = plugin()
        cls.cl = om.Client(cls.mod.USER_AGENT, cls.mod.INTERVALS)

    def check(self, c, s, src):
        self.assertIsNotNone(c, f"{src}: kein Kandidat")
        self.assertGreaterEqual(s, om.MAYBE, f"{src}: bester Treffer nur {s:.2f}: {c}")
        self.assertIn("daft punk", om.norm(", ".join(c.get("artists") or [])), src)

    def test_musicbrainz(self):
        c, s = om.best(INFO, self.mod.mb_candidates(self.cl, INFO))
        self.check(c, s, "MusicBrainz")
        c = self.mod.mb_details(self.cl, c)
        print("MusicBrainz:", {k: c.get(k) for k in ("title", "album", "date", "label", "catno", "isrc", "track", "cover")})
        self.assertTrue(c.get("album"))
        self.assertRegex(c.get("date") or "", r"^\d{4}")
        self.assertTrue(c.get("ids", {}).get("TXXX:MusicBrainz Album Id"))
        # ISRC-Weg mit der ISRC aus dem Treffer
        if c.get("isrc"):
            cands = self.mod.mb_candidates(self.cl, dict(INFO, isrc=c["isrc"]))
            self.assertTrue(cands, "ISRC-Suche liefert nichts")

    def test_deezer(self):
        raw = self.cl.json("https://api.deezer.com/search?q=" + om.urllib.parse.quote("Daft Punk One More Time") + "&limit=3")
        print("Deezer roh:", str(raw)[:400])
        c, s = om.best(INFO, self.mod.deezer_candidates(self.cl, INFO))
        self.check(c, s, "Deezer")
        c = self.mod.deezer_details(self.cl, c)
        print("Deezer:", {k: c.get(k) for k in ("title", "album", "date", "label", "genre", "isrc", "bpm", "cover")})
        self.assertRegex(c.get("isrc") or "", r"^[A-Z]{2}[A-Z0-9]{3}\d{7}$")
        self.assertTrue(c.get("album") and c.get("cover"))
        cands = self.mod.deezer_candidates(self.cl, dict(INFO, isrc=c["isrc"]))
        self.assertEqual(cands[0]["isrc"], c["isrc"])          # Abruf über ISRC

    def test_itunes(self):
        c, s = om.best(INFO, self.mod.itunes_candidates(self.cl, INFO, "US"))
        self.check(c, s, "iTunes")
        print("iTunes:", {k: c.get(k) for k in ("title", "album", "date", "genre", "track", "cover")})
        self.assertIn("1400x1400", c.get("cover") or "")
        self.assertTrue(c.get("genre"))


if __name__ == "__main__":
    unittest.main()
