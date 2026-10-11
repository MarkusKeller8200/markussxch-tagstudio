"""Aussortieren ins Archiv (#173): Tagger und Vorbereiten, Unterordner bleiben, Vermerk, Zurückholen."""
import os
import time

from helpers import write_mp3, text
from test_tagger_tools import Base

import archive


class TestArchive(Base):
    def setUp(self):
        super().setUp()
        self.lib = os.path.join(self.dir, "Lib")
        self.arch = os.path.join(self.dir, "02_Archiv")
        os.makedirs(os.path.join(self.lib, "House"))
        write_mp3(os.path.join(self.lib, "House", "a.mp3"), [text("TIT2", "A")], audio_seed=1)
        write_mp3(os.path.join(self.lib, "b.mp3"), [text("TIT2", "B")], audio_seed=2)
        os.makedirs(os.path.join(self.lib, "House", "a – Stems"))
        from session import Session
        self.s = Session()
        self.s.cfg["archive_dir"] = self.arch

    def wait(self):
        for _ in range(500):
            st = self.s.task_status()
            if st.get("done"):
                return st
            time.sleep(0.02)
        self.fail("hängt")

    def test_tagger_archive_and_restore(self):
        self.s.start_tag_load(self.lib, True)
        self.wait()
        names = [os.path.basename(f.path) for f in self.s.tag_files]
        i = names.index("a.mp3")
        p = self.s.tag_archive([i])
        self.assertEqual(p["ok"], 1)
        self.assertEqual(p["rows"][0]["dst"], os.path.join(self.arch, "House", "a.mp3"))   # Unterordner bleibt
        self.assertTrue(p["rows"][0]["stems"])
        j = names.index("b.mp3")
        self.s.tag_set([j], "TIT2", "geändert")
        self.assertIn("ungespeichert", self.s.tag_archive([j])["rows"][0]["problem"])
        r = self.s.tag_archive([i], True)
        self.assertEqual(r["moved"], 1)
        self.assertTrue(os.path.isfile(os.path.join(self.arch, "House", "a.mp3")))
        self.assertTrue(os.path.isdir(os.path.join(self.arch, "House", "a – Stems")))
        self.assertFalse(os.path.exists(os.path.join(self.lib, "House", "a.mp3")))
        ent = self.s.archive_list()["entries"]
        self.assertEqual(len(ent), 2)                                    # Titel + Stems-Ordner
        tid = next(e["id"] for e in ent if e["area"] == "Tagger")
        r = self.s.archive_restore([tid])
        self.assertEqual(r["restored"], 1)
        self.assertTrue(os.path.isfile(os.path.join(self.lib, "House", "a.mp3")))
        self.assertTrue(next(e for e in r["entries"] if e["id"] == tid)["restored"])
        self.assertEqual(self.s.archive_restore([tid])["restored"], 0)  # nicht doppelt

    def test_prep_archive(self):
        import prepare
        inbox = os.path.join(self.dir, "In")
        os.makedirs(inbox)
        write_mp3(os.path.join(inbox, "n.mp3"), [text("TIT2", "N")], audio_seed=3)
        w = prepare.template()
        w.update(inbox=inbox, library=self.lib)
        wid = self.s.prep_workflow_save(w)["workflow"]["id"]
        self.s.start_prep_run(wid, "s02")
        self.wait()
        stage = os.path.join(self.dir, "_02_MP3Tag", "n.mp3")
        self.assertTrue(os.path.isfile(stage))
        p = self.s.prep_archive(wid, ["n.mp3"])
        self.assertEqual(p["copies"], [stage])
        d = self.s.prep_archive(wid, ["n.mp3"], True, True)
        self.assertIn("1 Titel aussortiert", d["message"])
        self.assertTrue(os.path.isfile(os.path.join(self.arch, "n.mp3")))
        self.assertFalse(os.path.exists(stage))
        self.assertEqual([r["name"] for r in d["rows"]], [])

    def test_no_archive_dir(self):
        self.s.cfg["archive_dir"] = ""
        with self.assertRaises(ValueError):
            self.s.tag_archive([])
        self.assertEqual(archive.entries(""), [])
