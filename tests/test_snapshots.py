"""Tests für Snapshots und Änderungsjournal (snapshots.py, #52)."""
import datetime
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import snapshots as sn  # noqa: E402
from helpers import apic, geob, png, text, txxx, write_mp3  # noqa: E402
from id3tags import MP3File  # noqa: E402


def touch_later(path):
    """Änderungszeit sicher verschieben (Dateisysteme mit grober Auflösung)."""
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ts_snap_")
        self.lib = os.path.join(self.dir, "Bibliothek")
        os.makedirs(os.path.join(self.lib, "Album"))
        cover = png(400, 400, b"x" * 3000)
        for i in range(1, 5):
            write_mp3(os.path.join(self.lib, "Album", f"0{i} Titel.mp3"),
                      [text("TIT2", f"Titel {i}"), text("TPE1", "Mara Lind"), text("TKEY", "8A"),
                       txxx("Comment", "gute Bridge"), apic(cover), geob("Serato Markers2", b"\x01\x01AAAA")],
                      audio_seed=i, audio_frames=60)
        self.store = sn.Store(os.path.join(self.dir, "Snapshots"))
        self.libd = self.store.add_library(self.lib)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def path(self, n):
        return os.path.join(self.lib, "Album", f"0{n} Titel.mp3")


class TestSplit(Base):
    def test_split_reconstructs_bytes(self):
        info = sn.read_tags(self.path(1))
        parts = sn.split_tag(info["tag"])
        self.assertEqual(b"".join(parts), info["tag"])
        self.assertGreaterEqual(len(parts), 7)                 # Kopf + 6 Frames (+ Padding)
        self.assertEqual(sn.split_tag(b""), [])
        self.assertEqual(sn.split_tag(b"ID3\x03\x00\x80\x00\x00\x00\x05abcde"), [b"ID3\x03\x00\x80\x00\x00\x00\x05abcde"])


class TestSnapshots(Base):
    def test_create_dedupe_and_restore_bytes(self):
        s1 = sn.create(self.store, self.libd["id"], "Erster")
        self.assertEqual(s1["count"], 4)
        objs = sum(len(f) for _d, _s, f in os.walk(os.path.join(self.store.root, "objects")))
        self.assertLess(objs, 4 * 7)                          # Cover, Künstler, Tonart … nur einmal
        m = self.store.manifest(self.libd["id"], s1["id"])
        e = m["files"][0]
        tag, v1 = self.store.tag_bytes(e)
        self.assertEqual(tag, sn.read_tags(os.path.join(self.lib, e["p"]))["tag"])
        sizes = self.store.sizes()
        self.assertGreater(sizes["total"], 0)
        s2 = sn.create(self.store, self.libd["id"], auto=True)   # nichts geändert → nichts Neues
        objs2 = sum(len(f) for _d, _s, f in os.walk(os.path.join(self.store.root, "objects")))
        self.assertEqual(objs, objs2)
        self.assertEqual(len(self.store.snapshots(self.libd["id"])), 2)
        self.assertLess(self.store.sizes()["snaps"][f"{self.libd['id']}/{s2['id']}"], 4000)   # nur Manifest

    def test_journal_detects_external_changes(self):
        lid = self.libd["id"]
        s1 = sn.create(self.store, lid, "Vor MIK")
        # „Mixed In Key“ ändert Tonart, „Mp3tag“ löscht Kommentar
        f = MP3File(self.path(1))
        f.set_text("TKEY", "9A")
        f.set_text("TXXX:EnergyLevel", "7")
        f.save()
        f = MP3File(self.path(2))
        f.set("TXXX:Comment", None)
        f.save()
        # nur Umschreibung v2.4 → v2.3 (Werte gleich)
        f = MP3File(self.path(3))
        f.set_version(3)
        f.save()
        for n in (1, 2, 3):
            touch_later(self.path(n))
        # Umbenennen + neue Datei + Löschen
        os.rename(self.path(4), os.path.join(self.lib, "Album", "04 Neu benannt.mp3"))
        write_mp3(os.path.join(self.lib, "Album", "05 Neu.mp3"), [text("TIT2", "Neu")], audio_seed=9)
        q = sn.quick_changes(self.lib, self.store.manifest(lid, s1["id"]))
        self.assertEqual((q["changed"], q["new"], q["removed"]), (3, 2, 1))
        live = sn.MemStore(self.store)
        files, _err = sn.scan(self.lib, live, self.store.manifest(lid, s1["id"]))
        j = sn.journal(self.store.manifest(lid, s1["id"]), files, self.store, live)
        st = {r["p"]: r for r in j["rows"]}
        r1 = st["Album/01 Titel.mp3"]
        self.assertEqual(r1["status"], "changed")
        self.assertEqual({(f["key"], f["state"], f["old"], f["new"]) for f in r1["fields"]},
                         {("TKEY", "changed", "8A", "9A"), ("TXXX:EnergyLevel", "added", "", "7")})
        self.assertEqual([f["state"] for f in st["Album/02 Titel.mp3"]["fields"]], ["removed"])
        self.assertEqual(st["Album/03 Titel.mp3"]["status"], "rewrite")
        self.assertEqual(st["Album/04 Neu benannt.mp3"]["status"], "renamed")
        self.assertEqual(st["Album/04 Neu benannt.mp3"]["p_old"], "Album/04 Titel.mp3")
        self.assertEqual(st["Album/05 Neu.mp3"]["status"], "new")
        self.assertEqual(j["counts"], {"changed": 2, "rewrite": 1, "renamed": 1, "new": 1})
        # Live hat nichts in den Speicher geschrieben
        self.assertTrue(live.mem)

    def test_audio_change(self):
        lid = self.libd["id"]
        s1 = sn.create(self.store, lid)
        write_mp3(self.path(1), [text("TIT2", "Titel 1"), text("TPE1", "Mara Lind")], audio_seed=77, audio_frames=60)
        touch_later(self.path(1))
        live = sn.MemStore(self.store)
        files, _e = sn.scan(self.lib, live, self.store.manifest(lid, s1["id"]))
        j = sn.journal(self.store.manifest(lid, s1["id"]), files, self.store, live)
        r = j["rows"][0]
        self.assertTrue(r["audio"])
        self.assertEqual(j["counts"]["audio"], 1)

    def test_prune_and_gc(self):
        lid = self.libd["id"]
        base = datetime.datetime(2026, 10, 9, 12, 0)
        snap = sn.create(self.store, lid, auto=True)
        m = self.store.manifest(lid, snap["id"])
        self.store.delete_snapshot(lid, snap["id"])
        for d in range(60):             # 60 Tage täglich ein automatischer Snapshot
            t = base - datetime.timedelta(days=d)
            mm = dict(m, id=f"auto{d:03d}", created=sn._now(t))
            self.store.write_manifest(lid, mm)
        self.store.write_manifest(lid, dict(m, id="pin", created=sn._now(base - datetime.timedelta(days=300)),
                                            auto=True, pinned=True))
        self.store.write_manifest(lid, dict(m, id="named", created=sn._now(base - datetime.timedelta(days=200)),
                                            auto=False, label="Vor Platinum Notes"))
        gone = self.store.prune(lid, keep=20, weeks=12, now=base)
        left = {s["id"] for s in self.store.snapshots(lid)}
        self.assertIn("pin", left)
        self.assertIn("named", left)
        self.assertTrue(all(f"auto{d:03d}" in left for d in range(20)))
        autos_old = [s for s in left if s.startswith("auto") and int(s[4:]) >= 20]
        self.assertTrue(5 <= len(autos_old) <= 7)              # je Woche einer (Tage 20–59)
        self.assertEqual(len(gone), 40 - len(autos_old))
        # Objekte bleiben, solange sie benutzt werden; nach Löschen aller Snapshots weg
        for s in list(left):
            self.store.delete_snapshot(lid, s)
        self.assertEqual(sum(len(f) for _d, _s, f in os.walk(os.path.join(self.store.root, "objects"))), 0)

    def test_format_versioning(self):
        sn.create(self.store, self.libd["id"])
        meta = os.path.join(self.store.root, "store.json")
        with open(meta, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["format"], sn.FORMAT)
        with open(meta, "w", encoding="utf-8") as fh:
            json.dump({"format": sn.FORMAT + 1}, fh)
        st = sn.Store(self.store.root)
        self.assertTrue(st.readonly)
        self.assertEqual(len(st.snapshots(self.libd["id"])), 1)    # lesen geht
        with self.assertRaises(sn.StoreError):
            sn.create(st, self.libd["id"])

    def test_paths_are_relative(self):
        s1 = sn.create(self.store, self.libd["id"])
        moved = os.path.join(self.dir, "Woanders")
        shutil.copytree(self.lib, moved)
        self.store.update_library(self.libd["id"], root=moved)
        q = sn.quick_changes(moved, self.store.manifest(self.libd["id"], s1["id"]))
        self.assertEqual(q["new"] + q["removed"], 0)


class TestMoveStore(Base):
    """#60: Speicher verschieben, im Ordner erkennen, mit dem Ordner weitergeben."""

    def test_move_into_library_and_hand_over(self):
        lid = self.libd["id"]
        s1 = sn.create(self.store, lid, "Vor MIK", pinned=True)
        old = self.store.root
        with self.assertRaises(sn.StoreError):
            sn.move_store(old, os.path.join(old, "innen"))
        res = sn.move_store(old, self.lib)                      # nicht leer → Unterordner
        self.assertEqual(res["root"], os.path.join(self.lib, sn.STORE_DIRNAME))
        self.assertFalse(os.path.exists(old))
        st = sn.Store(res["root"])
        self.assertEqual(st.snapshots(lid)[0]["label"], "Vor MIK")
        self.assertEqual(st.library(lid)["rel"], "..")
        # Ordner samt Speicher weitergegeben (anderer Pfad): Bibliothek wird über den relativen Pfad gefunden
        moved = os.path.join(self.dir, "Weitergegeben")
        shutil.move(self.lib, moved)
        st2 = sn.Store(os.path.join(moved, sn.STORE_DIRNAME))
        self.assertEqual(st2.library(lid)["root"], os.path.normpath(moved))
        self.assertEqual(sn.find_store(os.path.join(moved, "Album", "01 Titel.mp3")), st2.root)
        j = sn.journal(st2.manifest(lid, s1["id"]), sn.scan(moved, sn.MemStore(st2))[0], st2, st2)
        self.assertEqual(j["rows"], [])
        self.assertEqual(sn.summary(st2.root)["libs"][0]["count"], 1)
        # zurück an einen leeren Ort; belegtes Ziel wird abgelehnt
        busy = os.path.join(self.dir, "Belegt", sn.STORE_DIRNAME)
        os.makedirs(busy)
        open(os.path.join(busy, "x.txt"), "w").close()
        with self.assertRaises(sn.StoreError):
            sn.move_store(st2.root, busy)
        back = sn.move_store(st2.root, os.path.join(self.dir, "Neu"))
        self.assertEqual(len(sn.Store(back["root"]).snapshots(lid)), 1)
        self.assertIsNone(sn.find_store(moved))


if __name__ == "__main__":
    unittest.main()


class TestSessionSnapshots(Base):
    def setUp(self):
        super().setUp()
        import core
        import jobs
        self._old = (core.CONFIG, core.CONFIG_OLD, jobs.STATE_FILE)
        core.CONFIG = core.CONFIG_OLD = os.path.join(self.dir, "cfg.json")
        jobs.STATE_FILE = os.path.join(self.dir, "Auftraege.json")
        core.save_config({"snap_dir": self.store.root, "backup_dir": os.path.join(self.dir, "Sicherungen")})
        import plugins
        self._logdir = plugins.log_dir
        logs = os.path.join(self.dir, "Logs")
        os.makedirs(logs, exist_ok=True)
        plugins.log_dir = lambda: logs
        from session import Session
        self.s = Session()

    def tearDown(self):
        import core
        import jobs
        import plugins
        core.CONFIG, core.CONFIG_OLD, jobs.STATE_FILE = self._old
        plugins.log_dir = self._logdir
        super().tearDown()

    def test_program_guess(self):
        """#57: Mixed In Key an TKEY + EnergyLevel erkannt, reine Titeländerung unbekannt."""
        s, lid = self.s, self.libd["id"]
        s.snap_create(lid, "Vor MIK")
        self.wait_jobs()
        sid = s.snap_list(lid)["snapshots"][0]["id"]
        f = MP3File(self.path(1))
        f.set_text("TKEY", "9A")
        f.set_text("TXXX:EnergyLevel", "7")
        f.save()
        f = MP3File(self.path(2))
        f.set_text("TIT2", "Anders")
        f.save()
        for n in (1, 2):
            touch_later(self.path(n))
        s.start_snap_journal(lid, sid, "live")
        j = self.wait_task()
        g = {r["p"]: r["guess"] for r in j["rows"]}
        self.assertEqual((g["Album/01 Titel.mp3"], g["Album/02 Titel.mp3"]), ("mik", ""))
        self.assertEqual(j["programs"]["mik"], {"name": "Mixed In Key", "rows": 1, "fields": 2})
        self.assertEqual(j["programs"][""]["name"], "unbekannt")

    def test_watch(self):
        """#58: Abfrage meldet fremde Änderungen, nicht die eigenen."""
        s, lid = self.s, self.libd["id"]
        self.assertEqual(s.snap_watch()["total"], 0)            # erste Abfrage = Ausgangslage
        f = MP3File(self.path(1))
        f.set_text("TKEY", "9A")
        f.save()
        touch_later(self.path(1))
        os.remove(self.path(4))
        w = s.snap_watch()
        self.assertEqual((w["total"], sorted(w["libs"][0]["files"])), (2, ["Album/01 Titel.mp3", "Album/04 Titel.mp3"]))
        # eigene Änderung über den Tagger: zählt nicht
        s.start_tag_load(self.lib, True)
        self.wait_task()
        i = next(k for k, g in enumerate(s.tag_files) if g.path.endswith("02 Titel.mp3"))
        s.tag_files[i].set_text("TIT2", "Neu")
        s.start_save()
        self.wait_task()
        touch_later(self.path(2))
        self.assertEqual(s.snap_watch()["total"], 2)
        s.snap_watch_ack(lid)
        self.assertEqual(s.snap_watch()["total"], 0)

    def test_move_detect_use(self):
        """#60 über die Session: verschieben, erkennen, verwenden, ignorieren."""
        s, lid = self.s, self.libd["id"]
        s.snap_create(lid, "Erster")
        self.wait_jobs()
        self.assertTrue(s.snap_overview()["default"] is False)
        self.assertIsNone(s.snap_detect(self.lib))
        s.start_snap_move(self.lib)
        res = self.wait_task()
        self.assertIn("verschoben", res["message"])
        self.assertEqual(s.snap_store.root, os.path.join(self.lib, sn.STORE_DIRNAME))
        self.assertEqual(len(s.snap_list(lid)["snapshots"]), 1)
        self.assertIsNone(s.snap_detect(self.lib))              # ist ja der aktuelle
        # ein anderer Speicher ist aktiv → der im Ordner wird angeboten
        other = os.path.join(self.dir, "Anderer")
        sn.Store(other)._init()
        self.assertTrue(s.snap_use(other)["ok"])
        d = s.snap_detect(os.path.join(self.lib, "Album"))
        self.assertEqual((d["root"], d["libs"][0]["count"]), (os.path.join(self.lib, sn.STORE_DIRNAME), 1))
        s.snap_ignore(d["root"])
        self.assertIsNone(s.snap_detect(self.lib))
        self.assertTrue(s.snap_use(d["root"])["ok"])
        self.assertEqual(len(s.snap_overview()["libs"]), 1)

    def test_job_log(self):
        """#62: Protokoll mit Start, Ende, Dauer und Speicherplatz."""
        s, lid = self.s, self.libd["id"]
        s.snap_create(lid, "Erster")
        self.wait_jobs()
        s.snap_create(lid, "Zweiter")
        self.wait_jobs()
        job = next(j for j in s.jobs_status()["jobs"] if j["logfile"])
        self.assertEqual(job["status"], "done", job)
        self.assertTrue(job["logfile"].endswith("snapshots.log"))
        with open(job["logfile"], encoding="utf-8") as fh:
            text = fh.read()
        for word in ("Start:", "Ende:", "Dauer:", "Speicherplatz:", "alle Snapshots"):
            self.assertIn(word, text)
        self.assertEqual(text.count("===== "), 2)
        self.assertIn("unverändert übernommen 4", text)

    def wait_jobs(self):
        t0 = time.time()
        while self.s.jobs_status()["active"]:
            self.assertLess(time.time() - t0, 20)
            time.sleep(0.02)

    def wait_task(self):
        while not self.s.task_status().get("done"):
            time.sleep(0.02)
        st = self.s.task_status()
        self.assertIsNone(st["error"], st)
        return st["result"]

    def test_flow(self):
        s, lid = self.s, self.libd["id"]
        ov = s.snap_overview()
        self.assertEqual([l["name"] for l in ov["libs"]], ["Bibliothek"])
        st = s.snap_startup()
        self.assertTrue(st["libs"][0]["due"])
        self.assertTrue(s.snap_create(lid, "Vor MIK", pinned=True)["ok"])
        self.wait_jobs()
        snaps = s.snap_list(lid)["snapshots"]
        self.assertEqual((len(snaps), snaps[0]["label"], snaps[0]["pinned"]), (1, "Vor MIK", True))
        self.assertGreater(snaps[0]["bytes"], 0)
        self.assertTrue(s.snap_startup()["libs"][0]["due"])      # kein automatischer heute
        s.snap_create(lid, auto=True)
        self.wait_jobs()
        self.assertFalse(s.snap_startup()["libs"][0]["due"])
        # Fremdprogramm ändert
        f = MP3File(self.path(1))
        f.set_text("TKEY", "9A")
        f.set("TXXX:Comment", None)
        f.save()
        touch_later(self.path(1))
        self.assertEqual(s.snap_startup()["libs"][0]["changed"], 1)
        s.start_snap_journal(lid, snaps[0]["id"], "live")
        j = self.wait_task()
        self.assertEqual(len(j["rows"]), 1)
        r = j["rows"][0]
        self.assertEqual(sorted(x["key"] for x in r["fields"]), ["TKEY", "TXXX:Comment"])
        # nur die Tonart zurück (Undo-Weg), dann speichern
        res = s.snap_revert([{"p": r["p"], "keys": ["TKEY"]}])
        self.assertEqual((res["done"], res["fields"], res["unsaved"]), (1, 1, 1))
        s.start_save()
        self.wait_task()
        f = MP3File(self.path(1))
        self.assertEqual((f.text("TKEY"), f.get("TXXX:Comment")), ("8A", None))
        # ganze Datei byte-genau
        res = s.snap_revert([{"p": r["p"]}], mode="bytes")
        self.assertEqual(res["done"], 1, res)
        self.assertEqual(sn.read_tags(self.path(1))["tag"], self.store.tag_bytes(self.store.manifest(lid, snaps[0]["id"])["files"][0])[0])
        self.assertEqual(MP3File(self.path(1)).text("TXXX:Comment"), "gute Bridge")
        # Aufräumen lässt den angehefteten stehen
        self.assertEqual(s.snap_prune()["removed"], 0)
        self.assertEqual(s.snap_set("snap_keep", 5)["snap_keep"], 5)
