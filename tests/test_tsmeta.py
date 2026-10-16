"""#184/#185: TagStudio-Zeitstempel „In Bibliothek aufgenommen“ und „Letzte Bearbeitung“."""
from __future__ import annotations

import datetime
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import core      # noqa: E402
import tsmeta    # noqa: E402
from helpers import text, write_mp3   # noqa: E402
from id3tags import MP3File, key_label   # noqa: E402


class TsMetaTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ts_meta_")
        self.p = os.path.join(self.dir, "a.mp3")
        write_mp3(self.p, [text("TIT2", "A")])

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_format_and_parse(self):
        v = tsmeta.now_iso(datetime.datetime(2026, 10, 16, 1, 55, 7, 123456))
        self.assertRegex(v, r"^2026-10-16T01:55:07[+-]\d\d:\d\d$")          # sekundengenau, mit Zeitzone
        self.assertEqual(tsmeta.parse(v).minute, 55)
        self.assertRegex(tsmeta.normalize("2026-10-01"), r"^2026-10-01T00:00:00[+-]")
        self.assertIsNone(tsmeta.parse("kein Datum"))
        with self.assertRaises(ValueError):
            tsmeta.normalize("31.12.")
        self.assertEqual(key_label(tsmeta.EDITED), "Letzte Bearbeitung (TagStudio)")
        self.assertEqual(key_label(tsmeta.ADDED), "In Bibliothek aufgenommen (TagStudio)")

    def test_edited_only_when_changed(self):
        f = MP3File(self.p)
        res = core.save_files([f], backup_on=False)                   # nichts geändert → kein Stempel
        self.assertEqual(MP3File(self.p).text(tsmeta.EDITED), "")
        f.set_text("TPE1", "Künstler")
        res = core.save_files([f], backup_on=False)
        self.assertEqual(res["saved"], 1)
        v1 = MP3File(self.p).text(tsmeta.EDITED)
        self.assertTrue(tsmeta.parse(v1))
        g = MP3File(self.p)                                             # Einlesen/Speichern ohne Änderung: bleibt
        core.save_files([g], backup_on=False)
        self.assertEqual(MP3File(self.p).text(tsmeta.EDITED), v1)
        h = MP3File(self.p)
        h.set_text("TALB", "Album")
        core.save_files([h], backup_on=False, stamp=False)              # abgeschaltet
        self.assertEqual(MP3File(self.p).text(tsmeta.EDITED), v1)
        self.assertEqual(MP3File(self.p).text("TALB"), "Album")

    def test_added_never_overwritten(self):
        f = MP3File(self.p)
        self.assertTrue(tsmeta.set_added(f, "2026-01-02"))
        self.assertFalse(tsmeta.set_added(f))                           # vorhanden → bleibt
        self.assertTrue(f.text(tsmeta.ADDED).startswith("2026-01-02T00:00:00"))
        self.assertTrue(tsmeta.set_added(f, "2026-03-04T10:00", overwrite=True))
        self.assertTrue(f.text(tsmeta.ADDED).startswith("2026-03-04T10:00:00"))


if __name__ == "__main__":
    unittest.main()
