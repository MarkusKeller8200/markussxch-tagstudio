"""#204: Online-Dienste als Plugins – Dienstbeschreibung, Übersicht, API-Tester, Testabfrage (ohne Internet)."""
import http.server
import json
import os
import threading
import unittest
import urllib.parse

from test_tagger_tools import Base   # setzt den Projektpfad

import services                       # noqa: E402


class FakeLexicon(http.server.BaseHTTPRequestHandler):
    """Nachbau der Lexicon Local API (nur was die Tests brauchen)."""
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        if u.path == "/v1/tracks":
            tracks = [{"id": 1, "artist": "Mara Lind", "title": "Nordlicht", "energy": 7, "danceability": 8, "location": "C:/M/n.mp3"},
                      {"id": 2, "artist": "Other", "title": "Kaltes Glas", "energy": 0, "danceability": 3}]
            off, lim = int(q.get("offset", 0)), int(q.get("limit", 1000))
            body = json.dumps({"data": {"tracks": tracks[off:off + lim], "total": len(tracks)}}).encode()
            self.send_response(200)
        else:
            body = json.dumps({"message": "Not found", "errorCode": 1}).encode()
            self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


class TestClean(unittest.TestCase):
    def test_clean_and_url(self):
        svc = services.clean({
            "name": "X", "docs": "javascript:alert(1)", "home": "https://x.example", "base": "https://api.x.example/v1",
            "auth": "magic",
            "endpoints": [
                {"id": "a", "method": "GET", "path": "/items/{id}", "label": "Item", "status": "full",
                 "params": [{"name": "fields", "default": "all"}]},
                {"id": "a", "method": "GET", "path": "/dup"},                       # doppelte ID fällt weg
                {"id": "b", "method": "POST", "path": "/items", "status": "partial"},
                {"id": "c", "method": "GET", "path": "/dl", "test": False},
                {"id": "bad id!", "path": "/x"}, {"id": "d", "method": "HACK", "path": "/x"}, {"id": "e", "path": "rel"}]})
        self.assertEqual(svc["docs"], "")                                         # nur http(s)
        self.assertEqual(svc["auth"], "none")
        self.assertEqual([e["id"] for e in svc["endpoints"]], ["a", "b", "c"])
        a, b, c = svc["endpoints"]
        self.assertEqual([(p["name"], p["in"], p["required"]) for p in a["params"]],
                         [("fields", "query", False), ("id", "path", True)])
        self.assertTrue(a["test"])
        self.assertFalse(b["test"])                                               # POST nie im Tester
        self.assertFalse(c["test"])
        self.assertEqual(services.counts(svc), {"full": 1, "partial": 1, "none": 1})
        self.assertEqual(services.build_url(svc, a, {"id": "4 2"}, {"key": "S3CR3T"}),
                         "https://api.x.example/v1/items/4%202?fields=all&key=S3CR3T")
        with self.assertRaises(ValueError):
            services.build_url(svc, a, {})
        self.assertIsNone(services.clean({"endpoints": []}))
        loc = services.clean({"name": "L", "kind": "local", "base": "http://localhost:1/v1", "docs": "http://localhost:1/docs"})
        self.assertEqual((loc["base"], loc["auth"]), ("http://localhost:1/v1", "local"))

    def test_redact_and_format(self):
        r = services.format_response(200, {"Content-Type": "application/json", "Set-Cookie": "x"},
                                     b'{"token":"S3CR3TVALUE","n":1}', "https://h/x?api_key=S3CR3TVALUE", 12.4,
                                     ["S3CR3TVALUE"])
        self.assertEqual(r["url"], "https://h/x?api_key=•••")
        self.assertIn('"token": "•••"', r["body"])
        self.assertTrue(r["json"] and r["ok"])
        self.assertNotIn("set-cookie", r["headers"])
        b = services.format_response(200, {"Content-Type": "image/jpeg"}, b"\xff\xd8\xff" + b"0" * 10, "u", 1)
        self.assertIn("Binärdaten", b["body"])

    def test_query_info(self):
        i = services.query_info({"title": "Nordlicht (Extended Mix)", "artist": " Mara Lind ", "duration": "6:12", "isrc": "cha1"})
        self.assertEqual((i["title"], i["mix"], i["artist"], i["duration"], i["isrc"]),
                         ("Nordlicht", "Extended Mix", "Mara Lind", 372, "CHA1"))


class TestServicePlugins(Base):
    def setUp(self):
        super().setUp()
        from session import Session
        self.s = Session()
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeLexicon)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def tearDown(self):
        self.srv.shutdown()
        super().tearDown()

    def wait(self):
        import time
        for _ in range(500):
            st = self.s.task_status()
            if st.get("done"):
                return st
            time.sleep(0.02)
        self.fail("hängt")

    def test_overview_and_detail(self):
        ov = self.s.services_overview()["services"]
        by = {x["name"]: x for x in ov}
        for name in ("LRCLIB", "Lexicon Local API", "Beatport API v4", "GitHub Releases (Updates)"):
            self.assertIn(name, by)
            self.assertTrue(by[name]["docs"].startswith("https://"), name)
        self.assertEqual(by["Lexicon Local API"]["counts"]["none"] + by["Lexicon Local API"]["counts"]["partial"], 27)
        self.assertIsNone(by["GitHub Releases (Updates)"]["plugin"])               # Kern, kein Plugin
        info = {p["id"]: p for p in self.s.plugins_list()["plugins"]}
        self.assertEqual(info["lyrics"]["service"]["docs"], "https://lrclib.net/docs")
        self.assertTrue(info["lyrics"]["service"]["test_query"])
        d = self.s.service_detail("beatport")
        dl = next(e for e in d["endpoints"] if e["id"] == "track-download")
        self.assertFalse(dl["test"])                                                # Downloads nie im Tester
        with self.assertRaises(ValueError):
            self.s.service_detail("mik")                                             # kein Dienst

    def test_api_tester_local(self):
        self.s.cfg.setdefault("plugin_options", {}).setdefault("lexicon", {})["import"] = {"url": self.url}
        r = self.s.start_service_api("lexicon", "tracks", {"limit": "1", "offset": "0"})
        self.assertTrue(r["ok"], r)
        st = self.wait()
        self.assertIsNone(st["error"], st)
        res = st["result"]
        self.assertEqual(res["status"], 200)
        self.assertTrue(res["json"])
        self.assertIn('"Nordlicht"', res["body"])
        self.assertIn("/v1/tracks?limit=1&offset=0", res["url"])
        # 404 wird angezeigt, nicht als Fehler geworfen
        self.s.start_service_api("lexicon", "track", {"id": "99"})
        res = self.wait()["result"]
        self.assertEqual((res["status"], res["ok"]), (404, False))
        # ändernde Endpunkte und ausgeschaltete Plugins werden abgelehnt
        self.s.start_service_api("lexicon", "tracks-delete", {})
        self.assertIn("ändert Daten", self.wait()["error"])
        self.s.plugin_enable("lexicon", False)
        self.assertFalse(self.s.start_service_api("lexicon", "tracks", {})["ok"])

    def test_test_query_without_track(self):
        self.s.cfg.setdefault("plugin_options", {}).setdefault("lexicon", {})["import"] = {"url": self.url}
        self.s.start_service_test("lexicon", {"artist": "mara", "title": "nordlicht"})
        res = self.wait()["result"]
        self.assertEqual([r["title"] for r in res["rows"]], ["Nordlicht"])
        self.assertIn("Energie 70", res["rows"][0]["extra"])
        self.assertTrue(any("2 Titel gelesen" in ln for ln in res["log"]))
        self.s.start_service_test("lexicon", {})
        self.assertIn("mindestens", self.wait()["error"])
        # LRCLIB mit nachgebautem Dienst: gleiche Bewertung wie im Tagger (Remix höchstens unsicher)
        from test_lyrics import FakeLrclib
        mod = self.s.plugins.get("lyrics").load()
        orig, iv = mod.http_get, dict(mod.INTERVALS)
        mod.http_get = FakeLrclib()
        for k in mod.INTERVALS:
            mod.INTERVALS[k] = 0
        try:
            self.s.start_service_test("lyrics", {"artist": "Mara Lind", "title": "Nordlicht", "duration": "6:12"})
            res = self.wait()["result"]
        finally:
            mod.http_get = orig
            mod.INTERVALS.update(iv)
        self.assertEqual(res["rows"][0]["title"], "Nordlicht")
        self.assertEqual(res["rows"][0]["mix"], "")
        self.assertTrue(res["rows"][0]["sure"])
        remix = next(r for r in res["rows"] if r["mix"])
        self.assertFalse(remix["sure"])
        self.assertTrue(any("Suche Titel + Künstler" in ln for ln in res["log"]))


if __name__ == "__main__":
    unittest.main()
