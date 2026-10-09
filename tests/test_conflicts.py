"""Tests für den Konfliktschutz beim Speichern (#55): externe Änderungen nicht stillschweigend überschreiben."""
import os
import shutil
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import core  # noqa: E402
from helpers import text, txxx, write_mp3  # noqa: E402
from id3tags import MP3File  # noqa: E402


class TestConflicts(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ts_conf_")
        self.old = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = core.CONFIG_OLD = os.path.join(self.dir, "cfg.json")
        self.lib = os.path.join(self.dir, "lib")
        os.makedirs(self.lib)
        for n in "ab":
            write_mp3(os.path.join(self.lib, f"{n}.mp3"), [text("TIT2", n), text("TKEY", "8A"), txxx("Comment", "alt")])
        from session import Session
        self.s = Session()
        self.s.set_backup(False)
        self.s.start_tag_load(self.lib, False)
        self.wait()

    def tearDown(self):
        core.CONFIG, core.CONFIG_OLD = self.old
        shutil.rmtree(self.dir, ignore_errors=True)

    def wait(self):
        while not self.s.task_status().get("done"):
            time.sleep(0.02)
        return self.s.task_status()

    def external(self, name, key, value, keep_mtime=False):
        p = os.path.join(self.lib, name)
        st = os.stat(p)
        f = MP3File(p)
        f.set_text(key, value)
        f.save()
        if keep_mtime:                       # wie Mp3tag mit „Änderungszeit erhalten“
            os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))

    def test_detect_and_merge(self):
        s = self.s
        s.tag_set([0], "TIT2", "Mein Titel")                 # eigene Änderung (ungespeichert)
        self.external("a.mp3", "TKEY", "9A", keep_mtime=True)  # fremdes Programm ändert Tonart
        r = s.start_save()
        self.assertFalse(r["ok"])
        self.assertTrue(r["conflict"])
        c = s.save_conflicts()["conflicts"]
        self.assertEqual(len(c), 1)
        self.assertEqual([(x["key"], x["old"], x["new"], x["mine"]) for x in c[0]["fields"]], [("TKEY", "8A", "9A", False)])
        s.save_merge_external()
        self.assertEqual(s.save_conflicts()["conflicts"], [])
        self.assertTrue(s.start_save()["ok"])
        self.wait()
        f = MP3File(os.path.join(self.lib, "a.mp3"))
        self.assertEqual((f.text("TIT2"), f.text("TKEY")), ("Mein Titel", "9A"))   # beides erhalten

    def test_force_and_clash(self):
        s = self.s
        s.tag_set([1], "TKEY", "1A")
        self.external("b.mp3", "TKEY", "9A")
        c = s.save_conflicts()["conflicts"][0]
        self.assertEqual(c["clash"], ["TKEY"])
        # Speichern ohne force schützt auch im Auftrag selbst
        st = core.save_files(s.modified(), backup_on=False)
        self.assertEqual(st["saved"], 0)
        self.assertIn("anderen Programm", st["errors"][0])
        self.assertTrue(s.start_save(force=True)["ok"])
        self.wait()
        self.assertEqual(MP3File(os.path.join(self.lib, "b.mp3")).text("TKEY"), "1A")

    def test_own_save_is_no_conflict(self):
        s = self.s
        s.tag_set([0], "TIT2", "x")
        self.assertTrue(s.start_save()["ok"])
        self.wait()
        s.tag_set([0], "TIT2", "y")
        self.assertTrue(s.start_save()["ok"])          # eigene Speicherung zählt nicht als fremd
        self.assertEqual(self.wait()["result"]["saved"], 1)


if __name__ == "__main__":
    unittest.main()
