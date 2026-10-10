"""Tests für tagger.py und die neuen Sitzungs-Funktionen (Tagger, Tag-Fixer, Sicherungen, Felder,
Sammelkopie, Bilder)."""
import os
import shutil
import tempfile
import time
import unittest

from helpers import write_mp3, text
from sample_library import png_solid

import core
import tagger
from id3tags import MP3File


def wait(s):
    t0 = time.time()
    while not s.task_status()["done"] and time.time() - t0 < 20:
        time.sleep(0.02)
    t = s.task_status()
    assert t["error"] is None, t["error"]
    return t["result"]


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tagstudio_tagger_")
        self._env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.dir
        self._cfg = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = os.path.join(self.dir, ".tagstudio.json")
        core.CONFIG_OLD = os.path.join(self.dir, ".mp3tagcompare.json")
        self.A = os.path.join(self.dir, "Album")
        os.makedirs(self.A)
        for i, (artist, title) in enumerate([("Mara Lind", "Nordlicht"), ("Mara Lind", "Kaltes Glas"),
                                             ("Oskar Vey", "Golden Hour")], 1):
            write_mp3(os.path.join(self.A, f"{i:02d} - {artist} - {title}.mp3"),
                      [text("TALB", "Nachtfahrt"), text("TCON", "Pop;Synth")] + ([text("TIT2", "alt")] if i == 1 else []),
                      audio_seed=i)

    def tearDown(self):
        core.CONFIG, core.CONFIG_OLD = self._cfg
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)

    def files(self):
        return [MP3File(os.path.join(self.A, n)) for n in sorted(os.listdir(self.A))]


class TestTaggerLogic(Base):
    def test_common_and_set(self):
        fs = self.files()
        c = tagger.common_values(fs)
        self.assertEqual(c["TALB"], {"value": "Nachtfahrt", "mixed": False})
        self.assertTrue(c["TIT2"]["mixed"])
        self.assertEqual(c["TPE1"], {"value": "", "mixed": False})
        self.assertEqual(tagger.set_field(fs, "TPE2", "Diverse"), 3)
        self.assertEqual(tagger.set_field(fs, "TPE2", "Diverse"), 0)
        self.assertEqual(tagger.set_field(fs, "TPE2", ""), 3)

    def test_from_filename(self):
        self.assertEqual(tagger.parse_filename("%track% - %artist% - %title%", "01 - A - B.mp3"),
                         {"TRCK": "01", "TPE1": "A", "TIT2": "B"})
        self.assertIsNone(tagger.parse_filename("%track% - %artist% - %title%", "kein Muster.mp3"))
        self.assertEqual(tagger.parse_filename("%artist% - %dummy% - %title%", "A - x - B.mp3"), {"TPE1": "A", "TIT2": "B"})
        plan = tagger.plan_from_filename(self.files(), "%track% - %artist% - %title%")
        self.assertTrue(all(p["match"] for p in plan))
        ch = dict((k, n) for k, _o, n in plan[0]["changes"])
        self.assertEqual(ch, {"TRCK": "1", "TPE1": "Mara Lind", "TIT2": "Nordlicht"})

    def test_rename(self):
        fs = self.files()
        tagger.set_field(fs, "TPE1", "Band")
        for i, f in enumerate(fs, 1):
            tagger.set_field([f], "TIT2", f"Lied/{i}")
            tagger.set_field([f], "TRCK", f"{i}/3")
        plan = tagger.plan_rename(fs, "%track% %artist% - %title%")
        self.assertEqual(plan[0]["new"], "01 Band - Lied_1.mp3")
        self.assertIsNone(plan[0]["problem"])
        res = tagger.do_rename(plan)
        self.assertTrue(all(r["ok"] for r in res))
        self.assertTrue(os.path.exists(os.path.join(self.A, "02 Band - Lied_2.mp3")))
        self.assertTrue(fs[0].path.endswith("01 Band - Lied_1.mp3"))
        # Kollision und leer
        plan = tagger.plan_rename(fs, "%artist%")
        self.assertEqual(sum(1 for p in plan if p["problem"]), 2)
        self.assertIn("leer", tagger.plan_rename(fs, "%composer%")[0]["problem"])

    def test_numbering_and_cover(self):
        fs = self.files()
        plan = tagger.plan_numbering(fs)
        self.assertEqual([n for _f, _o, n in plan], ["1/3", "2/3", "3/3"])
        img = png_solid((1, 2, 3), 8, 8)
        self.assertEqual(tagger.set_cover(fs[:2], img), 2)
        self.assertEqual(tagger.cover_summary(fs[:2])["state"], "same")
        self.assertEqual(tagger.cover_summary(fs)["state"], "mixed")
        self.assertEqual(tagger.cover_summary(fs[2:])["state"], "none")
        self.assertEqual(tagger.set_cover(fs, None), 2)


class TestSessionFeatures(Base):
    def test_tagger_session_and_registry(self):
        from session import Session
        s = Session()
        self.assertTrue(s.start_tag_load(self.A, False)["ok"])
        self.assertEqual(wait(s)["files"], 3)
        rows = s.tag_rows()["rows"]
        self.assertEqual(rows[0]["TALB"], "Nachtfahrt")
        d = s.tag_detail([0, 1, 2])
        self.assertTrue(d["common"]["TIT2"]["mixed"])
        d = s.tag_set([0, 1, 2], "TPE2", "Diverse")
        self.assertEqual(d["meta"]["unsaved"], 3)
        s.do_undo()
        self.assertEqual(s.unsaved(), 0)
        d = s.tag_from_filename([0, 1, 2], "%track% - %artist% - %title%", True)
        self.assertEqual(d["rows"][2]["TIT2"], "Golden Hour")
        # derselbe Ordner im Vergleich → gleiche Objekte (Register)
        s.start_load(self.A, "", False, "filename")
        wait(s)
        self.assertIs(s.pairs[0][0], s.tag_files[0])
        self.assertEqual(s.unsaved(), 0)  # Neu einlesen liest frisch (Änderungen verworfen)
        s.tag_set([0], "TIT2", "Neu")
        self.assertEqual(s.files()[0].text("TIT2"), "Neu")
        # Umbenennen aktualisiert Register und Pfade
        d = s.tag_rename([0], "%title%", True)
        self.assertTrue(d["renamed"])
        self.assertTrue(os.path.exists(os.path.join(self.A, "Neu.mp3")))
        self.assertIn(os.path.normcase(os.path.abspath(os.path.join(self.A, "Neu.mp3"))), s.reg)
        # Nummerieren, Version, Cover, Feld
        s.tag_number([0, 1, 2], True, True)
        self.assertEqual(s.tag_files[2].text("TRCK"), "3/3")
        s.tag_version([0], 4)
        img = os.path.join(self.dir, "c.png")
        with open(img, "wb") as fh:
            fh.write(png_solid((9, 9, 9), 6, 6))
        d = s.tag_cover([0, 1], img)
        self.assertEqual(d["cover"]["state"], "same")
        self.assertIn("ask", s.tag_add_field([0], "TALB", "", "X"))
        s.tag_add_field([0], "TXXX", "Quelle", "Test")
        self.assertEqual(s.tag_files[0].text("TXXX:Quelle"), "Test")
        # speichern
        self.assertTrue(s.start_save()["ok"])
        res = wait(s)
        self.assertEqual(res["errors"], [])
        self.assertEqual(MP3File(os.path.join(self.A, "Neu.mp3")).text("TXXX:Quelle"), "Test")

    def test_fixer_bulk_cover_backups(self):
        from session import Session
        B = os.path.join(self.dir, "B")
        shutil.copytree(self.A, B)
        for n in os.listdir(B):
            f = MP3File(os.path.join(B, n))
            f.set_text("TALB", "Anders")
            f.set_text("TXXX:Extra", "x")
            f.save()
        s = Session()
        s.start_load(self.A, B, False, "filename")
        wait(s)
        # Tag-Fixer über alle Dateien
        o = dict(s.fixer_settings()["saved"], scope="all")
        pv = s.fixer_preview(o)
        self.assertEqual(pv["count"], 6)
        self.assertEqual(pv["rows"][0]["new"], "Pop, Synth")
        s.fixer_apply(o)
        self.assertEqual(s.pairs[0][0].text("TCON"), "Pop, Synth")
        self.assertEqual(s.fixer_preview(o)["count"], 0)
        s.do_undo()
        # Sammelkopie rechts → links, nur Album
        bk = s.bulk_keys([0, 1, 2], "rl")
        self.assertIn("TXXX:Extra", [k["key"] for k in bk["keys"]])
        s.bulk_apply([0, 1, 2], "rl", ["TALB"])
        self.assertTrue(all(p[0].text("TALB") == "Anders" for p in s.pairs))
        # Feld hinzufügen, Bild
        st = s.add_field("L", "TXXX", "Neu", "Wert")
        self.assertEqual(st["added"], "TXXX:Neu")
        img = os.path.join(self.dir, "c.png")
        with open(img, "wb") as fh:
            fh.write(png_solid((9, 9, 9), 6, 6))
        s.cover_set_file("L", "APIC:3", img)
        self.assertIsNotNone(s.files()[0].get("APIC:3"))
        out = os.path.join(self.dir, "export.png")
        self.assertTrue(s.cover_export("L", "APIC:3", out)["ok"])
        with self.assertRaises(ValueError):
            s._read_image(os.path.join(self.A, os.listdir(self.A)[0]))
        # speichern → Sicherung → prüfen → wiederherstellen
        s.start_save()
        wait(s)
        bl = s.backups()
        self.assertEqual(len(bl["list"]), 1)
        path = bl["list"][0]["path"]
        self.assertTrue(s.start_backup_check(path)["ok"])
        chk = wait(s)
        self.assertTrue(all(f["code"] == "ok" for f in chk["files"]))
        self.assertTrue(s.start_restore(path, None, False)["ok"])
        res = wait(s)
        self.assertEqual(res["restored"], 3)
        self.assertEqual(s.pairs[0][0].text("TALB"), "Nachtfahrt")  # im Programm neu eingelesen
        self.assertFalse(s.delete_backup(os.path.join(self.dir, "x.zip"))["ok"])
        self.assertTrue(s.delete_backup(path)["ok"])
        self.assertEqual(s.set_backup(enabled=False)["enabled"], False)


if __name__ == "__main__":
    unittest.main()
