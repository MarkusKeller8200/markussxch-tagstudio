"""#59: Sicherungen im Snapshot-Speicher – Platz sparen, gleicher Speicher, ZIPs bleiben lesbar."""
import json
import os
import time

from helpers import write_mp3, text
from test_tagger_tools import Base

import backup
import snapshots
from id3tags import MP3File


class TestBackupStore(Base):
    def setUp(self):
        super().setUp()
        self.p = os.path.join(self.B, "s.mp3")
        write_mp3(self.p, [text("TIT2", "Nordlicht"), text("TPE1", "Mara Lind")], audio_seed=31)
        self.store = snapshots.Store(os.path.join(self.dir, "Snapshots"))

    def test_writer_list_diff_restore(self):
        w = backup.make_writer(os.path.join(self.dir, "bk"), "Test", self.store)
        self.assertIsInstance(w, backup.StoreBackupWriter)
        w.add(self.p)
        self.assertTrue(snapshots.PINNED)                       # laufende Sicherung: Objekte geschützt
        self.assertEqual(self.store.gc(), 0)
        path = w.close()
        self.assertFalse(snapshots.PINNED)
        self.assertTrue(backup.is_store_backup(path))
        with open(path, encoding="utf-8") as fh:
            man = json.load(fh)
        self.assertEqual((man["format"], man["kind"], len(man["files"])), (2, "store", 1))
        # zweite Sicherung derselben Datei: keine neuen Objekte (gleiche Tags nur einmal)
        n_obj = sum(len(f) for _d, _s, f in os.walk(os.path.join(self.store.root, "objects")))
        w2 = backup.make_writer(None, "Nochmal", self.store)
        w2.add(self.p)
        w2.close()
        self.assertEqual(sum(len(f) for _d, _s, f in os.walk(os.path.join(self.store.root, "objects"))), n_obj)
        # Aufräumen lässt die Objekte der Sicherungen stehen
        self.assertEqual(self.store.gc(), 0)
        lst = backup.list_backups(os.path.join(self.dir, "bk"), self.store)
        self.assertEqual([b["where"] for b in lst], ["store", "store"])
        e = next(b for b in lst if b["path"] == path)["files"][0]
        f = MP3File(self.p)
        f.set_text("TIT2", "Anders")
        f.save()
        rows = backup.diff_entry(path, e)["rows"]
        self.assertEqual([(r["key"], r["old"], r["new"]) for r in rows], [("TIT2", "Nordlicht", "Anders")])
        res = backup.restore(path, store=self.store)
        self.assertEqual(res[0][1], "restored")
        self.assertEqual(MP3File(self.p).text("TIT2"), "Nordlicht")
        self.assertEqual(len(backup.list_backups(None, self.store)), 3)   # Sicherheitsnetz auch im Speicher

    def test_zip_still_works(self):
        w = backup.make_writer(os.path.join(self.dir, "bk"), "ZIP", None)
        self.assertIsInstance(w, backup.BackupWriter)
        w.add(self.p)
        zp = w.close()
        lst = backup.list_backups(os.path.join(self.dir, "bk"), self.store)
        self.assertEqual([b["where"] for b in lst], ["zip"])
        self.assertEqual(backup.diff_entry(zp, lst[0]["files"][0])["rows"], [])

    def test_session_save_delete(self):
        from session import Session
        s = Session()
        s.set_backup(enabled=True, folder=os.path.join(self.dir, "bk"))
        self.assertTrue(s.settings_page()["backup_store"])
        s.start_tag_load(self.B, False)
        while not s.task_status()["done"]:
            time.sleep(0.02)
        i = [os.path.basename(f.path) for f in s.tag_files].index("s.mp3")
        s.tag_set([i], "TBPM", "124")
        s.start_save()
        while not s.task_status()["done"]:
            time.sleep(0.02)
        b = s.backups()
        self.assertTrue(b["in_store"])
        self.assertEqual(b["list"][0]["where"], "store")
        st = s.snap_store
        self.assertTrue(b["list"][0]["path"].startswith(os.path.join(st.root, "backups")))
        self.assertTrue(s.delete_backup(b["list"][0]["path"])["ok"])
        self.assertEqual(sum(len(f) for _d, _s, f in os.walk(os.path.join(st.root, "objects"))), 0)   # freigegeben
        # Umschalten auf ZIP
        s.set_backup(in_store=False)
        s.tag_set([i], "TBPM", "125")
        s.start_save()
        while not s.task_status()["done"]:
            time.sleep(0.02)
        self.assertEqual([x["where"] for x in s.backups()["list"]], ["zip"])
        with self.assertRaises(ValueError):
            s._backup_entry(os.path.join(st.root, "libs", "x.json"))


if __name__ == "__main__":
    import unittest
    unittest.main()
