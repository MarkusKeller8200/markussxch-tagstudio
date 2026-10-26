"""#375: Projekt-Webseite – Seiten, Links im Handbuch, Abschnitte für die Suche (braucht das Paket „markdown“)."""
import os
import sys
import tempfile
import unittest

try:
    import markdown  # noqa: F401
    HAVE = True
except ImportError:
    HAVE = False

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "ts_site", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "website.py"))
ts_site = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ts_site)


class TestLinks(unittest.TestCase):
    def test_link(self):
        L = ts_site._link
        self.assertEqual(L("HANDBUCH.en.md", "de"), "manual.html")
        self.assertEqual(L("HANDBUCH.md#installation", "en"), "handbuch.html#installation")
        self.assertEqual(L("../README.md", "de"), "index.html")
        self.assertEqual(L("../PLUGINS.md", "de"), ts_site.GH + "/blob/main/PLUGINS.md")
        self.assertEqual(L("ID3-FELDER.md", "de"), ts_site.GH + "/blob/main/docs/ID3-FELDER.md")
        self.assertEqual(L("#tagger", "de"), "#tagger")
        self.assertEqual(L("https://x.ch", "de"), "https://x.ch")


@unittest.skipUnless(HAVE, "Paket „markdown“ fehlt")
class TestBuild(unittest.TestCase):
    def test_build(self):
        with tempfile.TemporaryDirectory() as out:
            pages = ts_site.build(out)
            self.assertEqual(pages, ["datenschutz.html", "handbuch.html", "index.html", "manual.html", "statistik.html"])
            idx = open(os.path.join(out, "index.html"), encoding="utf-8").read()
            self.assertIn("certificate by", idx)                                   # #376: SignPath-Hinweis
            self.assertIn("SignPath Foundation", idx)
            self.assertIn("keine Telemetrie", open(os.path.join(out, "datenschutz.html"), encoding="utf-8").read())
            for p in pages:
                txt = open(os.path.join(out, p), encoding="utf-8").read()
                self.assertIn('<header class="top"', txt)
                self.assertNotIn("<script src=", txt)                                   # keine fremden Skripte
            hb = open(os.path.join(out, "handbuch.html"), encoding="utf-8").read()
            self.assertGreater(hb.count('<section data-s="'), 8)                       # Abschnitte je H2 für die Suche
            self.assertIn('id="installation"', hb)
            self.assertIn('id="q"', hb)
            self.assertNotIn("](", hb.split("<article>")[1][:2000])                     # Markdown-Links umgewandelt
            self.assertTrue(os.path.isfile(os.path.join(out, "img", "tagger-dark.png")))
            self.assertTrue(os.path.isfile(os.path.join(out, ".nojekyll")))
            st = open(os.path.join(out, "statistik.html"), encoding="utf-8").read()
            self.assertIn("summary.json", st)
            self.assertIn('href="handbuch.html"', st)


if __name__ == "__main__":
    unittest.main()
