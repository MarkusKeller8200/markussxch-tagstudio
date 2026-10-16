"""Live-Test der Online-Dienste (#6, #7, #204): echte Abfragen bei MusicBrainz, Deezer und iTunes über ihre Plugins.

Läuft nur mit ONLINE_TESTS=1 (Workflow „Online-Test“ in GitHub Actions) – prüft, ob die Antworten der Dienste
noch zu den Feldzuordnungen des Plugins passen. Ohne Netz bzw. ohne die Variable wird übersprungen.
"""
import os
import sys
import time
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
        try:
            return om.best(info, self.mod.candidates(self.ctx, self.cl, info, opts))
        except om.HttpError as ex:
            if ex.status in (429, 502, 503):              # Dienst überlastet (GitHub-Server teilen sich die IP)
                raise unittest.SkipTest(f"{self.p.name}: {ex}") from ex
            raise

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


# #205: Beispielwerte im Integrationsfenster müssen beim echten Dienst ein Resultat liefern
NOAUTH = {"musicbrainz": None, "deezer": None, "itunes": None, "lyrics": {"get", "search", "get-id"},  # get-cached: nur Zwischenspeicher
          "discogs": {"release", "master", "master-versions", "artist", "artist-releases", "label", "label-releases"}}


@unittest.skipUnless(LIVE, "nur mit ONLINE_TESTS=1 (Netz nötig)")
class TestExamples(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import plugins
        cls.m = plugins.Manager({})

    def test_endpoint_examples(self):
        bad, busy = [], []
        for pid, only in NOAUTH.items():
            svc = self.m.get(pid).service
            for ep in svc["endpoints"]:
                if not ep["test"] or (only is not None and ep["id"] not in only):
                    continue
                params = {p["name"]: p["example"] or p["default"] for p in ep["params"]}
                if any(p["required"] and not params[p["name"]] for p in ep["params"]):
                    bad.append(f"{pid}/{ep['id']}: kein Beispiel für Pflichtfeld")
                    continue
                if pid == "musicbrainz":
                    time.sleep(1.2)                         # 1 Anfrage/s (API-Tester drosselt nicht)
                try:
                    r = self.m.api_call(pid, ep["id"], params)
                except Exception as ex:  # noqa: BLE001
                    bad.append(f"{pid}/{ep['id']}: {type(ex).__name__}")
                    continue
                body = r.get("body") or ""
                empty = body.strip() in ("", "[]", "{}") or '"error"' in body[:200] or '"count": 0' in body[:200] \
                    or '"resultCount": 0' in body[:200] or '"data": []' in body[:200]
                if r["status"] in (429, 502, 503):           # Dienst überlastet – nicht das Beispiel
                    busy.append(f"{pid}/{ep['id']}")
                    continue
                if r["status"] != 200 or empty:
                    # nur Status und Art – keine Antwortdaten ins Protokoll (könnten Zugangsdaten enthalten, CodeQL #207/#209)
                    bad.append(f"{pid}/{ep['id']}: HTTP {r['status']}" + (" ohne Treffer" if empty else ""))
        # keine Ausgabe mit print (CodeQL #210/#211) – Befunde stehen in der Meldung des Tests
        self.assertEqual(bad, [], f"Beispiele ohne Resultat; ausgelastet, nicht abgefragt: {busy}")

    def test_query_examples(self):
        for pid in ("musicbrainz", "deezer", "itunes", "lyrics"):
            ex = self.m.get(pid).service["example"]
            self.assertTrue(ex.get("artist") and ex.get("title"), pid)
            try:
                r = self.m.test_query(pid, ex)
            except om.HttpError as e:
                if e.status in (429, 502, 503):
                    continue                                  # Dienst ausgelastet
                raise
            self.assertTrue(r["rows"], f"{pid}: keine Kandidaten für {ex}")
            self.assertTrue(r["rows"][0]["sure"], f"{pid}: bester Treffer nicht sicher: {r['rows'][0]}")


if __name__ == "__main__":
    unittest.main()
