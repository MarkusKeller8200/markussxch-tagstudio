"""Tests für Stems als aufklappbare Spuren im Tagger (#31): stemsview.py und Sitzung."""
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
import stemsview  # noqa: E402
from helpers import text, geob, write_mp3  # noqa: E402


def touch(path, data=b"x" * 10):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


class Lib(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ts_stv_")
        self.old = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = core.CONFIG_OLD = os.path.join(self.dir, "cfg.json")
        self.lib = os.path.join(self.dir, "lib")
        os.makedirs(os.path.join(self.lib, "01 Nordlicht – Stems"))
        os.makedirs(os.path.join(self.lib, "02 Ohne – Stems"))
        write_mp3(os.path.join(self.lib, "01 Nordlicht.mp3"), [text("TIT2", "Nordlicht"), text("TPE1", "Mara"),
                                                              geob("Serato Markers2", b"\x01\x01AA")])
        write_mp3(os.path.join(self.lib, "02 Ohne.mp3"), [text("TIT2", "Ohne")], audio_seed=2)
        sd = os.path.join(self.lib, "01 Nordlicht – Stems")
        for n in ("Bass", "Vocals", "Drums", "Other"):
            write_mp3(os.path.join(sd, f"01 Nordlicht ({n}).mp3"), [text("TIT2", "alt")], audio_seed=3)
        touch(os.path.join(sd, "01 Nordlicht (Vocals).flac"))
        touch(os.path.join(sd, "fremd.mp3"))
        touch(os.path.join(sd, "01 Nordlicht (Vocals).txt"))

    def tearDown(self):
        core.CONFIG, core.CONFIG_OLD = self.old
        shutil.rmtree(self.dir, ignore_errors=True)


class TestStemsView(Lib):
    def test_find_and_is_stem(self):
        st = stemsview.find(os.path.join(self.lib, "01 Nordlicht.mp3"))
        self.assertEqual([(x["name"], x["ext"]) for x in st],
                         [("Vocals", "FLAC"), ("Vocals", "MP3"), ("Drums", "MP3"), ("Bass", "MP3"), ("Other", "MP3")])
        self.assertEqual(stemsview.find(os.path.join(self.lib, "02 Ohne.mp3")), [])
        self.assertTrue(stemsview.is_stem(st[1]["path"]))
        self.assertFalse(stemsview.is_stem(os.path.join(self.lib, "01 Nordlicht – Stems", "fremd.mp3")))
        self.assertFalse(stemsview.is_stem(os.path.join(self.lib, "01 Nordlicht.mp3")))
        lister = stemsview.make_lister()
        self.assertEqual(len(stemsview.find(os.path.join(self.lib, "01 Nordlicht.mp3"), (), lister)), 5)
        self.assertEqual(stemsview.find(os.path.join(self.lib, "02 Ohne.mp3"), (), lister), [])
        calls = []
        orig = os.listdir
        os.listdir = lambda d: (calls.append(d), orig(d))[1]
        try:
            lister2 = stemsview.make_lister()
            for n in ("02 Ohne.mp3", "x.mp3", "y.mp3"):
                stemsview.find(os.path.join(self.lib, n), (), lister2)
        finally:
            os.listdir = orig
        self.assertEqual(len(calls), 2)          # Bibliotheksordner einmal + „02 Ohne – Stems“
        fixed = os.path.join(self.dir, "Fest")
        touch(os.path.join(fixed, "02 Ohne – Stems", "02 Ohne (Vocals).wav"))
        self.assertEqual([x["ext"] for x in stemsview.find(os.path.join(self.lib, "02 Ohne.mp3"), [fixed])], ["WAV"])


class TestSessionStems(Lib):
    def load(self, s, recursive):
        s.start_tag_load(self.lib, recursive)
        while not s.task_status()["done"]:
            time.sleep(0.02)
        return s.tag_rows()["rows"]

    def test_attach_rows_and_tags(self):
        from session import Session
        for recursive in (False, True):
            s = Session()
            rows = self.load(s, recursive)
            top = [r for r in rows if "parent" not in r]
            # fremde Dateien im Stems-Ordner bleiben normale Einträge (nur mit Unterordnern geladen)
            self.assertEqual([r["name"] for r in top], ["01 Nordlicht.mp3", "02 Ohne.mp3"] + (["fremd.mp3"] if recursive else []))
            orig = top[0]
            self.assertEqual([x["name"] for x in orig["stems"]], ["Vocals", "Vocals", "Drums", "Bass", "Other"])
            kids = [r for r in rows if r.get("parent") == orig["i"]]
            self.assertEqual(sorted(r["stem"] for r in kids), ["Bass", "Drums", "Other", "Vocals"])
            self.assertIsNone(orig["stems"][0]["i"])       # FLAC: keine Zeile, nur Spur
        # Tags übernehmen (ohne Serato-Daten), mit Rückgängig
        pv = s.tag_stem_tags([orig["i"]])
        self.assertEqual(pv, {"originals": 1, "stems": 4})
        d = s.tag_stem_tags([kids[0]["i"]], True)          # auch über eine Spur
        self.assertIn("4 Spur(en)", d["message"])
        f = s.tag_files[kids[0]["i"]]
        self.assertEqual((f.text("TPE1"), f.text("TIT2")), ("Mara", f"Nordlicht ({kids[0]['stem']})"))
        self.assertIsNone(f.get("GEOB:Serato Markers2"))
        s.do_undo()
        self.assertEqual(s.tag_files[kids[0]["i"]].text("TIT2"), "alt")
        # Wiedergabe einer FLAC-Spur über ihren Pfad
        info = s.media_info("stem", orig["stems"][0]["path"])
        self.assertEqual(info["stem"], "Vocals")
        # #66: Original und alle Spuren als Umschalt-Ziele – gleich, ob vom Original oder einer Spur aus
        grp = info["stems"]
        self.assertEqual([g["label"] for g in grp], ["Original", "Vocals", "Vocals", "Drums", "Bass", "Other"])
        self.assertEqual((grp[0]["kind"], grp[0]["ref"], grp[1]["kind"]), ("tag", orig["i"], "stem"))
        self.assertEqual(s.media_info("tag", orig["i"])["stems"], grp)
        kid = s.media_info("tag", kids[0]["i"])
        self.assertEqual((kid["stems"], kid["stem"]), (grp, kids[0]["stem"]))
        self.assertEqual(s.media_info("tag", top[1]["i"])["stems"], [])
        with self.assertRaises(ValueError):
            s.media_info("stem", "/etc/passwd")
        self.assertEqual(s.media_extra("stem", orig["stems"][0]["path"])["cues"], [])

    def test_flat_and_attach_later(self):
        from session import Session
        s = Session()
        s.set_stems_flat(True)
        rows = self.load(s, False)
        self.assertEqual(len(rows), 2)
        self.assertFalse(any("stems" in r for r in rows))
        s.set_stems_flat(False)
        rows = s.tag_rows()["rows"]
        self.assertEqual(len(rows), 6)
        # neue Stems für Titel 2 (wie nach „Stems erzeugen“)
        write_mp3(os.path.join(self.lib, "02 Ohne – Stems", "02 Ohne (Vocals).mp3"), [text("TIT2", "v")])
        r = s.tag_attach_stems()
        self.assertEqual(len(r["new"]), 1)
        self.assertEqual(r["rows"][r["new"][0]]["name"], "02 Ohne.mp3")
        self.assertEqual(len(r["rows"]), 7)


if __name__ == "__main__":
    unittest.main()
