"""Tests für den gemeinsamen Kern (core.py), die Sitzung (session.py) und die Web-Schnittstelle."""
import json
import os
import shutil
import tempfile
import time
import unittest
import urllib.error
import urllib.request

from helpers import write_mp3, text, txxx, comm

import core
from compare import Rules
from id3tags import MP3File


class TempHome(unittest.TestCase):
    """Einstellungen und Sicherungen in einen Testordner umleiten."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tagstudio_core_")
        self._env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.dir
        self._cfg = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = os.path.join(self.dir, ".tagstudio.json")
        core.CONFIG_OLD = os.path.join(self.dir, ".mp3tagcompare.json")
        self.L, self.R = os.path.join(self.dir, "L"), os.path.join(self.dir, "R")
        os.makedirs(self.L)
        os.makedirs(self.R)
        for i in (1, 2):
            write_mp3(os.path.join(self.L, f"{i}.mp3"),
                      [text("TIT2", f"Song {i}"), text("TPE1", "Band"), txxx("Acoustid Id", "aaa"),
                       comm("", "siehe https://example.org/x")])
            write_mp3(os.path.join(self.R, f"{i}.mp3"),
                      [text("TIT2", f"Song {i} (Edit)" if i == 1 else f"Song {i}"), text("TPE1", "Band"),
                       text("TBPM", "120"), txxx("Acoustid Id", "bbb")])
        write_mp3(os.path.join(self.R, "3.mp3"), [text("TIT2", "Nur rechts")])

    def tearDown(self):
        core.CONFIG, core.CONFIG_OLD = self._cfg
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)


class TestCore(TempHome):
    def test_spans_and_links(self):
        self.assertEqual(core.diff_spans("Song 1", "Song 1 (Edit)"), [])
        self.assertEqual(core.diff_spans("Song 1 (Edit)", "Song 1"), [(6, 13)])
        self.assertEqual(core.diff_spans("abc", "xyz"), [(0, 3)])  # komplett anders
        self.assertEqual(core.link_spans("siehe https://example.org/x."), [(6, 27, "https://example.org/x")])

    def test_rows_states_and_filters(self):
        pairs, errors = core.load_pairs(self.L, self.R, False, "filename")
        self.assertEqual(errors, [])
        self.assertEqual(len(pairs), 3)
        l, r = pairs[0]
        rules = Rules()
        rows, states = core.visible_keys(l, r, rules)
        self.assertEqual(states["TIT2"], "diff")
        self.assertEqual(states["TPE1"], "same")
        self.assertEqual(states["TBPM"], "only")
        self.assertEqual(states["TXXX:Acoustid Id"], "triv")
        rows, _ = core.visible_keys(l, r, rules, "diff", show_trivial=False)
        self.assertNotIn("TPE1", rows)
        self.assertNotIn("TXXX:Acoustid Id", rows)
        rows, _ = core.visible_keys(l, r, rules, query="tbpm")
        self.assertEqual(rows, ["TBPM"])
        rows, states = core.visible_keys(l, r, rules, empty_set="v1")
        self.assertEqual(states["TALB"], "empty")
        st = core.pair_status(l, r, rules)
        self.assertEqual((st["symbol"], st["tag"], st["n_imp"]), ("≠", "diff", 3))
        self.assertEqual(core.pair_status(None, pairs[2][1], rules)["tag"], "single")
        # Paarfilter
        flt = core.make_pair_filter("", "TBPM", "größer als", "100", "rechts")
        self.assertEqual(sum(1 for p in pairs if flt(p)), 2)
        flt = core.make_pair_filter("nur rechts")
        self.assertEqual([p[1].text("TIT2") for p in pairs if flt(p)], ["Nur rechts"])
        self.assertIsNone(core.make_pair_filter(""))
        self.assertIn("Dateiname", core.field_choices(pairs))

    def test_apply_value_and_save_with_backup(self):
        f = MP3File(os.path.join(self.L, "1.mp3"))
        self.assertFalse(core.apply_value(f, "TIT2", "Song 1"))
        self.assertTrue(core.apply_value(f, "TCON", "Pop ¦ Rock"))
        self.assertEqual(f.text("TCON"), "Pop\x00Rock")
        self.assertTrue(core.apply_value(f, "TPE1", "  "))
        self.assertIsNone(f.get("TPE1"))
        self.assertTrue(core.can_edit_text(f, "TXXX:Neu"))
        self.assertFalse(core.can_edit_text(f, "APIC:3"))
        res = core.save_files([f], True, os.path.join(self.dir, "Sicherungen"))
        self.assertEqual((res["saved"], res["errors"], res["cancelled"]), (1, [], False))
        self.assertTrue(os.path.isfile(res["backup"]))
        self.assertEqual(MP3File(f.path).text("TCON"), "Pop\x00Rock")

    def test_config_merges(self):
        core.save_config({"a": 1})
        core.save_config({"b": 2})
        self.assertEqual(core.load_config(), {"a": 1, "b": 2})
        self.assertEqual(core.history({"h": ["x", "y"]}, "h", "y"), ["y", "x"])
        self.assertIn("existiert nicht", core.check_paths("/gibt/es/nicht", ""))
        self.assertIsNotNone(core.check_paths(self.L, self.L))


class TestSession(TempHome):
    def _load(self, s):
        self.assertTrue(s.start_load(self.L, self.R, False, "filename")["ok"])
        t0 = time.time()
        while not s.task_status()["done"] and time.time() - t0 < 20:
            time.sleep(0.02)
        t = s.task_status()
        self.assertIsNone(t["error"])
        return t["result"]

    def test_workflow(self):
        from session import Session
        s = Session()
        self.assertEqual(self._load(s)["pairs"], 3)
        pr = s.pair_rows()
        self.assertEqual(pr["counts"]["single"], 1)
        v = s.state()["view"]
        self.assertTrue(v["both"])
        tit = next(r for r in v["rows"] if r["key"] == "TIT2")
        self.assertEqual([list(x) for x in tit["R"]["spans"]], [[6, 13]])
        com = next(r for r in v["rows"] if r["key"].startswith("COMM"))
        self.assertEqual(com["L"]["links"][0][2], "https://example.org/x")
        json.dumps(s.state())  # alles JSON-tauglich
        # kopieren, rückfragen, rückgängig
        st = s.copy_keys(["TIT2"], "lr")
        self.assertEqual(st["meta"]["unsaved"], 1)
        ask = s.copy_all("rl")
        self.assertIn("ask", ask)
        s.copy_all("rl", True)
        l, r = s.files()
        self.assertIsNone(l.get("COMM:"))  # nur links vorhanden → beim Angleichen entfernt
        self.assertEqual(l.text("TBPM"), "120")
        s.do_undo()
        self.assertEqual(l.text("TBPM"), "")
        s.do_redo()
        self.assertEqual(l.text("TBPM"), "120")
        s.set_value("L", "TCON", "Pop ¦ Rock")
        self.assertEqual(l.text("TCON"), "Pop\x00Rock")
        s.remove("R", ["TBPM"])
        self.assertIsNone(r.get("TBPM"))
        s.set_option("filter", "diff")
        self.assertTrue(all(row["state"] != "same" for row in s.view()["rows"]))
        self.assertEqual(s.filter_pairs("nur rechts"), [2])
        # speichern
        self.assertTrue(s.start_save()["ok"])
        t0 = time.time()
        while not s.task_status()["done"] and time.time() - t0 < 20:
            time.sleep(0.02)
        res = s.task_status()["result"]
        self.assertEqual(res["errors"], [])
        self.assertEqual(res["saved"], 2)
        self.assertEqual(s.unsaved(), 0)
        self.assertEqual(MP3File(os.path.join(self.L, "1.mp3")).text("TCON"), "Pop\x00Rock")
        self.assertEqual(core.load_config()["filter"], "diff")
        # Layout der Web-Oberfläche
        self.assertTrue(s.set_ui("pairs_w", 420))
        self.assertTrue(s.set_ui("side_collapsed", True))
        with self.assertRaises(ValueError):
            s.set_ui("pairs_w", True)
        with self.assertRaises(ValueError):
            s.set_ui("unbekannt", 1)
        self.assertEqual(Session().settings()["ui"], {"pairs_w": 420, "side_collapsed": True})


class TestWindowMode(TempHome):
    def test_window_mode(self):
        """#134: Vollbild ein/aus, zurück ins Fenster; ohne Fenster (Browser-Modus) nichts."""
        import tagstudio_web
        calls = []

        class FakeWin:
            def toggle_fullscreen(self):
                calls.append("fs")

            def restore(self):
                calls.append("restore")
        api = tagstudio_web.Api()
        self.assertFalse(api.window_mode("fullscreen")["ok"])
        api._window = FakeWin()
        self.assertTrue(api.window_mode("fullscreen")["fullscreen"])
        self.assertFalse(api.window_mode("window")["fullscreen"])      # aus Vollbild zurück
        api.window_mode("window")                                       # maximiert → normal
        self.assertEqual(calls, ["fs", "fs", "restore"])
        with self.assertRaises(ValueError):
            api.window_mode("riesig")
        self.assertTrue(api.close_cancelled())


class TestWebServer(TempHome):
    def test_api_and_static(self):
        import threading
        import tagstudio_web
        api = tagstudio_web.Api()
        srv, token = tagstudio_web.make_server(api, 0)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"

        def post(name, args, tok=token):
            req = urllib.request.Request(base + "/api/" + name, data=json.dumps(args).encode(), method="POST",
                                         headers={"X-Token": tok, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as res:
                return json.loads(res.read())
        try:
            with urllib.request.urlopen(base + "/index.html", timeout=10) as res:
                self.assertIn(b"TagStudio", res.read())
            for bad in ("/../core.py", "/%2e%2e/core.py"):
                with self.assertRaises(urllib.error.HTTPError):
                    urllib.request.urlopen(base + bad, timeout=10)
            with self.assertRaises(urllib.error.HTTPError) as cm:
                post("settings", [], tok="falsch")
            self.assertEqual(cm.exception.code, 403)
            with self.assertRaises(urllib.error.HTTPError):
                post("_s", [])
            self.assertTrue(post("settings", [])["ok"])
            self.assertTrue(post("start_load", [self.L, self.R, False, "filename"])["result"]["ok"])
            t0 = time.time()
            while not post("task_status", [])["result"]["done"] and time.time() - t0 < 20:
                time.sleep(0.05)
            st = post("state", [])["result"]
            self.assertEqual(st["view"]["index"], 0)
            self.assertEqual(len(post("pair_rows", [])["result"]["rows"]), 3)
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()


class TestSaveConfigConcurrent(unittest.TestCase):
    """Gleichzeitige save_config-Aufrufe (mehrere Anfragen der Oberfläche) dürfen keine Schlüssel verlieren."""

    def test_no_lost_updates(self):
        import json
        import tempfile
        import threading
        import core
        d = tempfile.mkdtemp(prefix="ts_cfg_")
        old = core.CONFIG
        core.CONFIG = os.path.join(d, "cfg.json")
        try:
            ts = [threading.Thread(target=core.save_config, args=({f"k{i}": i},)) for i in range(100)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
            with open(core.CONFIG, encoding="utf-8") as fh:
                self.assertEqual(len(json.load(fh)), 100)
            self.assertFalse(os.path.exists(core.CONFIG + ".tmp"))
        finally:
            core.CONFIG = old
