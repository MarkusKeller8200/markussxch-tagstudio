"""Tonart mit OpenKeyScan (#217): gemeinsamer Teil (keyscan.py), eigene Analyse (#245, Plugin „keyscan“) und
OpenKeyScan-App über die lokale API (#244, Plugin „openkeyscan“). Ohne PyTorch und ohne App: Worker-Ausgabe und
App werden nachgestellt."""
import hashlib
import importlib.util
import io
import json
import os
import sys
import time
import unittest

import fake_openkeyscan
from helpers import write_mp3, text, txxx, comm
from test_tagger_tools import Base

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, *rel.split("/")))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestCore(unittest.TestCase):
    def test_code_of_all_notations(self):
        import keyscan
        for v, want in (("9A", "9A"), ("09a", "9A"), ("1m", "8A"), ("1d", "8B"), ("E minor", "9A"), ("C major", "8B"),
                        ("Ab minor/G# minor", "1A"), ("F#m", "11A"), ({"camelot": "12B"}, "12B"),
                        ({"success": True, "key": "6d"}, "1B"), ({"analyzedKey": "Dm"}, "7A")):
            self.assertEqual(keyscan.code_of(v), want, v)
        for v in (None, "", "kein", {"success": False}, 7):
            self.assertIsNone(keyscan.code_of(v), v)

    def test_relation(self):
        import keyscan
        self.assertEqual(keyscan.relation("9A", "9A"), "same")
        for b in ("10A", "8A", "9B"):
            self.assertEqual(keyscan.relation("9A", b), "related", b)
        self.assertEqual(keyscan.relation("9A", "3B"), "different")

    def test_cache_bound_to_file_state(self):
        import tempfile
        import keyscan
        d = tempfile.mkdtemp()
        p = os.path.join(d, "a.mp3")
        with open(p, "wb") as fh:
            fh.write(b"x" * 10)
        c = keyscan.Cache(os.path.join(d, "c.json"))
        c.put(p, "9A", 0.81234, "keyscan")
        self.assertEqual((c.get(p)["camelot"], c.get(p)["conf"]), ("9A", 0.812))
        c.save()
        self.assertEqual(keyscan.Cache(os.path.join(d, "c.json")).get(p)["camelot"], "9A")
        st = os.stat(p)
        os.utime(p, (st.st_atime, st.st_mtime + 10))           # Datei geändert → Ergebnis ungültig
        self.assertIsNone(c.get(p))
        c.restamp(p)                                             # … ausser es wird bewusst neu gebunden
        self.assertEqual(c.get(p)["camelot"], "9A")
        self.assertIsNone(c.get(os.path.join(d, "fehlt.mp3")))


class TestEnvFiles(unittest.TestCase):
    def test_clean(self):
        import plugins
        sha = "a" * 64
        ok = {"url": "https://raw.githubusercontent.com/x/y/abc/model.py", "path": "engine/model.py", "sha256": sha}
        bad = [dict(ok, url="http://raw.githubusercontent.com/x"), dict(ok, url="https://example.org/m.py"),
               dict(ok, path="../x.py"), dict(ok, path="/abs.py"), dict(ok, path="env/x.py"), dict(ok, sha256="123"),
               "kein Objekt"]
        out = plugins.clean_env_files([ok] + bad)
        self.assertEqual([e["path"] for e in out], ["engine/model.py"])
        self.assertEqual(out[0]["label"], "model.py")

    def test_fetch_checks_sha256(self):
        import tempfile
        import plugins
        data = b"gewichte" * 1000
        good = {"url": "https://raw.githubusercontent.com/x", "path": "m.pt", "label": "Modell",
                "sha256": hashlib.sha256(data).hexdigest()}

        class R(io.BytesIO):
            headers = {"Content-Length": str(len(data))}

        opener = lambda req, timeout=0: R(data)  # noqa: E731
        d = tempfile.mkdtemp()
        dest = os.path.join(d, "engine", "m.pt")
        said = []
        self.assertTrue(plugins.fetch_file(good, dest, None, said.append, opener))
        self.assertTrue(os.path.isfile(dest) and said)
        self.assertFalse(plugins.fetch_file(good, dest, None, None, opener))          # schon da und korrekt
        os.remove(dest)
        with self.assertRaises(ValueError):
            plugins.fetch_file(dict(good, sha256="0" * 64), dest, None, None, opener)
        self.assertEqual(os.listdir(os.path.dirname(dest)), [])                    # nichts (auch kein .part) liegen


class TestWorker(unittest.TestCase):
    def test_class_to_camelot(self):
        w = _load("keyscan_worker_t", "plugins/keyscan/worker.py")
        # Klassen wie dataset.CAMELOT_MAPPING der Engine: 0 = G#-Moll (1A), 7 = a-Moll (8A), 12 = H-Dur (1B), 19 = C-Dur
        self.assertEqual([w.camelot(c) for c in (0, 7, 11, 12, 19, 23)], ["1A", "8A", "12A", "1B", "8B", "12B"])


class TestKeyscanPlugin(Base):
    """#245: Zustand der Umgebung, Analyse über den (nachgestellten) Worker, Vorschau, Zwischenspeicher."""

    def setUp(self):
        super().setUp()
        import core
        import plugins
        cfg = core.load_config()
        cfg["key_notation"] = "musical"
        core.save_config(cfg)
        self.m = plugins.Manager(core.load_config())
        self.p = self.m.plugins["keyscan"]
        write_mp3(os.path.join(self.B, "leer.mp3"), [text("TIT2", "Leer")], audio_seed=41)
        write_mp3(os.path.join(self.B, "gleich.mp3"), [text("TIT2", "Gleich"), text("TKEY", "Em")], audio_seed=42)
        write_mp3(os.path.join(self.B, "anders.mp3"), [text("TIT2", "Anders"), text("TKEY", "3B"),
                                                         comm("", "4B - Energy 6")], audio_seed=43)
        self.keys = {"leer.mp3": ("9A", 0.91), "gleich.mp3": ("9A", 0.88), "anders.mp3": ("9A", 0.42)}

    def install_fake(self, files=True):
        import plugins
        base = os.path.join(plugins.shared_root(), "keyscan")
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, "env.json"), "w") as fh:
            json.dump({"python": sys.executable, "variant": "cpu", "label": "Prozessor"}, fh)
        if files:
            for e in self.p.env_files():
                os.makedirs(os.path.dirname(self.p.env_file_path(e["path"])), exist_ok=True)
                open(self.p.env_file_path(e["path"]), "wb").close()

    def files(self):
        from id3tags import MP3File
        return [MP3File(os.path.join(self.B, n)) for n in ("leer.mp3", "gleich.mp3", "anders.mp3")]

    def ctx(self, calls):
        import plugins
        ctx = plugins.Context(self.p)

        def run_env(args, on_line, env=None):
            with open(args[1], encoding="utf-8") as fh:
                job = json.load(fh)
            calls.append(job)
            self.assertTrue(job["model"].endswith("openkeyscan3.pt") and os.path.isdir(job["engine"]))
            on_line('@@{"event": "loaded", "device": "cpu"}')
            for i, path in enumerate(job["files"]):
                on_line(json.dumps({"event": "start", "i": i, "path": path}).join(["@@", ""]))
                code, conf = self.keys.get(os.path.basename(path), (None, None))
                ev = {"event": "done", "i": i, "path": path, "camelot": code, "conf": conf} if code else \
                    {"event": "fail", "i": i, "path": path, "msg": "kaputt"}
                on_line("50%|███ \r@@" + json.dumps(ev))          # wie Stems: Ereignis hinter einem Balken
            on_line('@@{"event": "end"}')
            return 0, []
        ctx.run_env = run_env
        return ctx

    def test_states_and_manifest(self):
        files = self.p.env_files()
        self.assertEqual([e["path"] for e in files], ["engine/model.py", "engine/openkeyscan3.pt"])
        self.assertTrue(all("d5cac64bc7195826b6eb10c55b9b0c97fb3287c0" in e["url"] for e in files))
        self.assertEqual(self.p.state(), "missing")
        self.install_fake(files=False)
        self.assertEqual(self.p.state(), "missing")
        self.assertIn("Modell", self.p.missing()[0]["label"])
        self.install_fake()
        self.assertEqual(self.p.state(), "ready")

    def test_scan_proposals_and_cache(self):
        self.install_fake()
        mod = self.p.load()
        calls = []
        ctx = self.ctx(calls)
        res = mod.run("scan", ctx, self.files(), {"tkey": True, "force": False, "cache": True})
        self.assertIn("3 von 3", res["message"])
        self.assertIn("1 ohne Tonart, 1 gleich, 1 abweichend", res["message"])
        by = {(os.path.basename(p["file"].path), p["key"]): p for p in ctx.proposals}
        self.assertEqual(by[("leer.mp3", "TXXX:OPENKEYSCAN_KEY")]["new"], "09A")
        self.assertEqual((by[("leer.mp3", "TKEY")]["new"], by[("leer.mp3", "TKEY")]["checked"]), ("Em", True))
        self.assertNotIn(("gleich.mp3", "TKEY"), by)                           # schon gleich → kein Vorschlag
        ak = by[("anders.mp3", "TKEY")]
        self.assertFalse(ak["checked"])
        self.assertIn("abweichend", ak["hint"])
        note = by[("anders.mp3", "TXXX:OPENKEYSCAN_KEY")]["note"]
        self.assertIn("Sicherheit 42 %", note)
        self.assertIn("Kommentar (MIK): Ab – abweichend", note)
        # zweiter Lauf: alles aus dem Zwischenspeicher, Worker wird nicht gestartet
        ctx2 = self.ctx(calls)
        mod.run("scan", ctx2, self.files(), {"tkey": False, "cache": True})
        self.assertEqual(len(calls), 1)
        self.assertEqual({p["key"] for p in ctx2.proposals}, {"TXXX:OPENKEYSCAN_KEY"})
        # „Abweichende ebenfalls ankreuzen“
        ctx3 = self.ctx(calls)
        mod.run("scan", ctx3, self.files(), {"tkey": True, "force": True, "cache": True})
        self.assertTrue(next(p for p in ctx3.proposals if p["key"] == "TKEY" and "anders" in p["file"].path)["checked"])

    def test_prefetch_writes_nothing_and_failures(self):
        self.install_fake()
        mod = self.p.load()
        self.keys.pop("anders.mp3")
        calls = []
        ctx = self.ctx(calls)
        res = mod.run("prefetch", ctx, self.files(), {})
        self.assertEqual(ctx.proposals, [])
        self.assertIn("2 von 3", res["message"])
        self.assertTrue(any("kaputt" in line for line in ctx.log_lines))
        self.assertIn("2 Ergebnis", mod.status(ctx))
        ctx2 = self.ctx(calls)
        res = mod.run("scan", ctx2, self.files(), {"cache": True})
        self.assertEqual(calls[-1]["files"], [os.path.join(self.B, "anders.mp3")])     # nur das Fehlende neu
        self.assertIn("1 ohne Ergebnis", res["message"])

    def test_test_and_settings(self):
        self.install_fake()
        mod = self.p.load()
        calls = []
        self.assertEqual(mod.run("settings", self.ctx(calls), [], {"device": "cpu"})["message"], "Gespeichert: immer Prozessor.")
        res = mod.run("test", self.ctx(calls), [], {})
        self.assertIn("Prozessor", res["message"])
        self.assertEqual((calls[-1]["files"], calls[-1]["device"]), ([], "cpu"))

    def test_missing_model_message(self):
        self.install_fake(files=False)
        mod = self.p.load()
        with self.assertRaises(RuntimeError) as cm:
            mod.run("scan", self.ctx([]), self.files(), {"cache": False})
        self.assertIn("Neu installieren", str(cm.exception))


class TestOpenKeyScanApp(Base):
    """#244: über die (nachgestellte) App – einzeln, Warteschlange, Auto-Tagging-Warnung, Übernehmen."""

    def setUp(self):
        super().setUp()
        write_mp3(os.path.join(self.B, "a.mp3"), [text("TIT2", "A")], audio_seed=51)
        write_mp3(os.path.join(self.B, "b.mp3"), [text("TIT2", "B"), text("TKEY", "10A")], audio_seed=52)
        from session import Session
        self.s = Session()
        self.s.start_tag_load(self.B, False)
        self.wait()
        self.idx = {os.path.basename(f.path): i for i, f in enumerate(self.s.tag_files)}
        self.path = {n: self.s.tag_files[i].path for n, i in self.idx.items()}
        self.state = fake_openkeyscan.State({self.path["a.mp3"]: "1m", self.path["b.mp3"]: "2m",
                                             self.path["3.mp3"]: "C major"})
        self.srv, self.url = fake_openkeyscan.start(self.state)
        self.mod = self.s.plugins.get("openkeyscan").load()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        r = self.run_action("settings", url=self.url)
        self.assertIn(self.url, r["message"])

    def wait(self):
        for _ in range(1000):
            st = self.s.task_status()
            if st.get("done"):
                return st
            time.sleep(0.02)
        self.fail("hängt")

    def run_action(self, aid, **opts):
        r = self.s.start_plugin_action("openkeyscan", aid, sorted(self.idx.values()), opts)
        self.assertTrue(r["ok"], r)
        st = self.wait()
        self.assertIsNone(st["error"], st)
        return st["result"]

    def by(self, res):
        return {(r["name"], r["label"]): r for r in res.get("proposals", [])}

    def test_single_and_apply(self):
        self.assertIn("antwortet", self.run_action("test")["message"])
        res = self.run_action("scan", tkey=True, cache=True)
        self.assertIn("3 von 3", res["message"])
        self.assertEqual([c[1] for c in self.state.calls if c[0] == "POST"], ["/analyze/single"] * 3)
        by = self.by(res)
        self.assertEqual(by[("a.mp3", "Tonart (OpenKeyScan)")]["new"], "08A")
        self.assertTrue(by[("a.mp3", "Tonart")]["checked"])
        self.assertFalse(by[("b.mp3", "Tonart")]["checked"])            # 10A vorhanden, 9A erkannt → verwandt
        self.assertIn("verwandt", by[("b.mp3", "Tonart")]["hint"])
        ids = [r["id"] for r in res["proposals"] if r["checked"]]
        out = self.s.plugin_apply(res["proposals_token"], ids)
        self.assertTrue(out["ok"], out)
        fa, fb = self.s.tag_files[self.idx["a.mp3"]], self.s.tag_files[self.idx["b.mp3"]]
        self.assertEqual((fa.text("TKEY"), fa.text("TXXX:OPENKEYSCAN_KEY")), ("08A", "08A"))
        self.assertEqual((fb.text("TKEY"), fb.text("TXXX:OPENKEYSCAN_KEY")), ("10A", "09A"))
        import origins
        self.assertEqual(origins.Origins().of("TXXX:OPENKEYSCAN_KEY"), "openkeyscan")
        self.assertNotIn(("DELETE", "/analyze/clear"), self.state.calls)

    def test_queue_variants(self):
        self.mod.SINGLE_MAX, self.mod.POLL = 0, 0.01
        for shape in ("list", "dict", "empty"):
            self.state.results_shape = shape
            self.state.calls.clear()
            res = self.run_action("scan", cache=False)
            self.assertIn("3 von 3", res["message"], shape)
            self.assertIn(("POST", "/analyze/add", {"files": sorted(self.path.values())}),
                          [(c[0], c[1], {"files": sorted(c[2]["files"])}) for c in self.state.calls if c[1] == "/analyze/add"])
            if shape == "empty":
                self.assertIn(("GET", "/analyze/result"), self.state.calls)

    def test_auto_tagging_warning_and_errors(self):
        self.state.auto_tag = True
        del self.state.keys[self.path["b.mp3"]]
        res = self.run_action("scan", cache=False)
        self.assertIn("2 von 3", res["message"])
        self.assertIn("1 ohne Ergebnis", res["message"])
        self.assertIn("Auto-Tagging", res["message"])
        self.assertIn(("a.mp3", "Tonart (OpenKeyScan)"), self.by(res))      # Ergebnis gilt trotz Änderung

    def test_only_local_addresses(self):
        r = self.s.start_plugin_action("openkeyscan", "settings", [], {"url": "http://192.168.1.20:58721"})
        st = self.wait() if r.get("ok") else {"error": r.get("error")}
        self.assertIn("diesem Rechner", str(st["error"]))
        with self.assertRaises(self.mod.OKSError):
            self.mod.Client("http://example.org:58721")

    def test_finds_app_on_other_loopback_address(self):
        """Eingestellt [::1], App lauscht nur auf 127.0.0.1 → gefunden; /health fehlt (404) → läuft trotzdem."""
        port = self.url.rsplit(":", 1)[1]
        self.run_action("settings", url=f"http://[::1]:{port}")
        self.state.no_health = True
        self.assertIn("127.0.0.1", self.run_action("test")["message"])
        res = self.run_action("scan", cache=False)
        self.assertIn("3 von 3", res["message"])

    def run_error(self):
        r = self.s.start_plugin_action("openkeyscan", "scan", sorted(self.idx.values()), {})
        self.assertTrue(r["ok"])
        return str(self.wait()["error"])

    def test_no_app_running(self):
        """App nicht gefunden / läuft ohne Server / wird bei Bedarf gestartet."""
        m = self.mod
        port = int(self.url.rsplit(":", 1)[1])
        self.srv.shutdown()
        self.srv.server_close()
        orig = (m.find_app, m.app_running, m.launch, m.START_WAIT)
        self.addCleanup(lambda: setattr(m, "find_app", orig[0]) or setattr(m, "app_running", orig[1])
                        or setattr(m, "launch", orig[2]) or setattr(m, "START_WAIT", orig[3]))
        m.find_app, m.app_running = (lambda setting="": ""), (lambda: False)
        self.assertIn("nicht gefunden", self.run_error())
        m.app_running = lambda: True                                   # läuft, aber ohne Server
        self.assertIn("API-Server antwortet nicht", self.run_error())
        # gefunden, läuft nicht → wird gestartet; danach antwortet der Server
        started = []

        def launch(app):
            started.append(app)
            srv, _url = fake_openkeyscan.start(self.state, port)
            self.addCleanup(srv.server_close)
            self.addCleanup(srv.shutdown)
        m.find_app, m.app_running, m.launch = (lambda setting="": "C:/Apps/OpenKeyScan.exe"), (lambda: False), launch
        r = self.s.start_plugin_action("openkeyscan", "scan", sorted(self.idx.values()), {})
        st = self.wait()
        self.assertIsNone(st["error"], st)
        self.assertEqual(started, ["C:/Apps/OpenKeyScan.exe"])
        self.assertIn("3 von 3", st["result"]["message"])

    def test_find_app(self):
        import tempfile
        m = self.mod
        d = tempfile.mkdtemp()
        exe = os.path.join(d, "Programs", "openkeyscan", "OpenKeyScan.exe")
        os.makedirs(os.path.dirname(exe))
        open(exe, "w").close()
        open(os.path.join(os.path.dirname(exe), "Uninstall OpenKeyScan.exe"), "w").close()
        old = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = d
        self.addCleanup(lambda: os.environ.pop("LOCALAPPDATA") if old is None else os.environ.__setitem__("LOCALAPPDATA", old))
        if sys.platform != "darwin":
            self.assertEqual(m.find_app(), exe)
        self.assertEqual(m.find_app(exe), exe)
        self.assertEqual(m.find_app(os.path.join(d, "fehlt.exe")), "")

    def test_entries_tolerant(self):
        m = self.mod
        self.assertEqual(len(m.entries({"files": [{"path": "x"}]})), 1)
        self.assertEqual(m.entries({"/a.mp3": {"status": "done", "key": "8A"}})[0]["file"], "/a.mp3")
        self.assertEqual(m.entry_status({"status": "Done", "analyzedKey": "1m"}), "done")
        self.assertEqual(m.entry_status({"status": "queued"}), "pending")
        self.assertEqual(m.entry_status({"success": False}), "error")
        self.assertIsNone(m.entry_key({"currentKey": "8A", "status": "queued"}))


if __name__ == "__main__":
    unittest.main()
