"""Tests für xmltools.py (XML erkennen, prüfen, formatieren) und die XML-Anbindung der Sitzung."""
import os
import shutil
import tempfile
import unittest

from helpers import write_mp3, text, txxx, frame

import xmltools as x
from id3tags import MP3File

SRC = ('<?xml version="1.0" encoding="ISO-8859-1"?><root a="1 &amp; 2"><item id="x">Wert &lt;5</item><empty/>'
       '<!-- Kommentar --><p>Hallo <b>Welt</b> und mehr</p><c><![CDATA[a<b]]></c></root>')


class TestXmlTools(unittest.TestCase):
    def test_detect(self):
        for t in ("<root>x</root>", '<?xml version="1.0"?><r/>', "<a><b/></a>", "<x y='1'/><!-- -->"):
            self.assertTrue(x.looks_like_xml(t), t)
        for t in ("", "<a/>", "Hallo <b>", "< 3 >", "<ab>text", "a < b > c", "Pop"):
            self.assertFalse(x.looks_like_xml(t), t)

    def test_check(self):
        self.assertTrue(x.check(SRC)["ok"])
        r = x.check("<a>\n  <b></a>")
        self.assertEqual((r["ok"], r["line"]), (False, 2))
        self.assertIn("End-Tag", r["error"])
        self.assertIn("Entität", x.check("<a>&nbsp;</a>")["error"])
        self.assertFalse(x.check("<a/><b/>")["ok"])

    def test_format_and_compact_roundtrip(self):
        f = x.format_xml(SRC)
        self.assertTrue(f["ok"])
        lines = f["text"].split("\n")
        self.assertEqual(lines[0], '<?xml version="1.0" encoding="ISO-8859-1"?>')
        self.assertIn('  <item id="x">Wert &lt;5</item>', lines)
        self.assertIn("  <p>Hallo <b>Welt</b> und mehr</p>", lines)  # Fließtext bleibt unverändert
        self.assertIn("  <c><![CDATA[a<b]]></c>", lines)
        c = x.format_xml(f["text"], compact=True)
        self.assertNotIn("\n", c["text"])
        self.assertEqual(c["text"], SRC)
        self.assertEqual(x.format_xml(c["text"])["text"], f["text"])
        self.assertFalse(x.format_xml("<a><b></a>")["ok"])

    def test_unicode(self):
        r = x.format_xml("<a><b>Grüße – 東京</b></a>")
        self.assertEqual(r["text"], "<a>\n  <b>Grüße – 東京</b>\n</a>")


class TestXmlFields(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tagstudio_xml_")
        self.path = os.path.join(self.dir, "x.mp3")
        geob = frame("GEOB", b"\x00application/xml\x00\x00Cues\x00<cues><cue pos=\"1\"/></cues>")
        write_mp3(self.path, [text("TIT2", "<b>kein XML"), txxx("Analyse", "<a><b>1</b></a>"), geob])

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_xml_of_item(self):
        f = MP3File(self.path)
        self.assertIsNone(x.xml_of_item(f.get("TIT2")))
        self.assertEqual(x.xml_of_item(f.get("TXXX:Analyse")), ("<a><b>1</b></a>", True))
        geob = next(f.get(k) for k in f.keys() if k.startswith("GEOB"))
        self.assertEqual(x.xml_of_item(geob), ('<cues><cue pos="1"/></cues>', False))

    def test_session(self):
        import time
        import core
        from session import Session
        old = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = core.CONFIG_OLD = os.path.join(self.dir, "cfg.json")
        try:
            s = Session()
            s.start_load(self.path, "", False, "filename")
            while not s.task_status()["done"]:
                time.sleep(0.02)
            rows = {r["key"]: r for r in s.view()["rows"]}
            self.assertEqual(rows["TXXX:Analyse"]["L"]["xml"], "edit")
            self.assertEqual(rows["TXXX:Analyse"]["L"]["edit"], "")
            geob = next(k for k in rows if k.startswith("GEOB"))
            self.assertEqual(rows[geob]["L"]["xml"], "view")
            self.assertIsNone(rows["TIT2"]["L"]["xml"])
            g = s.get_xml("L", "TXXX:Analyse")
            self.assertTrue(g["ok"] and g["editable"])
            self.assertFalse(s.get_xml("L", "TIT2")["ok"])
            new = s.xml_tool("format", g["text"])["text"]
            st = s.set_value("L", "TXXX:Analyse", new)
            self.assertEqual(st["meta"]["unsaved"], 1)
            self.assertFalse(s.xml_tool("check", "<a>")["ok"])
        finally:
            core.CONFIG, core.CONFIG_OLD = old


if __name__ == "__main__":
    unittest.main()
