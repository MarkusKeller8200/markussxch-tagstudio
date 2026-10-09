"""Tests für die Einstellungsseite (#21): appsettings.py und die Sitzungs-Aufrufe."""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import appsettings  # noqa: E402
import core  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ts_set_")
        self.old = (core.CONFIG, core.CONFIG_OLD, appsettings.BACKUP_DIR)
        core.CONFIG = os.path.join(self.dir, ".tagstudio.json")
        core.CONFIG_OLD = os.path.join(self.dir, ".alt.json")
        appsettings.BACKUP_DIR = os.path.join(self.dir, "Einstellungen")

    def tearDown(self):
        core.CONFIG, core.CONFIG_OLD, appsettings.BACKUP_DIR = self.old
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, cfg):
        with open(core.CONFIG, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)


class TestAppSettings(Base):
    def test_export_strips_secrets(self):
        self.write({"web_theme": "light", "plugin_options": {"beatport": {"user": "m", "password": "x", "token": "t"}},
                    "api_key": "k"})
        data = json.loads(appsettings.export_text("9.9"))
        self.assertEqual(data["format"], appsettings.FORMAT)
        self.assertEqual(data["settings"]["plugin_options"], {"beatport": {"user": "m"}})
        self.assertNotIn("api_key", data["settings"])

    def test_import_preview_and_apply(self):
        self.write({"web_theme": "dark", "hist_left": ["C:\\Musik"], "key_notation": "camelot"})
        exp = {"format": appsettings.FORMAT, "platform": "fremd", "app_version": "3.2.0",
               "settings": {"web_theme": "light", "hist_left": ["/Users/m/Musik"], "key_notation": "camelot",
                            "unbekannt": 1}}
        pv = appsettings.import_preview(json.dumps(exp))
        g = {x["id"]: x for x in pv["groups"]}
        self.assertTrue(pv["foreign"])
        self.assertTrue(g["design"]["default"])
        self.assertEqual(g["design"]["changed"], 1)
        self.assertFalse(g["history"]["default"])          # Pfade eines anderen Systems nicht vorgewählt
        self.assertIn("other", g)
        r = appsettings.import_apply(json.dumps(exp), ["design"])
        self.assertTrue(r["ok"] and os.path.isfile(r["backup"]))
        cfg = core.load_config()
        self.assertEqual((cfg["web_theme"], cfg["hist_left"]), ("light", ["C:\\Musik"]))
        with self.assertRaises(ValueError):
            appsettings.import_preview("{kein json")
        with self.assertRaises(ValueError):
            appsettings.import_preview(json.dumps({"irgendwas": 1}))
        # rohe .tagstudio.json geht auch
        self.assertTrue(appsettings.import_preview(json.dumps({"web_theme": "dark"}))["groups"])

    def test_reset(self):
        self.write({"web_ui": {"side_w": 300}, "web_theme": "light", "players": [1]})
        r = appsettings.reset(["layout"])
        self.assertEqual(r["keys"], 1)
        self.assertEqual(core.load_config(), {"web_theme": "light", "players": [1]})
        appsettings.reset("all")
        self.assertEqual(core.load_config(), {})
        self.assertEqual(len(os.listdir(appsettings.BACKUP_DIR)), 2)


class TestSessionSettings(Base):
    def test_session_calls(self):
        from session import Session
        from compare import DEFAULT_TRIVIAL
        s = Session()
        page = s.settings_page()
        self.assertEqual(page["trivial"], DEFAULT_TRIVIAL)
        self.assertEqual(page["player"]["start"], "0")
        s.set_trivial(["TXXX:Eigen*", " ", "TXXX:Eigen*", "GEOB:*"])
        self.assertEqual(Session().rules.trivial, ["TXXX:Eigen*", "GEOB:*"])   # entfernte Standards bleiben weg
        self.assertTrue(Session().rules.is_trivial("TXXX:Eigenes Feld"))
        self.assertEqual(s.set_player_pref("start", "cue")["start"], "cue")
        self.assertEqual(s.set_player_pref("vol", 3)["vol"], 1.0)
        with self.assertRaises(ValueError):
            s.set_player_pref("start", "99")
        with self.assertRaises(ValueError):
            s.set_player_pref("wave", "ja")
        self.assertEqual(Session().settings()["player"]["start"], "cue")
        s.set_save_version(4)
        with self.assertRaises(ValueError):
            s.set_save_version(2)
        text = s.settings_export_text()
        r = s.settings_reset(["player", "trivial"])
        self.assertTrue(r["ok"])
        self.assertEqual(s.player_prefs()["start"], "0")       # Sitzung hat neu eingelesen
        self.assertEqual(s.rules.trivial, DEFAULT_TRIVIAL)
        r = s.settings_import(text, ["player"])
        self.assertTrue(r["ok"])
        self.assertEqual(s.player_prefs()["start"], "cue")
        self.assertFalse(s.settings_import("x", ["player"])["ok"])

    def test_save_version_applied(self):
        import time
        from session import Session
        from helpers import write_mp3, text
        from id3tags import MP3File
        lib = os.path.join(self.dir, "lib")
        os.makedirs(lib)
        p = os.path.join(lib, "a.mp3")
        write_mp3(p, [text("TIT2", "A")], ver=4)
        s = Session()
        s.set_backup(False)
        s.set_save_version(3)
        s.start_tag_load(lib, False)
        while not s.task_status()["done"]:
            time.sleep(0.02)
        s.tag_set([0], "TIT2", "B")
        s.start_save()
        while not s.task_status()["done"]:
            time.sleep(0.02)
        f = MP3File(p)
        self.assertEqual((f.text("TIT2"), f.tag_desc), ("B", "ID3v2.3"))


class TestDefaultDirs(unittest.TestCase):
    """#84: Standardordner für Vergleich und Tagger; Snapshot-Angaben nicht im Verlauf."""

    def test_defaults(self):
        import tempfile, shutil
        import core
        from session import Session
        d = tempfile.mkdtemp(prefix="ts_def_")
        old = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = core.CONFIG_OLD = os.path.join(d, "cfg.json")
        try:
            s = Session()
            self.assertEqual(s.settings()["defaults"], {"left": "", "right": "", "tagger": ""})
            self.assertFalse(s.set_default_dir("left", os.path.join(d, "fehlt"))["ok"])
            self.assertEqual(s.set_default_dir("left", d)["defaults"]["left"], d)
            s.set_default_dir("tagger", d)
            s2 = Session()
            self.assertEqual((s2.settings()["defaults"]["left"], s2.tagger_settings()["default"]), (d, d))
            with self.assertRaises(ValueError):
                s.set_default_dir("mitte", d)
            s.set_default_dir("left", "")
            self.assertEqual(Session().settings()["defaults"]["left"], "")
        finally:
            core.CONFIG, core.CONFIG_OLD = old
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
