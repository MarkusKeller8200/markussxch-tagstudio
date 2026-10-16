"""#187: Fehler melden / Funktion vorschlagen – vorausgefülltes GitHub-Formular, Schwärzen, Duplikatsuche (ohne Netz)."""
import io
import os
import sys
import unittest
import urllib.error
import urllib.parse
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import feedback  # noqa: E402


class TestFeedback(unittest.TestCase):
    def test_redact(self):
        s, hits = feedback.redact("Pfad C:\\Users\\Markus Keller\\Music\\a.mp3, /Users/markus/x, /home/mk/y, "
                                  "Mail a.b@example.ch, token=abc, Bearer xyz, 9f8e7d6c5b4a39281706f5e4d3c2b1a0ffee")
        for gone in ("Markus Keller", "markus/", "mk/", "a.b@example.ch", "abc", "xyz", "9f8e7d6c5b4a"):
            self.assertNotIn(gone, s)
        self.assertIn("C:\\Users\\…\\Music\\a.mp3", s)
        self.assertEqual(set(hits), {"Benutzerordner", "E-Mail-Adresse", "Zugangsdaten", "langer Schlüssel/Token"})
        self.assertEqual(feedback.redact("Speichern bricht bei TXXX:CATALOGNUMBER ab")[1], [])   # normaler Text bleibt

    def test_prepare(self):
        with self.assertRaises(ValueError):
            feedback.prepare("bug", {"title": "Absturz"})                      # Pflichtfelder fehlen
        with self.assertRaises(ValueError):
            feedback.prepare("spam", {})
        r = feedback.prepare("bug", {"title": "Absturz beim Speichern", "what": "Fehler in /Users/markus/a.mp3",
                                     "steps": "1. speichern", "area": "Tagger", "version": "4.5.0", "os": "Windows 11",
                                     "evil": "ignoriert", "labels": "_1 bereit"})
        u = urllib.parse.urlparse(r["url"])
        q = dict(urllib.parse.parse_qsl(u.query))
        self.assertEqual((u.netloc, u.path), ("github.com", "/MarkusKeller8200/markussxch-tagstudio/issues/new"))
        self.assertEqual(q["template"], "bug_report.yml")
        self.assertEqual(q["title"], "Fehler: Absturz beim Speichern")
        self.assertEqual((q["area"], q["version"]), ("Tagger", "4.5.0"))
        self.assertNotIn("markus", q["what"])
        self.assertNotIn("evil", q)
        self.assertNotIn("labels", q)                                          # Freigabe-Labels nie aus der Meldung
        self.assertEqual(r["labels"], ["bug", "triage"])
        self.assertEqual(r["redacted"], ["Benutzerordner"])
        f = feedback.prepare("feature", {"title": "Idee: Liedtexte im Player", "problem": "p", "solution": "s", "area": "Erfunden"})
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(f["url"]).query))
        self.assertEqual((q["title"], q["area"], q["template"]), ("Idee: Liedtexte im Player", "anderes", "feature_request.yml"))
        long = feedback.prepare("bug", {"title": "Lang", "what": "x " * 6000, "steps": "s"})
        self.assertTrue(long["truncated"])
        self.assertLessEqual(len(long["url"]), feedback.MAX_URL)

    def test_search(self):
        data = {"items": [{"number": 187, "title": "Melden", "state": "open", "html_url": "https://github.com/x/187",
                           "labels": [{"name": "idee"}]},
                          {"number": 5, "title": "PR", "state": "open", "html_url": "u", "pull_request": {}}]}
        urls = []
        with mock.patch.object(feedback, "fetch_json", lambda u: urls.append(u) or data):
            r = feedback.search("Fehler melden aus der App")
        self.assertEqual([x["number"] for x in r], [187])
        self.assertIn("repo:MarkusKeller8200/markussxch-tagstudio is:issue", urllib.parse.unquote(urls[0]))
        self.assertEqual(feedback.search("ab"), [])                           # zu kurz: keine Anfrage
        err = urllib.error.HTTPError("u", 403, "rate", {}, io.BytesIO(b""))
        with mock.patch.object(feedback, "fetch_json", mock.Mock(side_effect=err)):
            with self.assertRaisesRegex(RuntimeError, "zu viele Anfragen"):
                feedback.search("Speichern bricht ab")
        with mock.patch.object(feedback, "fetch_json", mock.Mock(side_effect=OSError("offline"))):
            with self.assertRaisesRegex(RuntimeError, "offline"):
                feedback.search("Speichern bricht ab")

    def test_templates_have_triage(self):
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".github", "ISSUE_TEMPLATE")
        for name in ("bug_report.yml", "feature_request.yml", "plugin_idea.yml"):
            with open(os.path.join(root, name), encoding="utf-8") as fh:
                head = fh.read()
            labels = head.split("body:")[0]
            self.assertIn('"triage"', labels, name)
            self.assertNotIn("_1 bereit", labels)                           # nie ein Freigabe-Label
        for kind, tpl in feedback.TEMPLATES.items():                           # Feld-IDs passen zur Vorlage
            with open(os.path.join(root, tpl), encoding="utf-8") as fh:
                t = fh.read()
            for fid, _l in feedback.FIELDS[kind]:
                self.assertIn(f"id: {fid}", t, f"{tpl}: {fid}")


if __name__ == "__main__":
    unittest.main()
