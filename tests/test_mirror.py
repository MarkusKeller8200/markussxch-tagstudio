"""#403: Spiegel der Bibliothek – Einweg-Kopie, Platzschätzung, überzählige Dateien nur nach Rückfrage, index.json,
Playlists mit relativen Pfaden, automatisch nachführen."""
import json
import os
import time

from test_tagger_tools import Base

import mirror


class TestMirrorCore(Base):
    def setUp(self):
        super().setUp()
        self.T = os.path.join(self.dir, "OneDrive", "TagStudio-Spiegel")
        os.makedirs(os.path.join(self.A, "Sub"))
        with open(os.path.join(self.A, "Sub", "4.mp3"), "wb") as fh:
            fh.write(b"ID3" + b"\0" * 300)
        self.libs = [{"id": "main", "name": "Haupt", "path": self.A}]

    def test_plan_copy_and_unchanged(self):
        pl = mirror.plan(self.libs, self.T)
        self.assertEqual(pl["error"], "")
        self.assertEqual(pl["files"], 3)                                  # nur Audio, keine Bilder
        self.assertEqual(len(pl["copy"]), 3)
        self.assertEqual(pl["present_bytes"], 0)
        r = mirror.run(pl)
        self.assertEqual(r["copied"], 3)
        self.assertTrue(os.path.isfile(os.path.join(self.T, "Haupt", "Sub", "4.mp3")))
        self.assertFalse([n for _d, _s, fs in os.walk(self.T) for n in fs if n.endswith(".part")])
        pl2 = mirror.plan(self.libs, self.T)
        self.assertEqual(len(pl2["copy"]), 0)                             # nichts geändert
        self.assertEqual(pl2["present_bytes"], pl2["bytes"])
        # Änderung in der Bibliothek → nur diese Datei
        p = os.path.join(self.A, "1.mp3")
        with open(p, "ab") as fh:
            fh.write(b"x")
        os.utime(p, (time.time(), time.time() + 10))
        pl3 = mirror.plan(self.libs, self.T)
        self.assertEqual([os.path.basename(x[0]) for x in pl3["copy"]], ["1.mp3"])

    def test_extra_only_reported(self):
        mirror.run(mirror.plan(self.libs, self.T))
        os.remove(os.path.join(self.A, "2.mp3"))
        pl = mirror.plan(self.libs, self.T)
        self.assertEqual([os.path.basename(x) for x in pl["extra"]], ["2.mp3"])
        mirror.run(pl)
        self.assertTrue(os.path.exists(pl["extra"][0]))                  # nie automatisch gelöscht
        r = mirror.delete_extra(pl["extra"] + [os.path.join(self.A, "1.mp3")], self.T)
        self.assertEqual(r["deleted"], 1)
        self.assertEqual(len(r["errors"]), 1)                             # ausserhalb des Spiegels: abgelehnt
        self.assertTrue(os.path.exists(os.path.join(self.A, "1.mp3")))

    def test_nested_refused_and_names(self):
        self.assertIn("ineinander", mirror.plan(self.libs, os.path.join(self.A, "Spiegel"))["error"])
        self.assertIn("Ziel", mirror.plan(self.libs, "")["error"])
        self.assertEqual(mirror.safe_name('A:B/C*'), "A_B_C_")
        two = [{"id": "a", "name": "Musik", "path": self.A}, {"id": "b", "name": "musik", "path": self.B}]
        dests = [x["dest"] for x in mirror.plan(two, self.T)["libs"]]
        self.assertEqual(len(set(d.lower() for d in dests)), 2)          # keine Kollision

    def test_layout_path(self):
        """#413: Aufbau „Pfad“ – Pfad der Bibliothek ohne Laufwerk; Index und Playlists in TagStudio/Spiegel."""
        import ntpath
        import posixpath
        self.assertEqual(mirror.path_parts(r"D:\Musik\DJ\Bibliothek", ntpath, False), ["Musik", "DJ", "Bibliothek"])
        self.assertEqual(mirror.path_parts(r"\\nas\musik\DJ", ntpath, False), ["DJ"])
        self.assertEqual(mirror.path_parts("/Volumes/Musik/DJ/Set", posixpath, True), ["DJ", "Set"])
        self.assertEqual(mirror.clean_cfg({})["layout"], "path")                  # neu: Standard „Pfad“
        self.assertEqual(mirror.clean_cfg({"folder": "/x"})["layout"], "name")    # schon gespeichert: wie bisher
        od = os.path.join(self.dir, "OneDrive")
        pl = mirror.plan(self.libs, od, "path")
        self.assertEqual(pl["error"], "")
        want = os.path.join(od, *mirror.path_parts(self.A))
        self.assertEqual(pl["libs"][0]["dest"], want)
        mirror.run(pl)
        self.assertTrue(os.path.isfile(os.path.join(want, "Sub", "4.mp3")))
        meta = mirror.meta_dir(od, "path")
        self.assertEqual(meta, os.path.join(od, "TagStudio", "Spiegel"))
        mirror.write_index(od, pl, None, meta)
        idx = mirror.load_index(meta)
        self.assertEqual(idx["root"], "../..")
        rel = pl["libs"][0]["rel"]
        self.assertTrue(all(t["path"].startswith(rel + "/") for t in idx["tracks"]))
        self.assertTrue(os.path.isfile(os.path.join(meta, *idx["root"].split("/"), *idx["tracks"][0]["path"].split("/"))))
        # ineinander liegende Bibliotheken würden sich überlagern → abgelehnt
        nest = self.libs + [{"id": "sub", "name": "Sub", "path": os.path.join(self.A, "Sub")}]
        self.assertIn("ineinander", mirror.plan(nest, od, "path")["error"])

    def test_estimate_and_index_and_playlists(self):
        pl = mirror.plan(self.libs, self.T)
        est = mirror.estimate(pl, 1000)
        self.assertEqual(est["total"], pl["bytes"] + 1000)
        self.assertIsNotNone(mirror.free_space(self.T))                  # Ordner gibt es noch nicht → Laufwerk darüber
        mirror.run(pl)
        n = mirror.write_index(self.T, pl)
        self.assertEqual(n, 3)
        idx = mirror.load_index(self.T)
        t = {e["path"]: e for e in idx["tracks"]}
        self.assertEqual(t["Haupt/1.mp3"]["title"], "golden hour")
        self.assertEqual(t["Haupt/1.mp3"]["artist"], "Mara Lind")
        k = mirror.write_playlists(self.T, [{"name": "Set", "folder": "DJ/Abend", "items": [
            {"path": os.path.join(self.A, "Sub", "4.mp3"), "artist": "X", "title": "Y"},
            {"path": os.path.join(self.dir, "fremd.mp3")}]}], pl)
        self.assertEqual(k, 1)
        with open(os.path.join(self.T, "Playlists", "DJ", "Abend", "Set.m3u8"), encoding="utf-8") as fh:
            txt = fh.read()
        self.assertIn("../../../Haupt/Sub/4.mp3", txt)                    # relativ, mit „/“
        self.assertNotIn("fremd", txt)


class TestMirrorSession(Base):
    def setUp(self):
        super().setUp()
        from session import Session
        self.s = Session()
        self.s.folders_lib_add("Musik", "custom", self.A)
        self.T = os.path.join(self.dir, "OneDrive", "TagStudio-Spiegel")

    def wait(self):
        for _ in range(200):
            if not self.s.task.get("running"):
                return self.s.task
            time.sleep(0.05)
        self.fail("Auftrag läuft noch")

    def test_flow(self):
        ov = self.s.mirror_overview()
        self.assertEqual(ov["cfg"]["folder"], "")
        self.assertFalse(self.s.start_mirror()["ok"])                    # ohne Ziel
        with self.assertRaises(ValueError):
            self.s.mirror_set({"folder": os.path.join(self.A, "x")})      # nicht in der Bibliothek
        self.s.mirror_set({"folder": self.T, "libraries": [], "playlists": True})
        est = self.s.mirror_estimate()
        self.assertGreater(est["music"], 0)
        self.assertEqual(est["present"], 0)
        self.assertTrue(self.s.start_mirror()["ok"])
        t = self.wait()
        self.assertIsNone(t["error"], t)
        self.assertIn("kopiert", t["result"]["message"])
        self.assertTrue(os.path.isfile(os.path.join(self.T, "Musik", "1.mp3")))
        self.assertTrue(os.path.isfile(os.path.join(self.T, mirror.INDEX)))
        self.assertEqual(self.s.mirror_overview()["last"]["copied"], 2)
        self.assertEqual(self.s.mirror_estimate()["to_copy"], 0)
        # überzählig: nur aus der Liste löschbar
        os.remove(os.path.join(self.A, "2.mp3"))
        self.s.start_mirror()
        self.wait()
        ex = self.s.mirror_extra()["files"]
        self.assertEqual([x["rel"] for x in ex], ["Musik/2.mp3"])
        r = self.s.mirror_delete_extra([os.path.join(self.T, "Musik", "1.mp3")])     # nicht in der Liste
        self.assertEqual(r["deleted"], 0)
        r = self.s.mirror_delete_extra([ex[0]["path"]])
        self.assertEqual((r["deleted"], r["left"]), (1, 0))
        self.assertEqual(self.s.mirror_overview()["last"]["extra"], 0)
        self.assertTrue(os.path.isfile(os.path.join(self.T, "Musik", "1.mp3")))

    def test_auto_touch(self):
        self.s.mirror_set({"folder": self.T, "auto": True})
        p = os.path.join(self.A, "1.mp3")
        self.s._mirror_touch([p])
        dst = os.path.join(self.T, "Musik", "1.mp3")
        for _ in range(100):
            if os.path.exists(dst):
                break
            time.sleep(0.05)
        self.assertTrue(os.path.exists(dst))
        self.assertFalse(os.path.exists(os.path.join(self.T, "Musik", "2.mp3")))   # nur die übergebenen Titel
        self.s.mirror_set({"folder": self.T, "auto": False})
        self.s._mirror_touch([os.path.join(self.A, "2.mp3")])
        time.sleep(0.3)
        self.assertFalse(os.path.exists(os.path.join(self.T, "Musik", "2.mp3")))

    def test_cloud_folder_suggestion(self):
        import plugins
        od = os.path.join(self.dir, "OneDrive")
        os.makedirs(od, exist_ok=True)
        p = self.s.plugins.get("onedrive")
        mod = p.load()
        mod.run("settings", plugins.Context(p), [], {"account": "private", "folder": od})
        ov = self.s.mirror_overview()
        self.assertEqual(ov["suggest"], os.path.abspath(od))                # #415: Aufbau „Pfad“ im OneDrive-Ordner
        self.assertEqual(ov["suggests"]["name"], os.path.join(os.path.abspath(od), mirror.DEFAULT_SUB))
        self.assertEqual(ov["dests"][0]["dest"], os.path.join(os.path.abspath(od), *mirror.path_parts(self.A)))
        self.assertEqual(self.s.cfg.get("mirror"), None)                         # nur Vorschlag, nichts gespeichert
        # #413: OneDrive › „Kontoart …“ › „Spiegel-Ordner erstellen“
        r = mod.run("settings", plugins.Context(p, self.s), [], {"account": "private", "folder": od, "mirror": True})
        self.assertIn("Spiegel-Ordner:", r["message"])
        dest = os.path.join(os.path.abspath(od), *mirror.path_parts(self.A))
        self.assertTrue(os.path.isdir(dest))
        c = self.s.mirror_overview()["cfg"]
        self.assertEqual((c["folder"], c["layout"]), (os.path.abspath(od), "path"))
        r2 = self.s.mirror_cloud_folders(od, True)                              # nochmals: kein Fehler, nichts neu
        self.assertEqual(r2["created"], 0)
        self.assertTrue(self.s.start_mirror()["ok"])
        self.wait()
        self.assertTrue(os.path.isfile(os.path.join(dest, "1.mp3")))
        self.assertTrue(os.path.isfile(os.path.join(od, "TagStudio", "Spiegel", "index.json")))
        with self.assertRaises(ValueError):
            self.s.mirror_cloud_folders(os.path.join(self.A, "Sub"), True)      # Cloud-Ordner in der Bibliothek
        self.assertEqual([x["id"] for x in ov["cloud_folders"]], ["onedrive"])
        json.dumps(ov)                                                      # für die Oberfläche serialisierbar
