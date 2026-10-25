"""Ordner ändern mit Inhalt (#313): verschieben/kopieren, Konflikte, Prüfsumme, Abbruch, Verweise nachführen."""
import os
import threading
import time
import unittest
from unittest import mock

from test_tagger_tools import Base
import foldermove  # noqa: E402 – Pfad setzt test_tagger_tools
import folders  # noqa: E402


def J(*p):
    return os.path.normpath(os.path.join(*p))


def put(path, data=b"x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


class TestFolderMove(Base):
    def tree(self, root):
        put(J(root, "a.mp3"), b"A" * 3000)
        put(J(root, "Sub", "b.mp3"), b"B" * 10)
        put(J(root, "Sub", "c.txt"), b"C")
        return root

    def test_plan(self):
        src = self.tree(J(self.dir, "Alt"))
        dst = J(self.dir, "Neu")
        put(J(dst, "a.mp3"), b"anders")
        p = foldermove.plan(src, dst)
        self.assertEqual((p["files"], p["bytes"], p["conflicts"]), (3, 3011, ["a.mp3"]))
        self.assertTrue(p["same_volume"])
        self.assertGreater(p["free"], 0)
        self.assertTrue(foldermove.plan(src, J(src, "innen"))["error"])          # Ziel im bisherigen Ordner
        self.assertTrue(foldermove.plan(src, src)["error"])
        self.assertEqual(foldermove.plan(J(self.dir, "fehlt"), dst)["files"], 0)

    def test_move_same_volume_keep_conflict(self):
        src = self.tree(J(self.dir, "Alt"))
        dst = J(self.dir, "Neu")
        put(J(dst, "a.mp3"), b"anders")
        r = foldermove.run(src, dst, "move", "keep")
        self.assertEqual(r["kept"], ["a.mp3"])
        with open(J(dst, "a.mp3"), "rb") as fh:
            self.assertEqual(fh.read(), b"anders")                               # nie überschrieben
        self.assertTrue(os.path.isfile(J(src, "a.mp3")))                         # Original bleibt beim Konflikt
        self.assertTrue(os.path.isfile(J(dst, "Sub", "b.mp3")))
        self.assertFalse(os.path.exists(J(src, "Sub", "b.mp3")))
        self.assertTrue(os.path.isdir(J(src, "Sub")))                            # alter Ordner bleibt stehen
        self.assertEqual(len(r["moved"]), 2)

    def test_copy_both(self):
        src = self.tree(J(self.dir, "Alt"))
        dst = J(self.dir, "Neu")
        put(J(dst, "a.mp3"), b"anders")
        r = foldermove.run(src, dst, "copy", "both")
        self.assertEqual(r["renamed"], ["a.mp3"])
        self.assertTrue(os.path.isfile(J(dst, "a (2).mp3")))
        self.assertTrue(os.path.isfile(J(src, "a.mp3")))                         # Kopie: Original bleibt
        self.assertEqual(r["copied"], 3)
        self.assertFalse(any(f.endswith(".part") for _d, _s, fs in os.walk(dst) for f in fs))

    def test_move_cross_volume_checks_sha(self):
        """Über Datenträger: kopieren, Prüfsumme vergleichen, erst dann Original entfernen."""
        src = self.tree(J(self.dir, "Alt"))
        dst = J(self.dir, "Neu")
        with mock.patch.object(foldermove, "same_volume", lambda a, b: False):
            r = foldermove.run(src, dst, "move")
        self.assertEqual(len(r["moved"]), 3)
        self.assertFalse(os.path.exists(J(src, "a.mp3")))
        with open(J(dst, "a.mp3"), "rb") as fh:
            self.assertEqual(fh.read(), b"A" * 3000)
        src2 = self.tree(J(self.dir, "Alt2"))                                     # Prüfsumme falsch → Original bleibt
        with mock.patch.object(foldermove, "same_volume", lambda a, b: False), \
                mock.patch.object(foldermove, "_sha", lambda p, c: "falsch"):
            r = foldermove.run(src2, J(self.dir, "Neu2"), "move")
        self.assertEqual(len(r["errors"]), 3)
        self.assertTrue(os.path.isfile(J(src2, "a.mp3")))
        self.assertFalse(os.path.exists(J(self.dir, "Neu2", "a.mp3")))
        self.assertFalse(any(f.endswith(".part") for _d, _s, fs in os.walk(J(self.dir, "Neu2")) for f in fs))

    def test_cancel_leaves_no_half_files(self):
        src = self.tree(J(self.dir, "Alt"))
        dst = J(self.dir, "Neu")
        ev = threading.Event()
        real = foldermove._sha_copy

        def slow(a, b, cancel):
            ev.set()                                                              # während der ersten Kopie abbrechen
            return real(a, b, cancel)
        with mock.patch.object(foldermove, "same_volume", lambda a, b: False), \
                mock.patch.object(foldermove, "_sha_copy", slow):
            r = foldermove.run(src, dst, "move", cancel=ev)
        self.assertTrue(r["cancelled"])
        self.assertEqual(r["moved"], [])
        self.assertTrue(os.path.isfile(J(src, "a.mp3")) and os.path.isfile(J(src, "Sub", "b.mp3")))
        self.assertFalse(any(f.endswith(".part") for _d, _s, fs in os.walk(dst) for f in fs))

    def test_rebase_and_remove_empty(self):
        old, new = J(self.dir, "Alt"), J(self.dir, "Neu")
        self.assertEqual(foldermove.rebase(J(old, "x", "a.mp3"), old, new), J(new, "x", "a.mp3"))
        self.assertEqual(foldermove.rebase(old, old, new), new)
        self.assertEqual(foldermove.rebase(J(self.dir, "Altes", "a.mp3"), old, new), J(self.dir, "Altes", "a.mp3"))
        os.makedirs(J(old, "a", "b"))
        put(J(old, "keep", "f.txt"))
        self.assertEqual(foldermove.remove_empty(old), 2)
        self.assertTrue(os.path.isfile(J(old, "keep", "f.txt")))                 # Dateien nie gelöscht

    def test_journal(self):
        p = J(self.dir, "Export", "Ordnerwechsel.csv")
        foldermove.journal(p, "Archiv", {"src": "a", "dst": "b", "moved": [1, 2], "copied": 0, "bytes": 5,
                                         "kept": [], "errors": []}, "move")
        foldermove.journal(p, "Archiv", {"src": "a", "dst": "b", "moved": [], "copied": 1, "cancelled": True}, "copy")
        with open(p, encoding="utf-8-sig") as fh:
            lines = fh.read().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertIn("Archiv;move;a;b;2;5", lines[1])
        self.assertTrue(lines[2].endswith(";ja"))


class TestSessionChange(Base):
    def session(self, cfg):
        from session import Session
        s = Session()
        s.cfg.clear()
        s.cfg.update(cfg)
        return s

    def wait(self, s):
        for _ in range(500):
            st = s.task_status()
            if st.get("done"):
                return st
            time.sleep(0.02)
        self.fail("hängt")

    def test_archive_move_relinks_log(self):
        import archive
        base = J(self.dir, "TS")
        lib = J(base, "01_Library")
        put(J(lib, "House", "t.mp3"), b"T")
        s = self.session({"base_dir": base, "default_tagger": lib})
        s.folders_get()
        arch = J(base, "02_Archiv")
        os.makedirs(arch)
        pl = archive.plan([J(lib, "House", "t.mp3")], lib, arch)
        archive.move(pl, arch)
        s.cfg["hist_tagger"] = [J(arch, "House")]
        new = J(self.dir, "Anderswo", "Archiv")
        pv = s.folders_change_preview("role", "archive", {"mode": "custom", "value": new})
        it = pv["items"][0]
        self.assertEqual((it["files"], it["default"], it["warning"]), (2, "move", ""))   # Titel + Vermerk
        r = s.start_folders_change("role", "archive", {"mode": "custom", "value": new}, {it["key"]: "move"})
        self.assertNotIn("error", r)
        st = self.wait(s)
        res = st["result"]
        self.assertTrue(res["ok"], res)
        self.assertEqual(folders.role(s.cfg, "archive"), new)
        self.assertTrue(os.path.isfile(J(new, "House", "t.mp3")))
        e = archive.entries(new)[0]
        self.assertEqual(e["dst"], J(new, "House", "t.mp3"))                    # Vermerk nachgeführt
        self.assertTrue(e["in_archive"])
        self.assertEqual(s.cfg["hist_tagger"], [J(new, "House")])
        self.assertEqual(res["empty_old"], [arch])                               # leerer Ordner bleibt bis zur Rückfrage
        self.assertTrue(os.path.isdir(arch))
        self.assertTrue(s.folders_remove_empty(arch)["ok"])
        self.assertFalse(os.path.exists(arch))
        res2 = s.archive_restore([e["id"]])                                      # „Zurückholen“ geht weiter
        self.assertEqual(res2["restored"], 1)
        self.assertTrue(os.path.isfile(J(lib, "House", "t.mp3")))
        self.assertTrue(os.path.isfile(J(self.dir, "Export", "Ordnerwechsel.csv"))
                        or os.path.isfile(J(base, "04_Export", "Ordnerwechsel.csv")))

    def test_library_default_none_with_warning_and_playlists(self):
        base = J(self.dir, "TS")
        lib = J(base, "01_Library")
        put(J(lib, "a.mp3"), b"A")
        s = self.session({"base_dir": base, "default_tagger": lib})
        s.folders_get()
        with s.lock:
            st = s._pls()
            p = st.create("Set", "", "manual")
            st.add(p["id"], [{"path": J(lib, "a.mp3")}], "skip")
        lid = s._folders()["libraries"][0]["id"]
        new = J(self.dir, "Musik")
        pv = s.folders_change_preview("lib", lid, {"mode": "custom", "value": new})
        it = pv["items"][0]
        self.assertEqual(it["default"], "none")                                  # O4
        self.assertIn("fremden Datenbanken", it["warning"])
        s.start_folders_change("lib", lid, {"mode": "custom", "value": new}, {it["key"]: "move"})
        res = self.wait(s)["result"]
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["relinked"]["Bibliothek Haupt"]["playlists"], 1)
        with s.lock:
            self.assertEqual(s._pls().get(p["id"])["items"][0]["path"], J(new, "a.mp3"))
        self.assertEqual(folders.main_library(s.cfg), new)

    def test_copy_none_and_base(self):
        base = J(self.dir, "TS")
        put(J(base, "03_Playlists", "x.m3u8"), b"#EXTM3U")
        put(J(base, "04_Export", "liste.csv"), b"1")
        s = self.session({"base_dir": base})
        s.folders_get()
        new = J(self.dir, "TS2")
        pv = s.folders_change_preview("base", None, {"value": new})
        keys = {x["key"]: x for x in pv["items"]}
        self.assertIn("role:playlists", keys)
        self.assertIn("role:export", keys)
        self.assertEqual(keys["lib:main"]["default"], "none")
        s.start_folders_change("base", None, {"value": new}, {"role:playlists": "copy", "role:export": "none"})
        res = self.wait(s)["result"]
        self.assertTrue(res["ok"], res)
        self.assertTrue(os.path.isfile(J(new, "03_Playlists", "x.m3u8")))
        self.assertTrue(os.path.isfile(J(base, "03_Playlists", "x.m3u8")))        # Kopie: Original bleibt
        self.assertFalse(os.path.exists(J(new, "04_Export", "liste.csv")))        # nicht übernommen
        self.assertEqual(s.cfg["base_dir"], new)

    def test_cancel_keeps_setting(self):
        base = J(self.dir, "TS")
        put(J(base, "02_Archiv", "a.mp3"), b"A")
        s = self.session({"base_dir": base})
        s.folders_get()
        new = J(self.dir, "X")
        with mock.patch.object(foldermove, "run", lambda *a, **k: {"moved": [], "copied": 0, "kept": [],
                                                                    "renamed": [], "errors": [], "bytes": 0,
                                                                    "cancelled": True, "src": a[0], "dst": a[1]}):
            s.start_folders_change("role", "archive", {"mode": "custom", "value": new}, {"role:archive": "move"})
            res = self.wait(s)["result"]
        self.assertFalse(res["ok"])
        self.assertTrue(res["cancelled_move"])
        self.assertEqual(folders.role(s.cfg, "archive"), J(base, "02_Archiv"))     # Einstellung unverändert


if __name__ == "__main__":
    unittest.main()
