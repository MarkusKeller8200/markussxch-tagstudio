"""Tests für compare.py (Zuordnung, Vergleich, Kopieren, Tag-Fixer) und backup.py (Sichern/Wiederherstellen)."""
import hashlib
import os
import shutil
import tempfile
import threading
import unittest

from helpers import write_mp3, text, txxx, geob, id3v1
from id3tags import MP3File, MV
import compare
from compare import scan, pair_files, diff, copy_tags, Rules, fix_multi, plan_multi_fix, INPUT_SEPARATORS, MULTI_FIELDS
import backup


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tagstudio_test_")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def make(self, sub, name, frames, **kw):
        d = os.path.join(self.dir, sub)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, name)
        write_mp3(p, frames, **kw)
        return p


class TestCompare(Base):
    def setUp(self):
        super().setUp()
        for i in (1, 2, 3):
            self.make("L", f"{i:02d} Song.mp3", [text("TIT2", f"Song {i}"), text("TRCK", str(i)),
                                                 text("TCON", "Techno"), text("TLEN", "1000")])
        for i in (1, 2, 4):
            self.make("R", f"{i:02d} Song.mp3", [text("TIT2", f"Song {i}"), text("TRCK", f"{i}/12"),
                                                 text("TCON", "House" if i == 2 else "Techno"), text("TLEN", "2000")])
        self.L = [MP3File(p) for p in scan(os.path.join(self.dir, "L"))]
        self.R = [MP3File(p) for p in scan(os.path.join(self.dir, "R"))]

    def test_scan_cancel(self):
        ev = threading.Event()
        ev.set()
        with self.assertRaises(compare.Cancelled):
            scan(os.path.join(self.dir, "L"), recursive=True, cancel=ev)

    def test_pair_by_filename(self):
        pairs = pair_files(self.L, self.R, "filename", os.path.join(self.dir, "L"), os.path.join(self.dir, "R"))
        names = [(os.path.basename(l.path) if l else None, os.path.basename(r.path) if r else None) for l, r in pairs]
        self.assertIn(("01 Song.mp3", "01 Song.mp3"), names)
        self.assertIn(("03 Song.mp3", None), names)
        self.assertIn((None, "04 Song.mp3"), names)

    def test_pair_by_track(self):
        pairs = pair_files(self.L, self.R, "track")
        self.assertEqual(sum(1 for l, r in pairs if l and r), 2)  # "1" passt zu "1/12"

    def test_diff_important_vs_trivial(self):
        l, r = self.L[1], self.R[1]  # Song 2
        imp, triv = diff(l, r, Rules())
        self.assertIn("TCON", imp)
        self.assertIn("TLEN", triv)  # Länge gilt als unwichtig
        self.assertIn("TRCK", imp)

    def test_copy_tags_and_delete_missing(self):
        l, r = self.L[0], self.R[0]
        r.set_text("TXXX:NurRechts", "x")
        n = copy_tags(l, r, ["TRCK", "TXXX:NurRechts"], delete_missing=False)
        self.assertEqual((n, r.text("TRCK"), r.text("TXXX:NurRechts")), (1, "1", "x"))
        copy_tags(l, r, ["TXXX:NurRechts"], delete_missing=True)
        self.assertIsNone(r.get("TXXX:NurRechts"))

    def test_trivial_patterns(self):
        rules = Rules()
        for k in ("GEOB:Serato Markers2", "TXXX:beaTunes_COLOR", "TXXX:SegmentsAlgorithm", "COMM:iTunNORM", "TLEN"):
            self.assertTrue(rules.is_trivial(k), k)
        for k in ("TIT2", "TPE1", "TKEY", "COMM:"):
            self.assertFalse(rules.is_trivial(k), k)


class TestFixer(Base):
    SEPS = [s for _, s, on in INPUT_SEPARATORS if on]

    def test_fix_multi_separators(self):
        self.assertEqual(fix_multi("Adriatique; Vincent Vossen / Yubik", self.SEPS, ", "),
                         "Adriatique, Vincent Vossen, Yubik")
        self.assertEqual(fix_multi("A\\\\B", self.SEPS, MV), "A" + MV + "B")
        self.assertEqual(fix_multi("AC/DC", self.SEPS, ", "), "AC/DC")  # "/" ohne Leerzeichen bleibt
        self.assertEqual(fix_multi("A; a; B", self.SEPS, ", ", dedupe=True), "A, B")

    def test_plan_v23_without_upgrade_gets_semicolon(self):
        p = self.make("F", "a.mp3", [text("TPE1", "A / B", 3)], ver=3)
        f = MP3File(p)
        plan = plan_multi_fix([f], MULTI_FIELDS, self.SEPS, MV, upgrade=False)
        self.assertEqual(plan[0][3], "A; B")
        plan = plan_multi_fix([f], MULTI_FIELDS, self.SEPS, MV, upgrade=True)
        self.assertEqual(plan[0][3], "A" + MV + "B")


def md5(p):
    with open(p, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


class TestBackup(Base):
    def test_backup_restore_byte_identical(self):
        files = [
            self.make("B", "inplace.mp3", [text("TIT2", "A"), text("TKEY", "8A"), geob("Serato Markers2", b"\x01")]),
            self.make("B", "grow.mp3", [text("TIT2", "B")], padding=0, v1=id3v1("B")),
            self.make("B", "v23.mp3", [text("TIT2", "C", 3), text("TYER", "2020", 3)], ver=3),
            self.make("B", "notag.mp3", None),
        ]
        orig = {p: md5(p) for p in files}
        bdir = os.path.join(self.dir, "Sicherungen")
        bw = backup.BackupWriter(bdir, "Test")
        for p in files:
            bw.add(p)
        z = bw.close()
        # ändern: in place, wachsend, Versionswechsel, Tag neu
        m = MP3File(files[0]); m.set_text("TKEY", "9A"); m.save()
        m = MP3File(files[1]); m.set_text("TIT2", "x" * 20000); m.save()
        m = MP3File(files[2]); m.set_version(4); m.set_text("TPE1", "A" + MV + "B"); m.save()
        m = MP3File(files[3]); m.set_text("TIT2", "neu"); m.save()
        self.assertTrue(all(md5(p) != orig[p] for p in files))
        res = backup.restore(z, None, bdir)
        self.assertEqual([r[1] for r in res], ["restored"] * 4)
        self.assertTrue(all(md5(p) == orig[p] for p in files))
        # Sicherheits-Sicherung vor dem Wiederherstellen wurde angelegt
        labels = [b["label"] for b in backup.list_backups(bdir)]
        self.assertTrue(any(l.startswith("Vor Wiederherstellung") for l in labels))
        # zweites Wiederherstellen: alles bereits gleich
        self.assertEqual({r[1] for r in backup.restore(z, None, bdir)}, {"skipped"})

    def test_check_entry_detects_changed_audio_and_missing(self):
        p = self.make("C", "a.mp3", [text("TIT2", "A")])
        bw = backup.BackupWriter(os.path.join(self.dir, "S"), "T")
        bw.add(p)
        z = bw.close()
        entry = backup.list_backups(os.path.join(self.dir, "S"))[0]["files"][0]
        self.assertEqual(backup.check_entry(entry)[0], "same")
        write_mp3(p, [text("TIT2", "A")], audio_seed=99)  # andere Audiodaten, gleicher Name
        self.assertEqual(backup.check_entry(entry)[0], "audio")
        os.remove(p)
        self.assertEqual(backup.check_entry(entry)[0], "missing")
        self.assertTrue(os.path.exists(z))


if __name__ == "__main__":
    unittest.main()
