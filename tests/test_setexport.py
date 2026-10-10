"""Tests für die DJ-Set-Exporte (setexport.py, #4)."""
import csv
import os
import shutil
import tempfile
import time
import unittest

from helpers import write_mp3, text, txxx

import core
import setexport


def entries(base):
    return [
        {"path": os.path.join(base, "Ä Ordner", "01 Grüße & Küsse.mp3"), "artist": "Mära", "title": "Grüße <live>",
         "album": "A&B", "genre": "House", "key": "8A", "bpm": 124.0, "energy": 70, "duration": 312.4,
         "to_next": {"key": "adjacent", "bpm_pct": 0.8, "score": 91}},
        {"path": os.path.join(base, "Ä Ordner", "sub dir", "02 #1 50%.mp3"), "artist": "", "title": "",
         "key": "9A", "bpm": 125.0, "energy": None, "duration": 0, "to_next": None},
    ]


class TestFormats(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ts_exp_")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_m3u8(self):
        es = entries(self.dir)
        txt = setexport.m3u8(es, name="Freitag")
        lines = txt.splitlines()
        self.assertEqual(lines[:3], ["#EXTM3U", "#PLAYLIST:Freitag", "#EXTINF:312,Mära - Grüße <live>"])
        self.assertEqual(lines[3], es[0]["path"])
        self.assertEqual(lines[4], "#EXTINF:-1,02 #1 50%")
        rel = setexport.m3u8(es, os.path.join(self.dir, "Ä Ordner"), relative=True).splitlines()
        self.assertEqual(rel[2], "01 Grüße & Küsse.mp3")
        self.assertEqual(rel[4], os.path.join("sub dir", "02 #1 50%.mp3"))

    def test_location_roundtrip(self):
        for p in (os.path.abspath(os.path.join(self.dir, "Musik", "Grüße & Küsse #1 50%.mp3")),
                  os.path.abspath(os.path.join(os.sep, "a b", "c.mp3"))):          # Windows: mit Laufwerk
            loc = setexport.location(p)
            self.assertTrue(loc.startswith("file://localhost/"))
            self.assertNotIn(" ", loc)
            self.assertEqual(setexport.path_from_location(loc), p)
        self.assertEqual(setexport.path_from_location("file://localhost/C:/Musik/a%20b.mp3"), "C:\\Musik\\a b.mp3")

    def test_rekordbox_roundtrip(self):
        es = entries(self.dir)
        xml = setexport.rekordbox_xml(es, name="Set 1", version="4.0.0")
        self.assertIn('Tonality="Am"', xml)
        self.assertIn('AverageBpm="124.00"', xml)
        self.assertIn("&lt;live&gt;", xml)
        back = setexport.read_rekordbox(xml)
        self.assertEqual(back["playlists"]["Set 1"], [e["path"] for e in es])
        self.assertEqual(back["tracks"]["1"]["Name"], "Grüße <live>")
        self.assertEqual(back["tracks"]["2"]["Name"], "02 #1 50%")
        self.assertIn('Tonality="08A"', setexport.rekordbox_xml(es, notation="camelot"))  # zweistellig wie überall

    def test_csv_and_write(self):
        es = entries(self.dir)
        for fmt in ("m3u8", "xml", "csv"):
            dest = os.path.join(self.dir, f"Set ä.{fmt}")
            self.assertEqual(setexport.write(fmt, dest, es, kinds={"adjacent": "±1 auf dem Rad"}), 2)
            self.assertGreater(os.path.getsize(dest), 50)
        with open(os.path.join(self.dir, "Set ä.csv"), encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh, delimiter=";"))
        self.assertEqual(rows[0], setexport.CSV_HEAD)
        self.assertEqual(rows[1][:11], ["1", "Mära", "Grüße <live>", "Am", "08A", "124", "70", "5:12", "±1 auf dem Rad", "0,8", "91"])
        self.assertEqual(rows[2][8:11], ["", "", ""])
        with self.assertRaises(ValueError):
            setexport.write("pdf", os.path.join(self.dir, "x"), es)


class TestSession(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ts_exps_")
        self._env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.dir
        self._cfg = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = core.CONFIG_OLD = os.path.join(self.dir, "cfg.json")
        self.lib = os.path.join(self.dir, "Mein Ordner ü")
        os.makedirs(self.lib)
        for n, (key, bpm) in enumerate((("9A", "124"), ("8A", "124"))):
            write_mp3(os.path.join(self.lib, f"{n} Titel ä.mp3"),
                      [text("TIT2", f"T{n}"), text("TPE1", "DJ"), text("TKEY", key), text("TBPM", bpm), txxx("ENERGY", "60")],
                      audio_seed=n + 1)

    def tearDown(self):
        core.CONFIG, core.CONFIG_OLD = self._cfg
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_export_and_numbering(self):
        from session import Session
        s = Session()
        with self.assertRaises(ValueError):
            s.dj_export_file("m3u8", os.path.join(self.dir, "x.m3u8"))
        s.start_tag_load(self.lib, False)
        while not s.task_status()["done"]:
            time.sleep(0.02)
        s.dj_add()
        s.dj_optimize()
        order = [r["path"] for r in s.dj_state()["items"]]
        self.assertTrue(s.dj_export_name("xml").endswith(".xml"))
        dest = os.path.join(self.dir, "out", "Set.xml")
        os.makedirs(os.path.dirname(dest))
        r = s.dj_export_file("xml", dest, {"notation": "camelot"})
        self.assertEqual(r["count"], 2)
        with open(dest, encoding="utf-8") as fh:
            back = setexport.read_rekordbox(fh.read())
        self.assertEqual(back["playlists"]["Set"], order)
        self.assertEqual(back["tracks"]["1"]["Artist"], "DJ")
        m3u = os.path.join(self.lib, "Set.m3u8")
        s.dj_export_file("m3u8", m3u, {"relative": True})
        with open(m3u, encoding="utf-8") as fh:
            self.assertEqual(fh.read().splitlines()[3], os.path.basename(order[0]))   # relativ, nach #PLAYLIST und #EXTINF
        # Spurnummern in Set-Reihenfolge (über tag_number mit den Tagger-Indizes)
        idx = s.dj_tag_indices()
        s.tag_number(idx, True, apply=True)
        self.assertEqual([s.tag_files[i].text("TRCK") for i in idx], ["1/2", "2/2"])


if __name__ == "__main__":
    unittest.main()
