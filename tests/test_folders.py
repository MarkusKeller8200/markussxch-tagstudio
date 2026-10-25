"""Ordner-Rollen (#310, docs/KONZEPT-ORDNER.md): Modell, Übernahme der alten Einstellungen, Hinweise, Session."""
import os
import unittest

from test_tagger_tools import Base
import folders  # noqa: E402 – Pfad setzt test_tagger_tools


def J(*p):
    return os.path.normpath(os.path.join(*p))


class TestModel(Base):
    def test_empty_and_normalize(self):
        m = folders.normalize({"roles": {"export": {"mode": "app"}, "inbox": {"mode": "custom", "path": self.A},
                                         "archive": {"mode": "base", "sub": "../x/Archiv:"}},
                               "libraries": [{"id": "a", "name": "A", "mode": "custom", "path": self.A},
                                             {"id": "a", "name": "B", "mode": "custom", "path": self.B, "main": True}]})
        self.assertEqual(set(m["roles"]), set(folders.ROLE_IDS))
        self.assertEqual(m["roles"]["export"]["mode"], "base")             # „app“ nur für Sicherung/Snapshots
        self.assertEqual(m["roles"]["archive"]["sub"], "x/Archiv")          # kein „..“, keine verbotenen Zeichen
        self.assertEqual(m["roles"]["inbox"]["path"], os.path.normpath(self.A))
        self.assertNotEqual(m["libraries"][0]["id"], m["libraries"][1]["id"])
        self.assertEqual([x["main"] for x in m["libraries"]], [False, True])

    def test_role_resolve_base_custom_app(self):
        base = J(self.dir, "Musik")
        m = folders.set_base(folders.empty(), base)
        self.assertEqual(folders.resolve_role(m, "export"), J(base, "04_Export"))
        self.assertEqual(folders.resolve_role(m, "snapshots"), J(base, "99_Sicherung", "Snapshots"))
        m = folders.set_role(m, "export", "custom", self.B)
        self.assertEqual(folders.resolve_role(m, "export"), os.path.normpath(self.B))
        m = folders.set_role(m, "export", "base", "Ausgabe")
        self.assertEqual(folders.resolve_role(m, "export"), J(base, "Ausgabe"))
        m = folders.set_role(m, "snapshots", "app")
        import snapshots
        self.assertEqual(folders.resolve_role(m, "snapshots"), snapshots.default_dir())
        with self.assertRaises(ValueError):
            folders.set_role(m, "export", "app")
        with self.assertRaises(ValueError):
            folders.set_role(m, "export", "custom", "")
        with self.assertRaises(ValueError):
            folders.set_role(m, "nix", "base")
        m = folders.set_base(m, "")                                          # ohne Basisordner: Rolle leer
        self.assertEqual(folders.resolve_role(m, "inbox"), "")

    def test_same_dir_and_inside(self):
        self.assertTrue(folders.same_dir(self.A, self.A + os.sep))
        self.assertTrue(folders.inside(J(self.A, "x"), self.A))
        self.assertFalse(folders.inside(self.A, self.A))
        self.assertFalse(folders.inside(self.B, self.A))
        link = J(self.dir, "LinkA")
        try:
            os.symlink(self.A, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("keine Verknüpfungen möglich")
        self.assertTrue(folders.same_dir(link, self.A))                     # anderer Weg zum selben Ordner

    def test_libraries_add_update_remove(self):
        m = folders.set_base(folders.empty(), self.dir)
        m, lib = folders.lib_add(m, "Haupt", "custom", self.A)
        self.assertTrue(lib["main"])
        m, lib2 = folders.lib_add(m, "Extern", "custom", self.B, active=False)
        self.assertFalse(m["libraries"][1]["main"])
        with self.assertRaises(ValueError):                                   # gleicher Ordner zweimal
            folders.lib_add(m, "Doppelt", "custom", self.A + os.sep)
        with self.assertRaises(ValueError):                                   # Hauptbibliothek nicht inaktiv
            folders.lib_update(m, lib["id"], active=False)
        m = folders.lib_update(m, lib2["id"], main=True)
        self.assertTrue(m["libraries"][1]["main"] and m["libraries"][1]["active"])
        self.assertFalse(m["libraries"][0]["main"])
        m = folders.lib_remove(m, lib2["id"])
        self.assertTrue(m["libraries"][0]["main"])                          # verbleibende wird Hauptbibliothek
        cfg = {"folders": m}
        self.assertEqual(folders.main_library(cfg), os.path.normpath(self.A))
        self.assertEqual([x["path"] for x in folders.libraries(cfg, active=True)], [os.path.normpath(self.A)])

    def test_status_hints(self):
        m = folders.set_base(folders.empty(), self.dir)
        m, _ = folders.lib_add(m, "Haupt", "custom", self.A)
        m, _ = folders.lib_add(m, "Unter", "custom", J(self.A, "sub"))
        m = folders.set_role(m, "inbox", "custom", J(self.A, "neu"))
        st = folders.status(m)
        self.assertIn("fehlt – anlegen?", st["roles"]["export"]["hints"])
        self.assertTrue(any("liegt in Bibliothek" in h for h in st["roles"]["inbox"]["hints"]))
        unter = m["libraries"][1]["id"]
        self.assertTrue(any("ist in" in h for h in st["libraries"][unter]["hints"]))
        m2 = folders.set_base(folders.empty(), "")
        self.assertIn("kein Basisordner", folders.status(m2)["roles"]["archive"]["hints"])

    def test_structure_model_keeps_snapshots(self):
        base = J(self.dir, "TS")
        paths = {k: J(base, n) for k, n in (("new", "00_New"), ("library", "01_Library"), ("archive", "02_Archiv"),
                                             ("playlists", "03_Playlists"), ("export", "04_Export"),
                                             ("download", "90_Download"), ("work", "91_Work"), ("backup", "99_Sicherung"))}
        m = folders.set_role(folders.empty(), "snapshots", "custom", self.B)
        m2 = folders.structure_model(m, base, paths, keep_snapshots=True)
        self.assertEqual(folders.resolve_role(m2, "snapshots"), os.path.normpath(self.B))
        self.assertEqual(folders.resolve_role(m2, "backup"), J(base, "99_Sicherung", "Tags"))
        m3 = folders.structure_model(m, base, paths)
        self.assertEqual(folders.resolve_role(m3, "snapshots"), J(base, "99_Sicherung", "Snapshots"))
        self.assertEqual(folders.main_library({"folders": m3}), J(base, "01_Library"))


class TestMigrate(Base):
    def test_single_library_no_review(self):
        base = J(self.dir, "Musik")
        os.makedirs(J(base, "01_Library"))
        cfg = {"base_dir": base, "default_tagger": J(base, "01_Library") + os.sep,
               "archive_dir": J(base, "02_Archiv"), "backup_dir": J(self.dir, "Sich"),
               "help_scan_root": J(base, "01_Library")}
        wf = [{"id": "w1", "name": "DJ", "inbox": J(base, "00_New"), "work": "", "library": J(base, "01_Library"),
               "sources": [{"folder": J(base, "90_Download")}]}]
        m = folders.migrate(cfg, wf, "w1", [{"root": J(base, "01_Library")}])
        self.assertNotIn("review", m)
        self.assertEqual(len(m["libraries"]), 1)
        lib = m["libraries"][0]
        self.assertEqual((lib["mode"], lib["sub"], lib["main"], lib["snapshots"]), ("base", "01_Library", True, True))
        r = m["roles"]
        self.assertEqual(r["archive"]["mode"], "base")
        self.assertEqual(r["inbox"]["mode"], "base")
        self.assertEqual(r["downloads"]["mode"], "base")
        self.assertEqual(r["backup"], {"mode": "custom", "sub": "99_Sicherung/Tags", "path": J(self.dir, "Sich")})
        self.assertEqual(r["snapshots"]["mode"], "app")                     # Speicher blieb in den Programmdaten
        self.assertEqual(r["export"]["mode"], "base")                       # neu (O1)
        lg = folders.legacy(m)                                                 # gleiche Werte wie vorher
        self.assertEqual((lg["base_dir"], lg["archive_dir"], lg["backup_dir"], lg["snap_dir"]),
                         (base, J(base, "02_Archiv"), J(self.dir, "Sich"), ""))
        self.assertEqual(lg["default_tagger"], J(base, "01_Library"))

    def test_several_libraries_need_review(self):
        cfg = {"default_tagger": self.A, "help_scan_root": self.B}
        wf = [{"id": "w1", "name": "DJ", "library": self.A + os.sep}]
        m = folders.migrate(cfg, wf, "w1", [{"root": self.B}])
        self.assertEqual(len(m["libraries"]), 2)
        self.assertEqual(len(m["review"]), 2)
        self.assertEqual(m["review"][0]["found"], ["Tagger-Standardordner", "Workflow „DJ“"])
        self.assertEqual(m["review"][1]["found"], ["Snapshots", "Hilfe › Scan"])
        self.assertTrue(all(x["active"] for x in m["libraries"]))           # nichts still verworfen
        second = m["libraries"][1]["id"]
        m2 = folders.review_apply(m, {"items": [{"id": "main", "keep": True}, {"id": second, "keep": True, "active": False}],
                                      "main": "main"})
        self.assertNotIn("review", m2)
        self.assertEqual([x["active"] for x in m2["libraries"]], [True, False])
        m3 = folders.review_apply(m, {"items": [{"id": "main", "keep": False}], "main": second})
        self.assertEqual([x["id"] for x in m3["libraries"]], [second])
        self.assertTrue(m3["libraries"][0]["main"])
        with self.assertRaises(ValueError):
            folders.review_apply(m, {"items": [{"id": "main", "keep": False}, {"id": second, "keep": False}]})

    def test_no_base_all_custom(self):
        m = folders.migrate({}, [], None, [])
        self.assertEqual(m["libraries"], [])
        for rid in ("inbox", "archive", "playlists", "export", "downloads", "work"):
            self.assertEqual(folders.resolve_role(m, rid), "", rid)


class TestSession(Base):
    def session(self, cfg):
        from session import Session
        s = Session()
        s.cfg.clear()
        s.cfg.update(cfg)
        return s

    def test_migrates_once_and_follows(self):
        base = J(self.dir, "Musik")
        os.makedirs(J(base, "01_Library"))
        s = self.session({"base_dir": base, "default_tagger": J(base, "01_Library"),
                          "prep_workflows": [{"id": "w1", "name": "DJ", "inbox": J(base, "00_New"), "work": J(base, "91_Work"),
                                              "library": J(base, "01_Library"), "steps": [],
                                              "sources": [{"name": "BP", "folder": J(base, "90_Download", "Beatport")}]}],
                          "prep_current": "w1", "archive_dir": J(base, "02_Archiv")})
        d = s.folders_get()
        self.assertIn("folders", s.cfg)
        self.assertEqual(d["review"], [])
        self.assertEqual({r["id"]: r["mode"] for r in d["roles"]}["inbox"], "base")
        new = J(self.dir, "Neu")
        d = s.folders_set_base(new)                                          # Rollen im Modus Basis folgen
        self.assertEqual(s.cfg["base_dir"], new)
        self.assertEqual(s.cfg["archive_dir"], J(new, "02_Archiv"))
        self.assertEqual(s.cfg["default_tagger"], J(new, "01_Library"))
        w = s._prep_get("w1")
        self.assertEqual((w["inbox"], w["work"], w["library"]), (J(new, "00_New"), J(new, "91_Work"), J(new, "01_Library")))
        self.assertEqual(w["sources"][0]["folder"], J(new, "90_Download", "Beatport"))    # Unterordner bleibt
        self.assertFalse(os.path.exists(new))                                # nichts angelegt, nichts verschoben
        self.assertTrue(os.path.isdir(J(base, "01_Library")))

    def test_role_change_writes_old_keys_only_when_changed(self):
        s = self.session({"base_dir": self.dir, "default_tagger": self.A})
        s.folders_get()
        s.cfg["default_tagger"] = self.B                                     # Tagger-Standardordner anders gesetzt
        s.folders_set_role("export", "custom", self.B)
        self.assertEqual(s.cfg["default_tagger"], self.B)                    # unberührt (Hauptbibliothek gleich)
        s.folders_set_role("archive", "custom", J(self.dir, "Arch"))
        self.assertEqual(s.cfg["archive_dir"], J(self.dir, "Arch"))
        snaps = J(self.dir, "Snaps")
        s.folders_set_role("snapshots", "custom", snaps)
        self.assertEqual(s.snap_store.root, snaps)
        self.assertEqual(s.cfg["snap_dir"], snaps)
        s.folders_set_role("snapshots", "app")
        self.assertEqual(s.cfg["snap_dir"], "")

    def test_old_setters_update_roles(self):
        s = self.session({"base_dir": self.dir})
        s.folders_get()
        s.set_archive_dir(self.B)
        self.assertEqual(s._folders()["roles"]["archive"]["path"], os.path.normpath(self.B))
        s.set_archive_dir(J(self.dir, "02_Archiv"))
        self.assertEqual(s._folders()["roles"]["archive"]["mode"], "base")
        s.set_backup(None, self.A, None)
        self.assertEqual(folders.role(s.cfg, "backup"), os.path.normpath(self.A))
        s._snap_dir_set(J(self.dir, "S2"))
        self.assertEqual(folders.role(s.cfg, "snapshots"), J(self.dir, "S2"))

    def test_libraries_and_create(self):
        s = self.session({"base_dir": J(self.dir, "TS")})
        d = s.folders_get()
        self.assertEqual(d["libraries"][0]["path"], J(self.dir, "TS", "01_Library"))
        d = s.folders_lib_add("Extern", "custom", self.A)
        ext = d["libraries"][1]["id"]
        d = s.folders_lib_update(ext, {"main": True})
        self.assertEqual(s.cfg["default_tagger"], os.path.normpath(self.A))
        with self.assertRaises(ValueError):
            s.folders_lib_remove(ext)                                          # Hauptbibliothek nicht entfernen
        d = s.folders_create()                                                 # alles unter dem Basisordner
        self.assertTrue(os.path.isdir(J(self.dir, "TS", "04_Export")))
        self.assertTrue(os.path.isdir(J(self.dir, "TS", "01_Library")))
        self.assertFalse(any("Basisordner" in h for r in d["roles"] for h in r["hints"]))
        d = s.folders_lib_update(d["libraries"][0]["id"], {"main": True})
        d = s.folders_lib_remove(ext)
        self.assertEqual(len(d["libraries"]), 1)
        self.assertTrue(os.path.isdir(self.A))                                # Dateien bleiben

    def test_review_apply_session(self):
        s = self.session({"default_tagger": self.A, "help_scan_root": self.B})
        d = s.folders_get()
        self.assertEqual(len(d["review"]), 2)
        d = s.folders_review_apply({"items": [{"id": d["libraries"][1]["id"], "keep": False}], "main": "main"})
        self.assertEqual(d["review"], [])
        self.assertEqual(len(d["libraries"]), 1)


class TestLibraries(Base):
    """#311: mehrere Bibliotheken – Einlesen, Module, Tagger „Alle aktiven“, Snapshots je Bibliothek."""

    def session(self, cfg):
        from session import Session
        s = Session()
        s.cfg.clear()
        s.cfg.update(cfg)
        return s

    def test_scan_roots(self):
        m = folders.set_base(folders.empty(), self.dir)
        m, a = folders.lib_add(m, "A", "custom", self.A)
        m, sub = folders.lib_add(m, "A-Unter", "custom", J(self.A, "sub"))
        os.makedirs(J(self.A, "sub"))
        m, b = folders.lib_add(m, "B", "custom", self.B, active=False)
        m, gone = folders.lib_add(m, "Weg", "custom", J(self.dir, "fehlt"))
        roots, skipped = folders.scan_roots(m)
        self.assertEqual([r["name"] for r in roots], ["A"])                  # Unterordner nur einmal, B inaktiv
        self.assertEqual([(x["name"], x["why"]) for x in skipped], [("Weg", "fehlt")])
        if os.name == "nt":
            return
        m, _ = folders.lib_add(m, "X", "custom", "/Volumes/TagStudioTestNichtDa/Musik")
        _r, skipped = folders.scan_roots(m)
        self.assertIn(("X", "nicht erreichbar"), [(x["name"], x["why"]) for x in skipped])

    def test_modules_use_active_libraries(self):
        s = self.session({"default_tagger": self.A, "base_dir": self.dir})
        s.folders_get()
        d = s.folders_lib_add("B", "custom", self.B, False)
        self.assertEqual(s._pl_lib_roots(), [os.path.normpath(self.A)])        # inaktiv: nicht abgeglichen
        info = s._lib_info()
        self.assertEqual([x["name"] for x in info["libs"]], ["Haupt"])
        s.folders_lib_update(d["libraries"][1]["id"], {"active": True})
        self.assertEqual(len(s._pl_lib_roots()), 2)
        self.assertEqual(s._disc_library(), "Haupt · B")
        self.assertEqual(len(s._disc_lib_files()), 3)                         # 2 Titel in A, 1 in B
        self.assertEqual([r["label"] for r in s._help_roots()][:2], ["Bibliothek Haupt", "Bibliothek B"])
        self.assertEqual(s._prep_get()["library"], os.path.normpath(self.A))   # Übernehmen → Hauptbibliothek
        st = s.purch_state()
        self.assertEqual([x["name"] for x in st["libs"]], ["Haupt", "B"])

    def test_tagger_all_libraries(self):
        import time
        s = self.session({"default_tagger": self.A, "base_dir": self.dir})
        s.folders_get()
        s.folders_lib_add("B", "custom", self.B, True)
        t = s.tagger_settings()
        self.assertEqual([x["name"] for x in t["libraries"]], ["Haupt", "B"])
        r = s.start_tag_load(folders.ALL_LIBS)
        self.assertTrue(r.get("ok", True), r)
        for _ in range(500):
            if s.task_status().get("done"):
                break
            time.sleep(0.02)
        self.assertEqual(len(s.tag_files), 3)
        self.assertEqual(s.tag_rows()["root"], folders.ALL_LIBS)
        s.folders_lib_update(s._folders()["libraries"][1]["id"], {"active": False})
        s.folders_lib_update(s._folders()["libraries"][0]["id"], {"name": "Haupt"})
        roots = s._lib_roots()["roots"]
        self.assertEqual(len(roots), 1)

    def test_snapshots_per_library(self):
        s = self.session({"default_tagger": self.A, "snap_dir": J(self.dir, "Snaps")})
        s.folders_get()
        lid = s._folders()["libraries"][0]["id"]
        r = s.folders_lib_update(lid, {"snapshots": True})
        self.assertEqual(r["snap_note"], "Snapshots eingeschaltet.")
        libs = s.snap_store.libraries()
        self.assertEqual(len(libs), 1)
        self.assertTrue(libs[0].get("auto", True))
        r = s.folders_lib_update(lid, {"snapshots": False})
        self.assertFalse(s.snap_store.libraries()[0]["auto"])                  # nicht gelöscht, nur nicht mehr täglich
        self.assertIn("vorhandene bleiben", r["snap_note"])


class TestExport(Base):
    def test_export_dir_and_save_dialog(self):
        """#312: Exporte starten im Export-Ordner; fehlt er, wird er angelegt; ohne Rolle: Benutzerordner."""
        import sys
        import types
        from unittest import mock
        import tagstudio_web
        api = tagstudio_web.Api()
        s = api._s
        s.cfg.clear()
        s.cfg.update({"base_dir": J(self.dir, "TS")})
        self.assertEqual(s.export_dir(), J(self.dir, "TS", "04_Export"))
        self.assertTrue(os.path.isdir(J(self.dir, "TS", "04_Export")))
        seen = {}

        class Win:
            def create_file_dialog(self, kind, directory="", save_filename="", file_types=()):
                seen["dir"], seen["name"] = directory, save_filename
                return [os.path.join(directory, save_filename)]
        api._window = Win()
        with mock.patch.dict(sys.modules, {"webview": types.SimpleNamespace(SAVE_DIALOG=30, OPEN_DIALOG=10, FOLDER_DIALOG=20)}):
            p = api.save_dialog("Liste.csv")
            self.assertEqual(seen["dir"], J(self.dir, "TS", "04_Export"))
            self.assertEqual(p, J(self.dir, "TS", "04_Export", "Liste.csv"))
            s.folders_set_role("export", "custom", self.B)
            api.save_dialog("x.csv")
            self.assertEqual(seen["dir"], os.path.normpath(self.B))
            s.folders_set_base("")
            s.folders_set_role("export", "base", "04_Export")                    # ohne Basisordner: keine Rolle
            self.assertEqual(s.export_dir(), "")
            api.save_dialog("x.csv")
            self.assertEqual(seen["dir"], os.path.expanduser("~"))
            r = api.prep_export_file(s._prep_get()["id"])
            self.assertTrue(r["ok"] and r["path"].endswith(".json"))
            with open(r["path"], encoding="utf-8") as fh:
                self.assertIn("tagstudio_workflow", fh.read())


if __name__ == "__main__":
    unittest.main()
