"""#402: Sicherung der Programmdaten – Inhalt ohne Zugangsdaten, atomar, Prüfsummen, Vorschau, Wiederherstellen mit
vorheriger Sicherung und Pfad-Umschreibung, ältere Sicherungen nur nach Rückfrage, automatisch täglich/beim Beenden."""
import json
import os
import time
import zipfile

from test_tagger_tools import Base

import appbackup
import core
import paths


class TestAppBackup(Base):
    def setUp(self):
        super().setUp()
        from session import Session
        self.s = Session()
        self.s.folders_lib_add("Musik", "custom", self.A)
        self.T = os.path.join(self.dir, "OneDrive", "TagStudio", "Sicherungen")
        core.save_config({"web_theme": "dark", "spotify_token": "GEHEIM"})
        self.s.cfg.update(core.load_config())
        os.makedirs(paths.sub("Entdecken"), exist_ok=True)
        with open(os.path.join(paths.sub("Entdecken"), "entdecken.json"), "w", encoding="utf-8") as fh:
            json.dump({"items": {"a": {"src": "deezer", "title": "A"}, "b": {"src": "sonovault", "title": "B"}}}, fh)
        os.makedirs(paths.sub("Vorbereiten"), exist_ok=True)
        with open(os.path.join(paths.sub("Vorbereiten"), "w1.json"), "w", encoding="utf-8") as fh:
            fh.write('{"tracks": {}}')
        os.makedirs(paths.sub("Plugin-Daten", "spotify"), exist_ok=True)
        with open(os.path.join(paths.sub("Plugin-Daten", "spotify"), "keys.bin"), "wb") as fh:
            fh.write(b"SECRET")
        self.pl = self.s._pls().create("Set", items=[{"path": os.path.join(self.A, "1.mp3"), "artist": "Mara", "title": "Gold"}])

    def wait(self):
        for _ in range(200):
            if not self.s.task.get("running"):
                return self.s.task
            time.sleep(0.05)
        self.fail("Auftrag läuft noch")

    def test_create_content(self):
        self.assertFalse(self.s.start_appbackup()["ok"])                 # ohne Ordner
        self.s.appbackup_set({"folder": self.T, "keep": 3})
        self.assertTrue(self.s.start_appbackup()["ok"])
        t = self.wait()
        self.assertIsNone(t["error"], t)
        lst = appbackup.listing(self.T)
        self.assertEqual(len(lst), 1)
        self.assertTrue(lst[0]["name"].startswith(appbackup.PREFIX))
        self.assertFalse([n for n in os.listdir(self.T) if n.endswith(".part")])
        with zipfile.ZipFile(lst[0]["path"]) as z:
            names = z.namelist()
            blob = b"".join(z.read(n) for n in names)
        self.assertIn("manifest.json", names)
        self.assertIn("settings/einstellungen.json", names)
        self.assertIn("discover/entdecken.json", names)
        self.assertIn("prepare/w1.json", names)
        self.assertTrue(any(n.startswith("playlists/") for n in names))
        self.assertNotIn(b"GEHEIM", blob)                                 # Zugangsdaten nie
        self.assertNotIn(b"SECRET", blob)
        self.assertNotIn(b"sonovault", blob)                              # SonoVault-Einträge nie
        man, files = appbackup.read(lst[0]["path"])
        self.assertEqual(man["libraries"][-1]["path"], self.A)

    def test_surplus_only_on_request(self):
        self.s.appbackup_set({"folder": self.T, "keep": 1})
        for _ in range(2):
            self.s.start_appbackup()
            r = self.wait()["result"]
            time.sleep(1.1)
        self.assertEqual(r["ab_surplus"], 1)
        self.assertEqual(len(appbackup.listing(self.T)), 2)                # nichts automatisch gelöscht
        sp = self.s.appbackup_surplus()["files"]
        self.assertEqual(len(sp), 1)
        bad = self.s.appbackup_delete([os.path.join(self.A, "1.mp3")])   # fremde Datei: abgelehnt
        self.assertEqual((bad["deleted"], len(bad["errors"])), (0, 1))
        self.assertTrue(os.path.exists(os.path.join(self.A, "1.mp3")))
        self.assertEqual(self.s.appbackup_delete([sp[0]["path"]])["deleted"], 1)
        self.assertEqual(len(appbackup.listing(self.T)), 1)

    def test_restore_with_remap(self):
        self.s.appbackup_set({"folder": self.T})
        self.s.start_appbackup()
        self.wait()
        src = appbackup.listing(self.T)[0]["path"]
        # „anderer Rechner“: Bibliothek liegt jetzt woanders (gleiche ID) – Manifest mit Windows-Pfad nachbilden
        man, files = appbackup.read(src)
        lib = [x for x in man["libraries"] if x["name"] == "Musik"][0]
        old_root = "S:\\Musik"
        lib["path"] = old_root
        fake = os.path.join(self.dir, "fremd.zip")
        pl_name = [n for n in files if n.startswith("playlists/") and self.pl["id"] in n][0]
        pl = json.loads(files[pl_name])
        for it in pl["items"]:
            it["path"] = old_root + "\\" + os.path.basename(it["path"])
        files[pl_name] = json.dumps(pl).encode()
        man["host"] = "ANDERER"
        man["files"] = {k: {"sha256": appbackup._sha(v), "size": len(v)} for k, v in files.items()}
        with zipfile.ZipFile(fake, "w") as z:
            z.writestr("manifest.json", json.dumps(man))
            for k, v in files.items():
                z.writestr(k, v)
        # hier ändern, dann wiederherstellen
        self.s._pls().update(self.pl["id"], name="Neu")
        pv = self.s.appbackup_preview(fake)
        self.assertTrue(pv["foreign"])
        self.assertEqual(pv["remap"], [{"from": "S:/Musik", "to": self.A}])
        parts = {p["id"]: p for p in pv["parts"]}
        self.assertGreaterEqual(parts["playlists"]["changed"], 1)
        self.assertIn("design", [g["id"] for g in parts["settings"]["settings"]["groups"]])
        n_before = len(appbackup.listing(self.T))
        self.assertTrue(self.s.start_appbackup_restore(fake, ["playlists", "settings"], ["design"])["ok"])
        t = self.wait()
        self.assertIsNone(t["error"], t)
        self.assertEqual(len(appbackup.listing(self.T)), n_before + 1)       # vorher gesichert
        self.assertTrue(any("vor-Wiederherstellen" in x["name"] for x in appbackup.listing(self.T)))
        got = self.s._pls().get(self.pl["id"])
        self.assertEqual(got["name"], "Set")
        self.assertEqual(got["items"][0]["path"], os.path.join(self.A, "1.mp3"))   # Pfad umgeschrieben

    def test_bad_files(self):
        bad = os.path.join(self.dir, "x.zip")
        with zipfile.ZipFile(bad, "w") as z:
            z.writestr("manifest.json", json.dumps({"format": "anders"}))
        self.assertFalse(self.s.start_appbackup_restore(bad)["ok"])
        self.s.appbackup_set({"folder": self.T})
        self.s.start_appbackup()
        self.wait()
        good = appbackup.listing(self.T)[0]["path"]
        man, files = appbackup.read(good)
        k = next(iter(files))
        tampered = os.path.join(self.dir, "t.zip")
        with zipfile.ZipFile(tampered, "w") as z:
            z.writestr("manifest.json", json.dumps(man))
            for n, v in files.items():
                z.writestr(n, v + b" " if n == k else v)
        with self.assertRaises(ValueError):
            appbackup.read(tampered)

    def test_auto(self):
        self.s.appbackup_set({"folder": self.T, "auto": "exit"})
        self.assertTrue(self.s.appbackup_exit())
        self.assertEqual(len(appbackup.listing(self.T)), 1)
        self.assertFalse(self.s.appbackup_daily())                        # nicht „täglich“
        self.s.appbackup_set({"folder": self.T, "auto": "daily"})
        self.assertFalse(self.s.appbackup_daily())                        # letzte Sicherung ist frisch
        self.s.cfg["app_backup_last"] = {"at": "2020-01-01T00:00:00"}
        self.assertTrue(self.s.appbackup_daily())
        for _ in range(100):
            if len(appbackup.listing(self.T)) == 2:
                break
            time.sleep(0.05)
        self.assertEqual(len(appbackup.listing(self.T)), 2)

    def test_mirror_estimate_counts_backups(self):
        self.s.appbackup_set({"folder": self.T, "keep": 5})
        self.assertGreater(self.s._appbackup_bytes(), 0)
