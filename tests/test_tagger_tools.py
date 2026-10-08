"""Tests für Schreibweise, Suchen & Ersetzen, Cover aus dem Ordner und Export (tagger.py + Sitzung)."""
import csv
import os
import shutil
import tempfile
import time
import unittest
import zipfile
from xml.dom import minidom

from helpers import write_mp3, text, txxx
from sample_library import png_solid

import core
import tagger
from id3tags import MP3File, MV


class TestCase(unittest.TestCase):
    def test_change_case(self):
        c = tagger.change_case
        self.assertEqual(c("golden HOUR of the night", "title"), "Golden HOUR Of The Night")
        self.assertEqual(c("golden HOUR of the night", "title", keep_upper=False, small_words=True),
                         "Golden Hour of the Night")
        self.assertEqual(c("the end", "title", small_words=True), "The End")
        self.assertEqual(c("don't stop", "title"), "Don't Stop")
        self.assertEqual(c("DJ SHADOW live", "sentence"), "DJ SHADOW live")
        self.assertEqual(c("hello WORLD", "sentence", keep_upper=False), "Hello world")
        self.assertEqual(c("Ärger über Öl", "upper"), "ÄRGER ÜBER ÖL")
        self.assertEqual(c(f"mara lind{MV}oskar vey", "title"), f"Mara Lind{MV}Oskar Vey")
        self.assertEqual(c("AC/DC – back in black", "title"), "AC/DC – Back In Black")
        with self.assertRaises(ValueError):
            c("x", "kaputt")


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tagstudio_tools_")
        self._env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.dir
        self._cfg = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = core.CONFIG_OLD = os.path.join(self.dir, "cfg.json")
        self.A = os.path.join(self.dir, "A")
        self.B = os.path.join(self.dir, "B")
        os.makedirs(self.A)
        os.makedirs(self.B)
        write_mp3(os.path.join(self.A, "1.mp3"), [text("TIT2", "golden hour"), text("TPE1", "Mara Lind"),
                                                  txxx("Info", "Mara Lind live")])
        write_mp3(os.path.join(self.A, "2.mp3"), [text("TIT2", "NORDLICHT"), text("TPE1", "mara lind")], audio_seed=2)
        write_mp3(os.path.join(self.B, "3.mp3"), [text("TIT2", "x")], audio_seed=3)
        with open(os.path.join(self.A, "Folder.JPG"), "wb") as fh:
            fh.write(b"\xff\xd8\xff\xe0" + b"0" * 50)
        with open(os.path.join(self.A, "other.png"), "wb") as fh:
            fh.write(png_solid((1, 1, 1), 4, 4))

    def tearDown(self):
        core.CONFIG, core.CONFIG_OLD = self._cfg
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)

    def files(self):
        return [MP3File(os.path.join(self.A, "1.mp3")), MP3File(os.path.join(self.A, "2.mp3")),
                MP3File(os.path.join(self.B, "3.mp3"))]


class TestTools(Base):
    def test_plan_case_and_replace(self):
        fs = self.files()
        plan = tagger.plan_case(fs, ["TIT2", "TPE1"], "title", keep_upper=False)
        self.assertEqual(sorted((k, n) for _f, k, _o, n in plan),
                         [("TIT2", "Golden Hour"), ("TIT2", "Nordlicht"), ("TIT2", "X"), ("TPE1", "Mara Lind")])
        plan = tagger.plan_replace(fs, None, "mara lind", "Mara Lind feat. X")
        self.assertEqual(len(plan), 3)  # TPE1 ×2 + TXXX (ohne Groß/klein)
        self.assertEqual(len(tagger.plan_replace(fs, None, "mara lind", "Y", case=True)), 1)
        self.assertEqual(len(tagger.plan_replace(fs, ["TPE1"], "Lind", "L", case=True, word=True)), 1)
        plan = tagger.plan_replace(fs, ["TIT2"], r"(\w+) (\w+)", r"\2 \1", regex=True)
        self.assertEqual(plan[0][3], "hour golden")
        self.assertEqual(tagger.plan_replace(fs, ["TPE1"], "Lind", r"a\1b")[0][3], r"Mara a\1b")  # kein Regex
        with self.assertRaises(ValueError):
            tagger.plan_replace(fs, None, "(", "x", regex=True)
        self.assertEqual(tagger.plan_replace(fs, None, "", "x"), [])

    def test_folder_cover(self):
        self.assertTrue(tagger.find_folder_image(self.A).endswith("Folder.JPG"))
        self.assertIsNone(tagger.find_folder_image(self.B))
        fs = self.files()
        plan = tagger.plan_folder_cover(fs)
        self.assertEqual([p["action"] for p in plan], ["set", "set", "skip"])
        os.remove(os.path.join(self.A, "Folder.JPG"))
        self.assertTrue(tagger.find_folder_image(self.A).endswith("other.png"))  # sonst größtes Bild

    def test_export(self):
        fs = self.files()
        head, rows = tagger.export_table(fs)
        self.assertEqual(head[0], "Datei")
        self.assertEqual(rows[0][0], "1.mp3")
        p = os.path.join(self.dir, "x.csv")
        tagger.write_csv(p, head, rows)
        with open(p, encoding="utf-8-sig") as fh:
            data = list(csv.reader(fh, delimiter=";"))
        self.assertEqual(data[1][head.index("Titel")], "golden hour")
        x = os.path.join(self.dir, "x.xlsx")
        tagger.write_xlsx(x, head, rows + [["<&>\x01", "ü", 5]])
        with zipfile.ZipFile(x) as z:
            self.assertIsNone(z.testzip())
            for n in z.namelist():
                if n.endswith(".xml") or n.endswith(".rels"):
                    minidom.parseString(z.read(n))  # alles wohlgeformt
            self.assertIn("golden hour", z.read("xl/worksheets/sheet1.xml").decode())


class TestSession(Base):
    def test_session_tools(self):
        from session import Session
        s = Session()
        s.start_tag_load(self.dir, True)
        while not s.task_status()["done"]:
            time.sleep(0.02)
        idx = list(range(len(s.tag_files)))
        pv = s.tag_case(idx, ["TIT2"], "title", False, False, False)
        self.assertEqual(pv["count"], 3)
        d = s.tag_case(idx, ["TIT2"], "title", False, False, True)
        self.assertEqual(d["meta"]["unsaved"], 3)
        self.assertIn("Golden Hour", [r["TIT2"] for r in s.tag_rows()["rows"]])
        s.do_undo()
        self.assertEqual(s.unsaved(), 0)
        self.assertIn("error", s.tag_replace(idx, None, "(", "x", False, True, False, False))
        d = s.tag_replace(idx, ["TPE1"], "mara lind", "Mara Lind", False, False, False, True)
        self.assertEqual(d["meta"]["unsaved"], 1)
        pv = s.tag_folder_cover(idx, True, False)
        self.assertEqual(pv["count"], 2)
        d = s.tag_folder_cover(idx, True, True)
        self.assertEqual(d["errors"], [])
        self.assertEqual(sum(1 for f in s.tag_files if f.get("APIC:3") is not None), 2)
        out = os.path.join(self.dir, "liste.xlsx")
        self.assertEqual(s.tag_export_file([], "xlsx", out)["count"], 3)
        self.assertTrue(zipfile.is_zipfile(out))
        self.assertTrue(s.tag_export_name("csv").endswith(".csv"))


if __name__ == "__main__":
    unittest.main()
