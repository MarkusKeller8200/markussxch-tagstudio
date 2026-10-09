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


if __name__ == "__main__":
    unittest.main()
