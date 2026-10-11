"""Tracks vorbereiten (#109–#116): Workflow mit Rezept, externem Schritt (Schutzregel), Übernahme, Status."""
import os
import time

from helpers import write_mp3, text, txxx
from test_tagger_tools import Base

import prepare
from id3tags import MP3File


class TestPrepare(Base):
    def setUp(self):
        super().setUp()
        self.inbox = os.path.join(self.dir, "Neu", "_01_Original")
        self.lib = os.path.join(self.dir, "Library")
        os.makedirs(self.inbox)
        os.makedirs(self.lib)
        write_mp3(os.path.join(self.inbox, "a.mp3"), [text("TIT2", "Golden_Hour"), text("TPE1", "Mara Lind")], audio_seed=81)
        write_mp3(os.path.join(self.inbox, "b.mp3"), [text("TIT2", "Nordlicht"), text("TPE1", "Kai Ost")], audio_seed=82)
        write_mp3(os.path.join(self.lib, "x.mp3"), [text("TIT2", "Nordlicht"), text("TPE1", "Kai Ost")], audio_seed=83)
        from session import Session
        self.s = Session()
        w = prepare.template()
        w.update(inbox=self.inbox, library=self.lib)
        self.w = self.s.prep_workflow_save(w)["workflow"]
        self.wid = self.w["id"]

    def wait(self):
        for _ in range(500):
            st = self.s.task_status()
            if st.get("done"):
                self.assertIsNone(st["error"], st)
                return st["result"]
            time.sleep(0.02)
        self.fail("hängt")

    def cells(self, ov, name):
        return {s["id"]: c for s, c in zip(ov["workflow"]["steps"], next(r for r in ov["rows"] if r["name"] == name)["cells"])}

    def test_flow(self):
        ov = self.s.prep_overview(self.wid)
        self.assertEqual([r["name"] for r in ov["rows"]], ["a.mp3", "b.mp3"])
        self.assertEqual(self.cells(ov, "a.mp3")["s02"]["state"], "open")
        self.assertEqual(self.cells(ov, "a.mp3")["s03"]["state"], "blocked")
        # 02 Rezept: Kopie im Stufen-Ordner, Original unverändert
        self.assertTrue(self.s.start_prep_run(self.wid, "s02")["ok"])
        r = self.wait()
        self.assertEqual(r["done"], 2)
        stage = os.path.join(self.dir, "Neu", "_02_MP3Tag", "a.mp3")
        self.assertEqual(MP3File(stage).text("TIT2"), "Golden Hour")
        self.assertEqual(MP3File(os.path.join(self.inbox, "a.mp3")).text("TIT2"), "Golden_Hour")
        self.assertTrue(MP3File(stage).had_v1)
        # 03 Platinum Notes: Kopie, wartet, ohne Programm; Erkennung über Herkunft
        self.s.start_prep_run(self.wid, "s03")
        r = self.wait()
        self.assertEqual(r["launched"], "")
        pn = os.path.join(self.dir, "Neu", "_03_PlatinumNotes", "a.mp3")
        self.assertEqual(self.cells(self.s.prep_overview(self.wid), "a.mp3")["s03"]["state"], "waiting")
        f = MP3File(pn)
        f.set_text("TXXX:PlatinumNotes", "1")
        f.save()
        ov = self.s.prep_refresh(self.wid)
        self.assertEqual(self.cells(ov, "a.mp3")["s03"]["state"], "done")
        self.assertEqual(self.cells(ov, "b.mp3")["s03"]["state"], "waiting")
        self.s.prep_mark(self.wid, "s03", ["b.mp3"], "done")
        # 04 Picard mit Schutzregel: Titel geändert → Warnung, zurücksetzen
        self.s.start_prep_run(self.wid, "s04")
        self.wait()
        f = MP3File(pn)
        f.set_text("TIT2", "Golden Hour (Picard)")
        f.set_text("TXXX:MusicBrainz Album Id", "123")
        f.save()
        ov = self.s.prep_refresh(self.wid)
        c = self.cells(ov, "a.mp3")["s04"]
        self.assertEqual(c["state"], "warn")
        self.assertEqual([v["key"] for v in c["viol"]], ["TIT2"])
        ov = self.s.prep_revert(self.wid, "s04", "a.mp3")
        self.assertEqual(MP3File(pn).text("TIT2"), "Golden Hour")
        self.assertEqual(MP3File(pn).text("TXXX:MusicBrainz Album Id"), "123")      # Ergänzung bleibt
        self.assertEqual(self.cells(ov, "a.mp3")["s04"]["state"], "done")
        for sid in ("s05", "s06"):
            self.s.prep_mark(self.wid, sid, ["a.mp3", "b.mp3"], "skipped")
        self.s.prep_mark(self.wid, "s04", ["b.mp3"], "done")
        # Übernahme: b ist ein mögliches Doppel (gleicher Künstler + Titel)
        self.s.start_prep_run(self.wid, "s07")
        r = self.wait()
        self.assertEqual(r["done"], 1)
        self.assertIn("gleicher Künstler und Titel", r["errors"][0])
        self.assertTrue(os.path.isfile(os.path.join(self.lib, "a.mp3")))
        self.assertFalse(os.path.isfile(os.path.join(self.lib, "b.mp3")))
        self.s.start_prep_run(self.wid, "s07", ["b.mp3"], True)       # trotzdem übernehmen
        self.assertEqual(self.wait()["done"], 1)
        # Status: Mixed In Key erkannt (EnergyLevel) – erlaubte Felder
        f = MP3File(os.path.join(self.lib, "a.mp3"))
        f.set_text("TXXX:EnergyLevel", "7")
        f.set_text("TKEY", "8A")
        f.save()
        ov = self.s.prep_refresh(self.wid)
        self.assertEqual(self.cells(ov, "a.mp3")["s08"]["state"], "done")
        self.assertEqual(self.cells(ov, "b.mp3")["s08"]["state"], "open")
        # Aufräumen der Stufen-Kopien (Liste, dann löschen)
        lst = self.s.prep_cleanup(self.wid)
        self.assertEqual(lst["count"], 4)
        self.assertEqual(self.s.prep_cleanup(self.wid, None, True)["removed"], 4)
        self.assertTrue(os.path.isfile(os.path.join(self.inbox, "a.mp3")))   # Rohdaten bleiben

    def test_export_import(self):
        txt = self.s.prep_export(self.wid)
        self.assertNotIn(self.inbox.replace("\\", "\\\\"), txt)
        d = self.s.prep_import(txt)
        self.assertEqual(len(d["workflows"]), 2)
        self.assertEqual(d["workflow"]["inbox"], "")
        with self.assertRaises(ValueError):
            self.s.prep_import("{kaputt")

    def test_plugin_step(self):
        """Plugin-Schritt: Kopie im Stufen-Ordner, Vorschläge je Modus übernehmen, Schutzregel."""
        import plugins
        from test_plugins import make_plugin
        code = (
            "ACTIONS = [{'id': 'go', 'label': 'Go', 'where': 'tagger', 'options': []}]\n"
            "def run(action, ctx, files, opts):\n"
            "    for f in files:\n"
            "        ctx.propose(f, 'TXXX:LUFS_I', '-9.1')\n"
            "        ctx.propose(f, 'TIT2', 'Anders', checked=False)\n"
            "        ctx.propose(f, 'TPE1', 'Neu', checked=True)\n"
            "    return {'message': 'ok'}\n")
        make_plugin(plugins.user_dir(), "fake", code=code)
        self.s.plugins.scan()
        w = dict(self.w)
        w["steps"] = [{"id": "p1", "type": "plugin", "label": "01 Messen", "plugin": "fake", "action": "go"},
                      {"id": "p2", "type": "plugin", "label": "02 Alles", "plugin": "fake", "action": "go",
                       "mode": "checked", "protect": True}]
        self.s.prep_workflow_save(w)
        self.assertEqual(self.s._prep_get(self.wid)["steps"][0]["folder"], "_p1")
        self.assertTrue(self.s.start_prep_run(self.wid, "p1")["ok"])
        r = self.wait()
        self.assertEqual(r["done"], 2, r)
        f = MP3File(os.path.join(self.dir, "Neu", "_p1", "a.mp3"))
        self.assertEqual(f.text("TXXX:LUFS_I"), "-9.1")       # leeres Feld gefüllt
        self.assertEqual(f.text("TPE1"), "Mara Lind")          # gefülltes Feld bleibt
        self.assertIsNone(MP3File(os.path.join(self.inbox, "a.mp3")).get("TXXX:LUFS_I"))
        c = self.cells(self.s.prep_overview(self.wid), "a.mp3")["p1"]
        self.assertEqual(c["state"], "done")
        self.assertIn("1 Feld", c["note"])
        # Modus „alle vorausgewählten“ mit Schutzregel: TPE1 geändert → Warnung, TIT2 nicht (nicht vorausgewählt)
        self.s.start_prep_run(self.wid, "p2")
        self.wait()
        f = MP3File(os.path.join(self.dir, "Neu", "_p2", "a.mp3"))
        self.assertEqual(f.text("TPE1"), "Neu")
        self.assertEqual(f.text("TIT2"), "Golden_Hour")
        c = self.cells(self.s.prep_overview(self.wid), "a.mp3")["p2"]
        self.assertEqual(c["state"], "warn")
        self.assertEqual([v["key"] for v in c["viol"]], ["TPE1"])

    def test_pick_proposals(self):
        props = [{"old": "", "checked": False, "kind": "text"}, {"old": "x", "checked": True, "kind": "text"},
                 {"old": "", "checked": True, "kind": "text", "same": True}, {"old": "", "kind": "cover", "data": None, "checked": True}]
        self.assertEqual(prepare.pick_proposals(props, "fill"), [props[0]])
        self.assertEqual(prepare.pick_proposals(props, "checked"), [props[1], props[3]])
        self.assertEqual(prepare.pick_proposals(props, "none"), [])


if __name__ == "__main__":
    import unittest
    unittest.main()
