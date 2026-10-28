"""Mix analysieren – Ergebnisse (#387): Tracklist-Zeit, Lücken, Text, CUE, Playlist, Ablage und Sitzung."""
import os
import shutil
import tempfile
import unittest

import mixresult


def rows():
    return [{"start": 85, "end": 310, "track_start": 25, "path": "/m/a.mp3", "artist": "Dan Sushi", "title": "Shadows",
             "tempo": -2.0, "keylock": True, "conf": 0.94, "hits": 99},
            {"start": 360, "end": 390, "track_start": 276, "path": "/m/b.mp3", "artist": "Boxer", "title": "Verde",
             "tempo": 2.0, "keylock": False, "conf": 0.58, "also": ["Boxer - Verde (Dub)"]},
            {"start": 615, "end": 815, "path": "", "artist": "", "title": "Ohne Datei", "tempo": 0, "conf": 0.8}]


class TestLogic(unittest.TestCase):
    def test_new_cleans_and_sorts(self):
        r = mixresult.new("/x/Purified 520.mp3", 1200, list(reversed(rows())), compare={"hit": ["a"], "miss": ["DJ Paulus - Mirage"], "expected": 3})
        self.assertRegex(r["id"], r"^mx_[0-9a-f]{12}$")
        self.assertEqual(r["name"], "Purified 520")
        self.assertEqual([x["title"] for x in r["rows"]], ["Shadows", "Verde", "Ohne Datei"])
        self.assertNotIn("hits", r["rows"][0])
        self.assertEqual(r["compare"]["miss"], ["DJ Paulus - Mirage"])
        self.assertIsNone(mixresult.clean_row({"start": "x"}))

    def test_mark_is_middle_of_transition(self):
        self.assertEqual(mixresult.mark({"start": 85, "track_start": 25}), 55)      # Messung 7: Tracklist 00:48
        self.assertEqual(mixresult.mark({"start": 85}), 85)
        self.assertEqual(mixresult.mark({"start": 85, "track_start": 25, "at": 48}), 48)
        self.assertEqual(mixresult.parse_time("1:02:10"), 3730)
        self.assertEqual(mixresult.parse_time("04:56"), 296)
        self.assertIsNone(mixresult.parse_time("vier"))

    def test_gaps_text_and_cue(self):
        r = mixresult.new("/x/Mix.mp3", 1000, rows())
        g = mixresult.with_gaps(r)
        self.assertTrue(g[0]["gap"])                       # 0–85 s ohne Titel
        self.assertEqual([e.get("n") for e in g if not e.get("gap")], [0, 1, 2])
        self.assertTrue(g[-1]["gap"] and g[-1]["end"] == 1000)
        txt = mixresult.to_text(r)
        self.assertIn("[00:55] Dan Sushi - Shadows", txt)
        self.assertIn("[05:18] Boxer - Verde", txt)
        self.assertIn("[00:00] ID - ID", txt)
        cue = mixresult.to_cue(r, "/x/Mix.cue")
        self.assertIn('FILE "Mix.mp3" MP3', cue)
        self.assertIn("TRACK 01 AUDIO", cue)
        self.assertIn("    INDEX 01 00:00:00", cue)
        self.assertIn('PERFORMER "Dan Sushi"', cue)
        self.assertIn("INDEX 01 00:55:00", cue)
        self.assertIn('FILE "/x/Mix.mp3" MP3', mixresult.to_cue(r, "/anders/Mix.cue"))   # nicht neben dem Mix: voller Pfad
        r["rows"][0]["drop"] = True
        self.assertNotIn("Shadows", mixresult.to_text(r))

    def test_items(self):
        r = mixresult.new("/x/Mix.mp3", 1000, rows())
        it = mixresult.to_items(r)
        self.assertEqual(it[0]["path"], "/m/a.mp3")
        self.assertEqual(it[0]["note"], "00:55 · -2.0 % · 94 %")
        self.assertEqual(it[2]["ref"]["title"], "Ohne Datei")

    def test_store(self):
        d = tempfile.mkdtemp()
        try:
            r = mixresult.save(d, mixresult.new("/x/Mix.mp3", 1000, rows()))
            self.assertEqual(mixresult.load(d, r["id"])["rows"][1]["title"], "Verde")
            lst = mixresult.listing(d)
            self.assertEqual((lst[0]["count"], lst[0]["sure"], lst[0]["exists"]), (3, 2, False))
            with self.assertRaises(ValueError):
                mixresult.load(d, "../böse")
            mixresult.remove(d, r["id"])
            self.assertEqual(mixresult.listing(d), [])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_online_gaps(self):
        """#393: Ausschnitte je Lücke reihum, Treffer zusammenfassen, unter 30 % verwerfen, Aufbewahrung."""
        r = mixresult.new("/x/Mix.mp3", 815, rows())
        self.assertEqual(mixresult.gaps(r), [(0.0, 85.0), (390.0, 615.0)])
        c = mixresult.plan_clips(r, 30, 10)
        self.assertEqual([x["gap"] for x in c], [0.0, 390.0, 390.0])          # 85 s → 1, 225 s → 2 Ausschnitte
        self.assertTrue(all(g <= x["start"] and x["end"] <= e for x in c for g, e in mixresult.gaps(r) if g == x["gap"]))
        self.assertEqual([x["gap"] for x in mixresult.plan_clips(r, 30, 2)], [0.0, 390.0])   # zuerst jede Lücke einmal
        self.assertEqual([x["gap"] for x in mixresult.plan_clips(r, 30, 10, only=390)], [390.0, 390.0])
        hit = {"artist": "X", "title": "Y", "conf": 0.8}
        n = mixresult.add_online(r, [(c[0], {"artist": "Z", "title": "W", "conf": 0.2}), (c[1], hit), (c[2], dict(hit, conf=0.5))],
                                 "sonovault", "SonoVault", today="2026-10-28")
        self.assertEqual(n, 1)
        on = [x for x in r["rows"] if x.get("online")]
        self.assertEqual((len(on), on[0]["start"], on[0]["end"], on[0]["conf"]), (1, c[1]["start"], c[2]["end"], 0.8))
        self.assertEqual(len(r["probed"]), 3)
        self.assertEqual(mixresult.plan_clips(r, 30, 10), [])
        self.assertEqual(mixresult.online_text(r), "X - Y")
        self.assertFalse(mixresult.purge_online(r, {"sonovault": None}, today="2027-01-01"))
        self.assertFalse(mixresult.purge_online(r, {"sonovault": 30}, today="2026-11-20"))
        self.assertTrue(mixresult.purge_online(r, {"sonovault": 30}, today="2026-12-01"))
        self.assertEqual(mixresult.online_text(r), "")

    def test_tracklist_fills_gaps(self):
        """#394: Zeitmarken in einer Lücke (±60 s) → Zeilen „aus Tracklist“; schon vorhandene/verworfene nicht."""
        tl = ("01. [00:10] Intro Act - Anfang\n[04:56] Dan Sushi - Shadows\n06:40 Boxer - Verde\n"
              "[07:20] DJ Paulus - Mirage (Extended Mix)\n[08:30] ID - ID\nOhne Zeit - Titel\n[16:00] Ende - Schluss")
        e = mixresult.parse_tracklist(tl)
        self.assertEqual([(x["at"], x["title"]) for x in e][:2], [(10, "Anfang"), (296, "Shadows")])
        self.assertIn((None, "Titel"), [(x["at"], x["title"]) for x in e])
        self.assertFalse(any(x["title"] == "ID" for x in e))
        self.assertEqual(mixresult.parse_tracklist("106:00 Aalson - With Each Other")[0]["at"], 6360)
        r = mixresult.new("/x/Mix.mp3", 1000, rows(), tracklist=tl)
        self.assertEqual(mixresult.fill_from_tracklist(r), 3)              # Anfang, Mirage, Schluss (Shadows/Verde schon da)
        tlr = [x for x in r["rows"] if x.get("tl")]
        self.assertEqual([(x["title"], x["start"], x["end"]) for x in tlr],
                         [("Anfang", 10.0, 85.0), ("Mirage (Extended Mix)", 440.0, 615.0), ("Schluss", 960.0, 1000.0)])
        self.assertEqual(mixresult.fill_from_tracklist(r), 0)              # nicht doppelt
        self.assertEqual(mixresult.note_of(tlr[0]), "00:10 · Tracklist")
        it = [x for x in mixresult.to_items(r) if x["title"] == "Anfang"][0]
        self.assertEqual(it["ref"]["source"], "tracklist")
        self.assertIn("Intro Act - Anfang", mixresult.online_text(r))
        # verworfene Zeile kommt nicht wieder; Lücke zu weit weg → nicht
        r2 = mixresult.new("/x/Mix.mp3", 1000, rows(), tracklist="[13:00] Weit - Weg")
        self.assertEqual(mixresult.fill_from_tracklist(r2), 1)              # Lücke 815–1000, 780 s liegt 35 s davor
        r3 = mixresult.new("/x/Mix.mp3", 1000, rows(), tracklist="[12:00] Weit - Weg")
        self.assertEqual(mixresult.fill_from_tracklist(r3), 0)              # 720 s: mehr als 60 s neben jeder Lücke
        r2["rows"][[x.get("tl") for x in r2["rows"]].index(True)]["drop"] = True
        self.assertEqual(mixresult.fill_from_tracklist(r2), 0)

    def test_link_rows(self):
        """#395: Zeilen ohne Datei mit der Bibliothek verknüpfen – nur sichere Treffer."""
        import playlists
        r = mixresult.new("/x/Mix.mp3", 1000, rows() + [
            {"start": 900, "end": 930, "artist": "Mara Lind", "title": "Kaltes Glas (Original Mix)", "conf": 0.9,
             "online": {"pid": "sonovault", "name": "SonoVault", "fetched": "2026-10-28"}},
            {"start": 950, "end": 990, "artist": "Niemand", "title": "Unbekannt", "conf": 1, "tl": True}])
        self.assertEqual(mixresult.unlinked(r), 2)
        ix = playlists.LibIndex([playlists.lib_entry("/m/Mara Lind - Kaltes Glas.mp3", "Mara Lind", "Kaltes Glas (Original Mix)", "", 340, "", 10)])
        self.assertEqual(mixresult.link_rows(r, ix), 1)
        row = [x for x in r["rows"] if x["start"] == 900][0]
        self.assertEqual((row["path"], row["linked"], "online" in row), ("/m/Mara Lind - Kaltes Glas.mp3", "SonoVault", False))
        self.assertEqual(mixresult.clean_row(row)["linked"], "SonoVault")
        self.assertEqual(mixresult.unlinked(r), 1)
        self.assertEqual(mixresult.link_rows(r, ix), 0)

class TestSession(unittest.TestCase):
    def setUp(self):
        import core
        self.home = tempfile.mkdtemp()
        self._env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.home
        self._cfg = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = os.path.join(self.home, ".tagstudio.json")
        core.CONFIG_OLD = os.path.join(self.home, ".mp3tagcompare.json")
        from session import Session
        self.s = Session()
        self.mix = os.path.join(self.home, "Mix 520.mp3")
        self.trk = os.path.join(self.home, "a.mp3")
        for p in (self.mix, self.trk):
            with open(p, "wb") as fh:
                fh.write(b"\xff\xfb\x90\x00" * 50)
        rs = rows()
        rs[0]["path"] = self.trk
        self.rid = self.s._mix_store({"mix": self.mix, "duration": 1000, "rows": rs, "version": "1.0",
                                      "compare": {"hit": ["x"], "miss": ["DJ Paulus - Mirage (Extended Mix)"], "expected": 2}})

    def tearDown(self):
        import core
        core.CONFIG, core.CONFIG_OLD = self._cfg
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.home, ignore_errors=True)

    def test_get_edit_and_playlist(self):
        d = self.s.mix_get(self.rid)
        self.assertTrue(d["mix_exists"])
        self.assertEqual([l.get("title") for l in d["lines"] if not l.get("gap")], ["Shadows", "Verde", "Ohne Datei"])
        self.assertTrue(d["lines"][1]["exists"])
        self.assertFalse(d["lines"][2]["exists"])
        d = self.s.mix_set_time(self.rid, 1, "05:36")
        self.assertIn("[05:36] Boxer - Verde", d["text"])
        with self.assertRaises(ValueError):
            self.s.mix_set_time(self.rid, 1, "99:99:99")
        d = self.s.mix_drop(self.rid, 2)
        self.assertEqual(d["dropped"][0]["title"], "Ohne Datei")
        r = self.s.mix_to_playlist(self.rid)
        pl = self.s._pls().get(r["playlist"])
        self.assertEqual((pl["folder"], pl["name"], len(pl["items"])), ("Mixe", "Mix 520", 2))
        self.assertEqual(self.s.mix_get(self.rid)["playlist"], pl["id"])
        self.s.mix_drop(self.rid, 1)
        r2 = self.s.mix_to_playlist(self.rid)                               # zweites Mal: dieselbe Playlist nachführen
        self.assertEqual(r2["playlist"], pl["id"])
        self.assertEqual(len(self.s._pls().get(pl["id"])["items"]), 1)

    def test_export_audio_ideas_delete(self):
        dest = os.path.join(self.home, "out.cue")
        self.assertEqual(self.s.mix_cue_beside(self.rid), os.path.join(self.home, "Mix 520.cue"))
        r = self.s.mix_export_write(self.rid, "cue", dest)
        self.assertTrue(r["ok"])
        self.assertTrue(self.s.mix_export_write(self.rid, "cue", dest)["exists"])          # nie ungefragt ersetzen
        with open(dest, encoding="utf-8-sig") as fh:
            self.assertIn('FILE "Mix 520.mp3" MP3', fh.read())
        self.assertEqual(self.s.mix_export_name(self.rid, "txt"), "Mix 520.txt")
        self.assertTrue(self.s.mix_audio(self.rid, None)["url"].endswith(".mp3"))
        self.assertTrue(self.s.mix_audio(self.rid, 0)["url"].startswith("http://127.0.0.1:"))
        with self.assertRaises(ValueError):
            self.s.mix_audio(self.rid, 2)                                                   # Datei fehlt
        r = self.s.mix_missing_to_ideas(self.rid, "", "Aus Mixen")
        self.assertEqual((r["name"], r["added"]), ("Aus Mixen", 1))
        self.assertEqual(self.s.mix_list()["items"][0]["count"], 3)
        self.assertFalse(self.s.mix_list()["ready"])                                         # Plugin ohne Umgebung
        self.assertEqual(self.s.mix_delete(self.rid)["items"], [])
        self.assertTrue(os.path.isfile(self.mix))                                            # Mix bleibt

    def test_tracklist_and_link_in_session(self):
        """#394/#395: Tracklist beim Speichern bzw. nachträglich; Verknüpfen nach „Vorbereiten“ über die Ergebnisse."""
        rid = self.s._mix_store({"mix": self.mix, "duration": 1000, "rows": rows(), "tracklist": "[00:20] Intro - Anfang"})
        d = self.s.mix_get(rid)
        self.assertEqual(d["tl_rows"], 1)
        self.assertTrue([ln for ln in d["lines"] if ln.get("tl") and ln["title"] == "Anfang"])
        d = self.s.mix_set_tracklist(rid, "[00:20] Intro - Anfang\n[16:10] Outro - Schluss")
        self.assertEqual((d["added"], d["tl_rows"]), (1, 2))
        self.assertIn("Outro - Schluss", d["tracklist"])
        self.assertEqual(d["nofile"], 2)                                    # nur online / aus Tracklist
        # nach „Vorbereiten“: neue Datei → Zeile verknüpft, gespeicherte Playlist nachgeführt
        self.s.mix_to_playlist(rid)
        from helpers import text, write_mp3
        new = os.path.join(self.home, "Outro - Schluss.mp3")
        write_mp3(new, [text("TPE1", "Outro"), text("TIT2", "Schluss")])
        self.assertEqual(self.s._mix_autolink([new]), 1)
        d = self.s.mix_get(rid)
        ln = [x for x in d["lines"] if x.get("title") == "Schluss"][0]
        self.assertEqual((ln["path"], ln["linked"], ln["tl"]), (new, "Tracklist", False))
        self.assertEqual(d["nofile"], 1)
        pl = self.s._pls().get(d["playlist"])
        self.assertIn(new, [x.get("path") for x in pl["items"]])
        self.assertEqual(self.s._mix_autolink([new]), 0)

        # start_plugin_action legt ein „mix_result“ als Ergebnis ab und gibt die Kennung zurück
        import mixresult as mr
        before = len(mr.listing(self.s._mix_dir()))
        rid = self.s._mix_store({"mix": self.mix, "duration": 10, "rows": []})
        self.assertEqual(len(mr.listing(self.s._mix_dir())), before + 1)
        self.assertEqual(self.s.mix_get(rid)["lines"], [])


if __name__ == "__main__":
    unittest.main()
