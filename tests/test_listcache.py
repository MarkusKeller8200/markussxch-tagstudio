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
        listcache.PACK._load()
        self.assertEqual(len(listcache.PACK.index), 2)             # Cover (für alle gleich) + Serato-Daten, #137: in einer Packdatei
        self.assertFalse(os.path.isdir(os.path.join(listcache.DIR, "objects")))
        self.assertTrue(os.path.isfile(os.path.join(listcache.DIR, "objects.idx.json")))
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

    def test_scan_stats_no_second_stat(self):
        """#326: Grösse/Änderungszeit kommen aus dem Durchsuchen des Ordners – aus dem Cache wird keine Datei mehr
        einzeln abgefragt (unter Windows ohne Zugriff je Datei; Netz- und USB-Laufwerke)."""
        from unittest import mock
        self.load()                                                # Cache anlegen
        real = os.stat
        calls = []

        def counting(path, *a, **k):
            if str(path).endswith(".mp3"):
                calls.append(path)
            return real(path, *a, **k)
        with mock.patch.object(listcache.os, "stat", counting), mock.patch.object(core.os, "stat", counting):
            files, st = self.load()
        self.assertEqual(len(st["cached"]), 3)
        self.assertEqual(calls, [])

    def test_scan_order_and_stats_like_walk(self):
        """#326: scan(recursive) liefert dieselbe Reihenfolge wie bisher (os.walk) – versteckte Ordner aussen vor,
        Verknüpfungen auf Ordner nicht verfolgt – und je Datei das stat-Ergebnis."""
        from compare import scan
        root = os.path.join(self.dir, "baum")
        for d in ("b", "A/z", "A/a", ".versteckt", "c"):
            os.makedirs(os.path.join(root, d))
        for f in ("x.mp3", "B.MP3", "a.mp3", "A/2.mp3", "A/1.mp3", "A/z/9.mp3", "A/a/k.mp3", ".versteckt/v.mp3",
                  "c/t.txt", "b/.h.mp3", "b/m.mp3"):
            with open(os.path.join(root, f), "wb") as fh:
                fh.write(b"x" * len(f))
        try:
            os.symlink(os.path.join(root, "A"), os.path.join(root, "link"), target_is_directory=True)
        except (OSError, NotImplementedError):
            pass

        def old(path):
            out = []
            for r, dirs, files in os.walk(path):
                dirs[:] = sorted((d for d in dirs if not d.startswith(".")), key=str.lower)
                out += [os.path.join(r, f) for f in sorted(files, key=str.lower)
                        if f.lower().endswith(".mp3") and not f.startswith(".")]
            return out
        sts = {}
        got = scan(root, True, stats=sts)
        self.assertEqual(got, old(root))
        self.assertEqual([os.path.relpath(p, root).replace(os.sep, "/") for p in got],
                         ["a.mp3", "B.MP3", "x.mp3", "A/1.mp3", "A/2.mp3", "A/a/k.mp3", "A/z/9.mp3", "b/m.mp3"])
        self.assertEqual(sorted(sts), sorted(got))
        for p in got:
            self.assertEqual((sts[p].st_size, sts[p].st_mtime_ns), (os.stat(p).st_size, os.stat(p).st_mtime_ns))
        sts1 = {}
        self.assertEqual(scan(os.path.join(root, "A"), False, stats=sts1), [os.path.join(root, "A", "1.mp3"),
                                                                             os.path.join(root, "A", "2.mp3")])
        self.assertEqual(len(sts1), 2)

    def test_pack_migrates_old_objects(self):
        """#137: Objekte im alten Format (je Datei) werden beim Lesen in die Packdatei übernommen."""
        self.load()
        listcache.PACK._load()
        for h, (off, n) in listcache.PACK.index.items():
            with open(os.path.join(listcache.DIR, "objects.pack"), "rb") as fh:
                fh.seek(off)
                data = fh.read(n)
            old = listcache._obj_path(h)
            os.makedirs(os.path.dirname(old), exist_ok=True)
            with open(old, "wb") as fh:
                fh.write(data)
        listcache.PACK.reset()
        os.remove(os.path.join(listcache.DIR, "objects.idx.json"))        # Index weg → wie altes Format
        files, st = self.load()
        self.assertEqual(len(st["cached"]), 3)
        self.assertIn(h, listcache.PACK.index)
        self.assertIn("load", st["times"])

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

    def test_tagger_preview_rows(self):
        """#326: zuletzt angezeigte Tagger-Zeilen werden gemerkt (im Listen-Cache) und nur für denselben Ordner
        geliefert; ohne Listen-Cache nie. Schneller Cover-Fingerabdruck: gleiche Bilder gleich, andere verschieden."""
        from session import Session
        s = Session()
        s.start_tag_load(self.lib, False)
        self.wait(s)
        rows = s.tag_rows()["rows"]
        t0 = time.time()
        while getattr(s, "_tag_prev_busy", False) and time.time() - t0 < 5:
            time.sleep(0.02)
        p = s.tag_rows_preview(self.lib)
        self.assertEqual([r["rel"] for r in p["rows"]], [r["rel"] for r in rows])
        self.assertEqual(p["rows"][0]["TIT2"], "Titel 1")
        self.assertEqual(s.tag_rows_preview(self.lib + os.sep)["rows"], p["rows"])         # gleiche Schreibweise egal
        self.assertEqual(s.tag_rows_preview(self.dir)["rows"], [])                          # anderer Ordner
        self.assertEqual(s.tag_rows_preview("")["rows"], [])
        self.assertTrue(os.path.isfile(os.path.join(listcache.DIR, "tagger-rows.json.gz")))
        self.assertEqual(len({r["ch"] for r in rows}), 1)                                   # gleiches Cover → gleicher Hash
        f = s.tag_files[0]
        c = s._front_cover(f)
        c._h = None
        h1 = s._cover_hash(f)
        c.data = c.data[:-1] + bytes([c.data[-1] ^ 1])                                    # letztes Byte anders
        c._h = None
        self.assertNotEqual(s._cover_hash(f), h1)
        # Details eines Titels direkt aus der Datei (Sofort-Liste), nur innerhalb des Ordners
        d = Session().tag_detail_file(self.lib, "02.mp3")
        self.assertEqual((d["count"], d["preview"], d["file"]["name"], d["common"]["TIT2"]["value"]), (1, True, "02.mp3", "Titel 2"))
        self.assertEqual(Session().tag_detail_file(self.lib, "../lib/02.mp3")["count"], 0)
        self.assertEqual(Session().tag_detail_file(self.lib, "fehlt.mp3")["count"], 0)
        self.assertEqual(Session().tag_detail_file(os.path.join(self.lib, "01.mp3"))["count"], 1)
        s.set_list_cache(False)
        self.assertEqual(s.tag_rows_preview(self.lib)["rows"], [])
        # Vorschaubild unter dem Listen-Hash: erst aus dem Cover (store), abgelegt → auch ohne eingelesene Titel
        import base64
        import thumbs
        old_dir = thumbs.CACHE_DIR
        thumbs.CACHE_DIR = os.path.join(self.dir, "thumbs")
        try:
            h = rows[0]["ch"]
            r = s.tag_cover_thumb(h)
            self.assertTrue(r["ok"] and r["store"])
            small = png(96, 96, b"z" * 50)
            self.assertTrue(s.tag_cover_thumb_store(h, base64.b64encode(small).decode()))
            self.assertFalse(s.tag_cover_thumb_store(h, base64.b64encode(b"keinPNG").decode()))
            self.assertFalse(s.tag_cover_thumb_store("../x", base64.b64encode(small).decode()))
            self.assertFalse(s.tag_cover_thumb_store(h, "%%%"))
            s2 = Session()
            self.assertEqual(s2.tag_files, [])
            r2 = s2.tag_cover_thumb(h)
            self.assertEqual(base64.b64decode(r2["src"].split(",")[1]), small)
            self.assertEqual(s2.tag_cover_thumb("0" * 16), {"ok": False, "retry": True})
            self.assertEqual(s2.tag_cover_thumb("kein-hash"), {"ok": False})
            # grosse Vorschau (440 px, JPEG) getrennt von der Listen-Vorschau
            big = b"\xff\xd8\xff\xe0" + b"j" * 100
            self.assertTrue(s.tag_cover_thumb(h, 440)["store"])
            self.assertFalse(s.tag_cover_thumb_store(h, base64.b64encode(small).decode(), 440))   # PNG ist hier falsch
            self.assertTrue(s.tag_cover_thumb_store(h, base64.b64encode(big).decode(), 440))
            r3 = s2.tag_cover_thumb(h, 440)
            self.assertTrue(r3["src"].startswith("data:image/jpeg;base64,"))
            self.assertEqual(base64.b64decode(s2.tag_cover_thumb(h)["src"].split(",")[1]), small)
            self.assertTrue(Session._cache_dirs()["covers"][1].match(f"tg_{h}_440.jpg"))
            self.assertTrue(Session._cache_dirs()["covers"][1].match(f"tg_{h}.png"))
        finally:
            thumbs.CACHE_DIR = old_dir

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
        # als Hintergrund-Auftrag
        import jobs
        old = jobs.STATE_FILE
        jobs.STATE_FILE = os.path.join(self.dir, "Auftraege.json")
        try:
            shutil.rmtree(listcache.DIR)
            r = s.start_cache_build("lists", background=True)
            self.assertTrue(r["ok"] and r["job"])
            t0 = time.time()
            while s.jobs_status()["active"]:
                self.assertLess(time.time() - t0, 10)
                time.sleep(0.02)
            job = s.jobs_status()["jobs"][0]
            self.assertEqual(job["status"], "done", job)
            self.assertIn("3 Titel", job["message"])
            self.assertEqual(len(listcache.ListCache(self.lib).entries), 3)
        finally:
            s.jobs.shutdown()
            jobs.STATE_FILE = old

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
