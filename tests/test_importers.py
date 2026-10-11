"""Importer mit Abgleich: beaTunes (#145) und Lexicon (#146), gemeinsamer Abgleich in importsync."""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from helpers import write_mp3, text, txxx
from test_tagger_tools import Base


class _Run(Base):
    def load(self):
        from session import Session
        self.s = Session()
        self.s.start_tag_load(self.B, False)
        self.wait()
        self.idx = {os.path.basename(f.path): i for i, f in enumerate(self.s.tag_files)}

    def wait(self):
        for _ in range(500):
            st = self.s.task_status()
            if st.get("done"):
                return st
            time.sleep(0.02)
        self.fail("hängt")

    def run_plugin(self, pid, **opts):
        r = self.s.start_plugin_action(pid, "import", sorted(self.idx.values()), opts)
        self.assertTrue(r["ok"], r)
        st = self.wait()
        self.assertIsNone(st["error"], st)
        return st["result"]

    def by(self, res):
        return {(r["name"], r["label"]): r for r in res.get("proposals", [])}

    def apply_checked(self, res):
        ids = [r["id"] for r in res["proposals"] if r["checked"]]
        out = self.s.plugin_apply(res["proposals_token"], ids)
        self.assertTrue(out["ok"], out)

    def f(self, name):
        return self.s.tag_files[self.idx[name]]


class TestBeatunes(_Run):
    def setUp(self):
        super().setUp()
        write_mp3(os.path.join(self.B, "a.mp3"), [text("TIT2", "Eins"), txxx("MOOD_DANCEABILITY", "37"),
                                                  txxx("MOOD_ACOUSTIC", "0"), txxx("MOOD_ELECTRONIC", "100")], audio_seed=31)
        write_mp3(os.path.join(self.B, "b.mp3"), [text("TIT2", "Zwei"), txxx("MOOD_DANCEABILITY", "80"),
                                                  txxx("Danceability", "55")], audio_seed=32)
        write_mp3(os.path.join(self.B, "c.mp3"), [text("TIT2", "Drei")], audio_seed=33)
        self.load()

    def test_sync_cycle(self):
        res = self.run_plugin("beatunes")
        by = self.by(res)
        self.assertRegex(res["message"], r"^2 von \d+ Titel")
        da = by[("a.mp3", "Danceability (DANCEABILITY)")]
        self.assertEqual((da["new"], da["checked"]), ("37", True))
        self.assertEqual(by[("a.mp3", "Acousticness (ACOUSTICNESS)")]["new"], "0")
        self.assertIn("Electronic 100", da["note"])
        # b: Datei hat schon einen anderen Wert, nie abgeglichen → fragen (nicht angehakt), alte Schreibweise bleibt
        db = by[("b.mp3", "Danceability (DANCEABILITY)")]
        self.assertFalse(db["checked"])
        self.assertIn("noch nie abgeglichen", db["hint"])
        self.apply_checked(res)
        a = self.f("a.mp3")
        self.assertEqual(a.text("TXXX:DANCEABILITY"), "37")
        self.assertEqual(json.loads(a.text("TXXX:TAGSTUDIO"))["sync"]["beatunes"], {"DANCEABILITY": 37, "ACOUSTICNESS": 0})
        # zweiter Lauf: nichts mehr zu tun für a
        res = self.run_plugin("beatunes")
        self.assertFalse([k for k in self.by(res) if k[0] == "a.mp3"])
        self.s._pending = None
        # beaTunes ändert den Wert, Datei unverändert → angehakt
        a.set_text("TXXX:MOOD_DANCEABILITY", "45")
        res = self.run_plugin("beatunes")
        r = self.by(res)[("a.mp3", "Danceability (DANCEABILITY)")]
        self.assertEqual((r["new"], r["checked"]), ("45", True))
        self.assertIn("geändert (37 → 45)", r["hint"])
        self.s._pending = None
        # Datei zusätzlich von Hand geändert → fragen
        a.set_text("TXXX:DANCEABILITY", "60")
        res = self.run_plugin("beatunes")
        r = self.by(res)[("a.mp3", "Danceability (DANCEABILITY)")]
        self.assertFalse(r["checked"])
        self.assertIn("seit dem letzten Abgleich geändert (37 → 60)", r["hint"])

    def test_like_kept(self):
        import ratings
        a = self.f("a.mp3")
        ratings.set_like(a, True)
        self.apply_checked(self.run_plugin("beatunes"))
        d = json.loads(a.text("TXXX:TAGSTUDIO"))
        self.assertTrue(d["like"])
        self.assertIn("beatunes", d["sync"])
        self.assertTrue(ratings.get_like(a))


class _Lexicon(BaseHTTPRequestHandler):
    tracks = []
    tags = {"categories": [{"id": 1, "label": "Genre"}, {"id": 2, "label": "Mood"}],
            "tags": [{"id": 1, "categoryId": 1, "label": "House"}, {"id": 5, "categoryId": 2, "label": "Dark"},
                     {"id": 6, "categoryId": 2, "label": "Driving"}]}

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/v1/tracks":
            lim, off = int(q.get("limit", ["100"])[0]), int(q.get("offset", ["0"])[0])
            if lim > 1000:
                body, code = {"message": "'limit' must be less than or equal to 1000", "errorCode": 5}, 400
            else:
                body, code = {"data": {"total": len(self.tracks), "limit": lim, "offset": off,
                                       "tracks": self.tracks[off:off + min(lim, 2)]}}, 200   # kleine Seiten testen
        elif u.path == "/v1/tags":
            body, code = {"data": self.tags}, 200
        else:
            body, code = {"message": f"Endpoint {u.path} does not exist", "errorCode": 4}, 400
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class TestLexicon(_Run):
    def setUp(self):
        super().setUp()
        write_mp3(os.path.join(self.B, "p.mp3"), [text("TIT2", "Pfad"), text("TPE1", "Mara Lind")], audio_seed=41)
        write_mp3(os.path.join(self.B, "n.mp3"), [text("TIT2", "Über Namen"), text("TPE1", "Kai Ost"),
                                                  txxx("ENERGY", "60")], audio_seed=42)
        write_mp3(os.path.join(self.B, "x.mp3"), [text("TIT2", "Fehlt"), text("TPE1", "Niemand")], audio_seed=43)
        self.load()
        p = self.f("p.mp3").path
        _Lexicon.tracks = [
            {"id": 1, "location": p.replace("\\", "/"), "locationUnique": p.replace("\\", "/").lower(), "artist": "Mara Lind",
             "title": "Pfad", "danceability": 7, "energy": 6, "happiness": 0, "tags": [1, 5, 6], "archived": 0},
            {"id": 2, "location": "Z:/anderswo/n.mp3", "locationUnique": "z:/anderswo/n.mp3", "artist": "Kai Ost",
             "title": "Über Namen", "danceability": 0, "energy": 6, "happiness": 3, "tags": [], "archived": 0},
            {"id": 3, "location": "Z:/archiv/x.mp3", "locationUnique": "z:/archiv/x.mp3", "artist": "Niemand",
             "title": "Fehlt", "danceability": 5, "energy": 5, "happiness": 5, "tags": [], "archived": 1},
        ]
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), _Lexicon)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def tearDown(self):
        if self.srv:
            self.srv.shutdown()
            self.srv.server_close()
        super().tearDown()

    def test_import(self):
        res = self.run_plugin("lexicon", url=self.url, happiness=True, mood=True)
        self.assertRegex(res["message"], r"^2 von \d+ Titel\(n\) in Lexicon gefunden \(3 Titel")
        by = self.by(res)
        self.assertEqual(by[("p.mp3", "Danceability (DANCEABILITY)")]["new"], "70")
        self.assertEqual(by[("p.mp3", "Energy (ENERGY)")]["new"], "60")
        self.assertNotIn(("p.mp3", "Happiness (HAPPINESS)"), by)              # 0 = nicht analysiert
        self.assertEqual(by[("p.mp3", "Stimmung (TMOO)")]["new"], "Dark, Driving")
        self.assertIn("über Pfad", by[("p.mp3", "Danceability (DANCEABILITY)")]["note"])
        self.assertNotIn(("n.mp3", "Energy (ENERGY)"), by)                     # schon gleich
        self.assertIn("Künstler + Titel", by[("n.mp3", "Happiness (HAPPINESS)")]["note"])
        self.assertFalse([k for k in by if k[0] == "x.mp3"])                  # archiviert
        self.apply_checked(res)
        n = self.f("n.mp3")
        # gleicher Wert (ENERGY) wird beim Übernehmen mitgemerkt
        self.assertEqual(json.loads(n.text("TXXX:TAGSTUDIO"))["sync"]["lexicon"], {"ENERGY": 60, "HAPPINESS": 30})

    def test_no_connection(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.srv = None
        r = self.s.start_plugin_action("lexicon", "import", [0], {"url": "http://127.0.0.1:9"})
        self.assertTrue(r["ok"])
        st = self.wait()
        self.assertIn("Keine Verbindung zu Lexicon", st["error"])


if __name__ == "__main__":
    import unittest
    unittest.main()
