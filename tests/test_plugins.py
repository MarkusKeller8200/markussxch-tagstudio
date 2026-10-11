"""Tests für das Plugin-System (plugins.py + Sitzung) und das Stems-Plugin (mit nachgebautem audio-separator)."""
import json
import os
import sys
import time
import unittest

from test_tagger_tools import Base

import plugins

DEMO_PY = '''
ACTIONS = [{"id": "mark", "label": "Markieren …", "options": [
    {"key": "text", "type": "text", "label": "Text", "default": "hallo"},
    {"key": "loud", "type": "check", "label": "Laut"},
    {"key": "n", "type": "number", "label": "Zahl", "default": 2},
    {"key": "mode", "type": "select", "label": "Modus", "choices": [["a", "A"], ["b", "B"]], "default": "a"},
    {"key": "x", "type": "unbekannt"}]}]

def run(action, ctx, files, opts):
    ctx.status("los")
    for i, f in enumerate(files):
        ctx.progress(i, len(files), f.path)
    val = opts["text"].upper() if opts["loud"] else opts["text"]
    ctx.edit_tags(files, lambda f: f.set_text("TXXX:Demo", f"{val}-{opts['n']}-{opts['mode']}"), "Demo")
    ctx.log("ok")
    with open(ctx.data_dir + "/out.txt", "w") as fh:
        fh.write("x")
    ctx.output(ctx.data_dir + "/out.txt")
    return {"message": f"{len(files)} markiert"}
'''


def make_plugin(base, pid, manifest=None, code=DEMO_PY):
    d = os.path.join(base, pid)
    os.makedirs(d, exist_ok=True)
    m = {"id": pid, "name": pid.title(), "version": "1.0", "api": 1, "description": "Test"}
    m.update(manifest or {})
    with open(os.path.join(d, "plugin.json"), "w", encoding="utf-8") as fh:
        json.dump(m, fh)
    if code is not None:
        with open(os.path.join(d, "plugin.py"), "w", encoding="utf-8") as fh:
            fh.write(code)
    return d


class PluginBase(Base):
    def wait_job(self, s):
        """Hintergrund-Auftrag (z. B. Stems) abwarten → wie task_status: {"error", "result"}."""
        for _ in range(1000):
            st = s.jobs_status()
            if not st["active"] and st["jobs"]:
                j = st["jobs"][-1]
                return {"error": j["error"] or None, "status": j["status"],
                        "result": {k: j[k] for k in ("message", "outputs", "logfile", "log")}}
            time.sleep(0.02)
        self.fail("Auftrag hängt")

    def setUp(self):
        super().setUp()
        self.udir = plugins.user_dir()
        os.makedirs(self.udir, exist_ok=True)

    def session(self):
        from session import Session
        s = Session()
        s.start_tag_load(self.dir, True)
        self.wait(s)
        return s

    def wait(self, s):
        for _ in range(500):
            st = s.task_status()
            if st.get("done"):
                return st
            time.sleep(0.02)
        self.fail("Auftrag hängt")


class TestManager(PluginBase):
    def test_scan_states(self):
        make_plugin(self.udir, "demo")
        make_plugin(self.udir, "needs", {"requires": [{"module": "gibt_es_nicht_xyz", "label": "xyz"}],
                                          "install": [{"id": "cpu", "label": "Inst", "packages": ["xyz"]}]})
        make_plugin(self.udir, "broken", code="def run(:\n")
        make_plugin(self.udir, "future", {"api": 99})
        make_plugin(self.udir, "nocode", code=None)
        os.makedirs(os.path.join(self.udir, "leer"))
        m = plugins.Manager({})
        info = {p["id"]: p for p in m.list()}
        self.assertIn("stems", info)            # eingebaut
        self.assertTrue(info["stems"]["builtin"])
        self.assertEqual(info["demo"]["state"], "ready")
        self.assertEqual([a["id"] for a in info["demo"]["actions"]], ["mark"])
        self.assertEqual(info["needs"]["state"], "missing")
        self.assertEqual(info["needs"]["missing"][0]["label"], "xyz")
        self.assertEqual(info["needs"]["install"][0]["packages"], ["xyz"])
        self.assertEqual(info["broken"]["state"], "error")
        self.assertIn("Fehler beim Laden", info["broken"]["error"])
        self.assertEqual(info["future"]["state"], "error")
        self.assertEqual(info["nocode"]["state"], "error")
        self.assertNotIn("leer", info)
        acts = m.actions("tagger")
        self.assertIn(("demo", "mark"), [(a["plugin"], a["id"]) for a in acts])
        self.assertNotIn("needs", [a["plugin"] for a in acts])

    def test_malformed_manifests_do_not_break_list(self):
        """3.0.1: Ein fehlerhaftes plugin.json legt nicht mehr die ganze Plugin-Liste lahm."""
        make_plugin(self.udir, "demo")
        make_plugin(self.udir, "badapi", {"api": "1.0"})
        make_plugin(self.udir, "badlists", {"requires": [{"label": "ohne Modul"}, 5], "install": ["x", {"packages": ["y"]}],
                                             "external": ["ffmpeg", {"label": "ohne cmd"}]})
        d = os.path.join(self.udir, "liste")
        os.makedirs(d)
        with open(os.path.join(d, "plugin.json"), "w", encoding="utf-8") as fh:
            fh.write('["kein", "objekt"]')
        info = {p["id"]: p for p in plugins.Manager({}).list()}
        self.assertEqual(info["demo"]["state"], "ready")
        self.assertEqual(info["badapi"]["state"], "error")
        self.assertIn("Plugin-API", info["badapi"]["error"])
        self.assertEqual(info["badlists"]["state"], "ready")
        self.assertEqual(info["badlists"]["external"], [])
        self.assertEqual(info["liste"]["state"], "error")

    def test_failed_edit_closes_undo_step(self):
        """3.0.1: Bricht ein Plugin mitten in edit_tags ab, bleibt kein halber Undo-Schritt offen."""
        make_plugin(self.udir, "demo")
        s = self.session()
        p = s.plugins.get("demo")
        ctx = plugins.Context(p, session=s)
        files = s.tag_files[:2]
        self.assertEqual(len(files), 2)
        calls = []

        def fn(f):
            calls.append(f)
            if len(calls) == 2:
                raise RuntimeError("kaputt")
            f.set_text("TXXX:Demo", "x")
        with self.assertRaises(RuntimeError):
            ctx.edit_tags(files, fn, "Demo")
        self.assertIsNone(s.undo.pending)

    def test_user_overrides_builtin_and_disable(self):
        make_plugin(self.udir, "stems", {"name": "Meine Stems"})
        cfg = {}
        m = plugins.Manager(cfg)
        self.assertEqual(m.get("stems").name, "Meine Stems")
        self.assertFalse(m.get("stems").builtin)
        m.set_enabled("stems", False)
        self.assertEqual(cfg["plugins_enabled"], {"stems": False})
        self.assertEqual(plugins.Manager(cfg).get("stems").enabled, False)
        self.assertNotIn("stems", [a["plugin"] for a in m.actions()])
        with self.assertRaises(ValueError):
            m.action("stems", "x")

    def test_form_and_clean(self):
        make_plugin(self.udir, "demo")
        cfg = {}
        m = plugins.Manager(cfg)
        f = m.form("demo", "mark")
        self.assertEqual([o["key"] for o in f["options"]], ["text", "loud", "n", "mode"])   # unbekannter Typ fehlt
        self.assertEqual(f["options"][0]["value"], "hallo")
        _p, a = m.action("demo", "mark")
        c = m.clean_options(a, {"text": 5, "loud": 1, "n": "3.5", "mode": "zzz"})
        self.assertEqual(c, {"text": "5", "loud": True, "n": 3.5, "mode": "a"})
        m.remember("demo", "mark", {"text": "neu"})
        self.assertEqual(m.form("demo", "mark")["options"][0]["value"], "neu")


class TestSessionPlugins(PluginBase):
    def test_run_action_with_undo(self):
        make_plugin(self.udir, "demo")
        s = self.session()
        lst = s.plugins_list()
        self.assertIn("demo", [p["id"] for p in lst["plugins"]])
        self.assertEqual(lst["user_dir"], self.udir)
        self.assertFalse(s.start_plugin_action("demo", "mark", [], {})["ok"])     # keine Auswahl
        self.assertFalse(s.start_plugin_action("nix", "mark", [0], {})["ok"])
        r = s.start_plugin_action("demo", "mark", [0, 1], {"text": "x", "loud": True, "n": 7, "mode": "b"})
        self.assertTrue(r["ok"])
        st = self.wait(s)
        self.assertIsNone(st["error"])
        res = st["result"]
        self.assertEqual(res["message"], "2 markiert")
        self.assertTrue(res["changed"])
        self.assertEqual(res["log"], ["ok"])
        self.assertTrue(res["outputs"][0].endswith("out.txt"))
        self.assertEqual(res["unsaved"], 2)
        self.assertEqual(s.tag_files[0].text("TXXX:Demo"), "X-7-b")
        s.do_undo()
        self.assertEqual(s.unsaved(), 0)
        self.assertEqual(s.plugin_form("demo", "mark")["options"][0]["value"], "x")   # gemerkt
        s.plugin_enable("demo", False)
        self.assertFalse(s.start_plugin_action("demo", "mark", [0], {})["ok"])

    def test_install_runs_pip(self):
        make_plugin(self.udir, "needs", {"requires": [{"module": "gibt_es_nicht_xyz"}],
                                          "install": [{"id": "a", "label": "A", "packages": ["xyz"]}]})
        s = self.session()
        calls = []

        def fake(pk, cancel=None, progress=None):
            calls.append(pk)
            progress(("text", "Collecting xyz"))
            return {"ok": True, "log": ["fertig"]}
        orig = plugins.pip_install
        plugins.pip_install = fake
        try:
            self.assertTrue(s.start_plugin_install("needs", "a")["ok"])
            st = self.wait(s)
        finally:
            plugins.pip_install = orig
        self.assertEqual(calls, [["xyz"]])
        self.assertEqual(st["result"]["state"], "missing")
        self.assertFalse(s.start_plugin_install("demo-gibts-nicht")["ok"])


# --------------------------------------------------------------------------- Stems mit Attrappe
FAKE_SEPARATOR = """
import os
class Separator:
    def __init__(self, output_dir, output_format="WAV", model_file_dir=None, output_single_stem=None,
                 log_level=None, use_directml=False):
        self.output_dir, self.fmt, self.single = output_dir, output_format.lower(), output_single_stem
        self.model_dir, self.dml = model_file_dir, use_directml
    def load_model(self, model_filename):
        self.model = model_filename
        if os.environ.get("FAIL_LOAD"):
            raise ValueError("Modell kaputt")
        with open(os.path.join(self.output_dir, "info.txt"), "w") as fh:
            fh.write(f"{self.model_dir}|{self.model}|{self.dml}")
    def separate(self, path):
        if "02" in os.path.basename(path) and os.environ.get("FAIL_02"):
            raise RuntimeError("Datei defekt")
        base = os.path.splitext(os.path.basename(path))[0]
        stems = [self.single] if self.single else ["Vocals", "Drums", "Bass", "Other"]
        out = []
        for st in stems:
            name = f"{base}_({st})_{self.model.split('.')[0]}.{self.fmt}"
            with open(os.path.join(self.output_dir, name), "wb") as fh:
                fh.write(b"RIFF")
            out.append(name)
        return out
"""


class TestStems(PluginBase):
    def setUp(self):
        super().setUp()
        fake = os.path.join(self.dir, "fakepkgs", "audio_separator")
        os.makedirs(fake)
        open(os.path.join(fake, "__init__.py"), "w").close()
        with open(os.path.join(fake, "separator.py"), "w") as fh:
            fh.write(FAKE_SEPARATOR)
        self._pp = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = os.path.join(self.dir, "fakepkgs")
        os.environ.pop("FAIL_02", None)
        self.base = os.path.join(plugins.data_root(), "stems")

    def tearDown(self):
        if self._pp is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = self._pp
        os.environ.pop("FAIL_02", None)
        super().tearDown()

    def fake_env(self, variant="cpu"):
        os.makedirs(self.base, exist_ok=True)
        with open(os.path.join(self.base, "env.json"), "w") as fh:
            json.dump({"python": sys.executable, "variant": variant, "label": "Test"}, fh)

    def test_not_installed(self):
        s = self.session()
        info = {p["id"]: p for p in s.plugins_list(True)["plugins"]}
        self.assertEqual(info["stems"]["state"], "missing")
        self.assertTrue(info["stems"]["env"])
        self.assertEqual([v["id"] for v in info["stems"]["install"]], ["cpu", "dml", "gpu"])

    def test_stems(self):
        self.fake_env("dml")
        s = self.session()
        info = {p["id"]: p for p in s.plugins_list(True)["plugins"]}
        self.assertEqual(info["stems"]["state"], "ready", info["stems"])
        self.assertEqual(info["stems"]["env_variant"], "Test")
        r = s.start_plugin_action("stems", "separate", [0], {"model": "htdemucs_ft.yaml", "format": "MP3"})
        self.assertTrue(r["ok"], r)
        st = self.wait_job(s)
        self.assertIsNone(st["error"], st)
        res = st["result"]
        f0 = s.tag_files[0]
        base = os.path.splitext(os.path.basename(f0.path))[0]
        dest = os.path.join(os.path.dirname(f0.path), f"{base} – Stems")
        self.assertEqual(res["outputs"], [dest])
        self.assertEqual(sorted(os.listdir(dest)), sorted(f"{base} ({x}).mp3" for x in ("Vocals", "Drums", "Bass", "Other")))
        self.assertIn("1 von 1", res["message"])
        self.assertTrue(os.path.exists(res["logfile"]))
        # zweiter Lauf: übersprungen
        s.start_plugin_action("stems", "separate", [0], {"model": "htdemucs_ft.yaml"})
        self.assertIn("schon Stems", self.wait_job(s)["result"]["message"])
        # fester Ordner, nur Gesang, überschreiben, eine Datei mit Fehler
        os.environ["FAIL_02"] = "1"
        out = os.path.join(self.dir, "Stems")
        s.start_plugin_action("stems", "separate", [0, 1, 2], {"model": "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
                                                                "stem": "Vocals", "format": "FLAC", "dest": "folder",
                                                                "folder": out, "overwrite": True})
        res3 = self.wait_job(s)["result"]
        names = [os.path.basename(p.path) for p in s.tag_files[:3]]
        expect_fail = sum(1 for n in names if "02" in n)
        self.assertEqual(len(res3["outputs"]), 3 - expect_fail)
        for d in res3["outputs"]:
            self.assertTrue(d.startswith(out))
            self.assertEqual(len(os.listdir(d)), 1)
            self.assertTrue(os.listdir(d)[0].endswith("(Vocals).flac"))
        if expect_fail:
            self.assertIn("mit Fehler", res3["message"])
            self.assertTrue(any("Datei defekt" in l for l in res3["log"]))
        # fester Ordner ohne Pfad → Fehlermeldung
        s.start_plugin_action("stems", "separate", [0], {"dest": "folder", "folder": ""})
        self.assertIn("Ordner", self.wait_job(s)["error"])

    def test_progress_within_title(self):
        """3.0.2: Fortschritt bewegt sich während eines Titels (tqdm-Balken → Ereignis „tick“), statt bei 0 zu stehen."""
        self.fake_env()
        s = self.session()
        p = s.plugins.get("stems")
        p.load()
        seen = []
        ctx = plugins.Context(p, progress=seen.append)
        f = s.tag_files[0]

        def fake_run(args, on_line, env=None):
            ev = lambda **kw: on_line("@@" + json.dumps(kw))
            ev(event="tick", n=8e3, total=1e3, unit="iB")             # Grösse falsch gemeldet → nur Menge
            ev(event="tick", n=50e6, total=100e6, unit="iB")          # Modell-Download
            ev(event="loaded")
            on_line("\r  0%|          | 0/9 [00:00<?, ?it/s]" + "@@" + json.dumps({"event": "status", "msg": "hinter Balken"}))
            ev(event="start", i=0, path=f.path)
            for k in range(8):                                        # 8 Demucs-Durchgänge à 0 → 100 %
                for n in (0, 30, 60, 100):
                    ev(event="tick", n=n, total=100, unit="seconds")
            on_line("kein Ereignis")
            ev(event="end")
            return 0, []
        ctx.run_env = fake_run
        p.module.run("separate", ctx, [f], {"model": "htdemucs_ft.yaml", "overwrite": True})
        texts = [m[1] for m in seen if m[0] == "text"]
        self.assertIn("hinter Balken", texts)           # Ereignis hinter einem tqdm-Balken in derselben Zeile
        self.assertTrue(any("Lade Modell herunter … 50 %" in t for t in texts), texts)
        self.assertFalse(any("800 %" in t for t in texts), texts)
        self.assertTrue(any(t.endswith("0.0 MB") for t in texts), texts)
        fr = [m[4] for m in seen if m[0] == "progress" and m[1] == 0 and m[4] is not None]
        self.assertEqual(fr, sorted(fr))                  # nie rückwärts
        self.assertGreater(max(fr), 0.9)                  # kommt bis fast 100 %
        self.assertTrue(0.05 < fr[len(fr) // 4] < 0.5)    # und nicht in einem Sprung

    def test_worker_fatal(self):
        self.fake_env()
        s = self.session()
        os.environ["FAIL_LOAD"] = "1"
        try:
            s.start_plugin_action("stems", "separate", [0], {"overwrite": True})
            err = self.wait_job(s)["error"]
        finally:
            os.environ.pop("FAIL_LOAD", None)
        self.assertIn("Modell kaputt", err)
        self.assertIn("Protokoll", err)
        self.assertTrue(os.path.exists(os.path.join(plugins.log_dir(), "stems.log")))

    def test_env_install_commands(self):
        calls = []

        def fake_run(cmd, on_line=None, cancel=None, env=None, cwd=None):
            calls.append(cmd)
            if on_line:
                on_line("Resolved 42 packages")
            return 0, ["ok"]
        orig = plugins.run_lines
        plugins.run_lines = fake_run
        try:
            s = self.session()
            self.assertTrue(s.start_plugin_install("stems", "gpu")["ok"])
            st = self.wait(s)
        finally:
            plugins.run_lines = orig
        self.assertIsNone(st["error"], st)
        self.assertTrue(st["result"]["ok"], st["result"])
        flat = [" ".join(c) for c in calls]
        self.assertTrue(any("venv --python 3.12 " in c for c in flat), flat)
        inst = next(c for c in flat if " pip install --python " in c)
        self.assertIn("audio-separator[gpu]", inst)
        self.assertIn("--extra-index-url https://download.pytorch.org/whl/cu128", inst)
        self.assertTrue(any(c.endswith("-c import audio_separator.separator") for c in flat))
        with open(os.path.join(self.base, "env.json")) as fh:
            info = json.load(fh)
        self.assertEqual(info["variant"], "gpu")

    def test_env_install_self_heal_and_reuse(self):
        state = {"checks": 0}
        calls = []

        def fake_run(cmd, on_line=None, cancel=None, env=None, cwd=None):
            calls.append(" ".join(cmd))
            if cmd[-2:] == ["-c", "import audio_separator.separator"]:
                state["checks"] += 1
                if state["checks"] == 1:
                    return 1, ["ModuleNotFoundError: No module named 'audioread'"]
            if cmd[-2:] == ["-c", "import sys"] and state.pop("broken", False):
                return 1, ["error: uv trampoline failed to spawn Python child process"]
            if "venv" in cmd:      # Umgebung „anlegen“
                py = plugins._env_python(cmd[-1])
                os.makedirs(os.path.dirname(py), exist_ok=True)
                open(py, "w").close()
            return 0, []
        orig = plugins.run_lines
        plugins.run_lines = fake_run
        try:
            s = self.session()
            s.start_plugin_install("stems", "cpu")
            res = self.wait(s)["result"]
            self.assertTrue(res["ok"], res)
            self.assertTrue(any(c.endswith("pip install --python " + plugins._env_python(
                os.path.join(self.base, "env")) + " audioread") for c in calls), calls)
            pk = next(c for c in calls if " pip install " in c and "audio-separator" in c)
            self.assertIn("librosa<1.0", pk)
            # zweiter Versuch, gleiche Variante: kein neues venv
            calls.clear()
            s.start_plugin_install("stems", "cpu")
            self.assertTrue(self.wait(s)["result"]["ok"])
            self.assertFalse(any(" venv " in c for c in calls))
            # andere Variante: neu anlegen
            calls.clear()
            s.start_plugin_install("stems", "dml")
            self.assertTrue(self.wait(s)["result"]["ok"])
            self.assertTrue(any(" venv " in c for c in calls))
            # #135: gleiche Variante, aber Basis-Python fehlt (uv-Trampolin) → neu anlegen statt weiterverwenden
            state["broken"] = True
            calls.clear()
            s.start_plugin_install("stems", "dml")
            self.assertTrue(self.wait(s)["result"]["ok"])
            self.assertTrue(any(" venv " in c for c in calls), calls)
        finally:
            plugins.run_lines = orig

    def test_broken_env_message(self):
        """#135: startet das Umgebungs-Python nicht (Basis-Python weg), klare Meldung statt „Code 1“."""
        def fake_run(cmd, on_line=None, cancel=None, env=None, cwd=None, low_priority=False):
            return 1, ["error: uv trampoline failed to spawn Python child process",
                       "  Caused by: entity not found (os error 2)"]
        self.assertTrue(plugins.env_broken(["error: uv trampoline failed to spawn Python child process"]))
        self.assertFalse(plugins.env_broken(["Traceback", "ValueError: kaputt"]))
        orig = plugins.run_lines
        plugins.run_lines = fake_run
        try:
            self.assertFalse(plugins.env_runs(__file__))
        finally:
            plugins.run_lines = orig

    def test_uv_command(self):
        import shutil as sh
        import sys as _sys
        orig_which, orig_find = sh.which, plugins.importlib.util.find_spec
        try:
            plugins.importlib.util.find_spec = lambda name: None if name == "uv" else orig_find(name)
            sh.which = lambda name: None
            with self.assertRaises(RuntimeError):
                plugins.uv_command()
            sh.which = lambda name: "/opt/uv"
            self.assertEqual(plugins.uv_command(), ["/opt/uv"])
            # installierte App: mitgelieferte uv-Datei hat Vorrang
            bundle = os.path.join(self.dir, "bundle")
            os.makedirs(bundle)
            exe = os.path.join(bundle, "uv.exe" if os.name == "nt" else "uv")
            open(exe, "w").close()
            _sys.frozen, _sys._MEIPASS = True, bundle
            self.assertEqual(plugins.uv_command(), [exe])
        finally:
            sh.which, plugins.importlib.util.find_spec = orig_which, orig_find
            for a in ("frozen", "_MEIPASS"):
                if hasattr(_sys, a):
                    delattr(_sys, a)

    def test_env_install_failure(self):
        def fake_run(cmd, on_line=None, cancel=None, env=None, cwd=None):
            return (1, ["error: no matching distribution"]) if "install" in cmd and "--python" in cmd else (0, [])
        orig = plugins.run_lines
        plugins.run_lines = fake_run
        try:
            s = self.session()
            s.start_plugin_install("stems", "cpu")
            res = self.wait(s)["result"]
        finally:
            plugins.run_lines = orig
        self.assertFalse(res["ok"])
        self.assertIn("Pakete", res["error"])
        self.assertTrue(os.path.exists(res["logfile"]))
        self.assertFalse(os.path.exists(os.path.join(self.base, "env.json")))


if __name__ == "__main__":
    unittest.main()
