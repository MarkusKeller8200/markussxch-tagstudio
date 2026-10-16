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


class AddedBackfillTest(unittest.TestCase):
    """#184: Nachtragen aus dem frühesten Snapshot (Audio-Inhalt, auch nach Umbenennen) bzw. von Hand."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ts_added_")
        self._env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.dir
        self._cfg = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = core.CONFIG_OLD = os.path.join(self.dir, "cfg.json")
        self.lib = os.path.join(self.dir, "lib")
        os.makedirs(self.lib)
        for n in range(3):
            write_mp3(os.path.join(self.lib, f"{n}.mp3"), [text("TIT2", f"T{n}")], audio_seed=n + 1)

    def tearDown(self):
        core.CONFIG, core.CONFIG_OLD = self._cfg
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_first_seen_and_session(self):
        import time
        import snapshots as sn
        from session import Session
        s = Session()
        st = s.snap_store
        lib = st.add_library(self.lib)
        old = sn.create(st, lib["id"], "Erster")
        m = st.manifest(lib["id"], old["id"])
        st.write_manifest(lib["id"], dict(m, created="2025-03-01T08:00:00"))    # älterer Stand
        os.replace(os.path.join(self.lib, "1.mp3"), os.path.join(self.lib, "eins.mp3"))   # umbenannt: Audio gleich
        write_mp3(os.path.join(self.lib, "neu.mp3"), [text("TIT2", "Neu")], audio_seed=9)
        seen = sn.first_seen(st, [os.path.join(self.lib, n) for n in ("0.mp3", "eins.mp3", "neu.mp3")])
        self.assertEqual(seen[os.path.join(self.lib, "0.mp3")]["created"], "2025-03-01T08:00:00")
        self.assertIn(os.path.join(self.lib, "eins.mp3"), seen)
        self.assertNotIn(os.path.join(self.lib, "neu.mp3"), seen)
        s.start_tag_load(self.lib, False)
        while not s.task_status()["done"]:
            time.sleep(0.02)
        names = [os.path.basename(f.path) for f in s.tag_files]
        idx = list(range(len(names)))
        prev = s.tag_added(idx, "snapshot", "", False, False)
        by = {r["name"]: r for r in prev["rows"]}
        self.assertTrue(by["0.mp3"]["new"].startswith("2025-03-01T08:00:00"))
        self.assertIn("Snapshot", by["0.mp3"]["source"])
        self.assertEqual(by["neu.mp3"]["new"], "")                         # ohne Snapshot und ohne Datum: nichts
        self.assertEqual(prev["count"], 3)
        prev = s.tag_added(idx, "snapshot", "2026-10-01", False, False)    # Ersatzdatum für den neuen Titel
        self.assertEqual(prev["count"], 4)
        s.tag_added(idx, "snapshot", "2026-10-01", False, True)
        f0 = s.tag_files[names.index("0.mp3")]
        self.assertTrue(f0.text(tsmeta.ADDED).startswith("2025-03-01T08:00:00"))
        self.assertTrue(f0.is_modified())                                   # erst beim Speichern geschrieben
        again = s.tag_added(idx, "date", "2026-01-01", False, False)        # vorhanden → bleibt
        self.assertEqual((again["count"], again["skipped"]), (0, 4))
        self.assertEqual(s.tag_added(idx, "date", "2026-01-01", True, False)["count"], 4)
        with self.assertRaises(ValueError):
            s.tag_added(idx, "date", "", False, False)
