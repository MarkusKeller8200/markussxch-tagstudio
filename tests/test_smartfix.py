"""Smart Fix (#339): mitgeliefertes Rezept, eigene Rezepte, Ziel-Trenner, Ausnahmen, Export/Import, Session."""
import json
import os
import shutil
import tempfile
import unittest

from helpers import write_mp3, text
from id3tags import MP3File, MV
import smartfix


class TestSmartFix(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def make(self, name, frames, ver=4):
        p = os.path.join(self.dir, name)
        write_mp3(p, frames, ver=ver)
        return MP3File(p)

    def test_builtin_multi_comma(self):
        f = self.make("a.mp3", [text("TPE1", "A & B; C; a"), text("TCON", "House; Tech House"),
                                text("TMOO", "Dark; Driving"), text("TIT2", "Rock & Roll")])
        r = smartfix.builtins()[0]
        plan = {k: new for _, k, _old, new in smartfix.plan([f], r)}
        self.assertEqual(plan["TPE1"], "A, B, C")                          # Doppelte entfernt
        self.assertEqual(plan["TCON"], "House, Tech House")
        self.assertEqual(plan["TMOO"], "Dark, Driving")
        self.assertNotIn("TIT2", plan)                                     # nur die Felder des Rezepts
        exc = {"@artists": ["Above & Beyond"]}
        g = self.make("b.mp3", [text("TPE1", "Above & Beyond; Zoë Johnston")])
        self.assertEqual(smartfix.plan([g], r, exc)[0][3], "Above & Beyond, Zoë Johnston")

    def test_target_separator(self):
        r = smartfix.builtins()[0]
        f4 = self.make("v4.mp3", [text("TPE1", "A & B")])
        f3 = self.make("v3.mp3", [text("TPE1", "A & B", 3)], ver=3)
        self.assertEqual(smartfix.plan([f4], r, out="v24")[0][3], "A" + MV + "B")
        self.assertEqual(smartfix.plan([f3], r, out="v24")[0][3], "A / B")      # v2.3: „ / “
        self.assertEqual(smartfix.plan([f4], r, out="; ")[0][3], "A; B")

    def test_clean_export_import(self):
        self.assertIsNone(smartfix.clean({"name": "", "fields": ["TPE1"], "seps": [";"]}))
        self.assertIsNone(smartfix.clean({"name": "X", "fields": ["ZZZZ"], "seps": [";"]}))
        c = smartfix.clean({"name": "Nur Genre", "fields": ["TCON", "XXX"], "seps": [";", "?"], "out": "kaputt"})
        self.assertEqual((c["id"], c["fields"], c["seps"], c["out"]), ("u_nur_genre", ["TCON"], [";"], ", "))
        txt = smartfix.export_text([c])
        self.assertEqual(json.loads(txt)["format"], smartfix.FORMAT)
        back = smartfix.import_text(txt, {"u_nur_genre"})
        self.assertEqual(back[0]["id"], "u_nur_genre_2")
        with self.assertRaises(ValueError):
            smartfix.import_text('{"format": "anders"}')
        with self.assertRaises(ValueError):
            smartfix.import_text("kein json")


class TestSmartSession(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self._env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.home
        import core
        self._cfg = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = os.path.join(self.home, ".tagstudio.json")
        core.CONFIG_OLD = os.path.join(self.home, ".mp3tagcompare.json")
        self.A = os.path.join(self.home, "A")
        os.makedirs(self.A)
        for n, art in (("1.mp3", "A & B; C"), ("2.mp3", "Above & Beyond; Zoë Johnston")):
            write_mp3(os.path.join(self.A, n), [text("TPE1", art), text("TCON", "House; Tech House")])
        self.B = os.path.join(self.home, "B")
        os.makedirs(self.B)

    def tearDown(self):
        import core
        core.CONFIG, core.CONFIG_OLD = self._cfg
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.home, ignore_errors=True)

    def test_session_flow(self):
        from session import Session
        from test_tagger import wait
        s = Session()
        self.assertTrue(s.start_load(self.A, self.B, False, "filename")["ok"])
        wait(s)
        o = {"scope": "all"}
        lst = s.smart_list()
        self.assertEqual(lst["builtin"][0]["id"], "multi_comma")
        self.assertEqual(lst["builtin"][0]["out"], ", ")
        s.set_fixer_exceptions({"@artists": ["Above & Beyond"]})
        pv = s.smart_preview("multi_comma", o)
        news = sorted({r["new"] for r in pv["rows"]})
        self.assertEqual(news, ["A, B, C", "Above & Beyond, Zoë Johnston", "House, Tech House"])
        skip = [r["id"] for r in pv["rows"] if r["key"] == "TCON"]
        s.smart_apply("multi_comma", dict(o, skip=skip))
        self.assertEqual({r["key"] for r in s.smart_preview("multi_comma", o)["rows"]}, {"TCON"})
        s.do_undo()
        self.assertEqual(s.smart_preview("multi_comma", o)["count"], pv["count"])
        # Ziel-Trenner im Rezept wählbar, mitgeliefertes merkt die Wahl
        self.assertEqual(s.smart_set_out("multi_comma", "v24")["builtin"][0]["out"], "v24")
        with self.assertRaises(ValueError):
            s.smart_set_out("multi_comma", "x")
        # eigene Rezepte: anlegen, ändern, mitgeliefertes nicht änderbar, löschen, export/import
        with self.assertRaises(ValueError):
            s.smart_save(dict(lst["builtin"][0]))
        r = s.smart_save({"name": "Genre", "fields": ["TCON"], "seps": [";"], "out": " / "})["recipe"]
        self.assertEqual(s.smart_list()["current"], r["id"])
        self.assertEqual({x["new"] for x in s.smart_preview(r["id"], o)["rows"]}, {"House / Tech House"})
        s.smart_save(dict(r, name="Genre neu"))
        self.assertEqual([x["name"] for x in s.smart_list()["own"]], ["Genre neu"])
        txt = s.smart_export_text()
        self.assertEqual(s.smart_import(txt)["added"], 1)
        self.assertEqual(len(s.smart_list()["own"]), 2)
        s.smart_delete(r["id"])
        self.assertEqual(len(s.smart_list()["own"]), 1)
        self.assertEqual(s.smart_list()["current"], "multi_comma")
        self.assertIn("smart_recipes", json.loads(s.settings_export_text())["settings"])


if __name__ == "__main__":
    unittest.main()
