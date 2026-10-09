"""Tests für Hintergrund-Aufträge (#29): jobs.py und die Warteschlange in der Sitzung."""
import json
import os
import shutil
import sys
import tempfile
import textwrap
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import jobs  # noqa: E402


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_text(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def wait_for(cond, timeout=10):
    t0 = time.time()
    while not cond():
        if time.time() - t0 > timeout:
            raise AssertionError("Zeitüberschreitung")
        time.sleep(0.02)


class TestJobManager(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ts_jobs_")
        self.state = os.path.join(self.dir, "Auftraege.json")
        self.gate = threading.Event()
        self.order = []

    def tearDown(self):
        self.gate.set()
        shutil.rmtree(self.dir, ignore_errors=True)

    def runner(self, job, cancel, progress):
        self.order.append(job["label"])
        for i in range(len(job["paths"])):
            progress(("progress", i, len(job["paths"]), job["paths"][i], 0.5))
            while not self.gate.is_set():
                if cancel.is_set():
                    return {"cancelled": True}
                time.sleep(0.01)
        if job["opts"].get("fail"):
            raise RuntimeError("kaputt")
        return {"message": f"{job['label']} ok", "outputs": [self.dir]}

    def test_queue_one_at_a_time(self):
        m = jobs.JobManager(self.runner, self.state)
        a = m.add("p", "x", "A", ["/a1", "/a2"], {})
        b = m.add("p", "x", "B", ["/b1"], {"fail": True})
        wait_for(lambda: m.status()["running"] is not None)
        st = m.status()
        self.assertEqual((st["active"], st["running"]["id"], st["running"]["frac"]), (2, a["id"], 0.5))
        self.assertEqual([j["status"] for j in st["jobs"]], ["running", "waiting"])
        self.assertEqual(read_json(self.state)["pending"][1]["label"], "B")   # für Neustart vermerkt
        self.gate.set()
        wait_for(lambda: m.status()["active"] == 0)
        st = {j["id"]: j for j in m.status()["jobs"]}
        self.assertEqual((st[a["id"]]["status"], st[a["id"]]["message"]), ("done", "A ok"))
        self.assertEqual((st[b["id"]]["status"], st[b["id"]]["error"]), ("error", "kaputt"))
        self.assertEqual(self.order, ["A", "B"])
        self.assertEqual(read_json(self.state)["pending"], [])
        self.assertEqual(m.clear_finished(), 2)

    def test_cancel_running_and_waiting(self):
        m = jobs.JobManager(self.runner, self.state)
        a = m.add("p", "x", "A", ["/a"], {})
        b = m.add("p", "x", "B", ["/b"], {})
        wait_for(lambda: m.status()["running"] is not None)
        self.assertTrue(m.cancel(b["id"]))
        self.assertTrue(m.cancel(a["id"]))
        wait_for(lambda: m.status()["active"] == 0)
        self.assertEqual([j["status"] for j in m.status()["jobs"]], ["cancelled", "cancelled"])
        self.assertEqual(self.order, ["A"])
        self.assertFalse(m.cancel(a["id"]))

    def test_shutdown_and_resume(self):
        f1 = os.path.join(self.dir, "t1.mp3")
        write_text(f1, "")
        m = jobs.JobManager(self.runner, self.state)
        m.add("p", "x", "A", [f1], {"k": 1})
        m.add("p", "x", "B", [os.path.join(self.dir, "fehlt.mp3")], {})
        wait_for(lambda: m.status()["running"] is not None)
        m.shutdown(keep_queue=True)
        m2 = jobs.JobManager(self.runner, self.state)
        self.assertEqual([r["label"] for r in m2.status()["resumable"]], ["A", "B"])
        self.gate.set()
        self.assertEqual(m2.resume(True), 1)              # fehlende Datei → Auftrag entfällt
        wait_for(lambda: m2.status()["active"] == 0)
        self.assertEqual(m2.status()["jobs"][0]["status"], "done")
        self.assertEqual(jobs.JobManager(self.runner, self.state).status()["resumable"], [])
        m3 = jobs.JobManager(self.runner, self.state)
        m3.add("p", "x", "C", [f1], {})
        m3.shutdown(keep_queue=False)
        self.assertEqual(jobs.JobManager(self.runner, self.state).resumable, [])


PLUGIN = textwrap.dedent('''
    ACTIONS = [{"id": "work", "label": "Arbeiten …", "run_label": "Arbeiten", "background": True, "options": []},
               {"id": "front", "label": "Vorne …", "options": []}]

    def run(action, ctx, files, opts):
        out = []
        for i, f in enumerate(files):
            ctx.progress(i, len(files), f.path)
            out.append(f.text("TIT2"))
        ctx.output(ctx.data_dir)
        return {"message": "fertig: " + ",".join(out) + (" bg" if ctx.background else " fg")}
''')


class TestSessionJobs(unittest.TestCase):
    def test_background_action(self):
        import core
        import plugins
        from session import Session
        from helpers import write_mp3, text
        d = tempfile.mkdtemp(prefix="ts_sj_")
        old = (core.CONFIG, core.CONFIG_OLD, jobs.STATE_FILE, plugins.data_root)
        core.CONFIG = core.CONFIG_OLD = os.path.join(d, "cfg.json")
        jobs.STATE_FILE = os.path.join(d, "Auftraege.json")
        plugins.data_root = lambda: os.path.join(d, "daten")
        try:
            pdir = os.path.join(d, "Plugins", "bgtest")
            os.makedirs(pdir)
            write_text(os.path.join(pdir, "plugin.json"), json.dumps({"id": "bgtest", "name": "BG-Test", "version": "1", "api": 1}))
            write_text(os.path.join(pdir, "plugin.py"), PLUGIN)
            lib = os.path.join(d, "lib")
            os.makedirs(lib)
            write_mp3(os.path.join(lib, "a.mp3"), [text("TIT2", "Gespeichert")])
            s = Session()
            s._plugins = plugins.Manager(s.cfg, dirs=[(os.path.join(d, "Plugins"), False)])
            self.assertTrue(s.plugin_form("bgtest", "work")["background"])
            s.start_tag_load(lib, False)
            wait_for(lambda: s.task_status()["done"])
            s.tag_set([0], "TIT2", "Ungespeichert")
            r = s.start_plugin_action("bgtest", "work", [0], {})
            self.assertTrue(r["ok"] and r["background"])
            self.assertFalse(s.task_status().get("running"))        # Oberfläche bleibt frei
            wait_for(lambda: s.jobs_status()["active"] == 0)
            j = s.jobs_status()["jobs"][0]
            self.assertEqual((j["status"], j["message"]), ("done", "fertig: Gespeichert bg"))   # eigene Dateikopie
            self.assertTrue(j["outputs"])
            r = s.start_plugin_action("bgtest", "front", [0], {})
            self.assertTrue(r["ok"] and not r.get("background"))
            wait_for(lambda: s.task_status()["done"])
            self.assertEqual(s.task_status()["result"]["message"], "fertig: Ungespeichert fg")
            self.assertEqual(len(s.jobs_clear()["jobs"]), 0)
        finally:
            core.CONFIG, core.CONFIG_OLD, jobs.STATE_FILE, plugins.data_root = old
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
