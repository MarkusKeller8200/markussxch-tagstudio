"""Cloud-Sync-Ordner (#315): erkennen, relative Pfade, Nur-online-Dateien, Konfliktkopien, Hinweise."""
import json
import os
import shutil
import types
import unittest
from unittest import mock

from test_tagger_tools import Base
import cloud  # noqa: E402 – Pfad setzt test_tagger_tools
import folders  # noqa: E402


def J(*p):
    return os.path.normpath(os.path.join(*p))


class CloudBase(Base):
    def setUp(self):
        super().setUp()
        self._env2 = {k: os.environ.get(k) for k in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial", "APPDATA",
                                                     "LOCALAPPDATA")}
        for k in self._env2:
            os.environ.pop(k, None)
        cloud._CACHE["t"] = 0.0
        self._lo = cloud.LOAD_ONLINE
        cloud.LOAD_ONLINE = False

    def tearDown(self):
        for k, v in self._env2.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        cloud._CACHE["t"] = 0.0
        cloud.LOAD_ONLINE = self._lo
        super().tearDown()

    def onedrive(self, name="OneDrive"):
        p = J(self.dir, name)
        os.makedirs(p, exist_ok=True)
        os.environ["OneDrive"] = p
        cloud._CACHE["t"] = 0.0
        return p


class TestDetect(CloudBase):
    def test_detect_providers(self):
        od = self.onedrive()
        cs = J(self.dir, "Library", "CloudStorage")
        os.makedirs(J(cs, "GoogleDrive-markus@example.org", "My Drive"))
        os.makedirs(J(cs, "OneDrive-Firma AG"))
        dbx = J(self.dir, "Dropbox")
        os.makedirs(dbx)
        os.makedirs(J(self.dir, ".dropbox"))
        with open(J(self.dir, ".dropbox", "info.json"), "w", encoding="utf-8") as fh:
            json.dump({"personal": {"path": dbx}}, fh)
        got = {(r["provider"], r["path"]) for r in cloud.detect(refresh=True)}
        self.assertIn(("onedrive", od), got)
        self.assertIn(("gdrive", J(cs, "GoogleDrive-markus@example.org", "My Drive")), got)
        self.assertIn(("onedrive_business", J(cs, "OneDrive-Firma AG")), got)
        self.assertIn(("dropbox", dbx), got)

    def test_locate_and_rebuild(self):
        od = self.onedrive()
        os.makedirs(J(od, "Musik", "Playlists"))
        loc = cloud.locate(J(od, "Musik", "Playlists"))
        self.assertEqual((loc["provider"], loc["label"], loc["rel"]), ("onedrive", "OneDrive", "Musik/Playlists"))
        self.assertIsNone(cloud.locate(self.A))
        od2 = J(self.dir, "Anderer Rechner", "OneDrive")                     # zweiter Rechner: anderer Pfad
        shutil.move(od, od2)
        os.environ["OneDrive"] = od2
        cloud._CACHE["t"] = 0.0
        self.assertEqual(cloud.rebuild({"provider": "onedrive", "rel": "Musik/Playlists"}), J(od2, "Musik", "Playlists"))
        self.assertEqual(cloud.rebuild({"provider": "onedrive", "rel": "../../etc"}), "")
        self.assertEqual(cloud.rebuild({"provider": "nix"}), "")

    def test_conflicts_and_online_only(self):
        self.assertTrue(cloud.is_conflict("Titel (Markus's conflicted copy 2026-10-25).mp3", "dropbox"))
        self.assertTrue(cloud.is_conflict("Titel (Konfliktkopie von Laptop 2026-10-25).mp3", "dropbox"))
        self.assertTrue(cloud.is_conflict("Titel-DESKTOP-4F2K9QZ.mp3", "onedrive"))
        self.assertTrue(cloud.is_conflict("Titel (Konflikt).mp3", "gdrive"))
        self.assertFalse(cloud.is_conflict("Titel (Extended Mix).mp3", "onedrive"))
        self.assertFalse(cloud.is_conflict("Titel-DESKTOP-4F2K9QZ.mp3", "dropbox"))
        st = types.SimpleNamespace(st_file_attributes=0x400000, st_flags=0)
        self.assertTrue(cloud.online_only("x", st))
        self.assertTrue(cloud.online_only("x", types.SimpleNamespace(st_file_attributes=0, st_flags=0x40000000)))
        self.assertFalse(cloud.online_only("x", types.SimpleNamespace(st_file_attributes=0x20, st_flags=0)))
        self.assertFalse(cloud.online_only(J(self.A, "1.mp3")))

    def test_load_skips_online_only(self):
        """Einlesen im Sync-Ordner: Nur-online-Dateien übersprungen (ausser eingeschaltet), Konfliktkopien gemeldet."""
        import core
        od = self.onedrive()
        lib = J(od, "Musik")
        shutil.copytree(self.A, lib)
        shutil.copy(J(lib, "1.mp3"), J(lib, "1-DESKTOP-4F2K9QZ.mp3"))
        real = cloud.online_only
        fake = lambda p, st=None: os.path.basename(p) == "2.mp3" or real(p, st)  # noqa: E731
        with mock.patch.object(cloud, "online_only", fake):
            stats = {}
            files, _e = core.load_files(lib, True, stats=stats)
            self.assertEqual(sorted(os.path.basename(f.path) for f in files), ["1-DESKTOP-4F2K9QZ.mp3", "1.mp3"])
            self.assertEqual([os.path.basename(p) for p in stats["cloud"]["online"]], ["2.mp3"])
            self.assertEqual([os.path.basename(p) for p in stats["cloud"]["conflicts"]], ["1-DESKTOP-4F2K9QZ.mp3"])
            cloud.LOAD_ONLINE = True
            files, _e = core.load_files(lib, True)
            self.assertEqual(len(files), 3)
        stats = {}
        core.load_files(self.A, True, stats=stats)                           # ausserhalb: unverändert
        self.assertEqual(stats["cloud"]["provider"], "")


class TestFoldersCloud(CloudBase):
    def session(self, cfg):
        from session import Session
        s = Session()
        s.cfg.clear()
        s.cfg.update(cfg)
        return s

    def test_roles_in_cloud(self):
        od = self.onedrive()
        os.makedirs(J(od, "TS", "Export"))
        s = self.session({"base_dir": J(self.dir, "TS")})
        s.folders_get()
        d = s.folders_set_role("export", "custom", J(od, "TS", "Export"))
        exp = next(r for r in d["roles"] if r["id"] == "export")
        self.assertEqual(exp["cloud"], "OneDrive")
        self.assertEqual(s._folders()["roles"]["export"]["cloud"], {"provider": "onedrive", "rel": "TS/Export"})
        self.assertEqual(d["cloud"]["roots"][0]["label"], "OneDrive")
        d = s.folders_set_role("snapshots", "custom", J(od, "Snaps"))         # Hinweis: nicht in die Cloud
        snap = next(r for r in d["roles"] if r["id"] == "snapshots")
        self.assertTrue(any("nicht empfohlen" in h for h in snap["hints"]))
        self.assertFalse(any("nicht empfohlen" in h for h in exp["hints"]))
        # zweiter Rechner: OneDrive liegt anders → Rolle zeigt auf den gleichen Ordner im neuen Sync-Ordner
        od2 = J(self.dir, "Neu", "OneDrive")
        shutil.move(od, od2)
        os.environ["OneDrive"] = od2
        cloud._CACHE["t"] = 0.0
        self.assertEqual(folders.role(s.cfg, "export"), J(od2, "TS", "Export"))

    def test_cloud_online_setting(self):
        s = self.session({})
        d = s.folders_cloud_online(True)
        self.assertTrue(d["cloud"]["load_online"] and cloud.LOAD_ONLINE)
        s.folders_cloud_online(False)
        self.assertFalse(cloud.LOAD_ONLINE)

    def test_cloud_result(self):
        from session import Session
        r = Session._cloud_result([{"cloud": {"provider": "OneDrive", "online": ["a", "b"], "conflicts": ["c"]}}, {}])
        self.assertEqual(r["cloud"]["online"], 2)
        self.assertEqual(r["cloud"]["conflicts"], ["c"])
        self.assertEqual(Session._cloud_result([{}]), {})


if __name__ == "__main__":
    unittest.main()
