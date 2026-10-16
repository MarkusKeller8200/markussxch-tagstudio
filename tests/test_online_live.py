"""Live-Test der Online-Dienste (#6, #7, #204): echte Abfragen bei MusicBrainz, Deezer und iTunes über ihre Plugins.

Läuft nur mit ONLINE_TESTS=1 (Workflow „Online-Test“ in GitHub Actions) – prüft, ob die Antworten der Dienste
noch zu den Feldzuordnungen des Plugins passen. Ohne Netz bzw. ohne die Variable wird übersprungen.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import onlinematch as om  # noqa: E402

LIVE = os.environ.get("ONLINE_TESTS") == "1"
INFO = {"title": "One More Time", "mix": "", "artist": "Daft Punk", "isrc": "", "duration": 320, "album": ""}


class Svc:
    """Modul und Context eines Dienst-Plugins."""
    def __init__(self, pid):
        import plugins
        self.p = plugins.Manager({}).get(pid)
        self.mod = self.p.load()
        assert self.mod is not None, self.p.error
        self.ctx = plugins.Context(self.p, None)
        self.cl = self.mod.client(self.ctx)

    def best(self, info, **opts):
        return om.best(info, self.mod.candidates(self.ctx, self.cl, info, opts))

    def details(self, c):
        return self.mod.details(self.ctx, self.cl, c)


@unittest.skipUnless(LIVE, "nur mit ONLINE_TESTS=1 (Netz nötig)")
class TestLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mb, cls.dz, cls.it = Svc("musicbrainz"), Svc("deezer"), Svc("itunes")

    def check(self, c, s, src):
        self.assertIsNotNone(c, f"{src}: kein Kandidat")
        self.assertGreaterEqual(s, om.MAYBE, f"{src}: bester Treffer nur {s:.2f}: {c}")
        self.assertIn("daft punk", om.norm(", ".join(c.get("artists") or [])), src)

    def test_musicbrainz(self):
        c, s = self.mb.best(INFO)
        self.check(c, s, "MusicBrainz")
        c = self.mb.details(c)
        print("MusicBrainz:", {k: c.get(k) for k in ("title", "album", "date", "label", "catno", "isrc", "track", "cover")})
        self.assertTrue(c.get("album"))
        self.assertRegex(c.get("date") or "", r"^\d{4}")
        self.assertTrue(c.get("ids", {}).get("TXXX:MusicBrainz Album Id"))
        # ISRC-Weg mit der ISRC aus dem Treffer
        if c.get("isrc"):
            cands = self.mb.mod.candidates(self.mb.ctx, self.mb.cl, dict(INFO, isrc=c["isrc"]), {})
            self.assertTrue(cands, "ISRC-Suche liefert nichts")

    def test_deezer(self):
        raw = self.dz.cl.json("https://api.deezer.com/search?q=" + om.urllib.parse.quote("Daft Punk One More Time") + "&limit=3")
        print("Deezer roh:", str(raw)[:400])
        c, s = self.dz.best(INFO)
        self.check(c, s, "Deezer")
        c = self.dz.details(c)
        print("Deezer:", {k: c.get(k) for k in ("title", "album", "date", "label", "genre", "isrc", "bpm", "cover")})
        self.assertRegex(c.get("isrc") or "", r"^[A-Z]{2}[A-Z0-9]{3}\d{7}$")
        self.assertTrue(c.get("album") and c.get("cover"))
        cands = self.dz.mod.candidates(self.dz.ctx, self.dz.cl, dict(INFO, isrc=c["isrc"]), {})
        self.assertEqual(cands[0]["isrc"], c["isrc"])          # Abruf über ISRC

    def test_itunes(self):
        c, s = self.it.best(INFO, itunes_country="US")
        self.check(c, s, "iTunes")
        print("iTunes:", {k: c.get(k) for k in ("title", "album", "date", "genre", "track", "cover")})
        self.assertIn("1400x1400", c.get("cover") or "")
        self.assertTrue(c.get("genre"))


if __name__ == "__main__":
    unittest.main()
