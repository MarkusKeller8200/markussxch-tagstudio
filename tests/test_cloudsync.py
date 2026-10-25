"""#317: Abgleich über die Dienste (Cloud Weg 2) – beide Richtungen, Konflikte nachfragen, Löschen nur nach Rückfrage,
keine Zugangsdaten, SonoVault-Einträge nie hochladen. Gegenstelle im Speicher (kein Netz)."""
import json
import os
import time

from test_tagger_tools import Base

import cloudsync


class MemProvider:
    """Ordner im Dienst als dict {Pfad: (Revision, Daten)}."""

    def __init__(self):
        self.files, self.n, self.calls = {}, 0, []

    def list(self, folder):
        pre = folder.rstrip("/") + "/"
        return {k[len(pre):]: {"rev": r, "size": len(d)} for k, (r, d) in self.files.items() if k.startswith(pre)}

    def get(self, path):
        self.calls.append(("get", path))
        return self.files[path][1]

    def put(self, path, data):
        self.calls.append(("put", path))
        self.n += 1
        self.files[path] = (f"r{self.n}", data)
        return f"r{self.n}"

    def delete(self, path):
        self.calls.append(("delete", path))
        del self.files[path]


SYNC = {"provider": "mem", "remote": "TagStudio/Playlists", "mode": "both"}


class TestEngine(Base):
    def part(self, name="a"):
        root = os.path.join(self.dir, name)
        os.makedirs(root, exist_ok=True)
        return cloudsync.FolderPart("playlists", "Playlists", root, exts=cloudsync.ROLE_EXTS["playlists"])

    def write(self, part, rel, text):
        p = os.path.join(part.root, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)

    def read(self, part, rel):
        with open(os.path.join(part.root, *rel.split("/")), encoding="utf-8") as fh:
            return fh.read()

    def test_two_machines_both_directions(self):
        prov = MemProvider()
        a, b = self.part("a"), self.part("b")
        self.write(a, "Set 1.m3u8", "#EXTM3U\nA\n")
        self.write(a, "DJ-Sets/Set 2.m3u8", "#EXTM3U\nB\n")
        self.write(a, "notiz.mp3", "kein Abgleich")                    # falsche Endung
        r = cloudsync.run(a, prov, SYNC)
        self.assertEqual(r["up"], 2)
        self.assertNotIn("TagStudio/Playlists/notiz.mp3", prov.files)
        # zweiter Rechner (eigener Zustand): lädt herunter
        sb = {}
        r = cloudsync.run(b, prov, SYNC, state=sb)
        self.assertEqual((r["down"], r["conflicts"]), (2, []))
        self.assertEqual(self.read(b, "DJ-Sets/Set 2.m3u8"), "#EXTM3U\nB\n")
        self.assertFalse([f for f in os.listdir(b.root) if f.endswith(".part")])     # atomar
        # B ändert, A holt
        self.write(b, "Set 1.m3u8", "#EXTM3U\nA2\n")
        self.assertEqual(cloudsync.run(b, prov, SYNC, state=sb)["up"], 1)
        self.assertEqual(cloudsync.run(a, prov, SYNC)["down"], 1)
        self.assertEqual(self.read(a, "Set 1.m3u8"), "#EXTM3U\nA2\n")
        # nichts geändert → nichts zu tun
        r = cloudsync.run(a, prov, SYNC)
        self.assertEqual((r["up"], r["down"]), (0, 0))

    def test_conflict_asks_never_overwrites(self):
        prov = MemProvider()
        a, b = self.part("a"), self.part("b")
        self.write(a, "Set.m3u8", "v1")
        cloudsync.run(a, prov, SYNC)
        sb = {}
        cloudsync.run(b, prov, SYNC, state=sb)
        self.write(a, "Set.m3u8", "hier")
        self.write(b, "Set.m3u8", "dort")
        cloudsync.run(b, prov, SYNC, state=sb)
        r = cloudsync.run(a, prov, SYNC)
        self.assertEqual(len(r["conflicts"]), 1)
        c = r["conflicts"][0]
        self.assertEqual((c["local"], c["remote"]), (b"hier", b"dort"))
        self.assertEqual(self.read(a, "Set.m3u8"), "hier")                       # nichts überschrieben
        self.assertEqual(prov.files["TagStudio/Playlists/Set.m3u8"][1], b"dort")
        # beide behalten
        cloudsync.resolve(a, prov, SYNC, "Set.m3u8", "both", c["remote"], c["rev"])
        self.assertEqual(self.read(a, "Set (Cloud).m3u8"), "dort")
        self.assertEqual(prov.files["TagStudio/Playlists/Set.m3u8"][1], b"hier")
        # neuer Konflikt → aus dem Dienst übernehmen
        self.write(a, "Set.m3u8", "hier2")
        prov.put("TagStudio/Playlists/Set.m3u8", b"dort2")
        c = cloudsync.run(a, prov, SYNC)["conflicts"]
        c = [x for x in c if x["rel"] == "Set.m3u8"][0]
        cloudsync.resolve(a, prov, SYNC, "Set.m3u8", "there", c["remote"], c["rev"])
        self.assertEqual(self.read(a, "Set.m3u8"), "dort2")
        self.assertEqual(cloudsync.run(a, prov, SYNC)["conflicts"], [])

    def test_deletions_only_reported(self):
        prov = MemProvider()
        a = self.part("a")
        self.write(a, "X.m3u8", "x")
        self.write(a, "Y.m3u8", "y")
        cloudsync.run(a, prov, SYNC)
        del prov.files["TagStudio/Playlists/X.m3u8"]                           # im Dienst gelöscht
        os.remove(os.path.join(a.root, "Y.m3u8"))                               # hier gelöscht
        r = cloudsync.run(a, prov, SYNC)
        self.assertEqual((r["gone_remote"], r["gone_local"]), (["X.m3u8"], ["Y.m3u8"]))
        self.assertTrue(os.path.exists(os.path.join(a.root, "X.m3u8")))         # nicht automatisch gelöscht
        self.assertIn("TagStudio/Playlists/Y.m3u8", prov.files)
        self.assertNotIn("delete", [c[0] for c in prov.calls])
        cloudsync.delete(a, prov, SYNC, "X.m3u8", "local")                      # nach Rückfrage
        self.assertFalse(os.path.exists(os.path.join(a.root, "X.m3u8")))
        cloudsync.forget("playlists", SYNC, "Y.m3u8")                           # nicht löschen → wieder holen
        self.assertEqual(cloudsync.run(a, prov, SYNC)["down"], 1)

    def test_foreign_remote_files_untouched_and_paths(self):
        prov = MemProvider()
        a = self.part("a")
        prov.put("TagStudio/Playlists/fremd.exe", b"x")
        r = cloudsync.run(a, prov, SYNC)
        self.assertEqual(r["down"], 0)
        self.assertFalse(os.path.exists(os.path.join(a.root, "fremd.exe")))
        with self.assertRaises(ValueError):
            cloudsync.clean_rel("../boese.m3u8")
        with self.assertRaises(ValueError):
            a.write("../boese.m3u8", b"x")
        self.assertIsNone(cloudsync.clean_sync({"provider": ""}))
        self.assertEqual(cloudsync.clean_sync({"provider": "onedrive", "remote": "/A/B/", "mode": "x"}),
                         {"provider": "onedrive", "remote": "A/B", "mode": "both"})

    def test_modes_up_and_down(self):
        prov = MemProvider()
        a = self.part("a")
        self.write(a, "U.m3u8", "u")
        prov.put("TagStudio/Playlists/D.m3u8", b"d")
        r = cloudsync.run(a, prov, dict(SYNC, mode="up"))
        self.assertEqual((r["up"], r["down"]), (1, 0))
        b = self.part("b")
        r = cloudsync.run(b, prov, dict(SYNC, mode="down"), state={})
        self.assertEqual((r["up"], r["down"]), (0, 2))

    def test_discover_without_sonovault_and_settings_without_secrets(self):
        import core
        import discover
        with discover.LOCK:
            d = discover.load()
            d["items"] = {"deezer:1": {"key": "deezer:1", "src": "deezer", "title": "A", "first": time.strftime("%Y-%m-%dT%H:%M:%S")},
                          "sonovault:rel:2": {"key": "sonovault:rel:2", "src": "sonovault", "title": "B",
                                              "first": time.strftime("%Y-%m-%dT%H:%M:%S")}}
            d["follow"]["sources"] = ["deezer", "sonovault"]
            discover.save(d)
        part = cloudsync.app_part("discover")
        data = part.files()["entdecken.json"]
        self.assertNotIn(b"sonovault", data)
        prov = MemProvider()
        sync = {"provider": "mem", "remote": "TagStudio/Programmdaten/Entdecken", "mode": "both"}
        cloudsync.run(part, prov, sync)
        # aus dem Dienst übernehmen: hiesige SonoVault-Einträge bleiben
        remote = json.loads(prov.files["TagStudio/Programmdaten/Entdecken/entdecken.json"][1])
        remote["items"]["deezer:3"] = {"key": "deezer:3", "src": "deezer", "title": "C", "first": time.strftime("%Y-%m-%dT%H:%M:%S")}
        prov.put("TagStudio/Programmdaten/Entdecken/entdecken.json", json.dumps(remote).encode())
        self.assertEqual(cloudsync.run(part, prov, sync)["down"], 1)
        items = discover.load()["items"]
        self.assertIn("deezer:3", items)
        self.assertIn("sonovault:rel:2", items)
        # Einstellungen: ohne Zugangsdaten und ohne Pfade
        core.save_config({"beatport_token": "geheim", "theme": "light", "base_dir": "C:/Musik", "web_theme": "light"})
        s = cloudsync.app_part("settings").files()["einstellungen.json"].decode()
        self.assertNotIn("geheim", s)
        self.assertNotIn("C:/Musik", s)
        self.assertIn("web_theme", s)


class TestSessionCloud(Base):
    def setUp(self):
        super().setUp()
        from session import Session
        self.s = Session()
        self.prov = MemProvider()
        self.s._cloud_plugins = lambda: {"mem": object()}
        self.s._cloud_provider = lambda pid, cancel=None, progress=None: self.prov
        self.s._cloud_provider_info = lambda: [{"id": "mem", "name": "Mem", "ready": True, "why": ""}]
        self.s.folders_set_base(os.path.join(self.dir, "Musik"), create=True)
        self.s.folders_create()

    def wait(self):
        for _ in range(500):
            st = self.s.task_status()
            if st.get("done"):
                return st
            time.sleep(0.02)
        self.fail("hängt")

    def test_settings_run_conflicts_and_gone(self):
        ov = self.s.cloud_sync_overview()
        self.assertEqual([r["id"] for r in ov["rows"]], ["playlists", "export", "pl_store", "purchases", "discover", "settings"])
        self.assertIsNone(ov["rows"][0]["sync"])
        self.assertFalse(self.s.start_cloud_sync()["ok"])                    # nichts eingerichtet
        with self.assertRaises(ValueError):
            self.s.cloud_sync_set("role", "inbox", {"provider": "mem"})        # Musik nie über die Dienste
        ov = self.s.cloud_sync_set("role", "playlists", {"provider": "mem", "remote": "TagStudio/Playlists"})
        self.assertEqual(ov["rows"][0]["sync"]["provider"], "mem")
        self.assertEqual(self.s.cfg["folders"]["roles"]["playlists"]["sync"]["mode"], "both")
        import folders
        pl = folders.resolve_role(self.s._folders(), "playlists")
        with open(os.path.join(pl, "A.m3u8"), "w", encoding="utf-8") as fh:
            fh.write("#EXTM3U\n")
        self.s.cloud_sync_set("app", "settings", {"provider": "mem"})
        self.assertTrue(self.s.start_cloud_sync()["ok"])
        st = self.wait()
        self.assertIsNone(st["error"], st)
        self.assertIn("TagStudio/Playlists/A.m3u8", self.prov.files)
        self.assertIn("TagStudio/Programmdaten/Einstellungen/einstellungen.json", self.prov.files)
        # Konflikt
        with open(os.path.join(pl, "A.m3u8"), "w", encoding="utf-8") as fh:
            fh.write("hier")
        self.prov.put("TagStudio/Playlists/A.m3u8", b"dort")
        self.s.start_cloud_sync()
        st = self.wait()
        self.assertEqual(st["result"]["conflicts"], 1)
        pend = self.s.cloud_pending()
        c = pend["conflicts"][0]
        self.assertEqual((c["local"], c["remote"]), ("hier", "dort"))
        self.assertEqual(self.s.cloud_resolve(c["id"], "here")["conflicts"], [])
        self.assertEqual(self.prov.files["TagStudio/Playlists/A.m3u8"][1], b"hier")
        # im Dienst gelöscht → Rückfrage, „nicht löschen“ lädt wieder hoch
        del self.prov.files["TagStudio/Playlists/A.m3u8"]
        self.s.start_cloud_sync()
        self.assertEqual(self.wait()["result"]["gone"], 1)
        g = self.s.cloud_pending()["gone"][0]
        self.assertEqual((g["where"], g["why"]), ("local", "im Dienst gelöscht"))
        self.assertTrue(os.path.exists(os.path.join(pl, "A.m3u8")))
        self.s.cloud_gone(g["id"], "keep")
        self.s.start_cloud_sync()
        self.wait()
        self.assertIn("TagStudio/Playlists/A.m3u8", self.prov.files)
        # aus
        ov = self.s.cloud_sync_set("role", "playlists", None)
        self.assertIsNone(ov["rows"][0]["sync"])
