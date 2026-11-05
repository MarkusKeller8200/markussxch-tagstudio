"""#262: Feld-Zuordnung ID3 ↔ MP4/M4A ↔ FLAC/OGG ↔ AAC (Grundlage der Übersicht in der Hilfe)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import formatmap  # noqa: E402
import id3frames  # noqa: E402


class TestFormatMap(unittest.TestCase):
    def test_keys_are_known_frames(self):
        for table in (formatmap.MP4, formatmap.VORBIS, formatmap.VORBIS_DIFF):
            for fid in table:
                self.assertIn(fid, id3frames.SPEC, fid)
        for table in (formatmap.MP4, formatmap.VORBIS):
            for fid, (lvl, txt) in table.items():
                self.assertIn(lvl, formatmap.MARK, fid)
                self.assertTrue(txt, fid)

    def test_cells(self):
        self.assertEqual(formatmap.cell(formatmap.MP4, "TIT2"), "✔ `©nam`")
        self.assertTrue(formatmap.cell(formatmap.MP4, "TBPM").startswith("◐"))
        self.assertEqual(formatmap.cell(formatmap.MP4, "AENC"), "✖")
        self.assertIn("*", formatmap.VORBIS["APIC"][1])          # Unterschied FLAC ↔ OGG markiert
        for fid in formatmap.VORBIS_DIFF:
            self.assertIn("*", formatmap.VORBIS[fid][1])

    def test_matches_implementation(self):
        """Hilfe-Tabelle und Lese-/Schreibschicht dürfen nicht auseinanderlaufen (#262)."""
        import mapfile
        import mp4tags
        for key, name in mapfile.VORBIS_MAP.items():
            fid = key.rstrip(":")
            self.assertIn(f"`{name}`", formatmap.VORBIS[fid][1], key)
        for key, atom in mp4tags.MP4_TEXT.items():
            self.assertIn(atom.decode("latin-1"), formatmap.MP4[key.rstrip(":")][1], key)
        for key, name in mp4tags.MP4_FREE.items():
            self.assertIn(name, formatmap.MP4[key][1], key)

    def test_formatcheck_tool(self):
        import importlib.util
        import shutil
        import tempfile
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        spec = importlib.util.spec_from_file_location("fc", os.path.join(root, "tools", "formatcheck.py"))
        fc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fc)
        from test_formats import make_flac, make_m4a, make_ogg, itext
        d = tempfile.mkdtemp()
        try:
            p, q, r = os.path.join(d, "a.flac"), os.path.join(d, "a.m4a"), os.path.join(d, "a.ogg")
            make_flac(p, ["TITLE=x", "SERATO_MARKERS_V2=QUJD"])
            make_m4a(q, itext(b"\xa9nam", "y"))
            make_ogg(r, ["TITLE=z"])
            rp = fc.report(p)
            self.assertEqual(rp["format"], "FLAC")
            self.assertEqual(rp["serato_fields"], ["SERATO_MARKERS_V2"])
            self.assertIn(["VORBIS_COMMENT", rp["layout"][1][1]], rp["layout"])
            self.assertEqual(fc.report(q)["native"][0], ["©nam", "y"])
            self.assertTrue(fc.roundtrip(p)["ok"])
            self.assertTrue(fc.roundtrip(q)["ok"])
            self.assertIsNone(fc.roundtrip(r)["ok"])
            self.assertEqual(fc.main([p, q, "--json", os.path.join(d, "r.json")]), 0)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_doc_up_to_date(self):
        import subprocess
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        r = subprocess.run([sys.executable, os.path.join(root, "tools", "id3_frames_doc.py"), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
