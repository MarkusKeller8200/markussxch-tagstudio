"""Tests für den Änderungs-Viewer der Sicherungen (backup.diff_entry + Sitzung)."""
import os
import time
import unittest

from helpers import write_mp3, text, txxx
from test_tagger_tools import Base

import backup
from id3tags import MP3File


class TestBackupDiff(Base):
    def make(self):
        p = os.path.join(self.B, "d.mp3")
        write_mp3(p, [text("TIT2", "Nordlicht"), text("TPE1", "Mara Lind"), text("TBPM", "122"),
                      txxx("Energy", "70")], audio_seed=21)
        return p

    def test_diff_entry(self):
        p = self.make()
        w = backup.BackupWriter(os.path.join(self.dir, "bk"))
        w.add(p)
        zp = w.close()
        f = MP3File(p)
        f.set_text("TIT2", "Nordlicht (Extended Mix)")    # geändert
        f.set("TBPM", None)                                # entfernt
        f.set_text("TKEY", "8A")                           # neu
        f.save()
        e = backup.list_backups(os.path.join(self.dir, "bk"))[0]["files"][0]
        d = backup.diff_entry(zp, e)
        by = {r["key"]: r for r in d["rows"]}
        self.assertEqual(set(by), {"TIT2", "TBPM", "TKEY"})
        self.assertEqual((by["TIT2"]["state"], by["TIT2"]["old"], by["TIT2"]["new"]),
                         ("changed", "Nordlicht", "Nordlicht (Extended Mix)"))
        self.assertEqual((by["TBPM"]["state"], by["TBPM"]["old"], by["TBPM"]["new"]), ("removed", "122", ""))
        self.assertEqual((by["TKEY"]["state"], by["TKEY"]["new"]), ("added", "8A"))
        self.assertEqual(d["version"][0], d["version"][1])
        # Sicherung zurückspielen → keine Unterschiede mehr
        backup.restore(zp, safety_folder=os.path.join(self.dir, "bk2"))
        self.assertEqual(backup.diff_entry(zp, e)["rows"], [])
        os.remove(p)
        self.assertTrue(backup.diff_entry(zp, e)["missing"])

    def test_session_check_and_viewer(self):
        from session import Session
        p = self.make()
        s = Session()
        s.set_backup(enabled=True, folder=os.path.join(self.dir, "bk"))
        s.start_tag_load(self.B, False)
        while not s.task_status()["done"]:
            time.sleep(0.02)
        i = [os.path.basename(f.path) for f in s.tag_files].index("d.mp3")
        s.tag_set([i], "TBPM", "124")
        s.tag_set([i], "TALB", "Nachtfahrt")
        s.start_save()
        while not s.task_status()["done"]:
            time.sleep(0.02)
        bk = s.backups()["list"][0]
        s.start_backup_check(bk["path"])
        while not s.task_status()["done"]:
            time.sleep(0.02)
        files = s.task_status()["result"]["files"]
        row = next(x for x in files if x["name"] == "d.mp3")
        self.assertEqual(row["changes"], 2)
        self.assertEqual(len(row["fields"]), 2)
        self.assertEqual(row["more"], 0)
        d = s.backup_diff(bk["path"], row["id"])
        by = {r["key"]: r for r in d["rows"]}
        self.assertEqual((by["TBPM"]["old"], by["TBPM"]["new"]), ("122", "124"))
        self.assertTrue(by["TBPM"]["spans_old"] and by["TBPM"]["spans_new"])
        self.assertEqual(by["TALB"]["state"], "added")
        self.assertFalse(d["unsaved"])
        with self.assertRaises(ValueError):
            s.backup_diff(bk["path"], 999)
        with self.assertRaises(ValueError):
            s.backup_diff(p, 0)                       # nicht im Sicherungsordner


if __name__ == "__main__":
    unittest.main()
