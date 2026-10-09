"""Tests für den Listen-Cache (#70): sofort laden, Hash-Prüfung im Hintergrund."""
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
import listcache  # noqa: E402
from helpers import apic, geob, png, text, write_mp3  # noqa: E402
from id3tags import MP3File  # noqa: E402


class TestListCache(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ts_lc_")
        self._old = (listcache.DIR, core.CONFIG, core.CONFIG_OLD)
        listcache.DIR = os.path.join(self.dir, "cache")
        core.CONFIG = core.CONFIG_OLD = os.path.join(self.dir, "cfg.json")
        self.lib = os.path.join(self.dir, "lib")
        os.makedirs(self.lib)
        cover = png(300, 300, b"y" * 9000)
        for i in range(1, 4):
            write_mp3(self.p(i), [text("TIT2", f"Titel {i}"), text("TKEY", "8A"), apic(cover),
                                  geob("Serato Overview", b"\x01" * 6000)], audio_seed=i, audio_frames=30)

    def tearDown(self):
        listcache.DIR, core.CONFIG, core.CONFIG_OLD = self._old
        shutil.rmtree(self.dir, ignore_errors=True)

    def p(self, i):
        return os.path.join(self.lib, f"0{i}.mp3")

    def load(self):
        stats = {}
        files, errors = core.load_files(self.lib, False, use_cache=True, stats=stats)
        self.assertEqual(errors, [])
        return files, stats

    def test_cache_roundtrip(self):
        files, st = self.load()
        self.assertEqual(len(st["cached"]), 0)                     # erstes Mal: von der Platte
        self.assertTrue(os.path.isfile(st["caches"][0].path))
        objs = [f for _r, _d, fs in os.walk(os.path.join(listcache.DIR, "objects")) for f in fs]
        self.assertEqual(len(objs), 2)                             # Cover (für alle gleich) + Serato-Daten
        files2, st2 = self.load()
        self.assertEqual(len(st2["cached"]), 3)                    # zweites Mal: ohne die Dateien zu öffnen
        for a, b in zip(files, files2):
            self.assertEqual((a.items, a.disk_sig, a.duration, a.bitrate, a.version, a.audio_start),
                             (b.items, b.disk_sig, b.duration, b.bitrate, b.version, b.audio_start))
            self.assertFalse(b.is_modified())
            self.assertFalse(b.external_change())
        # Änderung mit neuer Änderungszeit → von der Platte
        f = MP3File(self.p(1))
        f.set_text("TKEY", "9A")
        f.save()
        st_ = os.stat(self.p(1))
        os.utime(self.p(1), ns=(st_.st_atime_ns, st_.st_mtime_ns + 3_000_000_000))
        files3, st3 = self.load()
        self.assertEqual((len(st3["cached"]), files3[0].text("TKEY")), (2, "9A"))
        # entfernte Datei fällt aus dem Cache
        os.remove(self.p(3))
        self.load()
        self.assertEqual(sorted(listcache.ListCache(self.lib).entries), ["01.mp3", "02.mp3"])

    def test_session_verify_detects_hidden_change(self):
        """Programm ändert Tags und stellt die Änderungszeit zurück → Hash-Prüfung findet es."""
        from session import Session
        s = Session()
        s.start_tag_load(self.lib, False)
        self.wait(s)
        s.start_tag_load(self.lib, False)
        res = self.wait(s)
        self.assertEqual(res["cached"], 3)
        self.wait_verify(s)
        self.assertEqual(s.verify_status()["n_changed"], 0)
        st = os.stat(self.p(2))
        f = MP3File(self.p(2))
        f.set_text("TIT2", "Heimlich")
        f.save()
        os.utime(self.p(2), ns=(st.st_atime_ns, st.st_mtime_ns))  # Änderungszeit erhalten
        s.start_tag_load(self.lib, False)
        res = self.wait(s)
        self.assertEqual(res["cached"], 3)
        self.wait_verify(s)
        v = s.verify_status()
        self.assertEqual((v["n_changed"], v["changed"]), (1, ["02.mp3"]))
        self.assertEqual(next(g for g in s.tag_files if g.path == self.p(2)).text("TIT2"), "Heimlich")
        s.set_list_cache(False)
        s.start_tag_load(self.lib, False)
        self.assertEqual(self.wait(s)["cached"], 0)

    def test_single_file_always_fresh(self):
        """#81: eine einzelne Datei (z. B. aus dem Journal) kommt nie aus dem Cache."""
        from session import Session
        s = Session()
        s.start_tag_load(self.lib, False)
        self.wait(s)
        st = os.stat(self.p(1))
        f = MP3File(self.p(1))
        f.set_text("TKEY", "11B")
        f.save()
        os.utime(self.p(1), ns=(st.st_atime_ns, st.st_mtime_ns))  # Änderungszeit erhalten (wie manche Programme)
        s.start_load(self.p(1), self.p(2), False, "filename")
        self.assertEqual(self.wait(s)["cached"], 0)
        self.assertEqual(s.pairs[0][0].text("TKEY"), "11B")

    def test_reload_pair(self):
        """#82: nur das aktuelle Paar neu einlesen – mit Rückfrage bei ungespeicherten Änderungen."""
        from session import Session
        lib2 = os.path.join(self.dir, "lib2")
        shutil.copytree(self.lib, lib2)
        s = Session()
        s.start_load(self.lib, lib2, False, "filename")
        self.wait(s)
        s.select(0)
        other = s.pairs[1][0]
        other.set_text("TIT2", "bleibt ungespeichert")
        f = MP3File(os.path.join(lib2, "01.mp3"))
        f.set_text("TKEY", "4A")
        f.save()
        s.copy_keys(["TIT2"], "rl")                              # ungespeichert links (gleich, also nichts)
        s.set_value("L", "TIT2", "Geändert")
        self.assertIn("ask", s.reload_pair())
        st = s.reload_pair(force=True)
        self.assertIn("1 Datei(en) hatten sich geändert", st["message"])
        l, r = s.files()
        self.assertEqual((l.text("TIT2"), r.text("TKEY")), ("Titel 1", "4A"))
        self.assertEqual(other.text("TIT2"), "bleibt ungespeichert")   # übrige Liste unberührt
        self.assertEqual(st["pair"]["i"], 0)
        e = listcache.ListCache(lib2).entries["01.mp3"]
        self.assertEqual(e["sig"], r.disk_sig)                    # Cache erneuert

    def test_cache_build(self):
        """#80: Listen-Cache für die geladenen Titel neu erstellen; fehlende Wellenformen auflisten."""
        from session import Session
        s = Session()
        self.assertFalse(s.start_cache_build("lists")["ok"])      # nichts geladen
        s.start_tag_load(self.lib, False)
        self.wait(s)
        shutil.rmtree(listcache.DIR)
        s.start_cache_build("lists")
        self.assertIn("3 Titel", self.wait(s)["message"])
        self.assertEqual(len(listcache.ListCache(self.lib).entries), 3)
        self.assertEqual(len(s.wave_missing()), 3)

    def wait(self, s):
        while not s.task_status()["done"]:
            time.sleep(0.01)
        st = s.task_status()
        self.assertIsNone(st["error"], st)
        return st["result"]

    def wait_verify(self, s):
        t0 = time.time()
        while s.verify_status()["running"]:
            self.assertLess(time.time() - t0, 10)
            time.sleep(0.01)


if __name__ == "__main__":
    unittest.main()
