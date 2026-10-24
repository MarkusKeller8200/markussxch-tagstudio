"""Lexicon-Ausbau (#237–#239): Client, mehr Felder, Öffnen aus Lexicon, Zurückschreiben mit Journal (ohne Lexicon)."""
import importlib.util
import json
import os
import unittest

import fake_lexicon
from helpers import write_mp3, text, txxx
from test_importers import _Run, TAGS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("lexapi_t", os.path.join(ROOT, "plugins", "lexicon", "lexapi.py"))
lexapi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lexapi)


class TestClient(unittest.TestCase):
    def setUp(self):
        self.st = fake_lexicon.State([{"id": 1, "location": "C:/M/a.mp3", "title": "A", "archived": 0}])
        self.srv, self.url = fake_lexicon.start(self.st)

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def test_query_and_local(self):
        q = lexapi.encode_query({"fields": ["id", "title"], "filter": {"location": "C:/a b.mp3"}, "limit": 5, "x": None})
        self.assertEqual(q, "fields=id&fields=title&filter%5Blocation%5D=C%3A%2Fa+b.mp3&limit=5")
        for u in ("http://localhost:48624", "http://127.0.0.1:1", "http://[::1]:48624"):
            self.assertTrue(lexapi.is_local(u), u)
        for u in ("http://192.168.1.5:48624", "http://lexicon.example:48624", "http://10.0.0.1"):
            self.assertFalse(lexapi.is_local(u), u)
        with self.assertRaises(lexapi.LexiconError):
            lexapi.Client("ftp://x")
        self.assertEqual(lexapi.Client(self.url + "/v1/").base, self.url)

    def test_errors_and_retry(self):
        c = lexapi.Client(self.url, sleep=lambda s: None)
        self.assertEqual(c.search({"location": "c:\\m\\A.MP3"})[0]["id"], 1)
        with self.assertRaises(lexapi.LexiconError) as cm:
            c.track(99)
        self.assertEqual(cm.exception.code, 100)
        self.st.busy = 2                                   # Lexicon beschäftigt → wiederholen
        self.assertEqual(c.patch_track(1, {"title": "B"})["title"], "B")
        self.st.busy = 9
        with self.assertRaises(lexapi.LexiconError) as cm:
            lexapi.Client(self.url, sleep=lambda s: None, retries=2).patch_track(1, {"title": "C"})
        self.assertEqual(cm.exception.code, 2)

    def test_drops_unknown_parameter(self):
        """Lexicon lehnt unbekannte Parameter mit Fehler 5 ab („'x' is not allowed“) – ohne ihn nochmals fragen."""
        c = lexapi.Client(self.url)
        r = c.get("/search/tracks", {"filter": {"location": "a.mp3"}, "limit": 20})
        self.assertEqual(len(r["tracks"]), 1)
        self.assertEqual(c.dropped, {"/search/tracks": {"limit"}})
        n = len(self.st.calls)
        c.get("/search/tracks", {"filter": {"location": "a.mp3"}, "limit": 20})
        self.assertEqual(len(self.st.calls), n + 1)                            # gemerkt: gleich ohne „limit“
        self.assertNotIn("limit", self.st.calls[-1][2])

    def test_flatten(self):
        tree = [{"id": 1, "name": "ROOT", "type": "1", "playlists": [{"id": 2, "name": "Sets", "type": "1",
                                                                       "playlists": [{"id": 3, "name": "Fr", "type": "2"}]}]}]
        self.assertEqual([(p["id"], p["path"], p["depth"]) for p in lexapi.flatten(tree)],
                         [(1, ["ROOT"], 0), (2, ["ROOT", "Sets"], 1), (3, ["ROOT", "Sets", "Fr"], 2)])


class _LexRun(_Run):
    def setUp(self):
        super().setUp()
        write_mp3(os.path.join(self.B, "p.mp3"), [text("TIT2", "Pfad"), text("TPE1", "Mara Lind"), text("TCON", "House"),
                                                  text("TBPM", "124"), text("TKEY", "Am"), txxx("ENERGY", "80")],
                  audio_seed=41)
        write_mp3(os.path.join(self.B, "q.mp3"), [text("TIT2", "Zweiter"), text("TPE1", "Kai Ost")], audio_seed=42)
        self.load()
        self.p, self.q = self.f("p.mp3").path, self.f("q.mp3").path
        self.lex = fake_lexicon.State([
            {"id": 1, "location": self.p, "locationUnique": self.p.lower(), "artist": "Mara Lind", "title": "Pfad",
             "genre": "Techno", "bpm": 124, "key": "8A", "rating": 4, "color": "red", "popularity": 7, "danceability": 7,
             "energy": 6, "happiness": 0, "tags": [1, 5], "archived": 0, "incoming": 1,
             "tempomarkers": [{"startTime": 0.1, "bpm": 124}],
             "cuepoints": [{"type": "1", "startTime": 1.0, "position": 0}, {"type": "5", "startTime": 8.0, "position": 1}]},
            {"id": 2, "location": self.q, "locationUnique": self.q.lower(), "artist": "Kai Ost", "title": "Zweiter",
             "tags": [], "archived": 0},
            {"id": 3, "location": "Z:/nicht/da.mp3", "locationUnique": "z:/nicht/da.mp3", "artist": "X", "title": "Y",
             "tags": [], "archived": 0},
        ], json.loads(json.dumps(TAGS)), [
            {"id": 10, "name": "ROOT", "type": "1", "parentId": None},
            {"id": 11, "name": "Sets", "type": "1", "parentId": 10},
            {"id": 12, "name": "Freitag", "type": "2", "parentId": 11, "trackIds": [2, 1, 3]},
        ])
        self.srv, self.url = fake_lexicon.start(self.lex)
        self.settings(url=self.url)
        self.s._emit_wait = True

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def act(self, aid, idx=None, **opts):
        r = self.s.start_plugin_action("lexicon", aid, idx if idx is not None else sorted(self.idx.values()), opts)
        self.assertTrue(r["ok"], r)
        st = self.wait()
        return st

    def settings(self, **kw):
        d = {"url": "", "write": False, "move": True, "add": False, "playlist": "", "analyze": False}
        d.update(kw)
        st = self.act("settings", [], **d)
        self.assertIsNone(st["error"], st)

    def writes(self):
        return [c for c in self.lex.calls if c[0] != "GET"]


class TestImportMore(_LexRun):
    def test_more_fields_and_grid(self):
        st = self.act("import", url=self.url, rating=True, popularity=True, color=True, tags_to="TXXX:LEXICON_TAGS", grid=True)
        res = st["result"]
        by = self.by(res)
        self.assertEqual(by[("p.mp3", "Bewertung (Sterne)")]["new"], "4")
        self.assertEqual(by[("p.mp3", "Lexicon: Popularität (LEXICON_POPULARITY)")]["new"], "7")
        self.assertEqual(by[("p.mp3", "Lexicon: Farbe (LEXICON_COLOR)")]["new"], "red")
        self.assertEqual(by[("p.mp3", "Lexicon-Tags → TXXX:LEXICON_TAGS")]["new"], "Genre: House")
        note = by[("p.mp3", "Bewertung (Sterne)")]["note"]
        self.assertIn("Incoming", note)
        self.assertIn("Beatgrid in Lexicon: 124.00 BPM", note)
        self.assertIn("Cue-Punkte: Lexicon 2 (davon 1 Loop)", note)
        self.apply_checked(res)
        import ratings
        f = self.f("p.mp3")
        self.assertEqual(ratings.get_rating(f), 4)
        self.assertEqual(f.text("TXXX:LEXICON_POPULARITY"), "7")
        # #240: alles ohne offizielles MP3-Feld → Herkunft „Lexicon“
        for k in ("TXXX:LEXICON_POPULARITY", "TXXX:LEXICON_COLOR", "TXXX:LEXICON_TAGS"):
            self.assertEqual(self.s.origins.of(k), "lexicon", k)
        self.assertEqual(self.s.origins.catalog()["lexicon"]["name"], "Lexicon")


class TestOpen(_LexRun):
    def test_selected_tracks_to_tagger(self):
        st = self.act("open", [], source="tracks", target="tagger")
        self.assertIn("keine Titel markiert", st["result"]["message"])
        self.lex.selected = [2, 3, 1]
        res = self.act("open", [], source="tracks", target="tagger")["result"]
        self.assertEqual(res["open"]["files"], [self.q, self.p])                # Reihenfolge, fehlende Datei weg
        self.assertIn("1 nicht auf diesem Rechner", res["message"])
        r = self.s.start_tag_load_files(res["open"]["files"], res["open"]["label"])
        self.assertTrue(r["ok"])
        self.wait()
        self.assertEqual([f.path for f in self.s.tag_files], [self.q, self.p])

    def test_playlist_by_path_to_djset(self):
        res = self.act("open", [], source="path", path="sets / freitag", target="djset")["result"]
        self.assertEqual(res["open"]["files"], [self.q, self.p])
        self.assertEqual(res["open"]["target"], "djset")
        st = self.act("open", [], source="path", path="Gibtsnicht", target="djset")
        self.assertIn("Keine Playlist", st["error"])
        self.lex.selected_playlists = [11]                                      # Ordner: Titel aller Playlists
        res = self.act("open", [], source="playlist", target="tagger")["result"]
        self.assertEqual(res["open"]["label"], "Sets")
        d = self.s.dj_add_paths(res["open"]["files"], True, "Sets")
        self.assertEqual([x["path"] for x in self.s._dj()["items"]], [self.q, self.p])
        self.assertIn("aus „Sets“", d["message"])

    def test_prepare_detect(self):
        found = self.s.plugins.detect("lexicon", [self.p, os.path.join(self.B, "neu.mp3")], self.s)
        self.assertEqual(found, {self.p})
        self.assertEqual(self.s.plugins.detect("beatunes", [self.p], self.s), set())


class TestToTagStudio(_LexRun):
    def test_to_ts_from_file_fields(self):
        """#241: Werte aus den LEXICON-Feldern der Datei in die TagStudio-Felder (×10, mit Abgleich)."""
        import moods
        f = self.f("q.mp3")
        f.set_text("TXXX:LEXICON_ENERGY", "7")
        f.set_text("TXXX:LEXICON_DANCEABILITY", "6.5")
        f.set_text("TXXX:LEXICON_MOOD", "Dark\x00Happy")
        res = self.act("to_ts", [self.idx["q.mp3"], self.idx["p.mp3"]], danceability=True, energy=True, happiness=True,
                       mood=True)["result"]
        by = self.by(res)
        self.assertEqual(by[("q.mp3", "Energy (ENERGY)")]["new"], "70")
        self.assertEqual(by[("q.mp3", "Danceability (DANCEABILITY)")]["new"], "65")
        self.assertEqual(by[("q.mp3", "Stimmung (MOOD)")]["new"], "Dark ¦ Happy")
        self.assertFalse([k for k in by if k[0] == "p.mp3"])                  # ohne Lexicon-Felder
        self.apply_checked(res)
        self.assertEqual(moods.values(f), ["Dark", "Happy"])
        self.assertEqual(json.loads(f.text("TXXX:TAGSTUDIO"))["sync"]["lexicon"]["ENERGY"], 70)
        self.assertEqual(self.lex.calls, [c for c in self.lex.calls if c[0] == "GET"])   # keine Schreibzugriffe
        st = self.act("to_ts", [self.idx["p.mp3"]], energy=True)
        self.assertIn("Keine der Dateien", st["result"]["message"])

    def test_import_with_to_ts(self):
        res = self.act("import", [self.idx["p.mp3"]], url=self.url, energy=True, to_ts=True)["result"]
        by = self.by(res)
        self.assertEqual(by[("p.mp3", "Lexicon: Energie (LEXICON_ENERGY)")]["new"], "6")
        self.assertIn(("p.mp3", "Energy (ENERGY)"), by)                        # Datei hat 80 → Abgleich


class TestDjSource(_LexRun):
    def test_list_and_import(self):
        self.assertEqual([x["id"] for x in self.s.dj_sources()["sources"]], ["lexicon"])
        self.assertTrue(self.s.start_dj_source_list("lexicon")["ok"])
        pls = self.wait()["result"]["playlists"]
        self.assertEqual(pls[0]["id"], "queue")
        self.assertEqual([(p["name"], p["depth"]) for p in pls[1:]], [("Sets", 0), ("Freitag", 1)])   # ohne Wurzel
        self.assertTrue(self.s.start_dj_source_import("lexicon", [12, 11])["ok"])
        r = self.wait()["result"]
        self.assertEqual([x["name"] for x in r["lists"]], ["Lexicon: Freitag", "Lexicon: Sets"])
        self.assertEqual((r["first"], r["files"], r["missing"]), ("Lexicon: Freitag", [self.q, self.p], 2))
        self.assertEqual([x["path"] for x in self.s._dj()["items"]], [self.q, self.p])
        self.assertEqual(self.s.cfg["djset_name"], "Freitag")                    # #269: Playlist im Ordner „Lexicon“
        pl = self.s._pls().find("Freitag", "Lexicon")
        self.assertEqual((pl["kind"], pl["source"]["id"], self.s.cfg["djset_pl"]), ("import", 12, pl["id"]))
        self.lex.playlists[2]["trackIds"] = [1]                                 # erneut laden → aktualisiert
        self.s.start_dj_source_import("lexicon", [12])
        self.wait()
        self.assertEqual(len(self.s._pls().get(pl["id"])["items"]), 1)
        self.assertEqual(len([p for p in self.s._pls().active() if p["folder"] == "Lexicon"]), 2)   # nicht doppelt
        self.assertFalse(self.s.start_dj_source_import("lexicon", [])["ok"])
        # #238 Punkt 4: läuft gerade + Warteschlange
        self.lex.playing, self.lex.queue = 2, [1, 3]
        self.s.start_dj_source_import("lexicon", ["queue"])
        r = self.wait()["result"]
        self.assertEqual((r["first"], r["files"], r["missing"]), ("Lexicon: Warteschlange", [self.q, self.p], 1))


class TestWriteBack(_LexRun):
    def test_send_needs_switch_and_local(self):
        st = self.act("send", basic=True)
        self.assertIn("ausgeschaltet", st["error"])
        self.settings(url="http://192.168.1.5:48624", write=True)
        st = self.act("send", basic=True)
        self.assertIn("nur an Lexicon auf diesem Rechner", st["error"])
        self.assertEqual(self.writes(), [])

    def test_send_apply_undo(self):
        self.settings(url=self.url, write=True)
        res = self.act("send", basic=True, bpm_key=True, rating=False, features=True, mood=False)["result"]
        by = self.by(res)
        g = by[("p.mp3", "Lexicon: Genre")]
        self.assertEqual((g["old"], g["new"], g["kind"]), ("Techno", "House", "remote"))
        self.assertNotIn(("p.mp3", "Lexicon: Tonart"), by)                      # Am = 8A → gleich
        self.assertNotIn(("p.mp3", "Lexicon: BPM"), by)
        self.assertEqual(by[("p.mp3", "Lexicon: Energy")]["new"], "8")
        out = self.s.plugin_apply(res["proposals_token"], [r["id"] for r in res["proposals"] if r["checked"]])
        self.assertTrue(out["ok"], out)
        self.assertIn("1 Titel in Lexicon geändert", out["message"])
        t = self.lex.by_id(1)
        self.assertEqual((t["genre"], t["energy"]), ("House", 8))
        self.assertFalse(self.s.unsaved())                                     # Dateien unverändert
        st = self.act("undo", [])
        self.assertIn("1 Titel zurückgesetzt", st["result"]["message"])
        self.assertEqual((t := self.lex.by_id(1))["genre"], "Techno")
        self.assertEqual(t["energy"], 6)
        self.assertIn("Keine Änderung", self.act("undo", [])["result"]["message"])

    def test_mood_tags_created(self):
        self.settings(url=self.url, write=True)
        import moods
        f = self.f("q.mp3")
        f.set_text(moods.key_for(f), "Dark\x00Happy")
        res = self.act("send", [self.idx["q.mp3"]], basic=False, bpm_key=False, rating=False, features=False, mood=True)["result"]
        row = self.by(res)[("q.mp3", "Lexicon: Mood-Tags")]
        self.assertEqual(row["new"], "Dark, Happy")
        self.s.plugin_apply(res["proposals_token"], [row["id"]])
        new = next(t for t in self.lex.tags["tags"] if t["label"] == "Happy")
        self.assertEqual(sorted(self.lex.by_id(2)["tags"]), sorted([5, new["id"]]))

    def test_events_move_and_add(self):
        self.s._emit("files_moved", [{"old": self.p, "new": "C:/Neu/p.mp3"}])
        self.assertEqual(self.writes(), [])                                    # Schreiben aus
        self.settings(url=self.url, write=True, move=True, add=True, playlist="TagStudio Neu", analyze=True)
        self.s._emit("files_moved", [{"old": self.p, "new": "C:/Neu/p.mp3"}])
        self.assertEqual(self.lex.by_id(1)["location"], "C:/Neu/p.mp3")
        self.s._emit("files_added", ["C:/Lib/neu.mp3"])
        new = [t for t in self.lex.tracks if t["location"] == "C:/Lib/neu.mp3"]
        self.assertEqual(len(new), 1)
        pl = next(p for p in self.lex.playlists if p["name"] == "TagStudio Neu")
        self.assertEqual(pl["trackIds"], [new[0]["id"]])
        ctl = [c for c in self.lex.calls if c[1] == "/v1/control"]
        self.assertEqual(ctl[0][2]["action"], "AudioAnalyzer_Analyze")
        self.s._emit("files_added", ["C:/Lib/neu2.mp3"])                       # vorhandene Playlist wird benutzt
        self.assertEqual(len([p for p in self.lex.playlists if p["name"] == "TagStudio Neu"]), 1)
        st = self.act("undo", [])                                              # letzter Pfad-Eintrag wird zurückgesetzt
        self.assertIn("1 Titel zurückgesetzt", st["result"]["message"])
        self.assertEqual(self.lex.by_id(1)["location"], self.p)
        self.assertFalse([c for c in self.lex.calls if c[0] == "DELETE"])     # nie gelöscht

    def test_rename_emits(self):
        self.settings(url=self.url, write=True, move=True)
        self.s.tag_rename([self.idx["p.mp3"]], "%artist% - %title%", apply=True)
        self.assertTrue(self.lex.by_id(1)["location"].endswith("Mara Lind - Pfad.mp3"))

    def test_djset_playlist(self):
        self.settings(url=self.url, write=True)
        self.s.dj_add_paths([self.p, self.q, os.path.join(self.B, "fehlt.mp3")])
        st = self.act("djset", [], name="Mein Set")
        self.assertIn("2 Titel, 1 nicht in Lexicon", st["result"]["message"])
        pl = next(p for p in self.lex.playlists if p["name"] == "Mein Set")
        self.assertEqual(pl["trackIds"], [1, 2])


if __name__ == "__main__":
    unittest.main()
