"""#243: API-Rekorder – Schwärzen, Pfadmuster, Entwurf der Dienstbeschreibung (ohne Browser und ohne Netz)."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
import api_recorder as ar  # noqa: E402
import services  # noqa: E402


class TestRecorder(unittest.TestCase):
    def test_redact(self):
        d = ar.redact({"user": {"email": "a@b.ch", "name": "Mara"}, "access_token": "abc", "items": list(range(10)),
                       "note": "Kontakt mara@example.ch", "hash": "9f8e7d6c5b4a39281706f5e4d3c2b1a0ffee1234"})
        self.assertEqual(d["user"], {"email": "•••", "name": "Mara"})
        self.assertEqual(d["access_token"], "•••")
        self.assertEqual(d["items"], [0, 1, 2])                                 # Listen gekürzt
        self.assertEqual((d["note"], d["hash"]), ("•••", "•••"))
        self.assertEqual(ar.safe_headers({"Cookie": "s=1", "Authorization": "Bearer x", "Accept": "application/json",
                                          "X-CSRF-Token": "y"}), {"accept": "application/json"})
        self.assertEqual(ar.safe_query("q=house&api_key=123&page=2"), {"q": "house", "api_key": "•••", "page": "2"})

    def test_template_path(self):
        self.assertEqual(ar.template_path("/api/tracks/12345/cues"), ("/api/tracks/{track_id}/cues", ["track_id"]))
        self.assertEqual(ar.template_path("/mixes/0f8fad5b-d9cb-469f-a165-70867728950e")[0], "/mixes/{mixe_id}")
        self.assertEqual(ar.template_path("/search")[0], "/search")

    def test_record_and_build(self):
        rec = [ar.record_response("GET", "https://api.x.example/v2/tracks/1?q=a&token=t", 200, {"Cookie": "c"}, None,
                                  json.dumps({"data": {"tracks": [{"id": 1, "title": "A", "bpm": 124}]}})),
               ar.record_response("GET", "https://api.x.example/v2/tracks/2?q=b", 200, {}, None,
                                  json.dumps({"data": {"tracks": [{"id": 2, "title": "B", "key": "8A"}]}})),
               ar.record_response("POST", "https://api.x.example/v2/search", 200, {}, json.dumps({"q": "x", "password": "p"}),
                                  json.dumps({"results": []})),
               ar.record_response("GET", "https://cdn.other.example/a.json", 200, {}, None, json.dumps({"x": 1}))]
        self.assertIsNone(ar.record_response("GET", "https://x/a", 200, {}, None, "<html>"))
        self.assertEqual(rec[0]["query"], {"q": "a", "token": "•••"})
        self.assertNotIn("cookie", json.dumps(rec).lower())
        self.assertEqual(rec[2]["body"], {"q": "x", "password": "•••"})
        svc = ar.build_service(rec, "X", "https://x.example")
        self.assertEqual(svc["base"], "https://api.x.example")
        eps = {e["path"]: e for e in svc["endpoints"]}
        self.assertEqual(sorted(eps), ["/v2/search", "/v2/tracks/{track_id}"])
        t = eps["/v2/tracks/{track_id}"]
        self.assertEqual((t["seen"], t["method"]), (2, "GET"))
        self.assertIn("data.tracks[].bpm", t["note"])
        self.assertIn("data.tracks[].key", t["note"])                          # Felder aus beiden Antworten
        self.assertEqual({p["name"]: p["default"] for p in t["params"]}, {"q": "a", "token": ""})
        clean = services.clean(svc)                                              # direkt als "service" verwendbar
        self.assertEqual(len(clean["endpoints"]), 2)
        self.assertTrue(any(p["in"] == "path" for p in clean["endpoints"][1]["params"]))


if __name__ == "__main__":
    unittest.main()
