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

    def test_doc_up_to_date(self):
        import subprocess
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        r = subprocess.run([sys.executable, os.path.join(root, "tools", "id3_frames_doc.py"), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
