"""#461–#469: sichtbarer Name TagStudioSX – kein altes „TagStudio“ in Oberfläche, Übersetzungen und Plugin-Texten.

Erlaubt bleiben technische Namen (docs/KONZEPT-MARKE.md): Datenordner „TagStudio“, Tag-Felder TAGSTUDIO_… und
„TagStudio Overview“, Playlists „TagStudio_…“, TagStudio.app (Update von 4.x).
"""
import glob
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OLD = re.compile(r"(?<![\w/\\~.\-])TagStudio(?!SX|[\w/\\*]|-Profile|-Ordner| folder|\.app| Overview| ›)")
ALLOWED = ("Benutzerordner unter TagStudio.", "user folder under TagStudio.", 'root + "TagStudio"', '+ "TagStudio")',
           '"TagStudio",', '"title": "TagStudio"', '"example": "TagStudio"')      # Cloud-Ordner „TagStudio“


def hits(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        if OLD.search(line) and not any(a in line for a in ALLOWED):
            out.append(line.strip()[:160])
    return out


class TestBrand(unittest.TestCase):
    def test_no_old_name_in_ui(self):
        files = (glob.glob(os.path.join(ROOT, "web", "*.js")) + glob.glob(os.path.join(ROOT, "web", "*.html"))
                 + glob.glob(os.path.join(ROOT, "web", "i18n", "*.json"))
                 + glob.glob(os.path.join(ROOT, "plugins", "*", "plugin.json")))
        bad = {}
        for p in files:
            with open(p, encoding="utf-8") as fh:
                h = hits(fh.read())
            if h:
                bad[os.path.relpath(p, ROOT)] = h
        self.assertEqual(bad, {})

    def test_wordmark_and_tokens(self):
        with open(os.path.join(ROOT, "web", "index.html"), encoding="utf-8") as fh:
            html = fh.read()
        self.assertIn('aria-label="TagStudioSX"', html)
        self.assertIn('<span class="wm-v">T</span>ag<span class="wm-o">S</span>tudio<span class="wm-b">SX</span>', html)
        self.assertIn("Developed by MarKusSXCH", html)
        with open(os.path.join(ROOT, "web", "app.css"), encoding="utf-8") as fh:
            css = fh.read()
        for tok in ("--brand-violet:#7952B3", "--brand-orange:#FF8A00", "--brand-blue:#007EBB",       # CI-Manual § 2
                    "--brand-violet:#B59AFF", "--brand-blue:#32B8F2", "--acc:#00699E", "--acc:#32B8F2"):
            self.assertIn(tok, css)

    def test_accent_contrast(self):
        """E6: Akzent hell/dunkel erfüllt WCAG AA gegen die App-Hintergründe (Text 4,5:1)."""
        def lum(h):
            c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
            return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

        def ratio(a, b):
            a, b = lum(a), lum(b)
            return (max(a, b) + 0.05) / (min(a, b) + 0.05)
        for acc, fg, bgs in (("#00699E", "#FFFFFF", ("#F4F5F8", "#FFFFFF", "#ECEFF4", "#ECEEF3")),
                             ("#32B8F2", "#0E1430", ("#121419", "#191C23", "#21252E", "#0E1014"))):
            self.assertGreaterEqual(ratio(acc, fg), 4.5)
            for bg in bgs:
                self.assertGreaterEqual(ratio(acc, bg), 4.5, (acc, bg))

    def test_technical_names_unchanged(self):
        import paths
        import tsmeta
        import appbackup
        import mirror
        self.assertEqual(os.path.basename(paths.base_dir()), "TagStudio")
        self.assertEqual(paths.mutex_name(), "MarKusSXCH-TagStudio")
        self.assertTrue(tsmeta.EDITED.startswith("TXXX:TAGSTUDIO_"))
        self.assertEqual(appbackup.PREFIX, "TagStudio-Programmdaten_")
        self.assertEqual(mirror.DEFAULT_SUB, "TagStudio-Spiegel")
        with open(os.path.join(ROOT, "packaging", "windows.iss"), encoding="utf-8") as fh:
            iss = fh.read()
        self.assertIn("AppId={{8F1E6C2A-3B7D-4E59-9C1A-6D2F7A1B5E30}", iss)
        self.assertIn("AppMutex=MarKusSXCH-TagStudio", iss)
        self.assertIn(r'Type: files; Name: "{app}\TagStudio.exe"', iss)


if __name__ == "__main__":
    unittest.main()
